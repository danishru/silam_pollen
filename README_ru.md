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
> 🟦 **Синий** — зона покрытия **SILAM Finland (v6.1)** (наивысшая детализация, пространственное разрешение **0,8 км**).  
> 🟩 **Зелёный** — зона покрытия **SILAM Northern Europe (v6.1)** (повышенная детализация, пространственное разрешение **2,5 км**).  
> 🟨 **Жёлтый** — зона покрытия **SILAM Europe (v6.1)** (общее покрытие, пространственное разрешение **10 км**).  
>  
> Для оценки покрытия и выбора подходящего набора данных используйте интерактивную карту ниже.

<a href="https://danishru.github.io/silam_pollen/" target="_blank" rel="noopener">
  <img
    src="https://danishru.github.io/silam_pollen/pollen_area.webp"
    alt="Интерактивная карта покрытия с данными по уровню пыльцы"
    style="max-width:100%; cursor:pointer;"
  />
</a>

## 🆕 Что нового

### v0.3.2 🧠 Более умные обновления к новому сезону

Релиз **v0.3.2** усиливает **SMART-логику обновления данных**, делая прогнозы пыльцы более надёжными и удобными в начале нового сезона.

Благодаря **SMART-выбору датасета**, SILAM Pollen больше не зависит от жёстко заданных настроек.  
Интеграция **автоматически выбирает наиболее подходящий датасет для вашего местоположения**, исходя из реального покрытия прогноза.

На практике это означает:
- меньше ручной настройки и сомнений,
- меньше ситуаций с нерелевантными или вводящими в заблуждение данными,
- более спокойную и предсказуемую работу при смене сезонов и обновлении моделей.

![image](https://github.com/user-attachments/assets/c4f6b8f8-93e0-4543-9eb3-4e598fd4d54a)

Ручной выбор датасета по-прежнему доступен, но **SMART-режим рекомендуется для повседневного использования**.

#### 🌍 Датасеты SILAM pollen v6.1

В релизе добавлена поддержка **актуальных датасетов SILAM pollen v6.1**, которые становятся базой прогнозов на ближайшие пыльцевые сезоны.

По сравнению с предыдущими версиями, датасеты v6.1 дают:
- обновлённые расчёты **SILAM v6.1** для текущего сезона,
- актуализированный **общеевропейский базовый прогноз** (SILAM Europe pollen v6.1),
- новый **региональный датасет повышенной детализации** там, где он доступен.

- **SILAM Finland pollen v6.1** обеспечивает **наивысшую детализацию прогноза** в зоне своего покрытия  
  🟦 **Синяя зона** — покрытие **SILAM Finland (v6.1)** с пространственным разрешением **до 0,8 км**, особенно актуально для регионов:
  - Финляндия  
  - Санкт-Петербург и Северо-Запад России  
  - Северная и восточная Швеция (включая Стокгольм)  
  - Северо-Восток Норвегии  
  - Север Эстонии (включая Таллин и Нарву)

При наличии покрытия датасет **автоматически выбирается в SMART-режиме**, при этом ручной выбор остаётся доступным в настройках интеграции.

#### ⚠️ Устаревание

> [!WARNING]  
> 📉 Сенсор **Pollen Index** переведён в **legacy** и **отключён по умолчанию**.  
> При обновлении он автоматически удаляется и может быть включён вручную через **legacy-переключатель** в настройках интеграции.

#### 📦 История релизов и документация

Полная история обновлений SILAM Pollen теперь публикуется на сайте проекта:  
https://danishru.github.io/silam_pollen/site/blog

[![Подробнее в релизе v0.3.2](https://img.shields.io/badge/Подробнее--в--релизе-v0.3.2-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.3.2)

### v0.3.1 🧠 Умная логика обновления данных.

В версии v0.3.1 значительно улучшена **внутренняя логика определения и обновления прогнозных данных** в SILAM Pollen.

![image](https://github.com/user-attachments/assets/b5e654e7-77b6-43e5-a082-3dec4457a80f)

Интеграция теперь работает с учётом **run-ов модели** и предварительно проверяет **каталог запусков SILAM**, чтобы точно определить, появился ли **новый набор данных**, а не выполнять повторную загрузку без необходимости.

Если run не изменился:
- безопасно используется кеш,
- полная загрузка XML пропускается,
- при смещении горизонта прогноза догружаются **только недостающие часы**.

В результате:
- существенно сокращается количество лишних сетевых запросов,
- обновления становятся быстрее и предсказуемее,
- снижается нагрузка как на Home Assistant, так и на инфраструктуру SILAM.

Эти улучшения особенно важны перед началом сезона пыления, обеспечивая своевременные обновления без избыточных обращений к источнику данных.

[![Подробнее в релизе v0.3.1](https://img.shields.io/badge/Подробнее--в--релизе-v0.3.1-blue?style=flat)](https://github.com/danishru/silam_pollen/releases/tag/v0.3.1)

## Все обновления

<a href="https://danishru.github.io/silam_pollen/site/blog" target="_blank" rel="noopener">
История релизов и архив обновлений ↗
</a>

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

![image](https://github.com/user-attachments/assets/f3bfeb55-0a36-4150-b870-39c152e9d16e)

## Использование

После установки интеграции в Home Assistant создается служба с именем `SILAM Pollen - {Название зоны}`. В описании службы указываются координаты местоположения наблюдения и версия используемого набора данных.

![image](https://github.com/user-attachments/assets/e977c402-02da-4c06-bc0a-2282571047cb)

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

![image](https://github.com/user-attachments/assets/7aebe965-5810-4059-bb8d-2266dd89bb99)

Эти данные доступны через стандартный сервис `weather.get_forecasts`.

![image](https://github.com/user-attachments/assets/5c88e639-f72f-4b4e-b55d-d5035dc77d34)

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

**Время запроса (`fetch_duration`)** — сенсор, по умолчанию выключённый, показывающий общее время обновления данных (API-запрос, парсинг, расчёты).  

**Горизонт прогноза (`forecast_horizon`)** — сенсор, по умолчанию выключённый, показывающий фактический горизонт прогноза в часах (разница между меткой «сейчас» и последней точкой прогноза). Атрибут **`forecast_duration`** отображает **желаемую** длительность прогноза в часах, заданную в настройках интеграции.


|  ![image](https://github.com/user-attachments/assets/5602ed60-edfa-4037-8193-b96962d839cd) | ![image](https://github.com/user-attachments/assets/bfab36ea-d82d-41b1-b8ae-d3e1671e72c1)  | ![image](https://github.com/user-attachments/assets/d50ad92f-e330-4e65-8cb6-c6de65ceae7d) |
| ------------- | ------------- | ------------- |

## Панель

### Встроенная карточка (рекомендуется)

Начиная с версии **v0.3.0**, **SILAM Pollen** включает встроенную Lovelace-карточку —  
**Absolute Forecast Card** (локальная сборка), разработанную в рамках проекта.

Карточка предоставляет компактный, наглядный обзор **погоды и пыльцы** в одном элементе дашборда.

![image](https://github.com/user-attachments/assets/098a43aa-d35b-46a6-a5e1-73017888b635)

**Ключевые возможности:**
- Выделенный **слой аллергенов** с концентрациями пыльцы SILAM (ключевая функция)
- Индивидуальные линии прогноза для каждого аллергена с **подсветкой пиков** и **индикаторами тренда**
- Интегрированный прогноз **пыльцы и полной метеоинформации** в единой временной шкале
- Несколько режимов отображения прогноза (**Standard / Focus / Minimal**) с настраиваемыми макетами
- Полная интерактивность: действия по нажатию / удержанию / двойному нажатию на элементы прогноза
- Локальная, автономная карточка — **без CDN**, полностью работает офлайн

> [!IMPORTANT]  
> Чтобы использовать встроенную карточку, необходимо вручную добавить JavaScript-модуль:
> 
> [![Открыть Home Assistant и перейти к ресурсам дашборда](https://my.home-assistant.io/badges/lovelace_resources.svg)](https://my.home-assistant.io/redirect/lovelace_resources/)  
> **Настройки → Дашборды → Ресурсы → Добавить** → URL: `/local/absolute-forecast-card.js` → **Тип ресурса: JavaScript Module**.

➡️ Подробное описание, скриншоты и список изменений:  
**SILAM Pollen v0.3.0 — Release Notes**  
https://github.com/danishru/silam_pollen/releases/tag/v0.3.0


### Сторонняя карточка (опционально)

Сущности SILAM Pollen также можно использовать с карточками сообщества.

Один из таких вариантов — **pollenprognos-card**, поддерживающий сущности SILAM Pollen и доступный через **HACS**.

- Репозиторий: https://github.com/krissen/pollenprognos-card

Для установки нажмите **Download** в меню карточки:

[![HACS Repository Badge](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=krissen&repository=pollenprognos-card)

Большое спасибо [@krissen](https://github.com/krissen) за поддержку SILAM Pollen!
 
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
