
[![GitHub Release][releases-shield]][releases]
[![Downloads][download-shield]][Downloads]
[![HACS Custom][hacsbadge]][hacs]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

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
> 🟦 **Blue** — coverage zone of **SILAM Finland (v6.1)** (highest detail, **0.8 km** resolution).  
> 🟩 **Green** — coverage zone of **SILAM Northern Europe (v5.9.1)** (more detailed, **2.5 km** resolution).  
> 🟨 **Yellow** — coverage zone of **SILAM Europe (v6.1/v6.0)** (more general, **10 km** resolution).  
>  
> To evaluate coverage and choose the appropriate dataset, use the interactive map below.

<a href="https://danishru.github.io/silam_pollen/" target="_blank" rel="noopener">
  <img
    src="https://danishru.github.io/silam_pollen/pollen_area.webp"
    alt="Interactive pollen coverage map"
    style="max-width:100%; cursor:pointer;"
  />
</a>

## 🆕 What’s new

### v0.3.1 🧠 Smarter data updates.

Version v0.3.1 introduces a major internal improvement in how SILAM Pollen **detects and updates forecast data**.

![image](https://github.com/user-attachments/assets/b5e654e7-77b6-43e5-a082-3dec4457a80f)

The integration is now **run-aware** and checks the SILAM **runs catalog** before fetching data. This allows it to reliably determine whether a **new model run is actually available**, instead of blindly re-downloading the same dataset.

If the current run hasn’t changed:
- cached data is safely reused,
- full XML downloads are skipped,
- and only genuinely missing forecast hours are fetched when the forecast window moves forward.

This results in:
- significantly fewer unnecessary network requests,
- faster and more predictable updates,
- reduced load on both Home Assistant and the SILAM data infrastructure.

These changes are especially important ahead of the pollen season, ensuring timely updates while keeping the integration efficient and robust.

[![More in release v0.3.1](https://img.shields.io/badge/More--in--release-v0.3.1-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.3.1)

## All updates

<a href="https://danishru.github.io/silam_pollen/site/blog" target="_blank" rel="noopener">
Release history and changelog archive ↗
</a>

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
- **Desired forecast duration** — the forecast horizon you’d like to retrieve (36–120 h, default 36 h).  
  The actual horizon may be shorter if the SILAM server currently provides fewer hours of data.
- **Zone Name** – by default, the name from the selected zone is used. This name is applied to the service and sensor names. You can override it.  
- **Altitude above Sea Level** – the altitude used for data sampling. If the `"Home"` zone is selected, the value from the general settings (`config/general`) is used; otherwise, the default is 275 m. You can override it.  
- **Location** – shows the selected coordinates on the map. You can change the zone using the map or manually set the latitude, longitude, and radius. The specified radius reflects the approximate spatial resolution of the pollen data (about 10 km).

![image](https://github.com/user-attachments/assets/bd8358ab-3892-417d-bfd1-fb509c0fa1a6)

## Usage

After installing the integration in Home Assistant, a service named `SILAM Pollen - {Zone Name}` is created. The service description shows the observation location coordinates and the dataset version used.

![image](https://github.com/user-attachments/assets/568a723a-e9e5-4045-9e6d-a6b99e015b9b)


Within the service a weather entity called **Pollen Forecast** is created. Its `state` shows the pollen-index value for the *nearest* forecast, calculated from hourly mean concentrations and the threshold levels defined in Mikhail Sofiev’s table ([link](https://www.researchgate.net/profile/Mikhail-Sofiev)).

**Possible index values:**  
- `very_low` — Very Low  
- `low` — Low  
- `moderate` — Moderate  
- `high` — High  
- `very_high` — Very High  
- `unknown` — Unknown  

### "Pollen Forecast" sensor attributes

- **Next index** (`next_condition`) — expected condition from the first 3-hour window (shown only when forecasting is enabled).  
- **Pollen <allergen>** (`pollen_<allergen>`) — modelled numeric concentration of each selected allergen in the nearest forecast, grains/m³.  
- **Altitude (above sea level)** (`altitude`) — closest available grid height used for sampling.  
- **Forecast date/time** (`date`) — ISO 8601 timestamp for which the forecast is valid.  
- **Primary allergen** (`responsible_elevated`) — allergen that contributed most to the index value.  
- **Data source** (`attribution`) — `Powered by silam.fmi.fi`.

If **Pollen Forecast** is enabled, three additional forecast types become available:

1. **Hourly forecast** for the next 24 h (3-hour steps).  
2. **Twice-daily forecast** across the chosen horizon (default 36 h, up to 120 h) with the index and peak values for each allergen.  
3. **Daily forecast** for the coming days (default 36 h, up to 120 h) with the index and peak values for each allergen.

> [!IMPORTANT]  
> **Important:** the *actual* forecast horizon depends on data currently available on the SILAM Thredds server.  
> Even if you request up to 120 hours, the model might return a shorter span (e.g. 48 hours) depending on the latest run time.  
>  
> The diagnostic sensor **Forecast Horizon** helps track this: it shows the real (available) horizon, while its attribute **`forecast_duration`** displays the duration you requested in the integration settings.

![image](https://github.com/user-attachments/assets/b5ff0507-fe13-48eb-a891-910df2c03707)

This data is available via the standard `weather.get_forecasts` service.

![image](https://github.com/user-attachments/assets/def0ba1d-73f9-4aec-9a3d-7bf3013c5ab8)

<details>
<summary>Show "Hourly" response example</summary>

```yaml
weather.silam_pollen_home_assistant_forecast:
  forecast:
    - datetime: "2025-07-09T16:00:00+00:00"
      condition: low
      native_temperature_unit: °C
      pollen_index: 2
      temperature: 28.8
      pollen_birch: 0
      pollen_grass: 17
    - datetime: "2025-07-09T19:00:00+00:00"
      condition: low
      native_temperature_unit: °C
      pollen_index: 2
      temperature: 24.7
      pollen_birch: 0
      pollen_grass: 13
    - datetime: "2025-07-09T22:00:00+00:00"
      condition: low
      native_temperature_unit: °C
      pollen_index: 2
      temperature: 23.5
      pollen_birch: 0
      pollen_grass: 12
    - datetime: "2025-07-10T01:00:00+00:00"
      condition: moderate
      native_temperature_unit: °C
      pollen_index: 3
      temperature: 22.8
      pollen_birch: 0
      pollen_grass: 27
    - datetime: "2025-07-10T04:00:00+00:00"
      condition: moderate
      native_temperature_unit: °C
      pollen_index: 3
      temperature: 24.4
      pollen_birch: 0
      pollen_grass: 46
    - datetime: "2025-07-10T07:00:00+00:00"
      condition: moderate
      native_temperature_unit: °C
      pollen_index: 3
      temperature: 29.4
      pollen_birch: 0
      pollen_grass: 35
    - datetime: "2025-07-10T10:00:00+00:00"
      condition: low
      native_temperature_unit: °C
      pollen_index: 2
      temperature: 33.4
      pollen_birch: 0
      pollen_grass: 19
    - datetime: "2025-07-10T13:00:00+00:00"
      condition: low
      native_temperature_unit: °C
      pollen_index: 2
      temperature: 33.4
      pollen_birch: 0
      pollen_grass: 12
```
</details>  

<details>
<summary>Show "Twice-daily" response example</summary>

```yaml
weather.silam_pollen_home_assistant_forecast:
  forecast:
    - datetime: "2025-07-09T21:00:00+00:00"
      is_daytime: false
      condition: low
      pollen_index: 2
      temperature: 28.8
      allergen_peaks:
        grass:
          peak: 27
          time: "2025-07-10T02:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 13
      templow: 22.5
    - datetime: "2025-07-10T09:00:00+00:00"
      is_daytime: true
      condition: moderate
      pollen_index: 3
      temperature: 33.4
      allergen_peaks:
        grass:
          peak: 46
          time: "2025-07-10T05:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 35
      templow: 22.6
    - datetime: "2025-07-10T21:00:00+00:00"
      is_daytime: false
      condition: low
      pollen_index: 2
      temperature: 32.9
      allergen_peaks:
        grass:
          peak: 21
          time: "2025-07-10T19:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 14
      templow: 23
    - datetime: "2025-07-11T09:00:00+00:00"
      is_daytime: true
      condition: low
      pollen_index: 2
      temperature: 35.2
      allergen_peaks:
        grass:
          peak: 20
          time: "2025-07-11T08:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 16
      templow: 23.3
    - datetime: "2025-07-11T21:00:00+00:00"
      is_daytime: false
      condition: low
      pollen_index: 2
      temperature: 35.1
      allergen_peaks:
        grass:
          peak: 22
          time: "2025-07-11T19:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 15
      templow: 23.3
    - datetime: "2025-07-12T09:00:00+00:00"
      is_daytime: true
      condition: low
      pollen_index: 2
      temperature: 35.1
      allergen_peaks:
        grass:
          peak: 16
          time: "2025-07-12T06:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 14
      templow: 23.3
    - datetime: "2025-07-12T21:00:00+00:00"
      is_daytime: false
      condition: low
      pollen_index: 2
      temperature: 34.8
      allergen_peaks:
        grass:
          peak: 16
          time: "2025-07-12T20:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 15
      templow: 24
    - datetime: "2025-07-13T09:00:00+00:00"
      is_daytime: true
      condition: low
      pollen_index: 2
      temperature: 31.9
      allergen_peaks:
        grass:
          peak: 19
          time: "2025-07-13T09:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 14
      templow: 23.7
    - datetime: "2025-07-13T21:00:00+00:00"
      is_daytime: false
      condition: low
      pollen_index: 2
      temperature: 29
      allergen_peaks:
        grass:
          peak: 14
          time: "2025-07-13T18:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 14
      templow: 21.5
```
</details>

<details>
<summary>Show "Daily" response example</summary>

```yaml
weather.silam_pollen_home_assistant_forecast:
  forecast:
    - datetime: "2025-07-10T09:00:00+00:00"
      condition: moderate
      pollen_index: 3
      temperature: 33.4
      allergen_peaks:
        grass:
          peak: 46
          time: "2025-07-10T05:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 34
      templow: 22.5
    - datetime: "2025-07-11T09:00:00+00:00"
      condition: low
      pollen_index: 2
      temperature: 35.2
      allergen_peaks:
        grass:
          peak: 22
          time: "2025-07-11T19:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 18
      templow: 23
    - datetime: "2025-07-12T09:00:00+00:00"
      condition: low
      pollen_index: 2
      temperature: 35.1
      allergen_peaks:
        grass:
          peak: 16
          time: "2025-07-12T06:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 15
      templow: 23.3
    - datetime: "2025-07-13T09:00:00+00:00"
      condition: low
      pollen_index: 2
      temperature: 31.9
      allergen_peaks:
        grass:
          peak: 19
          time: "2025-07-13T09:00:00+00:00"
      pollen_birch: 0
      pollen_grass: 14
      templow: 21.5
```
</details>

### How the forecast is calculated

In **SILAM Pollen**, SILAM‐model XML responses are parsed, merged by the `date` field, and then aggregated into three forecast types:

#### Hourly forecast (24 h)
* Built in 3-hour steps.  
* For each 3-hour window we compute:  
  * Maximum temperature.  
  * Pollen index — the maximum value (captures the true peak).  
  * Maximum value for every selected allergen.  
* The forecast timestamp is the midpoint of the 3-hour window (local time).  
* Uses “today + 24 h” as the time span.

#### Twice-daily forecast (12-hour windows, 36 – 120 h)
* Two windows per day: 06:00–18:00 and 18:00–06:00 local time.  
* For each 12-hour window we calculate:  
  * Maximum and minimum temperature.  
  * **Pollen index** and **allergen levels**, smoothed by an *observational percentile*:  
    * ≥ 18 points → 80th percentile  
    * 12 – 17 points → 70th percentile  
    * < 12 points → maximum  
    * No interpolation is used — the actual value at the percentile (ceil-index) is taken.  
  * **Allergen peaks** (`allergen_peaks`) — the maximum concentration and the time it occurs within the window.  
* Forecast timestamps are placed at 00:00 and 12:00 local time.

#### Daily forecast (24-hour windows, 36 – 120 h)
* 24-hour windows starting "tomorrow."  
* For each day we compute:  
  * Maximum and minimum temperature.  
  * **Pollen index** and **allergen levels** using the same observational-percentile method.  
  * **Allergen peaks** for the day.  
* Forecast timestamp is 12:00 local time.

#### Aggregation technique
* SILAM XML is parsed and merged by `date`.  
* Aggregations use `max`, `min`, and a custom *observational percentile* function (ceil-index, no interpolation).  
* All forecasts are cached in `merged_data` and served via `weather.get_forecasts`.

If one or more pollen types are selected, a separate **{Pollen Type}** sensor is created for each, displaying the modeled pollen grain concentration (grains/m³).

**Attributes of the "{Pollen Type}" sensors:**  
- **Altitude (sea level)** — the nearest available altitude used for data sampling.  
- **Forecast for Tomorrow** — the aggregated pollen level forecast value for the next day (shown if the forecast is enabled).

**Attributes of the "Pollen Index" sensor:**  
- **Forecast Date & Time** — the timestamp for which the index is calculated (ISO 8601).  
- **Primary Allergen** — the allergen that had the greatest impact on the index calculation.  
- **Forecast for Tomorrow** — the daily pollen level forecast for the next day (shown if the forecast is enabled).

**Fetch duration (`fetch_duration`)** — a sensor (disabled by default) that shows the total time spent refreshing the data (API call, parsing, calculations).  

**Forecast horizon (`forecast_horizon`)** — a sensor (disabled by default) that displays the *actual* forecast span in hours (the gap between the “now” timestamp and the last forecast point).  
Its attribute **`forecast_duration`** reveals the *requested* forecast length in hours, as set in the integration options.

|  ![image](https://github.com/user-attachments/assets/ae513967-6ddc-43be-8b7b-c8076f6155a5) | ![image](https://github.com/user-attachments/assets/06fc40d5-32e6-4332-8696-0e7ff970a48c)  | ![image](https://github.com/user-attachments/assets/8307c335-6de9-4517-8ded-f5923f66b6da) |
| ------------- | ------------- | ------------- |

## Dashboard Card

### Built-in card (recommended)

Starting from **v0.3.0**, **SILAM Pollen** includes a built-in Lovelace card —  
**Absolute Forecast Card** (local build), developed as part of the project.

The card provides a compact, at-a-glance view of **weather and pollen** in a single dashboard element.

![image](https://github.com/user-attachments/assets/15a81dae-7c99-4418-9525-08411045bd56)

**Key features:**
- Dedicated **allergen layer** with SILAM pollen concentrations (core feature)
- Individual forecast lines for each allergen with **peak highlighting** and **trend indicators**
- Integrated **pollen + full weather forecast** in a single, unified timeline
- Multiple forecast display modes (**Standard / Focus / Minimal**) with configurable layouts
- Fully interactive: tap / hold / double actions on forecast elements
- Local, self-contained card — **no CDN**, works fully offline

> [!IMPORTANT]  
> To use the built-in card, add the JavaScript module manually:
> 
> [![Open your Home Assistant instance and show your dashboard resources.](https://my.home-assistant.io/badges/lovelace_resources.svg)](https://my.home-assistant.io/redirect/lovelace_resources/)  
> **Settings → Dashboards → Resources → Add** → URL: `/local/absolute-forecast-card.js` → **Resource type: JavaScript Module**.

➡️ Detailed overview, screenshots, and change log:  
**SILAM Pollen v0.3.0 Release Notes**  
https://github.com/danishru/silam_pollen/releases/tag/v0.3.0

### Third-party card (optional)

SILAM Pollen entities can also be used with community dashboard cards.

One such option is **pollenprognos-card**, which supports SILAM Pollen entities and is available via **HACS**.

- Repository: https://github.com/krissen/pollenprognos-card

To install, click **Download** in the card’s menu:

[![HACS Repository Badge](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=krissen&repository=pollenprognos-card)

Huge thanks to [@krissen](https://github.com/krissen) for supporting SILAM Pollen!

## Additional Resources

For more detailed information on pollen and its distribution zones, we recommend the following projects:

- **SILAM Pollen (FMI)**  
  [https://silam.fmi.fi/pollen.html](https://silam.fmi.fi/pollen.html)  
  Official source of pollen forecasts from the Finnish Meteorological Institute. Provides 5-day pollen distribution forecasts for Europe and Northern Europe (birch, grasses, olive, ragweed) in cooperation with the European Allergy Network (EAN).

## Publications on the SILAM Model

Below are key papers detailing the main modules and validation of the SILAM pollen dispersion model, ordered by publication date:

- **A numerical model of birch pollen emission and dispersion in the atmosphere. Description of the emission module** (Mikhail Sofiev et al., 2012)  
  Detailed description of the SILAM birch pollen emission module. Published 13 March 2012.  
  <https://link.springer.com/article/10.1007/s00484-012-0532-z>

- **Variation of the group 5 grass pollen allergen content of airborne pollen in relation to geographic location and time in season** (Jeroen Buters et al., 2015)  
  Study of seasonal and geographic variability in group 5 grass pollen allergen content. Published online 6 May 2015.  
  <https://www.jacionline.org/article/S0091-6749(15)00412-1/fulltext>

- **On impact of transport conditions on variability of the seasonal pollen index** (Mikhail Sofiev, 2016)  
  Investigation of how atmospheric transport affects seasonal pollen index variability. Published 24 October 2016.  
  <https://link.springer.com/article/10.1007/s10453-016-9459-x>

- **Bioaerosols in the atmosphere at two sites in Northern Europe in spring 2021: Outline of an experimental campaign** (Mikhail Sofiev et al., 2022)  
  Overview of an experimental campaign studying bioaerosols at two sites in Northern Europe in spring 2021. Published 7 July 2022.  
  <https://www.sciencedirect.com/science/article/pii/S0013935122011252>

- **European pollen reanalysis, 1980–2022, for alder, birch, and olive** (Mikhail Sofiev et al., 2024)  
  A reanalysis of European pollen data for alder, birch, and olive from 1980 to 2022. Published 3 October 2024.  
  <https://www.nature.com/articles/s41597-024-03686-2>

## Thanks

Thanks to all the people who have contributed!

[![contributors](https://contributors-img.web.app/image?repo=danishru/silam_pollen)](https://github.com/danishru/silam_pollen/graphs/contributors)

## License

[MIT License](LICENSE)

## Support

If you have questions or issues, create an issue in the [repository](https://github.com/danishru/silam_pollen/issues).  

![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.silam_pollen.total&style=flat-square&label=use&cacheSeconds=15600)


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
