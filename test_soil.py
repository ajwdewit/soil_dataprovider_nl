import soil_dataprovider_nl as soil
from soil_dataprovider_nl import SoilDataProviderNL
from pcse.models import Wofost72_WLP_CWB, Wofost73_WLP_MLWB

soild = SoilDataProviderNL(Wofost72_WLP_CWB, xcoord=173716, ycoord=444551, max_root_depth=100, cache_soildb=True)
print(soild)

soild = SoilDataProviderNL(Wofost72_WLP_CWB, xcoord=5.660973, ycoord=51.989778, cache_soildb=True)
print(soild)


soild = SoilDataProviderNL(Wofost72_WLP_CWB, xcoord=5.660488, ycoord=51.978928)
print(soild)
