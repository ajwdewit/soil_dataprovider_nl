# -*- coding: utf-8 -*-
# Copyright (c) 2026 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), April 2026
import urllib.request
from pathlib import Path
import tempfile

import pandas as pd
pd.options.mode.chained_assignment = None
import matplotlib.pyplot as plt
import duckdb
import numpy as np

from .coords import CoordinateStore
from .mualemvangenuchten import MualemvanGenuchten, get_water_content_from_MvG, get_conductivity_from_MvG

this_dir = Path(__file__).parent
top_dir = this_dir.parent.absolute()
tmp_dir = Path(tempfile.gettempdir())


class SoilBDconnector:
    bofek_soil_source = "https://github.com/ajwdewit/collections/raw/refs/heads/main/BodemkaartNL/bofek_soil_nl.ddb"
    bofek_soil_cache = tmp_dir / "bofek_soil_nl.ddb"

    def __init__(self, cache_soildb=False):
        self._cache_soildb = cache_soildb
        if self._cache_soildb:
            if not self.bofek_soil_cache.exists():
                print("Downloading Soil DB (~135 Mb)...")
                urllib.request.urlretrieve(self.bofek_soil_source, self.bofek_soil_cache)

        self.connection = None

    def __enter__(self):

        soildb = self.bofek_soil_cache if self._cache_soildb else self.bofek_soil_source
        sql1 = "install spatial; load spatial; install httpfs; load httpfs;"
        sql2 = f"attach '{soildb}' as soildb (READONLY)"
        self.connection = duckdb.connect()
        self.connection.sql(sql1)
        self.connection.sql(sql2)
        return self.connection

    def __exit__(self, exc_type, exc_value, exc_traceback):

        self.connection.close()


class SoilDataProviderNL_CWB(dict):
    """A SoilDataProvider that retrieves soil parameters from the Dutch BOFEK soil database for use
    with the PCSE classic waterbalance.

    :param xcoord: the X coordinate. Either in Dutch RD coordinates or as longitude
    :param ycoord: the Y coordinates. Either in Dutch RD coordinates or as latitude
    :param max_root_depth: user defined rootable depth in cm, otherwise the whole soil is assumed rootable.
    :param cache_soildb: set to True to download the soil database file and store a local cached copy of it.

    Since the classic water balance uses a single soil layer, the soil parameters for each layer
    have to be aggregated. The following assumptions have been made:
    - SMW is calculated from a layer-weighted average of the wilting point, the latter is assumed at pF=4.2
    - SMFCF is computed by calculating the water holding capacity for all layers. The latter is defined as the amount
      of volume between wilting point (SMW) and field capacity (pF=2) for each layer. The SMFCF is than calculated
      as the value with an equivalent water holding capacity given the soil rootable depth (RDMSOL).
    - SM0 is computed as the value required to store an equivalent volume of water given the rootable depth.
    - SOPE/KSUB are computed as the conductivity of the bottom layer at pF=1. There is no physical basis for this
      but since the water balance starts draining water when the water content is above field capacity we just
      take pF=1 as representative for that proces.
    - RDMSOL is derived from the maximum soil depth or from the user-defined max_root_depth. The smallest of the
      two values is taken.
    """
    non_soil_codes = {99980, 99990, 99991}
    param_units = {"SMW": "[-]",
                   "SMFCF": "[-]",
                   "SM0": "[-]",
                   "CRAIRC": "[-]",
                   "RDMSOL": "[cm]",
                   "SOPE": "[cm day-1]",
                   "KSUB": "[cm day-1]",
                   }

    def __init__(self, *, xcoord=None, ycoord=None, max_root_depth=1E6, cache_soildb=False):
        super().__init__()

        self.crds = CoordinateStore(xcoord, ycoord)
        with SoilBDconnector(cache_soildb=cache_soildb) as DBconn:
            self.soil_profile = self._find_soil_profile(DBconn)
            profile_characteristics = self._find_profile_characteristics(DBconn, self.soil_profile)

        # self._compute_pF_curves(self.profile_characteristics)
        self.profile_characteristics = self._compute_water_content_at_referencepoints(profile_characteristics)
        self.rootable_depth, self._root_depth_limit_forced = self._determine_rootable_depth(max_root_depth)
        self._compute_CWB_volumetric_parameters()
        self._compute_CWB_conductivity_parameters()

    def _compute_pF_curves(self, profile_characteristics):
        pF_range = np.arange(-1.0, 7.1, 0.1)
        H = 10**pF_range
        fig, axes = plt.subplots(ncols=2, figsize=(10,5))
        for row in profile_characteristics.itertuples():
            p_mvg = MualemvanGenuchten(wcr=row.ores, wcs=row.osat, alpha=row.alfa, npar=row.npar,
                                       lamda=row.lexp, ksat=row.ksatfit)
            pF_WC = get_water_content_from_MvG(H, p_mvg)
            pF_Cond = get_conductivity_from_MvG(H, p_mvg)
            label = f"layer {row.layer_top}-{row.layer_bottom}"
            axes[0].plot(pF_range, pF_WC, label=label)
            axes[1].plot(pF_range, pF_Cond, label=label)

        axes[0].legend()
        axes[0].set_xlabel("pF value")
        axes[0].set_ylabel("Soil moisture content [-]")
        axes[1].set_xlabel("pF value")
        axes[1].set_ylabel("Soil conductivity [cm/day]")
        fig.suptitle("PF curves")
        fig.savefig(top_dir / "profile_curves.png")

    def _compute_CWB_volumetric_parameters(self):
        """Computes the soil volumetric parameters for the WOFOST classic waterbalance as layer-weighted values

        :return: a dict with relevant parameters
        """
        df = self.profile_characteristics

        # Determine which layers are rooted
        df["is_rooted"] = df.layer_top < self.rootable_depth
        if not df.is_rooted.all():
            df = df[df.is_rooted]
        df.layer_bottom.iloc[-1] = self.rootable_depth

        # Recompute layer thickness as bottom layer may be bounded by rootable depth.
        df["thickness"] = df.layer_bottom - df.layer_top

        # wilting point as layer-weighted value
        SMW = (df.SMW * df.thickness).sum() / df.thickness.sum()
        # compute total water holding capacity (AWC) for all layers
        AWC = ((df.SMFCF - df.SMW) * df.thickness).sum()
        # Recomputed field capacity as required to store AWC above wilting point SMW
        SMFCF = SMW + AWC/self.rootable_depth
        # pore space above field capacity (AWC0)
        AWC0 = ((df.SM0 - df.SMFCF) * df.thickness).sum()
        # Recompute soil porosity (SM0) as required to store AWC0 above field capacity
        SM0 = SMFCF + AWC0/self.rootable_depth
        # Critical air content as halfway between SMFCF and SM0
        CRAIRC = AWC0/self.rootable_depth * 0.5

        self.update(dict(SMW=SMW, SMFCF=SMFCF, SM0=SM0, CRAIRC=CRAIRC, RDMSOL=self.rootable_depth))

    def _compute_CWB_conductivity_parameters(self):
        """Computes the soil conductivity parameters for the WOFOST classic waterbalance

        The are three parameters in WOFOST CWB that have to be estimated:
        - SOPE : maximum percolation rate root zone[cm day-1]
        - KSUB : maximum percolation rate subsoil [cm day-1]

        It is unclear how this parameters have to be estimated physically. In practice they
        were probably used as a calibration parameter in order to limit excessive drainage.
        In the classic water balance drainage occurs only when soil moisture is above
        field capacity (pF=2.0), therefore we estimate both parameters as the conducitivity
        at pF=1.0. Moreover, since drainage happens mostly in the lower soil layers, we
        use the MvG parameters of the bottom layer to estimate the conductivity.

        :return: a dict with relevant parameters
        """
        bottom_layer = self.profile_characteristics.iloc[-1]
        p_mvg = MualemvanGenuchten(wcr=bottom_layer.ores, wcs=bottom_layer.osat, alpha=bottom_layer.alfa,
                                   npar=bottom_layer.npar, lamda=bottom_layer.lexp, ksat=bottom_layer.ksatfit)
        pF = 1.0
        H = 10**pF
        cond = get_conductivity_from_MvG(H, p_mvg)
        self.update(dict(SOPE=cond, KSUB=cond))

    def _compute_water_content_at_referencepoints(self, profile_characteristics):
        """Computes the water content at saturation, field capacity and wilting point based on the profile
        characteristics and the Mualem van Genugten parameters.

        :param profile_characteristics: a dataframe with soil profile characteristics
        :return: The updated dataframe with soil profile characteristics
        """

        ref_point_names = ["SM0", "SMFCF", "SMW"]
        ref_point_pF = np.array([-1, 2, 4.2])
        H = 10**ref_point_pF
        layer_ref_points = []
        for layer in profile_characteristics.itertuples():
            p_mvg = MualemvanGenuchten(wcr=layer.ores, wcs=layer.osat, alpha=layer.alfa, npar=layer.npar,
                                       lamda=layer.lexp, ksat=layer.ksatfit)
            water_content = get_water_content_from_MvG(H, p_mvg)
            layer_ref_points.append(dict(zip(ref_point_names, water_content)))
        df_water_content = pd.DataFrame.from_dict(layer_ref_points)
        profile_characteristics = pd.concat([profile_characteristics, df_water_content], axis=1)

        return profile_characteristics

    def _determine_rootable_depth(self, max_rootable_depth):
        """Determines the rootable depth as the minimum of the sum of the layer thickness and the user defined
        max_rootable_depth parameter.

        :param max_rootable_depth: the user-defined maximum rootable depth.
        :return: the rootable depth
        """
        soil_rootable_depth = self.profile_characteristics.thickness.sum()
        rootable_depth = min(max_rootable_depth, soil_rootable_depth)
        if rootable_depth < soil_rootable_depth:
            return rootable_depth, True
        else:
            return rootable_depth, False

    def _find_soil_profile(self, DBconn):
        sql = """SELECT profile_code FROM soildb.bofek_soil_nl t1
                 WHERE ST_intersects(t1.geom, ST_Point(?, ?))
              """

        cursor = DBconn.execute(sql, (self.crds.xcoord, self.crds.ycoord))
        row = cursor.fetchone()
        if not row:
            msg = (f"No soil profile found for this location: (X:{self.crds.xcoord:.0f}, Y:{self.crds.ycoord:.0f})! "
                   f"Is this location on land?")
            raise RuntimeError(msg)

        profile_code = row[0]
        if profile_code in self.non_soil_codes:
            msg = (f"Not a valid soil profile found for this location: (X:{self.crds.xcoord:.0f}, Y:{self.crds.ycoord:.0f})! "
                   f"Probably an urban area, land fill or other location with no soil description!")
            raise RuntimeError(msg)

        return row[0]

    def _find_profile_characteristics(self, DBconn, profile_code):
        """Reads the soil profile characteristics from the database

        :param profile_code: the profile code
        :return: a dataframe with soil profile characteristics
        """
        sql = """SELECT t1.*, t2.* 
                 FROM 
                     soildb.soil_profiles t1 
                   INNER JOIN 
                     soildb.soil_physical_description t2 ON t1.soil_physical_code=t2.soil_physical_code
                WHERE
                   t1.profile_code = ?
                ORDER BY
                   t1.idlayer
            """
        df = DBconn.execute(sql, (profile_code,)).df()
        if len(df) == 0:
            msg = f"No valid soil profile description found for this soil profile code: {profile_code})!"
            raise RuntimeError(msg)

        df["thickness"] = df.layer_bottom - df.layer_top

        return df

    def __str__(self):
        msg = (f"Soil properties for location at X/Y: {self.crds.xcoord:.0f}/{self.crds.ycoord:.0f} - "
               f"lon/lat: {self.crds.lon:.3f}/{self.crds.lat:.3f}\n")
        if self._root_depth_limit_forced:
            msg += f"Soil rootable depth estimated at {self.rootable_depth} cm (forced by `max_root_depth` parameter)\n"
        else:
            msg += f"Soil rootable depth estimated at {self.rootable_depth} cm (from maximum soil profile depth)\n"
        msg += "Soil profile characteristics:\n"
        s = self.profile_characteristics.to_string(index=False, columns=["thickness", "pclay", "psilt", "psand", "SMW",
                                                                         "SMFCF", "SM0"],
                                                   max_rows=5)
        msg += (s + "\n")
        msg += f"Actual CWB parameter values:\n"
        for name, value in self.items():
            unit = self.param_units[name]
            msg += f"- {name}: {value:.3f} {unit}\n"
        return msg


class SoilDataProviderNL_MLWB(dict):
    """A SoilDataProvider that retrieves soil parameters from the Dutch BOFEK soil database for use
    with the PCSE multi-layered waterbalance.
    """
    non_soil_codes = {99980, 99990, 99991}

    def __init__(self, *, xcoord=None, ycoord=None, max_root_depth=1E6, cache_soildb=False):
        super().__init__()

        raise NotImplementedError("Soil dataprovider for the multi-layer waterbalance not yet implemented.")


class SoilDataProviderNL_MLWB_SNOMIN(dict):
    """A SoilDataProvider that retrieves soil parameters from the Dutch BOFEK soil database for use
    with the PCSE multi-layered waterbalance with SNOMIN C/N soil model.
    """
    non_soil_codes = {99980, 99990, 99991}

    def __init__(self, *, xcoord=None, ycoord=None, max_root_depth=1E6, cache_soildb=False):
        super().__init__()

        raise NotImplementedError("Soil dataprovider for the multi-layer waterbalance and SNOMIN not yet implemented.")