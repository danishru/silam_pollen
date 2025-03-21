[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Downloads][download-shield]][Downloads]
[![License][license-shield]][license]
[![HACS Custom][hacsbadge]][hacs]

# SILAM Pollen Allergy Sensor for Home Assistant

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
> Обратите внимание, что охват территории ограничен и может не включать все регионы. Для подробного просмотра территории и оценки покрытия воспользуйтесь интерактивной картой ниже.

[![Интерактивная карта покрытия с данными по уровню пыльцы](https://danishru.github.io/silam_pollen/pollen_area.webp)](https://danishru.github.io/silam_pollen/)

## Установка

### Ручная установка

1. Скопируйте папку `silam_pollen` в каталог `custom_components` вашей конфигурации Home Assistant.
2. Перезапустите Home Assistant.
3. Добавьте интеграцию через веб-интерфейс:
   - Перейдите в **Настройки → Интеграции**.
   - Нажмите **Добавить интеграцию** и выберите **SILAM Pollen**.
   - Заполните необходимые поля (например, имя, координаты, высоту, выбор типа пыльцы, интервал опроса).

### Установка через HACS

**Убедитесь, что HACS установлен:**  
Если HACS ещё не установлен, следуйте [официальной инструкции по установке HACS](https://hacs.xyz/docs/use/).

#### Установка одним кликом

Для установки интеграции **SILAM Pollen** перейдите по ссылке ниже:  

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danishru&repository=silam_pollen&category=integration)

#### Обычная установка через HACS

1. **Откройте Home Assistant и перейдите в HACS:**  
   На боковой панели найдите и нажмите на значок HACS.
2. **Добавление пользовательского репозитория:**  
   - В HACS перейдите на вкладку **Интеграции**.
   - Нажмите кнопку **Добавить пользовательский репозиторий** (Custom Repositories).
   - В появившемся окне введите URL репозитория:  
     `https://github.com/danishru/silam_pollen`  
   - Выберите тип репозитория **Integration**.
   - Нажмите **Добавить**.
3. **Установка интеграции:**  
   - После добавления репозитория HACS автоматически обнаружит релиз вашей интеграции.
   - В разделе **Интеграции** появится интеграция с именем **SILAM Pollen**.
   - Найдите её и нажмите **Установить**.
   - Дождитесь завершения установки.

Теперь ваша интеграция установлена и готова к использованию через HACS!

## Конфигурация

Перейдите по ссылке ниже и следуйте инструкциям мастера настройки **SILAM Pollen**:  

[![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=silam_pollen)

Или откройте **Настройки → Интеграции** в Home Assistant, найдите `SILAM Pollen` и следуйте инструкциям мастера настройки.

Здесь вы сможете задать параметры для корректной работы интеграции:

- **Зона наблюдения** – позволяет выбрать настроенную зону в вашем Home Assistant. По умолчанию выбирается зона `"Home"`.
- **Тип пыльцы** – выбор наблюдаемой пыльцы. Можно не выбирать ни один тип или выбрать несколько из списка.
- **Интервал обновления** – интервал загрузки данных с сервера SILAM Thredds server в минутах (по умолчанию 60, минимальное значение — 30 минут).
- **Название зоны** – по умолчанию используется название из выбранной зоны. Это имя используется для формирования названий служб и сенсоров. Параметр можно переопределить.
- **Высота над уровнем моря** – высота над уровнем моря, используемая для выборки данных об уровне пыльцы из набора данных. Если выбрана зона `"Home"`, данные берутся из общих настроек (`config/general`); в ином случае по умолчанию устанавливается значение 275. Параметр можно переопределить.
- **Местоположение** – отображает на карте местоположение выбранной зоны. Зону наблюдения можно изменить с помощью карты или вручную задать координаты "Широта" и "Долгота". Указанный радиус отражает примерное пространственное разрешение данных о пыльце (около 10 км).

## Использование

После установки интеграции в Home Assistant создается служба с именем `SILAM Pollen - {Название зоны}`. В описании службы указываются координаты местоположения наблюдения и версия используемого набора данных.

![image](https://github.com/user-attachments/assets/e8c3c44d-d98d-44ee-85c7-bac838df7094)


В рамках службы создается сенсор **Индекс пыльцы**, состояние которого отображает локализованное значение, соответствующее числовому индексу, рассчитанному на основе почасовых средних значений и пороговых значений из справочной таблицы Mikhail Sofiev ([ссылка](https://www.researchgate.net/profile/Mikhail-Sofiev)). 

Возможные значения индекса:
- 1 – Очень низкий
- 2 – Низкий
- 3 – Средний
- 4 – Высокий
- 5 – Очень высокий
- Если значение не соответствует ни одному из указанных уровней, отображается «Неизвестно».

Дополнительно в атрибуты сенсора записываются дата прогноза и основной аллерген, оказывающий существенное влияние на формирование индекса.

Если выбран тип пыльцы, то для каждого выбранного типа создается отдельный сенсор, отображающий округленное до целого число, представляющее смоделированное количество пыльцы (единиц на кубический метр). В атрибутах таких сенсоров также указывается ближайшая доступная высота над уровнем моря, которая использовалась для выборки данных.

|  ![image](https://github.com/user-attachments/assets/b5d990c6-3d0b-4dcb-a191-7c15a77fe8f7) | ![image](https://github.com/user-attachments/assets/aacafdae-07c3-48ce-8aa3-f31e3e9932a6)  |
| ------------- | ------------- |

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

## Лицензия

[MIT License](LICENSE)

## Поддержка

Если возникнут вопросы или проблемы, создайте issue в [репозитории](https://github.com/danishru/silam_pollen/issues).

<!-- Определения ссылок для бейджей -->
[releases-shield]: https://img.shields.io/github/release/danishru/silam_pollen.svg?style=for-the-badge
[releases]: https://github.com/danishru/silam_pollen/releases
[commits-shield]: https://img.shields.io/github/commit-activity/m/danishru/silam_pollen.svg?style=for-the-badge
[commits]: https://github.com/danishru/silam_pollen/commits
[download-shield]: https://img.shields.io/github/downloads/danishru/silam_pollen/total.svg?style=for-the-badge
[downloads]: https://github.com/danishru/silam_pollen/releases
[license-shield]: https://img.shields.io/github/license/danishru/silam_pollen.svg?style=for-the-badge
[license]: https://github.com/danishru/silam_pollen/blob/master/LICENSE
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs]: https://hacs.xyz/
