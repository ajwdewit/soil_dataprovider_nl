#  Soil data providers for Dutch soils for PCSE

---
Allard de Wit  
Wageningen Environmental Research  
April 2026  
---

This package provides a set of data providers that can provide the soil parameters for the Netherlands as input
for running crop/soil models in PCSE. It takes the input from the [Dutch soil map](https://app.pdok.nl/viewer/#x=160000.00&y=455000.00&z=3.0000&background=BRT-A%20standaard&layers=d9cc67ba-5491-4640-86ac-b8d392250270;soilarea;_;1)
but the soil data itself is hosted in a [duckdb file on github](https://github.com/ajwdewit/collections/raw/refs/heads/main/BodemkaartNL/bofek_soil_nl.ddb).

Getting soil information has always been a bit of a hassle for models in [PCSE](https://pcse.readthedocs.io). 
While crop parameters are well managed through [YAML files on github](https://github.com/ajwdewit/WOFOST_crop_parameters), 
soil parameters are more difficult as they are spatially variable and thus location dependent. Moreover, soil 
maps and definitions are variable between countries making it hard to develop dataproviders for soils. 

This soil data provider derives soil parameters from the Dutch soil map and derives soil hydraulic properties as well
as soil mineralogic properties (bulk density, organic matter content) depending on the type of PCSE soil component used.
Several data providers are available from this package:
- `SoilDataProviderNL_CWB`
- `SoilDataProviderNL_MLWB` *under development*
- `SoilDataProviderNL_MLWB_SNOMIN` *under development*

These dataproviders map to the different soil modules in pcse: the classic soil water balance (CWB), the multi-layered
soil water balance (MLWB) and the multi-layered water balance plus the SNOMIN carbon/nitrogen model (MLWB_SNOMIN). 
The correct soil dataprovider will be selected automatically based on the pcse model that you pass in to the call
to `soil_dataprovider_nl.SoilDataProviderNL`, however they can also be imported manually from the package.

# Setting up the package

## Dependencies

This package has been developed using python 3.10 and has dependencies on several other packages:
- pandas
- numpy
- duckdb == 1.4
- matplotlib
- pyproj == 3.7

These should be automatically downloaded and installed during installing the package.

## Installing

The package can be pip-installed from PyPI: `pip install soil_dataprovider_nl` should be sufficient.

## Usage

Using the soil dataprovider is easy:
```python
>> from soil_dataprovider_nl import SoilDataProviderNL_CWB
>> from pcse.models import Wofost72_WLP_CWB
>> soild = SoilDataProviderNL_CWB(Wofost72_WLP_CWB, xcoord=170342, ycoord=438503, cache_soildb=True)
>> print(soild)
Soil properties for location at X/Y: 170342/438503 - lon/lat: 5.611/51.936
Soil rootable depth estimated at 120 cm (from maximum soil profile depth)
Soil profile characteristics:
 thickness  pclay  psilt  psand      SMW    SMFCF      SM0
        25   0.23   0.40   0.37 0.122168 0.387381 0.429530
        35   0.23   0.40   0.37 0.142978 0.413028 0.472326
        30   0.20   0.25   0.55 0.142978 0.413028 0.472326
        30   0.04   0.07   0.89 0.040080 0.269736 0.387057
Actual CWB parameter values:
- SMW: 0.113 [-]
- SMFCF: 0.372 [-]
- SM0: 0.442 [-]
- CRAIRC: 0.035 [-]
- RDMSOL: 120.000 [cm]
- SOPE: 8.436 [cm day-1]
- KSUB: 8.436 [cm day-1]
```

The derived soildata can then be used in the usual procedure for running a model (in pseudo code):
```python
>> params = ParameterProvider(cropdata=cropd, soildata=soild, sitedata=sited)
>> agro = get_agromanagement(...)
>> wdp = get_weatherdata(...)
>> wofost = Wofost72_WLP_CWB(params, wdp, agro)
>> wofost.run_till_terminate()
...
```

See for more elaborate examples the [notebook on the repository](https://github.com/ajwdewit/soil_dataprovider_nl).