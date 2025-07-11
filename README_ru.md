[![GitHub Release][releases-shield]][releases]
[![Downloads][download-shield]][Downloads]
[![HACS Custom][hacsbadge]][hacs]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

# SILAM Pollen Allergy Sensor for Home Assistant

[README in English here 👈](https://github.com/danishru/silam_pollen/blob/main/README.md)

Интеграция для Home Assistant, использующая набор данных `"Лучший временной ряд, полученный из последнего доступного прогона."` с сервера SILAM Thredds server для создания службы с сенсорами уровня пыльцы для конкретного местоположения. Расчет прогноза производится Finnish Meteorological Institute с учетом данных аэробиологических, фенологических и метеорологических наблюдений.

Источник данных: [https://silam.fmi.fi/pollen.html](https://silam.fmi.fi/pollen.html)

> [!CAUTION]  
> Предоставленные данные являются непроверенными модельными прогнозами, созданными только для научного использования.
> Ни качество, ни полнота представленной информации не гарантируются, и производители данных не несут никакой ответственности за её правильность и своевременность.

> [!IMPORTANT]  
> Эта интеграция создана с использованием редакции ChatGPT для совместного написания кода, исправления ошибок и редактуры.
> Если вы придерживаетесь иной этической точки зрения, приношу извинения. Однако, я считаю, что данное применение является морально приемлемым, поскольку интеграция является некоммерческой, бесплатной и свободной, а её цель — способствовать открытости и взаимодействию.

## Описание

Интеграция **SILAM Pollen** предоставляет службу, состоящую из сенсоров, которая динамически формирует URL для запроса данных о пыльце. Данные запрашиваются с сервера SILAM с помощью HTTP-запроса, затем парсятся и обновляются в Home Assistant. Можно создавать несколько служб для разных местоположений, а также предоставляется возможность выбора необходимых типов пыльцы.

> [!NOTE]
> Обратите внимание: охват территории ограничен и зависит от выбранного набора данных.  
> 🟩 **Зелёный** — зона покрытия **SILAM Regional (v5.9.1)** (более детальная).  
> 🟨 **Жёлтый** — зона покрытия **SILAM Europe (v6.0)** (более общая).  
>  
> Для оценки покрытия и выбора подходящего региона используйте интерактивную карту ниже.

[![Интерактивная карта покрытия с данными по уровню пыльцы](https://danishru.github.io/silam_pollen/pollen_area.webp)](https://danishru.github.io/silam_pollen/)

## 🆕 Что нового

## v0.2.6

- 🆕 **Атрибут `native_name`**  
  Все сенсоры аллергенов теперь включают атрибут `native_name`, который отражает оригинальный ключ из API SILAM (например, `alder_m22`, `grass_m32` и т.д.), обеспечивая лучшую совместимость с внешними инструментами и визуализациями.

- 🔧 **Унификация `entity_id`**  
  ID сущностей (в том числе при сбросе) теперь точно соответствуют ключам в файлах локализации, например `sensor.silam_pollen_{Zone Name}_grass` остаётся одинаковым во всех языках и для всех сенсоров интеграции.

> [!IMPORTANT]  
> Чтобы вернуть имена сущностей к новым значениям по умолчанию, следуйте инструкции по [кастомизации устройств](https://www.home-assistant.io/docs/configuration/customizing-devices/) в документации Home Assistant.

> [!NOTE]  
> Если вы уже создали автоматизации или скрипты, не забудьте обновить в них соответствующие `entity_id`.   
> > Если ваш системный язык Home Assistant на русском или английском, можете игнорировать это уведомление — для этих языков ничего не изменится.

[![Подробнее в релизе v0.2.6](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.6-blue?style=flat-square)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.6)

## Предыдущие обновления
<details>
<summary>Показать</summary>

### v0.2.5 🌟

Это по-настоящему важное обновление для **SILAM Pollen**!
- 🎉 **HACS по умолчанию**  
  Хочу поздравить нас всех — интеграция теперь включена в HACS по умолчанию, и установить её стало ещё проще!  
- 🖼️ **Красивые панели**  
  Крутые новости для любителей дашбордов: [@krissen](https://github.com/krissen) добавил поддержку **SILAM Pollen** в карточку [pollenprognos-card](https://github.com/krissen/pollenprognos-card) (с v2.3.0) — теперь текущее состояние и прогноз аллергенов доступны прямо на вашем дашборде!  
  [Подробнее тут 👈](#панель)  
- 📈 **Долгосрочная статистика**  
  Сенсоры пыльцы и новый диагностический сенсор теперь собирают и показывают исторические данные

[![Подробнее в релизе v0.2.5](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.5-blue?style=flat-square)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.5)

### v0.2.4

- **📖 README по умолчанию на английском**  
  Теперь файл README отображается на английском языке по умолчанию.

[![Подробнее в релизе v0.2.4](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.4-blue?style=flat-square)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.4)

### v0.2.3

- **📦 Подготовка к публикации в HACS**  
  Внесены изменения для размещения интеграции в официальном каталоге HACS по умолчанию.
- **🌐 Добавлен словацкий перевод**  
  Благодарим [@misa1515](https://github.com/misa1515) за реализацию словацкий локализации!
- **🌐 Добавлен голландский перевод**  
  Благодарим [@rubdos](https://github.com/rubdos) за реализацию голландский локализации!

[![Подробнее в релизе v0.2.3](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.3-blue?style=flat-square)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.3)  

### v0.2.2

- **⏱️ Настройка длительности прогноза**  
  При создании или изменении записи теперь можно выбрать длительность прогноза от 36 до 120 часов (по умолчанию 36 ч). При увеличении часов пропорционально растёт число точек прогноза дважды в день.  
- **🛠️ Диагностический сенсор "fetch_duration"**  
  Сенсор для отображения времени выполнения обновления данных (API-запросы, обработка, расчёты). По умолчанию не активирован.
- **🌐 Добавлен чешский перевод**  
  Благодарим [@kasparmir](https://github.com/kasparmir) за первую реализацию чешской локализации!
  
[![Подробнее в релизе v0.2.2](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.2-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.2)  

##
### v0.2.1

**🌸 Прогноз пыльцы (BETA)**  
- В почасовой и дважды в день прогнозы пыльцы добавлены значения для выбранных аллергенов.  
- Для каждого сенсора пыльцы теперь есть атрибут с прогнозом на следующий день, который отображает дневной прогноз на следующий день, так же как для индекса пыльцы.  

[![Подробнее в релизе v0.2.1](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.1-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.1)

##
### v0.2.0

- **🌍 Поддержка двух версий SILAM**  
  Возможность выбрать между `SILAM Europe (v6.0)` и `SILAM Regional (v5.9.1)` — с автоматическим тестом доступности.  
  `SILAM Regional (v5.9.1)` обеспечивает более **детальные и точные прогнозы** для северной и северо-западной Европы.

- **🌸 Прогноз пыльцы (BETA)**  
  Новый погодный сенсор с почасовым и двухразовым прогнозом пыльцы через `weather.get_forecasts`.

- **📊 Единый обработчик данных + служба обновления**  
  Все данные кэшируются через `data_processing.py`.  
  Добавлена служба `SILAM Pollen monitor: Ручное обновление` — можно вызывать вручную или в автоматизациях.

- **🎨 Иконки для интеграции и сенсор**  
  Индикаторы стали нагляднее: каждый аллерген теперь со своей иконкой.

- **🌐 Локализация (на 8 языках)**  
  Интерфейс переведён на: русский, английский, финский, итальянский, шведский, норвежский, датский и немецкий.

[![Подробнее в релизе v0.2.0](https://img.shields.io/badge/Подробнее--в--релизе-v0.2.0-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.2.0)

</details>

## Установка  

### Установка через HACS (рекомендуется)

**Убедитесь, что HACS установлен:**  
Если HACS ещё не установлен, следуйте [официальной инструкции по установке HACS](https://hacs.xyz/docs/use/).

#### Установка одним кликом

Для установки интеграции **SILAM Pollen** перейдите по ссылке ниже и нажмите **Скачать**:  

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danishru&repository=silam_pollen)

#### Обычная установка через HACS

1. Откройте Home Assistant и перейдите в HACS. 
2. В строке поиска введите `SILAM Pollen` и нажмите **Скачать** в меню итеграции.

Теперь ваша интеграция установлена и готова к использованию через HACS!

### Ручная установка

1. Скопируйте папку `silam_pollen` в каталог `custom_components` вашей конфигурации Home Assistant.  
2. Перезапустите Home Assistant.  
3. Добавьте интеграцию через веб-интерфейс:  
   - Перейдите в **Настройки → Интеграции**.  
   - Нажмите **Добавить интеграцию** и выберите **SILAM Pollen**.  
   - Заполните необходимые поля (имя, координаты, высоту, выбор типа пыльцы, интервал опроса).  

## Конфигурация

Перейдите по ссылке ниже и следуйте инструкциям мастера настройки **SILAM Pollen**:  

[![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=silam_pollen)

Или откройте **Настройки → Интеграции** в Home Assistant, найдите `SILAM Pollen` и следуйте инструкциям мастера настройки.

Здесь вы сможете задать параметры для корректной работы интеграции:

- **Зона наблюдения** – позволяет выбрать настроенную зону в вашем Home Assistant. По умолчанию выбирается зона `"Home"`.  
- **Тип пыльцы** – выбор наблюдаемой пыльцы. Можно не выбирать ни один тип или выбрать несколько из списка.  
- **Интервал обновления** – интервал загрузки данных с сервера SILAM Thredds server в минутах (по умолчанию 60, минимальное значение — 30 минут).  
- **Прогноз пыльцы (BETA)** – включает дополнительный погодный сенсор с прогнозом уровня пыльцы. Может увеличить время ответа API.  
- **Желаемая длительность прогноза** – желаемый горизонт прогнозирования (от 36 до 120 ч, по умолчанию 36 ч). Фактический объём данных может быть короче, если сервер SILAM возвращает менее продолжительный прогноз.    
- **Название зоны** – по умолчанию используется название из выбранной зоны. Это имя применяется для формирования имён службы и сенсоров. Можно переопределить.  
- **Высота над уровнем моря** – высота, используемая для выборки данных. Если выбрана зона `"Home"`, берётся значение из общих настроек (`config/general`); иначе по умолчанию 275 м. Можно переопределить.  
- **Местоположение** – показывает на карте выбранные координаты. Зону можно изменить с помощью карты или вручную задать широту, долготу и радиус. Указанный радиус отражает примерное пространственное разрешение данных о пыльце (около 10 км).

## Использование

После установки интеграции в Home Assistant создается служба с именем `SILAM Pollen - {Название зоны}`. В описании службы указываются координаты местоположения наблюдения и версия используемого набора данных.

![image](https://github.com/user-attachments/assets/5d060b47-e758-4d4c-9325-0188d991bfee)

В рамках службы создаётся погодная сущность **Прогноз пыльцы**, состояние которой отображает значение **индекса пыльцы ближайшего прогноза**, рассчитанному на основе почасовых средних значений и пороговых уровней из таблицы Mikhail Sofiev ([ссылка](https://www.researchgate.net/profile/Mikhail-Sofiev)).  

**Возможные значения индекса**:  
- `very_low` — Очень низкий  
- `low` — Низкий  
- `moderate` — Средний  
- `high` — Высокий  
- `very_high` — Очень высокий  
- `unknown` — Неизвестно  

**Атрибуты сенсора «Прогноз пыльцы»**:  
- **Следующий индекс** (`next_condition`) — ожидаемое состояние из первого 3-часового интервала (только при включённом прогнозе).  
- **Пыльца <аллерген>** (`pollen_<allergen>`) — смоделированная числовая концентрация каждого выбранного аллергена ближайшего прогноза, зерна/м³.  
- **Высота (уровень моря)** (`altitude`) — ближайшая доступная высота, использованная для выборки данных.  
- **Дата/время прогноза** (`date`) — точка времени, на которую рассчитан прогноз (ISO 8601).  
- **Основной аллерген** (`responsible_elevated`) — аллерген, оказавший наибольшее влияние на расчёт индекса.  
- **Источник данных** (`attribution`) — `Powered by silam.fmi.fi`.  

Если включена опция **Прогноз пыльцы**, будут дополнительно доступны прогнозы:
- почасовой прогноз на 24 часа (с шагом 3 часа);
- прогноз дважды в сутки на выбранную длительность (по умолчанию 36 ч, максимальная до 120 ч) с индексом и пиковыми значениями по каждому аллергену;
- ежедневный прогноз на следующие дни (по умолчанию 36 ч, максимальная до 120 ч) с индексом и пиковыми значениями по каждому аллергену.  

> [!IMPORTANT]
> **Важно:** фактический горизонт прогноза зависит от доступных данных на [SILAM Thredds server](https://thredds.silam.fmi.fi/thredds/catalog/catalog.html). Даже если в настройках указана длительность до 120 часов, модель может вернуть только более короткий интервал (например, 48 часов) — в зависимости от времени последнего прогноза.
>
> Для отслеживания этого используется диагностический сенсор **Горизонт прогноза**, который показывает реальный (фактически доступный) горизонт прогноза. Дополнительный атрибут **Желаемая длительность прогноза** этого сенсора отображает значение, заданное в конфигурации интеграции.

![image](https://github.com/user-attachments/assets/99e236a0-b45e-4b51-8c80-d3cdde66d27e)

Эти данные доступны через стандартный сервис `weather.get_forecasts`.

![image](https://github.com/user-attachments/assets/54f85a99-6b78-4035-a206-5f4aa64e562e)

<details>
<summary>Показать пример ответа "Ежечасный"</summary>

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
<summary>Показать пример ответа "Два раза в день"</summary>

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
<summary>Показать пример ответа "Ежедневный"</summary>

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

### Как рассчитывается прогноз

В интеграции **SILAM Pollen** данные модели SILAM парсятся из XML-ответов, объединяются по полю `date`, а затем агрегируются в три вида прогнозов:

#### Почасовой прогноз (24 часа)
- Строится с шагом в 3 часа.
- Для каждого 3-часового окна рассчитываются:
  - Максимальная температура.
  - Индекс пыльцы — максимальное значение (отражает истинный пик);
  - Максимальное значение для каждого выбранного аллергена.
- Метка времени прогноза — середина 3-часового окна (локальное время).
- Используется текущая дата + 24 часа вперёд.

#### Прогноз дважды в сутки (12-часовые интервалы, 36 – 120 ч)
- Интервалы по 12 ч (06:00–18:00 и 18:00–06:00 местного времени).  
- Для интервала рассчитываются:  
  - максимальная и минимальная температура;  
  - **Индекс пыльцы** и **уровень каждого аллергена**, сглаженные «наблюдательным» процентилем:  
    - ≥ 18 точек → 80-й перцентиль; 12 – 17 точек → 70-й; < 12 → максимум;  
    - метод без интерполяции — берётся фактическое значение (ceil-индекс).  
  - **Пиковые значения аллергенов** (`allergen_peaks`) — максимальная концентрация и время её наступления в интервале.  
- Метки прогноза ставятся на 00:00 и 12:00 местного времени.

#### Ежедневный прогноз (сутки, 36 – 120 ч)
- Окна по 24 ч, начиная «завтра».  
- Для каждого дня вычисляется:  
  - максимальная и минимальная температура;  
  - **Индекс пыльцы** и **уровень аллергенов** по той же схеме «наблюдательного» процентиля;  
  - **Пиковые значения аллергенов** за сутки.  
- Метка прогноза — 12:00 местного времени.

#### Техника агрегации
- Данные из SILAM парсятся из XML и объединяются по дате (`date`).
- Агрегации выполняются через `max`, `min` и собственную функцию «observational percentile» (ceil-индекс без интерполяции).  
- Все прогнозы кэшируются в `merged_data` и доступны через `weather.get_forecasts`.

Если выбран один или несколько типов пыльцы, для каждого из них создаётся дополнительный отдельный сенсор **{Название типа}**, отображающий смоделированное количество пыльцы (зерна/м³).

**Атрибуты сенсоров «{Тип пыльцы}»**:  
- **Высота (уровень моря)** — ближайшая доступная высота, использованная для выборки данных.  
- **Прогноз на завтра** — агрегированное значение прогноза уровня пыльцы на следующий день (отображается, если включён прогноз).

**Атрибуты сенсора «Индекс пыльцы»**:  
- **Дата/время прогноза** — точка времени, на которую рассчитан индекс (ISO 8601).  
- **Основной аллерген** — аллерген, оказавший наибольшее влияние на расчёт индекса.  
- **Прогноз на завтра** — дневной прогноз уровня пыльцы на следующий день (отображается, если включён прогноз).

**Время запроса (`fetch_duration`)** — сенсор, по умолчанию отключённый, показывающий общее время обновления данных (API-запрос, парсинг, расчёты).  

**Горизонт прогноза (`forecast_horizon`)** — сенсор, по умолчанию включённый, показывающий фактический горизонт прогноза в часах (разница между меткой «сейчас» и последней точкой прогноза). Атрибут **`forecast_duration`** отображает **желаемую** длительность прогноза в часах, заданную в настройках интеграции.


|  ![image](https://github.com/user-attachments/assets/99a5e8a3-303c-4c7c-b885-a70c5e54269b) | ![image](https://github.com/user-attachments/assets/dbc735f0-10f0-4a88-8fbb-1dbc5d98f5eb)  |
| ------------- | ------------- |

## Панель

Отличная новость для любителей красивых дашбордов — теперь прогноз уровня пыльцы можно вывести в виде наглядной карточки!  
Карточка [pollenprognos-card](https://github.com/krissen/pollenprognos-card) с версии [v2.3.0](https://github.com/krissen/pollenprognos-card/releases/tag/v2.3.0) поддерживает интеграцию **SILAM Pollen**, а в [v2.3.3](https://github.com/krissen/pollenprognos-card/releases/tag/v2.3.3) добавлены:

- отображение почасовых и двухразовых прогнозов;  
- локализация на множество языков, включая русский;  
- другие полезные улучшения.  

Начиная с версии [v2.3.5](https://github.com/krissen/pollenprognos-card/releases/tag/v2.3.5):

- поддержка **ежедневного прогноза** (через `weather.get_forecasts`) — до 5 дней прогноза;  
- упрощённая логика (можно использовать одну погодную сущность для всего прогноза).  

> [!IMPORTANT]  
> **Совместимость версий:**  
> pollenprognos-card **≥ v2.3.5** требует silam_pollen **≥ v0.2.7** (в более ранних версиях карты подойдут silam_pollen ≥ v0.2.5).

Огромное спасибо [@krissen](https://github.com/krissen) за его работу!

Карточка доступна в **репозитории по умолчанию HACS**.  
Для установки нажмите **Скачать** в меню карточки:

[![HACS Repository Badge](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=krissen&repository=pollenprognos-card)

### Взгляните, как это выглядит:

![Пример отображения pollenprognos-card](https://github.com/user-attachments/assets/e25e5b05-5fca-49e9-a673-7932edfdc84e)

Дополнительную информацию и документацию смотрите в репозитории, а если карточка вам понравилась — не забудьте отметить её звёздочкой ⭐ и оставить issue при обнаружении ошибок или пожеланий:  
https://github.com/krissen/pollenprognos-card.

 
## Дополнительные ресурсы

Для более подробного изучения информации о пыльце и зонах её распространения рекомендуем ознакомиться со следующими проектами:

- **SILAM Pollen (FMI)**  
  [https://silam.fmi.fi/pollen.html](https://silam.fmi.fi/pollen.html)  
  Официальный источник пыльцевых прогнозов от Финского метеорологического института. Предоставляет 5-дневные прогнозы распределения пыльцы по Европе и Северной Европе (береза, трава, олива, амброзия) в сотрудничестве с Европейской сетью аллергенов (EAN).

- **Pollen Club**  
  [https://pollen.club/](https://pollen.club/)  
  Совместный проект SILAM и Пыльца Club, предлагающий прогнозы появления пыльцы для европейской части России. На карте отображается почасовой прогноз SILAM и дневной прогноз для Москвы, при этом при совмещении выбирается вариант с более высокими концентрациями.

- **Allergotop: Allergofon**  
  [https://allergotop.com/allergofon](https://allergotop.com/allergofon)  
  Проект, предоставляющий лабораторно-исследовательские данные пыльцевого мониторинга, полученные с помощью пыльцевых ловушек. Эти данные помогают определить порог чувствительности к аллергенам и оптимизировать ежедневную активность аллергиков.

- **MyAllergo**  
  [https://myallergo.ru/pylca/](https://myallergo.ru/pylca/)  
  Проект, публикующий ежедневные данные пыльцевой ловушки в Санкт-Петербурге. Предоставляет информацию о концентрации пыльцы с удобной цветовой индикацией, что особенно полезно для аллергиков.

- **Allergo.Space: Pollen Monitoring**  
  [https://allergo.space/pollen-monitoring/](https://allergo.space/pollen-monitoring/)  
  Информационный ресурс, публикующий модельные прогнозы пыльцы, собранные из открытых источников (в том числе данных SILAM). Проект ориентирован на улучшение качества жизни аллергиков за счёт точного мониторинга аллергенов.

- **Яндекс.Погода – Аллергии**  
  [https://yandex.ru/pogoda/allergies](https://yandex.ru/pogoda/allergies)  
  Раздел Яндекс.Погоды, где по уникальной формуле рассчитывается активность пыльцы с учётом периодов цветения, погодных условий и отзывов пользователей для оценки влияния аллергенов на самочувствие.

## Публикации по модели SILAM

Ниже приведены ключевые статьи, описывающие основные модули и валидацию модели распространения пыльцы SILAM, упорядоченные по дате публикации:

- **A numerical model of birch pollen emission and dispersion in the atmosphere. Description of the emission module** (Mikhail Sofiev et al., 2012)  
  Подробное описание модуля эмиссии берёзовой пыльцы в SILAM. Опубликовано 13 марта 2012.  
  <https://link.springer.com/article/10.1007/s00484-012-0532-z>

- **Variation of the group 5 grass pollen allergen content of airborne pollen in relation to geographic location and time in season** (Jeroen Buters et al., 2015)  
  Исследование сезонной и географической изменчивости содержания аллергенов группы 5 в воздушной пыльце трав. Опубликовано онлайн 6 мая 2015.  
  <https://www.jacionline.org/article/S0091-6749(15)00412-1/fulltext>

- **On impact of transport conditions on variability of the seasonal pollen index** (Mikhail Sofiev, 2016)  
  Анализ влияния метеорологических условий переноса на сезонный индекс пыльцы. Опубликовано 24 октября 2016.  
  <https://link.springer.com/article/10.1007/s10453-016-9459-x>

- **Bioaerosols in the atmosphere at two sites in Northern Europe in spring 2021: Outline of an experimental campaign** (Mikhail Sofiev et al., 2022)  
  Обзор экспериментальной кампании по изучению биоаэрозолей в атмосфере на двух площадках Северной Европы весной 2021 г. Опубликовано 7 июля 2022.  
  <https://www.sciencedirect.com/science/article/pii/S0013935122011252>

- **European pollen reanalysis, 1980–2022, for alder, birch, and olive** (Mikhail Sofiev et al., 2024)  
  Реанализ европейских данных по пыльце ольхи, берёзы и оливы за период 1980–2022 гг. Опубликовано 3 октября 2024.  
  <https://www.nature.com/articles/s41597-024-03686-2>

## Благодарности

Спасибо всем, кто внёс свой вклад!

[![contributors](https://contributors-img.web.app/image?repo=danishru/silam_pollen)](https://github.com/danishru/silam_pollen/graphs/contributors)

## Лицензия

[MIT License](LICENSE)

## Поддержка

Если возникнут вопросы или проблемы, создайте issue в [репозитории](https://github.com/danishru/silam_pollen/issues).  

![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.silam_pollen.total&style=flat-square&label=use&cacheSeconds=15600)

<!-- Определения ссылок для бейджей -->
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
