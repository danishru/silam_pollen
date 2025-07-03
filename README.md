
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Downloads][download-shield]][Downloads]
[![License][license-shield]][license]
[![HACS Custom][hacsbadge]][hacs]

# SILAM Pollen Allergy Sensor for Home Assistant

[README на русском тут 👈](https://github.com/danishru/silam_pollen/blob/main/README_ru.md)

Integration for Home Assistant using the dataset “Best time series obtained from the latest available run” from the SILAM Thredds server to create a service with pollen level sensors for a specific location. The forecast calculation is carried out by the Finnish Meteorological Institute taking into account aerobiological, phenological, and meteorological observations.

Data source: [https://silam.fmi.fi/pollen.html](https://silam.fmi.fi/pollen.html)

> [!CAUTION]  
> The provided data are unverified model forecasts created for scientific use only.  
> Neither the quality nor completeness of the information is guaranteed, and the data producers assume no responsibility for its accuracy or timeliness.

> [!IMPORTANT]  
> This integration was created using the ChatGPT edition for collaborative code writing, debugging, and editing.  
> If you hold a different ethical viewpoint, I apologize. However, I consider this use to be morally acceptable, as the integration is non-commercial, free, and open-source, and its purpose is to promote openness and collaboration.

## Description

The **SILAM Pollen** integration provides a service consisting of sensors that dynamically build the URL for requesting pollen data. The data are requested from the SILAM server via HTTP, then parsed and updated in Home Assistant. You can create multiple services for different locations, and you can also choose the types of pollen you need.

> [!NOTE]  
> Please note: the coverage area is limited and depends on the selected dataset.  
> 🟩 **Green** — coverage zone of **SILAM Regional (v5.9.1)** (more detailed).  
> 🟨 **Yellow** — coverage zone of **SILAM Europe (v6.0)** (more general).  
>  
> To evaluate coverage and choose the appropriate region, use the interactive map below.

[![Interactive pollen coverage map](https://danishru.github.io/silam_pollen/pollen_area.webp)](https://danishru.github.io/silam_pollen/)

## 🆕 What's New

## v0.2.4

- **📖 Default README in English**  
  The README file is now presented in English by default.

[![More in release v0.2.4](https://img.shields.io/badge/More--in--release-v0.2.4-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.4)

## v0.2.3

- **📦 Prepared for HACS publication**  
  Changes made to host the integration in the default HACS catalog.
- **🌐 Added Slovak translation**  
  Thanks to [@misa1515](https://github.com/misa1515) for implementing the Slovak localization!
- **🌐 Added Dutch translation**  
  Thanks to [@rubdos](https://github.com/rubdos) for implementing the Dutch localization!

[![More in release v0.2.3](https://img.shields.io/badge/More--in--release-v0.2.3-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.3)

## Previous updates
<details>
<summary>Show</summary>

### v0.2.2

- **⏱️ Forecast duration setting**  
  When creating or modifying an entry, you can now choose the forecast duration from 36 to 120 hours (default is 36 h). As the hours increase, the number of forecast points twice a day increases proportionally.
- **🛠️ Diagnostic sensor “fetch_duration”**  
  A sensor to display the data update execution time (API requests, processing, calculations). Disabled by default.
- **🌐 Added Czech translation**  
  Thanks to [@kasparmir](https://github.com/kasparmir) for the first implementation of the Czech localization!

[![More in release v0.2.2](https://img.shields.io/badge/More--in--release-v0.2.2-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.2)

### v0.2.1

**🌸 Pollen Forecast (BETA)**  
- Hourly and twice-daily pollen forecasts now include values for selected allergens.  
- For each pollen sensor, there is now an attribute with the forecast for the next day, showing the daily forecast for the next day, just like for the pollen index.

[![More in release v0.2.1](https://img.shields.io/badge/More--in--release-v0.2.1-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.1)

### v0.2.0
  
- **🌍 Support for two SILAM versions**  
  Ability to choose between `SILAM Europe (v6.0)` and `SILAM Regional (v5.9.1)` — with an automatic availability check.  
  `SILAM Regional (v5.9.1)` provides more **detailed and accurate forecasts** for Northern and Northwestern Europe.

- **🌸 Pollen Forecast (BETA)**  
  New weather sensor with hourly and twice-daily pollen forecasts via `weather.get_forecasts`.

- **📊 Unified data handler + update service**  
  All data are cached through `data_processing.py`.  
  Added service `SILAM Pollen monitor: Manual Update` — can be called manually or in automations.

- **🎨 Icons for integration and sensors**  
  Visual indicators are clearer: each allergen now has its own icon.

- **🌐 Localization (in 8 languages)**  
  The interface is translated into: Russian, English, Finnish, Italian, Swedish, Norwegian, Danish, and German.

[![More in release v0.2.0](https://img.shields.io/badge/More--in--release-v0.2.0-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.0)

</details>

## Installation  

### Installation via HACS (recommended)

**Ensure HACS is installed:**  
If HACS is not yet installed, follow the [official HACS installation guide](https://hacs.xyz/docs/use/).

#### One-click installation

To install the **SILAM Pollen** integration, click the link below and select **Download**:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danishru&repository=silam_pollen)

#### Regular installation via HACS

1. Open Home Assistant and go to HACS.  
2. In the search bar, type `SILAM Pollen` and click **Download** next to the integration.

Now your integration is installed and ready to use via HACS!

### Manual installation

1. Copy the `silam_pollen` folder into the `custom_components` directory of your Home Assistant configuration.  
2. Restart Home Assistant.  
3. Add the integration via the web interface:  
   - Go to **Settings → Integrations**.  
   - Click **Add Integration** and select **SILAM Pollen**.  
   - Fill in the required fields (name, coordinates, altitude, pollen type selection, polling interval).  

## Configuration

Follow the setup wizard for **SILAM Pollen** at the link below:

[![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=silam_pollen)

Or open **Settings → Integrations** in Home Assistant, find `SILAM Pollen`, and follow the setup wizard.

Here you can set the parameters for the proper operation of the integration:

- **Observation Zone** – allows you to choose a configured zone in your Home Assistant. By default, the zone `"Home"` is selected.  
- **Pollen Type** – select the pollen to monitor. You can leave it empty or select multiple types from the list.  
- **Update Interval** – the interval for loading data from the SILAM Thredds server in minutes (default is 60, minimum is 30).  
- **Pollen Forecast (BETA)** – enables an additional weather sensor with pollen level forecasts. May increase API response time.  
- **Forecast Duration** – sets how many hours ahead the forecast is built (from 36 to 120 h, default is 36 h).  
- **Zone Name** – by default, the name from the selected zone is used. This name is applied to the service and sensor names. You can override it.  
- **Altitude above Sea Level** – the altitude used for data sampling. If the `"Home"` zone is selected, the value from the general settings (`config/general`) is used; otherwise, the default is 275 m. You can override it.  
- **Location** – shows the selected coordinates on the map. You can change the zone using the map or manually set the latitude, longitude, and radius. The specified radius reflects the approximate spatial resolution of the pollen data (about 10 km).

## Usage

After installing the integration in Home Assistant, a service named `SILAM Pollen - {Zone Name}` is created. The service description shows the observation location coordinates and the dataset version used.

![image](https://github.com/user-attachments/assets/47c28fa0-baac-4d33-9493-8c53a6592166)

As part of the service, a **Pollen Index** sensor is created, whose state displays a localized value corresponding to the numerical index calculated based on hourly average values and threshold levels from Mikhail Sofiev’s table ([link](https://www.researchgate.net/profile/Mikhail-Sofiev)).

**Possible index values:**  
- `very_low` — Very Low  
- `low` — Low  
- `moderate` — Moderate  
- `high` — High  
- `very_high` — Very High  
- `unknown` — Unknown  

**Attributes of the “Pollen Index” sensor:**  
- **Forecast Date & Time** — the timestamp for which the index is calculated (ISO 8601).  
- **Primary Allergen** — the allergen that had the greatest impact on the index calculation.  
- **Forecast for Tomorrow** — the daily pollen level forecast for the next day (shown if the forecast is enabled).

If one or more pollen types are selected, a separate **{Pollen Type}** sensor is created for each, displaying the modeled pollen grain concentration (grains/m³).

**Attributes of the “{Pollen Type}” sensors:**  
- **Altitude (sea level)** — the nearest available altitude used for data sampling.  
- **Forecast for Tomorrow** — the aggregated pollen level forecast value for the next day (shown if the forecast is enabled).

**Fetch Duration (fetch_duration)** — a sensor, disabled by default, showing the total time to update data (API request, parsing, calculations).

|  ![image](https://github.com/user-attachments/assets/c497819b-8521-4a02-9891-c1936ef2a4c2) | ![image](https://github.com/user-attachments/assets/41fdd143-b74e-42fc-bddb-db3b0b33b025)  |
| ------------- | ------------- |

If the **Pollen Forecast** option is enabled, an additional **weather sensor** is created, which provides:  
- an hourly forecast for 24 hours (in 3-hour steps);  
- a twice-daily forecast for the chosen duration (default 36 h, maximum 120 h).

The state of the weather sensor shows the **pollen index for the first available hourly forecast interval**.

![image](https://github.com/user-attachments/assets/cb832f76-43e0-402e-9f60-b383c4131ced)

This data is available via the standard `weather.get_forecasts` service.

![image](https://github.com/user-attachments/assets/bdd37fbc-9dc7-4bf1-95b2-7f3843d106e0)

<details>
<summary>Show example “Hourly” response</summary>

```yaml
weather.silam_pollen_france_forecast:
  forecast:
    - datetime: "2025-04-10T14:00:00+00:00"
      condition: high
      native_temperature_unit: °C
      pollen_index: 4
      temperature: 15.2
      pollen_alder: 0
      pollen_birch: 260
    - datetime: "2025-04-10T17:00:00+00:00"
      condition: high
      native_temperature_unit: °C
      pollen_index: 4
      temperature: 15.3
      pollen_alder: 0
      pollen_birch: 308
    - datetime: "2025-04-10T20:00:00+00:00"
      condition: high
      native_temperature_unit: °C
      pollen_index: 4
      temperature: 13.7
      pollen_alder: 0
      pollen_birch: 340
    - datetime: "2025-04-10T23:00:00+00:00"
      condition: high
      native_temperature_unit: °C
      pollen_index: 4
      temperature: 10.5
      pollen_alder: 0
      pollen_birch: 264
    - datetime: "2025-04-11T02:00:00+00:00"
      condition: moderate
      native_temperature_unit: °C
      pollen_index: 3
      temperature: 7.8
      pollen_alder: 0
      pollen_birch: 79
    - datetime: "2025-04-11T05:00:00+00:00"
      condition: moderate
      native_temperature_unit: °C
      pollen_index: 3
      temperature: 5.9
      pollen_alder: 0
      pollen_birch: 162
    - datetime: "2025-04-11T08:00:00+00:00"
      condition: high
      native_temperature_unit: °C
      pollen_index: 4
      temperature: 10.3
      pollen_alder: 0
      pollen_birch: 352
    - datetime: "2025-04-11T11:00:00+00:00"
      condition: high
      native_temperature_unit: °C
      pollen_index: 4
      temperature: 16.8
      pollen_alder: 0
      pollen_birch: 332
```
</details>

<details>
<summary>Show example “Twice Daily” response</summary>

```yaml
weather.silam_pollen_france_forecast:
  forecast:
    - datetime: "2025-04-10T21:00:00+00:00"
      is_daytime: false
      condition: high
      pollen_index: 4
      temperature: 15.3
      pollen_alder: 0
      pollen_birch: 296
      templow: 8.6
    - datetime: "2025-04-11T09:00:00+00:00"
      is_daytime: true
      condition: moderate
      pollen_index: 3
      temperature: 16.8
      pollen_alder: 0
      pollen_birch: 278
      templow: 5.2
    - datetime: "2025-04-11T21:00:00+00:00"
      is_daytime: false
      condition: high
      pollen_index: 4
      temperature: 19.7
      pollen_alder: 0
      pollen_birch: 416
      templow: 12.1
```
</details>

### How the forecast is calculated

The pollen forecast in the **SILAM Pollen** integration is formed based on the SILAM model and is aggregated into two types of forecasts:

#### Hourly forecast (24 hours)
- Constructed in 3-hour steps.  
- For each 3-hour window, the following are calculated:  
  - Maximum temperature.  
  - Pollen index — median value rounded up to the nearest integer.  
  - Median value for each selected allergen.  
- Uses the current date + 24 hours ahead.

#### Twice-daily forecast (36–120 hours)
- Data are grouped into 12-hour intervals within the selected forecast duration (default 36 h; can be up to 120 h).  
- For each interval, the following are calculated:  
  - Maximum and minimum temperature.  
  - Median pollen index (rounded up).  
  - Median value for each selected allergen.  
- Forecast labels are set at 00:00 and 12:00 (local time) for each interval.

#### Parameters used
- `POLI` — pollen index value.  
- `temp_2m` — temperature at 2 meters height.

#### Aggregation technique
- Data from SILAM are parsed from XML and merged by `date`.  
- Calculations are performed using `statistics.median`, `max`, `min`.  
- All forecasts are cached in `merged_data` and available via `weather.get_forecasts`.

## Dashboard Card

Great news for dashboard enthusiasts — you can now display the pollen forecast with a beautiful card!  
The [pollenprognos-card](https://github.com/krissen/pollenprognos-card) has supported **SILAM Pollen** integration since [v2.3.0](https://github.com/krissen/pollenprognos-card/releases/tag/v2.3.0), and in [v2.3.3](https://github.com/krissen/pollenprognos-card/releases/tag/v2.3.3) it added:

- hourly and twice-a-day forecasts;  
- localization in multiple languages;  
- other useful enhancements.  

Huge thanks to [@krissen](https://github.com/krissen) for this work!

The card is available in the **default HACS repository**.  
To install, click **Download** in the card’s menu:

[![HACS Repository Badge](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=krissen&repository=pollenprognos-card)

### See it in action:

![pollenprognos-card preview](https://github.com/user-attachments/assets/d9b53a99-d183-4968-80b7-8a2b25381783)


For more information and documentation, visit the repository. If you enjoy the card, don’t forget to give it a ⭐ and open an issue for bugs or feature requests:  
https://github.com/krissen/pollenprognos-card  

## Additional Resources

For more detailed information on pollen and its distribution zones, we recommend the following projects:

- **SILAM Pollen (FMI)**  
  [https://silam.fmi.fi/pollen.html](https://silam.fmi.fi/pollen.html)  
  Official source of pollen forecasts from the Finnish Meteorological Institute. Provides 5-day pollen distribution forecasts for Europe and Northern Europe (birch, grasses, olive, ragweed) in cooperation with the European Allergy Network (EAN).

## License

[MIT License](LICENSE)

## Support

If you have questions or issues, create an issue in the [repository](https://github.com/danishru/silam_pollen/issues).

<!-- Badge link definitions -->
[releases-shield]: https://img.shields.io/github/release/danishru/silam_pollen.svg?style=for-the-badge
[releases]: https://github.com/danishru/silam_pollen/releases
[commits-shield]: https://img.shields.io/github/commit-activity/m/danishru/silam_pollen.svg?style=for-the-badge
[commits]: https://github.com/danishru/silam_pollen/commits
[download-shield]: https://img.shields.io/github/downloads/danishru/silam_pollen/total.svg?style=for-the-badge
[downloads]: https://github.com/danishru/silam_pollen/releases
[license-shield]: https://img.shields.io/github/license/danishru/silam_pollen.svg?style=for-the-badge
[license]: https://github.com/danishru/silam_pollen/blob/master/LICENSE
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge
[hacs]: https://hacs.xyz/
