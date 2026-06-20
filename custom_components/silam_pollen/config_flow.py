import asyncio
import collections
import voluptuous as vol
import aiohttp
import async_timeout
import xml.etree.ElementTree as ET
import logging
import ssl

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
)

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_ALTITUDE,
    COVERAGE_MAP_URL,
    THREDDS_CATALOG_NS,
    THREDDS_ROOT_CATALOG_NAME,
    THREDDS_ROOT_CATALOG_TIMEOUT_SECONDS,
    THREDDS_ROOT_CATALOG_URL,
    THREDDS_ROOT_CATALOG_WAIT_SECONDS,
    # dataset table
    DATASETS,
    dataset_base_url,
    iter_datasets_for_probe,
)

_LOGGER = logging.getLogger(__name__)


class SilamPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Конфигурационный мастер для интеграции SILAM Pollen с двумя шагами.

    Шаг 1: Пользователь выбирает базовые параметры – зону наблюдения, типы пыльцы (опционально)
           и интервал обновления.
    Шаг 2: Отображаются координаты выбранной зоны и предлагается ввести (или исправить)
           название зоны и координаты через селектор местоположения.
           Итоговое имя интеграции формируется как "SILAM Pollen - {zone_name}".
    """
    VERSION = 3
    MINOR_VERSION = 5

    @staticmethod
    def _new_catalog_check_result(
        *,
        completed: bool = True,
        error: str | None = None,
    ) -> dict:
        """Создать пустой результат проверки каталога SILAM."""
        return {
            "completed": completed,
            "http_ok": False,
            "http_status": None,
            "ssl_ok": None,
            "catalog_name_ok": None,
            "catalog_name": None,
            "pollen_catalogs_ok": None,
            "pollen_catalogs": None,
            "error": error,
        }

    def _ensure_catalog_check_task(self) -> None:
        """Запустить фоновую проверку корневого каталога SILAM один раз."""
        if getattr(self, "_catalog_check_task", None) is None:
            self._catalog_check_task = self.hass.async_create_task(
                self._async_check_root_catalog()
            )

    async def _async_check_root_catalog(self) -> dict:
        """Проверить HTTP, SSL, имя корневого каталога и pollen-каталоги."""
        result = self._new_catalog_check_result()
        session = async_get_clientsession(self.hass)

        try:
            async with async_timeout.timeout(THREDDS_ROOT_CATALOG_TIMEOUT_SECONDS):
                async with session.get(THREDDS_ROOT_CATALOG_URL) as response:
                    # Полученный HTTPS-ответ означает, что стандартная SSL-проверка
                    # общей aiohttp-сессии Home Assistant успешно пройдена.
                    result["ssl_ok"] = True
                    result["http_status"] = response.status
                    result["http_ok"] = response.status == 200

                    if response.status != 200:
                        result["error"] = "http_error"
                        return result

                    text = await response.text()

        except (
            aiohttp.ClientConnectorCertificateError,
            aiohttp.ClientConnectorSSLError,
            ssl.CertificateError,
            ssl.SSLError,
        ) as err:
            result["ssl_ok"] = False
            result["error"] = "ssl_error"
            _LOGGER.debug("SILAM catalog SSL check failed: %s", err)
            return result
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            result["error"] = "connection_error"
            _LOGGER.debug("SILAM catalog availability check failed: %s", err)
            return result
        except Exception as err:
            result["error"] = "unknown_error"
            _LOGGER.debug("Unexpected SILAM catalog check error: %s", err)
            return result

        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            result["error"] = "invalid_xml"
            _LOGGER.debug("SILAM root catalog returned invalid XML: %s", err)
            return result

        catalog_name = root.attrib.get("name")
        result["catalog_name"] = catalog_name
        result["catalog_name_ok"] = catalog_name == THREDDS_ROOT_CATALOG_NAME

        pollen_catalogs = sorted(
            {
                catalog_ref.attrib.get("name", "")
                for catalog_ref in root.findall(".//t:catalogRef", THREDDS_CATALOG_NS)
                if "pollen" in catalog_ref.attrib.get("name", "").lower()
            }
        )
        result["pollen_catalogs"] = pollen_catalogs
        result["pollen_catalogs_ok"] = bool(pollen_catalogs)

        return result

    async def _async_wait_catalog_check(self) -> dict:
        """Дождаться фоновой проверки, но не более четырёх секунд."""
        self._ensure_catalog_check_task()
        task = self._catalog_check_task

        if task.cancelled():
            return self._new_catalog_check_result(
                completed=False,
                error="timeout",
            )

        try:
            return await asyncio.wait_for(
                task,
                timeout=THREDDS_ROOT_CATALOG_WAIT_SECONDS,
            )
        except asyncio.TimeoutError:
            _LOGGER.debug(
                "SILAM catalog check did not finish within %s seconds",
                THREDDS_ROOT_CATALOG_WAIT_SECONDS,
            )
            return self._new_catalog_check_result(
                completed=False,
                error="timeout",
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.debug("SILAM catalog task failed while waiting: %s", err)
            return self._new_catalog_check_result(error="unknown_error")

    @staticmethod
    def _catalog_check_is_ok(result: dict) -> bool:
        """Вернуть True, только если успешно пройдены все проверки каталога."""
        return all(
            result.get(key) is True
            for key in (
                "http_ok",
                "ssl_ok",
                "catalog_name_ok",
                "pollen_catalogs_ok",
            )
        )

    @staticmethod
    def _catalog_check_error_key(result: dict) -> str | None:
        """Вернуть локализованный ключ ошибки проверки SILAM."""
        if SilamPollenConfigFlow._catalog_check_is_ok(result):
            return None

        error = result.get("error")

        if error == "ssl_error" or result.get("ssl_ok") is False:
            return "silam_ssl_error"

        if error in ("connection_error", "http_error"):
            return "silam_connection_error"

        if (
            error == "invalid_xml"
            or result.get("catalog_name_ok") is False
            or result.get("pollen_catalogs_ok") is False
        ):
            return "silam_catalog_error"

        return "silam_check_unconfirmed"

    @staticmethod
    def _log_catalog_check_result(result: dict) -> None:
        """Записать подробный результат проверки только в DEBUG-лог."""
        _LOGGER.debug(
            "SILAM catalog check: completed=%s http_ok=%s http_status=%s "
            "ssl_ok=%s catalog_name_ok=%s catalog_name=%s "
            "pollen_catalogs_ok=%s pollen_catalogs=%s error=%s",
            result.get("completed"),
            result.get("http_ok"),
            result.get("http_status"),
            result.get("ssl_ok"),
            result.get("catalog_name_ok"),
            result.get("catalog_name"),
            result.get("pollen_catalogs_ok"),
            result.get("pollen_catalogs"),
            result.get("error"),
        )

    @staticmethod
    def _iter_probe_datasets_fallback() -> tuple[str, ...]:
        """Fallback-порядок для probe, если iter_datasets_for_probe() вдруг пуст."""
        # 1) пробуем все датасеты с probe_priority (в порядке приоритета)
        items = [(name, meta) for name, meta in DATASETS.items() if meta.probe_priority is not None]
        items.sort(key=lambda x: x[1].probe_priority)
        if items:
            return tuple(name for name, _ in items)

        # 2) иначе пробуем хотя бы "основной" (Europe v6.1), если он есть
        if "silam_europe_pollen_v6_1" in DATASETS:
            return ("silam_europe_pollen_v6_1",)

        # 3) иначе любой первый датасет (чтобы не упасть)
        for name in DATASETS.keys():
            return (name,)

        return tuple()

    async def async_step_user(self, user_input=None):
        """Шаг 1: базовые параметры (без координат)."""
        zones = {
            state.entity_id: state.attributes.get("friendly_name", state.entity_id)
            for state in self.hass.states.async_all()
            if state.entity_id.startswith("zone.")
        }
        if not zones:
            zones = {"zone.home": "Home"}
        default_zone = "zone.home" if "zone.home" in zones else list(zones.keys())[0]
        default_altitude = getattr(self.hass.config, "elevation", DEFAULT_ALTITUDE)

        # Создаем список опций из словаря zones
        zone_options = [{"value": zone_id, "label": name} for zone_id, name in zones.items()]

        data_schema = vol.Schema({
            vol.Required("zone_id", default=default_zone): SelectSelector(
                SelectSelectorConfig(
                    options=zone_options,
                    multiple=False,
                    mode="dropdown"
                )
            ),
            # vol.Required("altitude", default=default_altitude): vol.Coerce(float),
            vol.Optional("var", default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "alder_m22",
                        "birch_m22",
                        "grass_m32",
                        "hazel_m23",
                        "mugwort_m18",
                        "olive_m28",
                        "ragweed_m18"
                    ],
                    multiple=True,
                    mode="dropdown",
                    translation_key="config_pollen"
                )
            ),
            vol.Required("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=30)),
            vol.Optional("forecast", default=False): bool,
            vol.Optional("forecast_duration", default=36): NumberSelector(
                NumberSelectorConfig(
                    min=36,
                    max=120,
                    step=1,
                    mode="slider",
                    unit_of_measurement="h",
                )
            ),  # Длительность прогноза в часах (36–120), по умолчанию 36
        })

        if user_input is None:
            # Проверка стартует сразу при открытии первого шага и выполняется
            # параллельно с заполнением формы пользователем.
            self._ensure_catalog_check_task()
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema
            )

        # Если фоновая проверка ещё не завершилась, ждём не более 4 секунд.
        catalog_result = await self._async_wait_catalog_check()
        self.context["catalog_check_result"] = catalog_result
        self._log_catalog_check_result(catalog_result)

        # Сохраняем данные первого шага в context
        self.context["base_data"] = user_input.copy()
        self.context["zone_id"] = user_input.get("zone_id")

        service_error = self._catalog_check_error_key(catalog_result)
        self.context["catalog_check_error"] = service_error

        step_id = "manual_coords" if service_error is None else "manual_coords_warning"
        return await self._async_step_manual_coords(
            None,
            step_id=step_id,
            service_error=service_error,
        )

    async def async_step_manual_coords(self, user_input=None):
        """Шаг 2: ввод координат при доступной службе SILAM."""
        return await self._async_step_manual_coords(
            user_input,
            step_id="manual_coords",
        )

    async def async_step_manual_coords_warning(self, user_input=None):
        """Шаг 2: ввод координат, когда доступность SILAM не подтверждена."""
        return await self._async_step_manual_coords(
            user_input,
            step_id="manual_coords_warning",
            service_error=self.context.get("catalog_check_error"),
        )

    async def _async_step_manual_coords(
        self,
        user_input,
        *,
        step_id: str,
        service_error: str | None = None,
    ):
        """Общая реализация шага ввода координат."""
        if user_input is None:
            zone_id = self.context.get("zone_id", "zone.home")
            zone = self.hass.states.get(zone_id)
            if zone is not None:
                default_latitude = zone.attributes.get("latitude", self.hass.config.latitude)
                default_longitude = zone.attributes.get("longitude", self.hass.config.longitude)
                default_zone_name = zone.attributes.get("friendly_name", "Home")
            else:
                default_latitude = self.hass.config.latitude
                default_longitude = self.hass.config.longitude
                default_zone_name = "Home"

            # Если выбрана зона "zone.home", берем высоту из hass.config.elevation,
            # иначе используем DEFAULT_ALTITUDE из const.py.
            if zone_id == "zone.home":
                default_altitude = getattr(self.hass.config, "elevation", DEFAULT_ALTITUDE)
            else:
                default_altitude = DEFAULT_ALTITUDE

            schema_fields = collections.OrderedDict()
            schema_fields[vol.Optional("zone_name", default=default_zone_name)] = str
            schema_fields[vol.Required("altitude", default=default_altitude)] = vol.Coerce(float)
            schema_fields[vol.Required("location", default={
                "latitude": default_latitude,
                "longitude": default_longitude,
                "radius": 5000,
            })] = LocationSelector(LocationSelectorConfig(radius=True))

            data_schema = vol.Schema(schema_fields)
            return self.async_show_form(
                step_id=step_id,
                data_schema=data_schema,
                errors={"base": service_error} if service_error else {},
                description_placeholders={
                    "altitude": "Altitude above sea level",
                    "coverage_url": COVERAGE_MAP_URL,
                },
            )

        # Обработка введённых данных
        location = user_input.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        altitude_input = user_input.get("altitude")
        if altitude_input in (None, ""):
            altitude_input = getattr(self.hass.config, "elevation", DEFAULT_ALTITUDE)

        base_data = self.context.get("base_data", {})
        base_data["latitude"] = latitude
        base_data["longitude"] = longitude
        base_data["altitude"] = altitude_input
        base_data["zone_name"] = user_input.get("zone_name")
        base_data["manual_coordinates"] = True
        base_data["title"] = "SILAM Pollen - {zone_name}".format(zone_name=base_data["zone_name"])

        # Сохранение параметров прогноза из первого шага
        base_data["forecast"] = self.context.get("base_data", {}).get("forecast", False)
        base_data["forecast_duration"] = self.context.get("base_data", {}).get("forecast_duration", 36)

        # Добавляем уникальный идентификатор на основе координат.
        unique_id = f"{latitude}_{longitude}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Выполняем тестовый запрос к API с использованием введённых координат.
        # Метод _test_api возвращает True, None и выбранный URL (chosen_url) при успешном ответе.
        valid, error, chosen_url = await self._test_api(latitude, longitude)
        if not valid:
            errors = {"base": error}
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema({
                    vol.Optional("zone_name", default=base_data["zone_name"]): str,
                    vol.Required("altitude", default=altitude_input): vol.Coerce(float),
                    vol.Required("location", default={
                        "latitude": latitude,
                        "longitude": longitude,
                        "radius": 5000,
                    }): LocationSelector(LocationSelectorConfig(radius=True)),
                }),
                errors=errors,
                description_placeholders={
                    "altitude": "Altitude above sea level",
                    "coverage_url": COVERAGE_MAP_URL,
                },
            )

        # Сохраняем выбранный базовый URL в конфигурационных данных.
        base_data["base_url"] = chosen_url

        # Политика выбора набора данных:
        # По умолчанию для новых записей используем SMART — далее интеграция сможет
        # пере-выбирать лучший набор данных при обновлениях и (в будущем) догружать
        # недостающие данные из других наборов.
        #
        # При этом base_url мы сохраняем уже сейчас (chosen_url), чтобы сервис начал
        # работать сразу после создания записи.
        base_data["version"] = "smart"

        return self.async_create_entry(title=base_data["title"], data=base_data)

    async def _test_api(self, latitude, longitude):
        """
        Проверка доступности API с использованием введённых координат.
        Порядок берём из iter_datasets_for_probe() (const.py).

        Возвращает локализованный ключ ошибки вместо сырого ответа SILAM:
        - silam_location_unavailable: все ответившие датасеты вернули HTTP 400;
        - silam_location_check_failed: сетевая, серверная или неизвестная ошибка.
        """
        dataset_names = iter_datasets_for_probe()
        if not dataset_names:
            dataset_names = self._iter_probe_datasets_fallback()

        urls = []
        for dataset_name in dataset_names:
            try:
                urls.append(dataset_base_url(dataset_name))
            except Exception:
                continue

        saw_location_error = False
        saw_service_error = False

        for url in urls:
            test_url = url + f"?var=POLI&latitude={latitude}&longitude={longitude}&time=present&accept=xml"
            try:
                async with aiohttp.ClientSession() as session:
                    async with async_timeout.timeout(10):
                        async with session.get(test_url) as response:
                            response_text = await response.text()

                            if response.status == 200:
                                return True, None, url

                            if response.status == 400:
                                saw_location_error = True
                            else:
                                saw_service_error = True

                            _LOGGER.debug(
                                "Location probe returned HTTP %s from %s: %s",
                                response.status,
                                url,
                                response_text,
                            )
            except Exception as err:
                saw_service_error = True
                _LOGGER.debug("Location probe exception when requesting %s: %s", url, err)

        # Если хотя бы один запрос завершился сетевой/серверной ошибкой,
        # нельзя достоверно считать местоположение находящимся вне зоны покрытия.
        if saw_service_error:
            return False, "silam_location_check_failed", None

        if saw_location_error:
            return False, "silam_location_unavailable", None

        return False, "silam_location_check_failed", None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Возвращает обработчик Options Flow для этой записи."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Обработчик Options Flow для интеграции SILAM Pollen."""

    # ---------------------------------------------------------------------
    # Helpers для SMART + UI (табличная логика)
    # ---------------------------------------------------------------------
    @staticmethod
    def _dataset_name_from_base_url(base_url: str | None) -> str | None:
        """Пытается определить dataset_name по base_url через DATASETS."""
        if not base_url:
            return None
        for dataset_name, meta in DATASETS.items():
            if meta.path and meta.path in base_url:
                return dataset_name
        return None

    @staticmethod
    def _normalize_version_key(version: str | None) -> str | None:
        """Нормализует version:
        - 'smart' -> 'smart'
        - legacy ('v6_1', 'v6_0', 'v5_9_1', 'v6_1_fi') -> новый src-ключ ('sep61'...)
        - уже новый src-ключ -> как есть
        """
        if not version:
            return None
        if version == "smart":
            return "smart"

        # уже новый формат (src)
        for dataset_name, meta in DATASETS.items():
            if meta.src == version:
                return version

        # legacy значения (поддерживаем старые записи)
        legacy_map = {
            "v6_1_fi": DATASETS["silam_hires_pollen_v6_1"].src,
            "v5_9_1":  DATASETS["silam_regional_pollen_v5_9_1"].src,
            "v6_1":    DATASETS["silam_europe_pollen_v6_1"].src,
            "v6_0":    DATASETS["silam_europe_pollen_v6_0"].src,
        }
        return legacy_map.get(version)

    @staticmethod
    def _effective_dataset_label(base_url: str | None) -> str:
        """Человекочитаемое имя датасета по текущему base_url (для UI/описаний)."""
        if not base_url:
            return "unknown"
        dataset_name = OptionsFlowHandler._dataset_name_from_base_url(base_url)
        if dataset_name and dataset_name in DATASETS:
            return DATASETS[dataset_name].label or "unknown"
        return "unknown"

    @staticmethod
    def _iter_probe_datasets_fallback() -> tuple[str, ...]:
        """Fallback-порядок для SMART/probe, если iter_datasets_for_probe() вдруг пуст."""
        items = [(name, meta) for name, meta in DATASETS.items() if meta.probe_priority is not None]
        items.sort(key=lambda x: x[1].probe_priority)
        if items:
            return tuple(name for name, _ in items)

        if "silam_europe_pollen_v6_1" in DATASETS:
            return ("silam_europe_pollen_v6_1",)

        for name in DATASETS.keys():
            return (name,)

        return tuple()

    async def _probe_best_base_url(self, latitude, longitude) -> str | None:
        """SMART: подбор лучшего base_url по координатам."""
        if latitude is None or longitude is None:
            return None

        dataset_names = iter_datasets_for_probe()
        if not dataset_names:
            dataset_names = self._iter_probe_datasets_fallback()

        urls = []
        for dataset_name in dataset_names:
            try:
                urls.append(dataset_base_url(dataset_name))
            except Exception:
                continue

        async with aiohttp.ClientSession() as session:
            for url in urls:
                test_url = url + f"?var=POLI&latitude={latitude}&longitude={longitude}&time=present&accept=xml"
                try:
                    async with async_timeout.timeout(10):
                        async with session.get(test_url) as response:
                            if response.status == 200:
                                return url
                except Exception as err:
                    _LOGGER.debug("SMART probe exception when requesting %s: %s", url, str(err))

        return None

    async def _is_dataset_available(self, session: aiohttp.ClientSession, latitude, longitude, dataset_name: str) -> bool:
        """Проверяет доступность датасета по координатам (для UI-опций)."""
        if latitude is None or longitude is None:
            return False

        try:
            base_url = dataset_base_url(dataset_name)
        except Exception:
            return False

        test_url = base_url + f"?var=POLI&latitude={latitude}&longitude={longitude}&time=present&accept=xml"
        try:
            async with async_timeout.timeout(10):
                async with session.get(test_url) as response:
                    return response.status == 200
        except Exception as err:
            _LOGGER.debug("Availability check failed for %s (%s): %s", dataset_name, test_url, err)
            return False

    @staticmethod
    def _iter_ui_datasets_sorted() -> list[str]:
        """Возвращает dataset_name для UI в порядке ui_order (меньше = выше)."""
        items: list[tuple[int, str]] = []
        for dataset_name, meta in DATASETS.items():
            if not getattr(meta, "ui_enabled", True):
                continue
            order = meta.ui_order if meta.ui_order is not None else 10_000
            items.append((order, dataset_name))
        items.sort(key=lambda x: x[0])
        return [name for _, name in items]

    async def async_step_init(self, user_input=None):
        """Первый и единственный шаг Options Flow."""
        if user_input is not None:

            # Если пользователь выбрал forecast_daily, то автоматически устанавливаем forecast_hourly в True
            if user_input.get("forecast_daily"):
                user_input["forecast_hourly"] = True

            # Обновляем опции
            new_options = dict(self.config_entry.options)
            new_options.update(user_input)

            # гарантируем сохранение выбора version в options
            new_version_raw = user_input.get("version")
            if new_version_raw is not None:
                new_version_norm = self._normalize_version_key(new_version_raw)
                if new_version_norm is not None:
                    new_options["version"] = new_version_norm
            else:
                new_options.setdefault(
                    "version",
                    self.config_entry.options.get("version", self.config_entry.data.get("version")),
                )

            # Обновляем данные: base_url хранится в data и используется координатором
            new_data = dict(self.config_entry.data)

            new_version = self._normalize_version_key(new_options.get("version"))
            if new_version is not None:
                new_options["version"] = new_version
                new_data["version"] = new_version

            if new_version == "smart":
                # SMART: выбираем лучший доступный набор по координатам (тот же приоритет, что при создании записи).
                lat = new_data.get("latitude")
                lon = new_data.get("longitude")
                chosen_url = await self._probe_best_base_url(lat, lon)
                # Если координаты отсутствуют или probe не дал результата — не ломаем запись:
                # оставляем текущий base_url как есть.
                if chosen_url:
                    new_data["base_url"] = chosen_url
            else:
                # фиксированный датасет: new_version = src (например 'sep61')
                dataset_name = None
                for name, meta in DATASETS.items():
                    if meta.src == new_version:
                        dataset_name = name
                        break

                if dataset_name:
                    new_data["base_url"] = dataset_base_url(dataset_name)
                else:
                    _LOGGER.debug("Unknown dataset version in options: %s", new_version)

            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data, options=new_options)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data=new_options)

        # ------------------------------------------------------------
        # Форма (GET): универсально собираем version_options из DATASETS
        # ------------------------------------------------------------
        base_url = self.config_entry.data.get("base_url", "")

        lat = self.config_entry.data.get("latitude")
        lon = self.config_entry.data.get("longitude")

        # 1) Текущее значение версии (нормализуем)
        stored_version = self.config_entry.options.get("version", self.config_entry.data.get("version"))
        stored_version = self._normalize_version_key(stored_version)

        # 2) Собираем доступные варианты из DATASETS
        version_options = []
        ui_dataset_names = self._iter_ui_datasets_sorted()

        async with aiohttp.ClientSession() as session:
            for dataset_name in ui_dataset_names:
                meta = DATASETS[dataset_name]

                # если датасет нужно показывать только при доступности — проверяем
                if getattr(meta, "ui_requires_probe", False):
                    ok = await self._is_dataset_available(session, lat, lon, dataset_name)
                    if not ok:
                        continue

                label = meta.label or dataset_name
                version_options.append({"value": meta.src, "label": label})

        # smart всегда сверху
        version_options.insert(0, {"value": "smart", "label": "Smart selection (recommended)"})

        # 3) Выбираем default_version универсально
        option_values = {opt["value"] for opt in version_options}

        if stored_version in option_values:
            default_version = stored_version
        else:
            # если stored_version невалиден/недоступен — выбираем первый фиксированный (после smart)
            fixed = [opt["value"] for opt in version_options if opt["value"] != "smart"]
            if fixed:
                default_version = fixed[0]
            else:
                default_version = DATASETS["silam_europe_pollen_v6_1"].src if "silam_europe_pollen_v6_1" in DATASETS else "smart"

        data_schema = vol.Schema({
            vol.Optional(
                "var",
                default=self.config_entry.options.get("var", self.config_entry.data.get("var", []))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "alder_m22",
                        "birch_m22",
                        "grass_m32",
                        "hazel_m23",
                        "mugwort_m18",
                        "olive_m28",
                        "ragweed_m18"
                    ],
                    multiple=True,
                    mode="dropdown",
                    translation_key="config_pollen"
                )
            ),
            vol.Optional(
                "update_interval",
                default=self.config_entry.options.get(
                    "update_interval",
                    self.config_entry.data.get("update_interval", DEFAULT_UPDATE_INTERVAL)
                )
            ): vol.All(vol.Coerce(int), vol.Range(min=30)),
            vol.Optional(
                "version",
                default=default_version
            ): SelectSelector(
                SelectSelectorConfig(
                    options=version_options,
                    multiple=False,
                    mode="dropdown"
                )
            ),
            vol.Optional(
                "forecast",
                default=self.config_entry.options.get("forecast", self.config_entry.data.get("forecast", False))
            ): bool,
            vol.Optional(
                "forecast_duration",
                default=self.config_entry.options.get(
                    "forecast_duration",
                    self.config_entry.data.get("forecast_duration", 36)
                )
            ): NumberSelector(
                NumberSelectorConfig(
                    min=36,
                    max=120,
                    step=1,
                    mode="slider",
                    unit_of_measurement="h",
                )
            ),  # Длительность прогноза в часах (36–120)
            vol.Optional(
                "legacy",
                default=self.config_entry.options.get(
                    "legacy",
                    self.config_entry.data.get("legacy", False)
                )
            ): bool,
        })

        # runtime-first — если координатор уже есть, берём активный effective_base_url
        try:
            coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if coordinator:
                md = getattr(coordinator, "merged_data", None)
                if isinstance(md, dict):
                    base_url = md.get("diag", {}).get("dataset", {}).get("effective_base_url") or base_url
                else:
                    base_url = getattr(coordinator, "_base_url", base_url)
        except Exception:
            pass

        effective_dataset = self._effective_dataset_label(base_url)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={"effective_dataset": effective_dataset},
        )
