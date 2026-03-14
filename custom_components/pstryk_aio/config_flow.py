"""Przepływ konfiguracji dla integracji Pstryk AIO (uwierzytelnianie Kluczem API)."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY 
from homeassistant.core import HomeAssistant, callback 
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util 
from datetime import timedelta 


from .api import PstrykApiClientApiKey, PstrykAuthError, PstrykApiError 
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_CHEAP_PURCHASE_PRICE_THRESHOLD,
    CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD,
    CONF_CHEAP_SALE_PRICE_THRESHOLD,
    CONF_EXPENSIVE_SALE_PRICE_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD,
    DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD,
    DEFAULT_CHEAP_SALE_PRICE_THRESHOLD,
    DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)

async def async_migrate_entry(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Migruje stary wpis konfiguracyjny."""
    _LOGGER.debug(f"Sprawdzanie migracji dla wpisu Pstryk AIO v{config_entry.version}")
    if config_entry.version < 7: 
        _LOGGER.warning(
            "Wykryto konfigurację Pstryk AIO w wersji %s, która wymaga ponownej konfiguracji "
            "w celu zastosowania nowego schematu nazewnictwa encji. "
            "Proszę usunąć istniejącą integrację Pstryk AIO i dodać ją ponownie, "
            "używając Klucza API.",
            config_entry.version,
        )
        return False 
    return True


class PstrykConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obsługuje przepływ konfiguracji Pstryk AIO z Kluczem API."""

    VERSION = 7 # Zwiększona wersja dla zmian w nazewnictwie
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Inicjalizacja przepływu konfiguracji."""
        super().__init__()
        self._flow_data: Dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return PstrykOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Obsługuje krok inicjowany przez użytkownika (wprowadzenie Klucza API)."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            
            unique_id_suffix = api_key[-8:] if len(api_key) > 8 else api_key
            await self.async_set_unique_id(unique_id_suffix) 
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api_client = PstrykApiClientApiKey(api_key=api_key, session=session)

            try:
                authenticated = await api_client.test_authentication()
                if authenticated:
                    entry_title = DEFAULT_NAME # Domyślny tytuł "Pstryk AIO"
                    try:
                        now = dt_util.utcnow()
                        start_time = now - timedelta(days=1)
                        usage_data = await api_client.get_integrations_meter_data_usage(
                            resolution="day", window_start=start_time, window_end=now
                        )
                        _LOGGER.debug(f"Odpowiedź z unified-metrics (meter_values) podczas config_flow: {str(usage_data)[:1000]}")

                        if usage_data and isinstance(usage_data, dict):
                            name_from_api = usage_data.get("name") 
                            if name_from_api and isinstance(name_from_api, str) and name_from_api.strip():
                                entry_title = f"{DEFAULT_NAME} {name_from_api.strip()}"
                                _LOGGER.info(f"Pomyślnie pobrano nazwę licznika dla tytułu wpisu: {name_from_api}")
                            else:
                                _LOGGER.debug("Klucz 'name' nie znaleziony lub pusty w odpowiedzi z unified-metrics. Używam domyślnego tytułu.")
                        else:
                            _LOGGER.debug("Brak danych lub nieprawidłowy format odpowiedzi z unified-metrics. Używam domyślnego tytułu.")
                    except Exception as e:
                        _LOGGER.warning(
                            f"Nie udało się pobrać/przetworzyć nazwy licznika dla tytułu wpisu, używam domyślnego. Błąd: {e}"
                        )
                    
                    _LOGGER.debug(f"Ustawiono tytuł wpisu konfiguracyjnego na: {entry_title}")
                    
                    self._flow_data = {
                        CONF_API_KEY: api_key,
                        "title": entry_title
                    }
                    return await self.async_step_options()
                else:
                    _LOGGER.warning("Test autoryzacji Kluczem API zwrócił False. Sprawdź logi klienta API.")
                    errors["base"] = "auth_test_failed" 
            except PstrykAuthError as e: 
                _LOGGER.warning(f"Błąd autoryzacji podczas konfiguracji (Klucz API): {e}")
                errors["base"] = "invalid_api_key" 
            except PstrykApiError as e:
                _LOGGER.exception(f"Błąd API podczas testowania Klucza API: {e}")
                errors["base"] = "cannot_connect"
            except Exception as e: 
                _LOGGER.exception(f"Nieoczekiwany błąd podczas testowania Klucza API: {e}")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors,
            description_placeholders={
                "api_key_url": "https://pstryk.pl/panel/ustawienia/api/", 
                "auth_method_info": "Integracja użyje podanego Klucza API do uwierzytelnienia (wysyłany bezpośrednio w nagłówku 'Authorization: {klucz_api}')."
            }
        )

    async def async_step_options(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Obsługuje krok opcji podczas początkowej konfiguracji."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            cheap_purchase = user_input.get(CONF_CHEAP_PURCHASE_PRICE_THRESHOLD)
            expensive_purchase = user_input.get(CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD)
            if cheap_purchase is not None and expensive_purchase is not None and \
               expensive_purchase <= cheap_purchase:
                errors["base"] = "invalid_purchase_thresholds"
            
            cheap_sale = user_input.get(CONF_CHEAP_SALE_PRICE_THRESHOLD)
            expensive_sale = user_input.get(CONF_EXPENSIVE_SALE_PRICE_THRESHOLD)
            if cheap_sale is not None and expensive_sale is not None and \
               expensive_sale <= cheap_sale:
                if "base" not in errors:
                    errors["base"] = "invalid_sale_thresholds"
                else:
                    _LOGGER.debug("Multiple threshold errors, reporting first one: invalid_purchase_thresholds")
            if not errors:
                return self.async_create_entry(
                    title=self._flow_data["title"], 
                    data={CONF_API_KEY: self._flow_data[CONF_API_KEY]}, 
                    options=user_input
                )

        # Show the form for the first time
        options_schema_dict = {
            vol.Optional(
                CONF_CHEAP_PURCHASE_PRICE_THRESHOLD, 
                default=DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD
            ): vol.Coerce(float),
            vol.Optional(
                CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD, 
                default=DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD
            ): vol.Coerce(float),
            vol.Optional(
                CONF_CHEAP_SALE_PRICE_THRESHOLD, 
                default=DEFAULT_CHEAP_SALE_PRICE_THRESHOLD
            ): vol.Coerce(float),
            vol.Optional(
                CONF_EXPENSIVE_SALE_PRICE_THRESHOLD, 
                default=DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD
            ): vol.Coerce(float),
            vol.Optional(
                "update_interval", 
                default=DEFAULT_UPDATE_INTERVAL_MINUTES
            ): vol.Coerce(int)
        }
        if user_input:
            options_schema_dict = {
                key: vol.Optional(key, default=user_input.get(key, default_val.default))
                for key, default_val in options_schema_dict.items()
            }

        return self.async_show_form(
            step_id="options", data_schema=vol.Schema(options_schema_dict), errors=errors
        )

class PstrykOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Inicjalizacja przepływu opcji."""

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        errors: Dict[str, str] = {}
        if user_input is not None:
            cheap_purchase = user_input.get(CONF_CHEAP_PURCHASE_PRICE_THRESHOLD)
            expensive_purchase = user_input.get(CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD)
            if cheap_purchase is not None and expensive_purchase is not None and \
               expensive_purchase <= cheap_purchase:
                errors["base"] = "invalid_purchase_thresholds"
            else:
                cheap_sale = user_input.get(CONF_CHEAP_SALE_PRICE_THRESHOLD)
                expensive_sale = user_input.get(CONF_EXPENSIVE_SALE_PRICE_THRESHOLD)
                if cheap_sale is not None and expensive_sale is not None and \
                   expensive_sale <= cheap_sale:
                    errors["base"] = "invalid_sale_thresholds"
            
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current_options = self.config_entry.options
        options_schema_dict = {
            vol.Optional(
                CONF_CHEAP_PURCHASE_PRICE_THRESHOLD, 
                default=current_options.get(CONF_CHEAP_PURCHASE_PRICE_THRESHOLD, DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD)
            ): vol.Coerce(float),
            vol.Optional(
                CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD, 
                default=current_options.get(CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD, DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD)
            ): vol.Coerce(float),
            vol.Optional(
                CONF_CHEAP_SALE_PRICE_THRESHOLD, 
                default=current_options.get(CONF_CHEAP_SALE_PRICE_THRESHOLD, DEFAULT_CHEAP_SALE_PRICE_THRESHOLD)
            ): vol.Coerce(float),
            vol.Optional(
                CONF_EXPENSIVE_SALE_PRICE_THRESHOLD, 
                default=current_options.get(CONF_EXPENSIVE_SALE_PRICE_THRESHOLD, DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD)
            ): vol.Coerce(float),
            vol.Optional(
                "update_interval", 
                default=current_options.get("update_interval", DEFAULT_UPDATE_INTERVAL_MINUTES)
            ): vol.Coerce(int)
        }
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema_dict), errors=errors
        )
