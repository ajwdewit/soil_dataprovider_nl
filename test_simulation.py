import matplotlib.pyplot as plt
import pandas as pd
from pcse.base import ParameterProvider
from pcse.models import Wofost72_WLP_CWB
from pcse.input import WOFOST72SiteDataProvider, NASAPowerWeatherDataProvider, YAMLCropDataProvider
from soil_dataprovider_nl import SoilDataProviderNL
import yaml

def main():
    agro_string = \
    """
    Version: 1.0
    AgroManagement:
    - 2014-04-01:
        CropCalendar:
            crop_name: potato
            variety_name: Fontane
            crop_start_date: 2014-04-15
            crop_start_type: sowing
            crop_end_date: 2014-10-01
            crop_end_type: harvest
            max_duration: 400
        TimedEvents: null
        StateEvents: null
    """
    latitude = 51.989778
    longitude = 5.660973
    WAV = 10.

    agrod = yaml.safe_load(agro_string)
    cropd = YAMLCropDataProvider(Wofost72_WLP_CWB)
    soild = SoilDataProviderNL(
        Wofost72_WLP_CWB,
        xcoord=longitude,
        ycoord=latitude,
        max_root_depth=40,
        cache_soildb=True
    )
    sited = WOFOST72SiteDataProvider(WAV = WAV)
    weatherd = NASAPowerWeatherDataProvider(latitude = latitude, longitude = longitude)

    parameters = ParameterProvider(cropdata=cropd, soildata=soild, sitedata=sited)
    wofost = Wofost72_WLP_CWB(parameters, weatherd, agrod)
    wofost.run_till_terminate()
    output = wofost.get_output()
    df_output = pd.DataFrame(output)
    fig, ax = plt.subplots()
    ax.plot(df_output.day, df_output.TWSO)
    ax.set_xlabel("Date")
    ax.set_ylabel("Yield (Mg ha$^{-1}$)")
    fig.autofmt_xdate()
    plt.show()

if __name__ == "__main__":
    main()