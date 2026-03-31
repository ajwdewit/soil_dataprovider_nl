from pathlib import Path
this_dir = Path(__file__).parent
top_dir = this_dir.parent.absolute()

import pandas as pd
pd.options.mode.chained_assignment = None
import matplotlib.pyplot as plt
import duckdb
import numpy as np

from .mualemvangenuchten import MualemvanGenugten, get_water_content_from_MvG, get_conductivity_from_MvG

class SoilDataProviderNL_CWB(dict):
    """A SoilDataProvider that retrieves soil parameters from the Dutch BOFEK soil database for use
    with the PCSE classic waterbalance.
    """
    bofek_soil_source = Path(r"C:\data\NoBackup\bodemkaartNL\bofek_soil_nl.ddb")
    param_units = {"SWM": "[-]",
                   "SMFCF": "[-]",
                   "SM0": "[-]",
                   "CRAIRC": "[-]",
                   "RDMSOL": "[cm]",
                   "SOPE": "[cm day-1]",
                   "KSUB": "[cm day-1]",
                   }

    def __init__(self, xcoord=None, ycoord=None, max_root_depth=1E6):
        super().__init__()
        self.xcoord = self._valid_xcoord_rd(xcoord)
        self.ycoord = self._valid_ycoord_rd(ycoord)
        self.DBconn = self._connect_soil_db()
        self.soil_profile = self._find_soil_profile()

        profile_characteristics = self._find_profile_characteristics(self.soil_profile)
        # self._compute_pF_curves(self.profile_characteristics)
        self.profile_characteristics = self._compute_WC_at_referencepoints(profile_characteristics)
        self.rootable_depth, self._root_depth_limit_forced = self._determine_rootable_depth(max_root_depth)
        self._compute_CWB_volumetric_parameters()
        self._compute_CWB_conductivity_parameters()

    def _compute_pF_curves(self, profile_characteristics):
        pF_range = np.arange(-1.0, 7.1, 0.1)
        H = 10**pF_range
        fig, axes = plt.subplots(ncols=2, figsize=(10,5))
        for row in profile_characteristics.itertuples():
            p_mvg = MualemvanGenugten(wcr=row.ores, wcs=row.osat, alpha=row.alfa, npar=row.npar,
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

        # wilting point as layer-weighted values
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

        self.update(dict(SWM=SMW, SMFCF=SMFCF, SM0=SM0, CRAIRC=CRAIRC, RDMSOL=self.rootable_depth))

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
        p_mvg = MualemvanGenugten(wcr=bottom_layer.ores, wcs=bottom_layer.osat, alpha=bottom_layer.alfa,
                                  npar=bottom_layer.npar, lamda=bottom_layer.lexp, ksat=bottom_layer.ksatfit)
        pF = 1.0
        H = 10**pF
        cond = get_conductivity_from_MvG(H, p_mvg)
        self.update(dict(SOPE=cond, KSUB=cond))

    def _compute_WC_at_referencepoints(self, profile_characteristics):
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
            p_mvg = MualemvanGenugten(wcr=layer.ores, wcs=layer.osat, alpha=layer.alfa, npar=layer.npar,
                                      lamda=layer.lexp, ksat=layer.ksatfit)
            water_content = get_water_content_from_MvG(H, p_mvg)
            layer_ref_points.append(dict(zip(ref_point_names, water_content)))
        df_WC = pd.DataFrame.from_dict(layer_ref_points)
        profile_characteristics = pd.concat([profile_characteristics, df_WC], axis=1)

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

    @staticmethod
    def _valid_xcoord_rd(xcoord):

        if 7000 < xcoord < 289000:
            return xcoord
        else:
            raise ValueError(f"Xcoord {xcoord} not a valid value for Dutch the RD system")

    @staticmethod
    def _valid_ycoord_rd(ycoord):

        if 289000 < ycoord < 629000:
            return ycoord
        else:
            raise ValueError(f"Ycoord {ycoord} not a valid value for Dutch the RD system")

    def _connect_soil_db(self):

        sql1 = f"attach '{self.bofek_soil_source}' as soildb (READONLY)"
        sql2 = "install spatial; load spatial"
        connect = duckdb.connect()
        connect.sql(sql1)
        connect.sql(sql2)
        return connect

    def _find_soil_profile(self):
        sql = """SELECT profile_code FROM soildb.bofek_soil_nl t1
                 WHERE ST_intersects(t1.geom, ST_Point(?, ?))
              """

        cursor = self.DBconn.execute(sql, (self.xcoord, self.ycoord))
        row = cursor.fetchone()
        if not row:
            msg = f"No valid soil profile found for this location: (X:{self.xcoord}, Y:{self.ycoord})!"
            raise RuntimeError(msg)

        return row[0]

    def _find_profile_characteristics(self, profile_code):
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
        df = self.DBconn.execute(sql, (profile_code,)).df()
        if len(df) == 0:
            msg = f"No valid soil profile description found for this soil profile code: {profile_code})!"
            raise RuntimeError(msg)

        df["thickness"] = df.layer_bottom - df.layer_top

        return df

    def __str__(self):
        msg = f"Soil properties for location at X/Y: {self.xcoord}/{self.ycoord}\n"
        if self._root_depth_limit_forced:
            msg += f"Soil rootable depth estimated at {self.rootable_depth} (forced by `max_root_depth` parameter)\n"
        else:
            msg += f"Soil rootable depth estimated at {self.rootable_depth} (from maximum soil profile depth)\n"
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