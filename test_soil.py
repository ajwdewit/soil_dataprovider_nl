import soil_dataprovider_nl as soil
from soil_dataprovider_nl import SoilDataProviderNL
from pcse.models import Wofost72_WLP_CWB, Wofost73_WLP_MLWB

soild = SoilDataProviderNL(Wofost72_WLP_CWB, xcoord=173716, ycoord=444551, max_root_depth=100, cache_soildb=True)
print(soild)
#
# soild = SoilDataProviderNL(Wofost72_WLP_CWB, xcoord=5.660973, ycoord=51.989778, cache_soildb=True)
# print(soild)
#
#
# soild = SoilDataProviderNL(Wofost72_WLP_CWB, xcoord=5.660488, ycoord=51.978928)
# print(soild)
#
# from ipyleaflet import Map, WMSLayer, basemaps
# import ipyleaflet
#
# wms = WMSLayer(
#     url='https://service.pdok.nl/tno/bro-bodemkaart/wms/v1_0',
#     layers='Bodemvlakken',
#     format='image/png',
#     transparent=False,
#     crs=ipyleaflet.projections.EPSG3857
# )
#
# m = Map(basemap=basemaps.CartoDB.Positron, center=(52, 5), zoom=5, crs=ipyleaflet.projections.EPSG3857)
# # m = Map(center=(52, 5), zoom=9)
#
# m.add(wms)
#
# m