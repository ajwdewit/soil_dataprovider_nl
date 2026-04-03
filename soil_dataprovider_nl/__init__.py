# -*- coding: utf-8 -*-
# Copyright (c) 2026 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), April 2026
from .soil_dataprovider_nl import SoilDataProviderNL_CWB, SoilDataProviderNL_MLWB, SoilDataProviderNL_MLWB_SNOMIN

__version__ = "1.0.0"


class SoilDataProviderNL:
    """Convenience class that selected the right soil data provider based on the model annotations.
    """

    def __new__(cls, model, *args, **kwargs):

        if model.__nitrogenbalance__ == "SNOMIN":
            final_cls = SoilDataProviderNL_MLWB_SNOMIN
        elif model.__waterbalance__ == "MLWB":
            final_cls = SoilDataProviderNL_MLWB
        elif model.__waterbalance__ == "CWB":
            final_cls = SoilDataProviderNL_CWB
        else:
            raise RuntimeError("soil module not recognized")

        # Here we instantiate the selected class with __new__()
        instance = final_cls.__new__(final_cls, *args, **kwargs)
        # Here we initialize the instance with an explicit call to __init__()
        instance.__init__(*args, **kwargs)
        return instance

