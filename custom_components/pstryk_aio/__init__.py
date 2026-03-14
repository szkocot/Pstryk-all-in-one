"""Integracja Pstryk AIO."""
import asyncio
import logging
from datetime import datetime, timedelta

from typing import Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY 
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PstrykApiClientApiKey, PstrykApiError, PstrykAuthError 
from .const import (
    DOMAIN,
    PLATFORMS,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    COORDINATOR_KEY_MAIN,
    KEY_METER_DATA_USAGE,
    KEY_METER_DATA_COST,
    KEY_PRICING_DATA_PURCHASE_TODAY,
    KEY_PRICING_DATA_PURCHASE_TOMORROW,
    KEY_PRICING_DATA_PROSUMER_TODAY,
    KEY_PRICING_DATA_PROSUMER_TOMORROW,
    KEY_LAST_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Konfiguruje Pstryk AIO z wpisu konfiguracyjnego (Klucz API)."""
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug(f"Rozpoczynanie konfiguracji wpisu dla {entry.title} z Kluczem API.")

    api_key = entry.data[CONF_API_KEY]

    session = async_get_clientsession(hass)
    api_client = PstrykApiClientApiKey(api_key=api_key, session=session) 

    async def async_update_data():
        """Pobiera najnowsze dane z API Pstryk przy użyciu Klucza API."""
        _LOGGER.debug("Rozpoczynanie aktualizacji danych dla Pstryk AIO (Klucz API, unified-metrics + pricing)")
        
        try:
            now_in_ha_tz = dt_util.now()
            current_local_date = now_in_ha_tz.date()
            tomorrow_local_date = current_local_date + timedelta(days=1)
            is_after_13_local = now_in_ha_tz.hour >= 13
            now_utc = dt_util.utcnow() # Użyjemy tego dla końca okna danych z miernika

            # Oblicz początek bieżącego i poprzedniego miesiąca
            start_of_current_month_local = now_in_ha_tz.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_of_previous_month_local = (start_of_current_month_local - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            meter_data_history_start_utc = dt_util.as_utc(start_of_previous_month_local) # Pobieraj dane od początku poprzedniego miesiąca
            meter_data_history_end_utc = now_utc # Do teraz
            today_start_in_ha_tz = now_in_ha_tz.replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_utc = dt_util.as_utc(today_start_in_ha_tz)
            today_end_utc = dt_util.as_utc(today_start_in_ha_tz + timedelta(days=1))
            tomorrow_start_utc = today_end_utc
            tomorrow_end_utc = dt_util.as_utc(today_start_in_ha_tz + timedelta(days=2))

            # Pobierz dane o zużyciu/produkcji (kWh, miesięczne, saldo)
            meter_data_usage_response = await api_client.get_integrations_meter_data_usage(
                resolution="hour",
                window_start=meter_data_history_start_utc,
                window_end=meter_data_history_end_utc
            )
            if meter_data_usage_response is None:
                _LOGGER.warning("Nie udało się pobrać danych zużycia z unified-metrics (metrics=meter_values).")
            
            # Pobierz dane o kosztach (fae_cost, rae_cost)
            meter_data_cost_response = await api_client.get_integrations_meter_data_cost(
                resolution="hour",
                window_start=meter_data_history_start_utc,
                window_end=meter_data_history_end_utc
            )
            if meter_data_cost_response is None:
                _LOGGER.warning("Nie udało się pobrać danych kosztowych z unified-metrics (metrics=cost).")

            refresh_today_purchase_prices = (
                coordinator._date_prices_today_fetched != current_local_date or
                coordinator._cached_purchase_prices_today is None
            )
            refresh_today_prosumer_prices = (
                coordinator._date_prices_today_fetched != current_local_date or
                coordinator._cached_prosumer_prices_today is None
            )
            successfully_updated_any_today_prices = False

            # --- Ceny ZAKUPU na dziś ---
            pricing_purchase_today_response: Optional[dict] = None
            if refresh_today_purchase_prices:
                _LOGGER.debug(f"Pobieranie nowych cen zakupu na dziś ({current_local_date}). Poprzedni cache date: {coordinator._date_prices_today_fetched}")
                api_response_purchase = await api_client.get_integrations_pricing_data(
                    resolution="hour", window_start=today_start_utc, window_end=today_end_utc
                )
                if api_response_purchase and api_response_purchase.get("frames"):
                    pricing_purchase_today_response = api_response_purchase
                    coordinator._cached_purchase_prices_today = api_response_purchase
                    successfully_updated_any_today_prices = True # Zaznaczamy sukces
                    _LOGGER.info(f"Pomyślnie pobrano i zbuforowano ceny zakupu na dziś ({current_local_date}).")
                else:
                    _LOGGER.warning(f"Nie udało się pobrać danych cen zakupu na dziś ({current_local_date}) lub ramki są puste. Używam starych z cache, jeśli dostępne.")
                    pricing_purchase_today_response = coordinator._cached_purchase_prices_today # Użyj starych, jeśli są
            else:
                _LOGGER.debug(f"Używanie zbuforowanych cen zakupu na dziś ({current_local_date}), data cache ({coordinator._date_prices_today_fetched}) zgodna.")
                pricing_purchase_today_response = coordinator._cached_purchase_prices_today
            
            if pricing_purchase_today_response is None: pricing_purchase_today_response = {}

            # --- Logika resetowania cache dla danych "na jutro" przy zmianie dnia ---
            # Sprawdź, czy obliczamy dla nowego "jutra" w porównaniu do ostatnio buforowanej daty "jutra"
            if coordinator._date_prices_tomorrow_valid_for != tomorrow_local_date:
                _LOGGER.info(
                    f"Wykryto nowy dzień dla danych 'jutro': {tomorrow_local_date}. "
                    f"Poprzedni cache 'jutro' był dla: {coordinator._date_prices_tomorrow_valid_for}. "
                    "Resetowanie buforów cen zakupu i sprzedaży na jutro."
                )
                coordinator._cached_purchase_prices_tomorrow = {}  # Resetuj bufor zakupu na jutro
                coordinator._cached_prosumer_prices_tomorrow = {}  # Resetuj bufor sprzedaży na jutro
                coordinator._date_prices_tomorrow_valid_for = tomorrow_local_date # Ustaw nową datę ważności dla "jutra"


            def _has_meaningful_price_data(response_data: Optional[dict]) -> bool:
                if not response_data or not isinstance(response_data.get("frames"), list):
                    return False
                if not response_data["frames"]: # Pusta lista ramek
                    return False
                for frame in response_data["frames"]:
                    # Sprawdzamy, czy istnieje cena brutto i czy jest różna od zera (lub None)
                    if frame.get("price_gross") is not None and frame.get("price_gross") != 0.0:
                        return True
                return False

            def _are_frames_for_expected_date(response_data: Optional[dict], expected_date: datetime.date) -> bool:
                """Sprawdza, czy daty w ramkach odpowiedzi API odpowiadają oczekiwanej dacie."""
                if not response_data or not isinstance(response_data.get("frames"), list) or not response_data["frames"]:
                    _LOGGER.debug(f"Brak ramek w odpowiedzi do sprawdzenia daty dla {expected_date}.")
                    return False # Brak ramek, więc nie mogą być na oczekiwaną datę
                
                # Sprawdź pierwszą ramkę, zakładając, że wszystkie są z tego samego dnia
                first_frame = response_data["frames"][0]
                start_utc_str = first_frame.get("start")
                if not start_utc_str:
                    _LOGGER.debug(f"Pierwsza ramka w odpowiedzi dla {expected_date} nie ma klucza 'start': {first_frame}")
                    return False
                
                try:
                    start_utc_dt = dt_util.parse_datetime(start_utc_str)
                    if not start_utc_dt:
                        _LOGGER.debug(f"Nie udało się sparsować 'start' z pierwszej ramki dla {expected_date}: {start_utc_str}")
                        return False
                    
                    start_local_dt = dt_util.as_local(start_utc_dt) # Konwersja na czas lokalny HA
                    frame_date = start_local_dt.date()
                    
                    return frame_date == expected_date
                except Exception as e:
                    _LOGGER.error(f"Błąd podczas sprawdzania daty ramek dla {expected_date}: {e}. Ramka: {first_frame}", exc_info=True)
                    return False


            pricing_purchase_tomorrow_response: Optional[dict] = None
            # Po potencjalnym resecie powyżej, _date_prices_tomorrow_valid_for jest już ustawione na tomorrow_local_date
            if (coordinator._cached_purchase_prices_tomorrow and
                    coordinator._cached_purchase_prices_tomorrow.get("frames")):
                _LOGGER.debug(f"Używanie zbuforowanych cen ZAKUPU na jutro ({tomorrow_local_date}).")
                pricing_purchase_tomorrow_response = coordinator._cached_purchase_prices_tomorrow
            else:
                _LOGGER.info(
                    f"Próba pobrania nowych cen ZAKUPU na jutro ({tomorrow_local_date}). "
                    "Cache był pusty lub nie zawierał ramek (mógł zostać zresetowany lub poprzednia próba nie powiodła się)."
                )
                api_response = await api_client.get_integrations_pricing_data(
                    resolution="hour", window_start=tomorrow_start_utc, window_end=tomorrow_end_utc
                )
                if _has_meaningful_price_data(api_response) and \
                   _are_frames_for_expected_date(api_response, tomorrow_local_date):
                    pricing_purchase_tomorrow_response = api_response
                    coordinator._cached_purchase_prices_tomorrow = api_response
                    _LOGGER.info(f"Pomyślnie pobrano i zbuforowano ceny ZAKUPU na jutro ({tomorrow_local_date}) z rzeczywistymi danymi.")
                else:
                    reason = "brak znaczących danych"
                    if not _are_frames_for_expected_date(api_response, tomorrow_local_date) and _has_meaningful_price_data(api_response):
                        reason = "daty w ramkach nie odpowiadają jutrzejszej dacie"
                    _LOGGER.debug(
                        f"Dane cen ZAKUPU na jutro ({tomorrow_local_date}) nie są dostępne lub niepoprawne ({reason}). "
                        "Ponowna próba pobrania nastąpi po interwale czasowym ustawiony w konfiguracji."
                    )
                    coordinator._cached_purchase_prices_tomorrow = {} # Zapisz pusty słownik, aby oznaczyć próbę
                    pricing_purchase_tomorrow_response = {} 
            
            if pricing_purchase_tomorrow_response is None: pricing_purchase_tomorrow_response = {}
            
            # --- Ceny SPRZEDAŻY (prosument) na dziś ---
            pricing_prosumer_today_response: Optional[dict] = None
            if refresh_today_prosumer_prices:
                _LOGGER.debug(f"Pobieranie nowych cen sprzedaży na dziś ({current_local_date}). Poprzedni cache date: {coordinator._date_prices_today_fetched}")
                api_response_prosumer = await api_client.get_integrations_prosumer_pricing_data(
                    resolution="hour", window_start=today_start_utc, window_end=today_end_utc
                )
                if api_response_prosumer and api_response_prosumer.get("frames"):
                    pricing_prosumer_today_response = api_response_prosumer
                    coordinator._cached_prosumer_prices_today = api_response_prosumer
                    successfully_updated_any_today_prices = True # Zaznaczamy sukces
                    _LOGGER.info(f"Pomyślnie pobrano i zbuforowano ceny sprzedaży na dziś ({current_local_date}).")
                else:
                    _LOGGER.warning(f"Nie udało się pobrać danych cen sprzedaży na dziś ({current_local_date}) lub ramki są puste. Używam starych z cache, jeśli dostępne.")
                    pricing_prosumer_today_response = coordinator._cached_prosumer_prices_today # Użyj starych, jeśli są
            else:
                _LOGGER.debug(f"Używanie zbuforowanych cen sprzedaży na dziś ({current_local_date}), data cache ({coordinator._date_prices_today_fetched}) zgodna.")
                pricing_prosumer_today_response = coordinator._cached_prosumer_prices_today
            
            if pricing_prosumer_today_response is None: pricing_prosumer_today_response = {}
            
            if successfully_updated_any_today_prices:
                 coordinator._date_prices_today_fetched = current_local_date
                 _LOGGER.debug(f"Zaktualizowano _date_prices_today_fetched na {current_local_date} ponieważ przynajmniej jeden zestaw cen na dziś został pomyślnie pobrany/zbuforowany.")
            elif coordinator._date_prices_today_fetched != current_local_date:
                 _LOGGER.debug(f"_date_prices_today_fetched ({coordinator._date_prices_today_fetched}) pozostaje niezmienione, nie udało się pobrać żadnych nowych danych dla {current_local_date}.")

            # --- Logika pobierania lub używania zbuforowanych cen SPRZEDAŻY (prosument) na jutro ---
            pricing_prosumer_tomorrow_response: Optional[dict] = None
            # Po potencjalnym resecie powyżej, _date_prices_tomorrow_valid_for jest już ustawione na tomorrow_local_date
            if (coordinator._cached_prosumer_prices_tomorrow and
                    coordinator._cached_prosumer_prices_tomorrow.get("frames")):
                _LOGGER.debug(f"Używanie zbuforowanych cen SPRZEDAŻY na jutro ({tomorrow_local_date}).")
                pricing_prosumer_tomorrow_response = coordinator._cached_prosumer_prices_tomorrow
            else:
                _LOGGER.info(
                    f"Próba pobrania nowych cen SPRZEDAŻY na jutro ({tomorrow_local_date}). "
                    "Cache był pusty lub nie zawierał ramek (mógł zostać zresetowany lub poprzednia próba nie powiodła się)."
                )
                api_response_prosumer = await api_client.get_integrations_prosumer_pricing_data(
                    resolution="hour", window_start=tomorrow_start_utc, window_end=tomorrow_end_utc
                )
                if _has_meaningful_price_data(api_response_prosumer) and \
                   _are_frames_for_expected_date(api_response_prosumer, tomorrow_local_date):
                    pricing_prosumer_tomorrow_response = api_response_prosumer
                    coordinator._cached_prosumer_prices_tomorrow = api_response_prosumer
                    _LOGGER.info(f"Pomyślnie pobrano i zbuforowano ceny SPRZEDAŻY na jutro ({tomorrow_local_date}) z rzeczywistymi danymi.")
                else:
                    reason_prosumer = "brak znaczących danych"
                    if not _are_frames_for_expected_date(api_response_prosumer, tomorrow_local_date) and _has_meaningful_price_data(api_response_prosumer):
                        reason_prosumer = "daty w ramkach nie odpowiadają jutrzejszej dacie"
                    _LOGGER.debug(
                        f"Ceny SPRZEDAŻY na jutro ({tomorrow_local_date}) nie są dostępne lub niepoprawne ({reason_prosumer}). "
                        "Ponowna próba pobrania nastąpi po interwale czasowym ustawionym w konfiguracji."
                    )
                    coordinator._cached_prosumer_prices_tomorrow = {} # Cache pusty, aby wymusić ponowienie
                    pricing_prosumer_tomorrow_response = {}
            
            if pricing_prosumer_tomorrow_response is None: pricing_prosumer_tomorrow_response = {}
            
            data_payload = {
                KEY_METER_DATA_USAGE: meter_data_usage_response,
                KEY_METER_DATA_COST: meter_data_cost_response,
                KEY_PRICING_DATA_PURCHASE_TODAY: pricing_purchase_today_response,
                KEY_PRICING_DATA_PURCHASE_TOMORROW: pricing_purchase_tomorrow_response,
                KEY_PRICING_DATA_PROSUMER_TODAY: pricing_prosumer_today_response,
                KEY_PRICING_DATA_PROSUMER_TOMORROW: pricing_prosumer_tomorrow_response,
                KEY_LAST_UPDATE: dt_util.utcnow().isoformat(),
            }
            _LOGGER.info(
                f"Pomyślnie pobrano dane dla Pstryk AIO (Klucz API, unified-metrics/pricing). "
                f"Usage: {'OK' if meter_data_usage_response else 'FAIL'}, "
                f"Cost: {'OK' if meter_data_cost_response else 'FAIL'}, "
                f"PurchasePricesToday: {'OK' if pricing_purchase_today_response and pricing_purchase_today_response.get('frames') else 'FAIL_EMPTY'}, "
                f"ProsumerPricesToday: {'OK' if pricing_prosumer_today_response and pricing_prosumer_today_response.get('frames') else 'FAIL_EMPTY'}, "
                f"PurchasePricesTomorrow: {'OK' if pricing_purchase_tomorrow_response and pricing_purchase_tomorrow_response.get('frames') else 'FAIL_EMPTY'}, "
                f"ProsumerPricesTomorrow: {'OK' if pricing_prosumer_tomorrow_response and pricing_prosumer_tomorrow_response.get('frames') else 'FAIL_EMPTY'}"
            )
            return data_payload

        except PstrykAuthError as err: 
            _LOGGER.error(f"Błąd autoryzacji Kluczem API podczas aktualizacji danych Pstryk AIO: {err}")
            raise UpdateFailed(f"Błąd autoryzacji Kluczem API: {err}") from err
        except PstrykApiError as err:
            _LOGGER.error(f"Błąd API podczas aktualizacji danych Pstryk AIO: {err}")
            raise UpdateFailed(f"Błąd API: {err}") from err
        except Exception as err:
            _LOGGER.exception(f"Nieoczekiwany błąd podczas aktualizacji danych Pstryk AIO: {err}")
            raise UpdateFailed(f"Nieoczekiwany błąd: {err}") from err

    update_interval_minutes = entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL_MINUTES)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN} ({entry.title})",
        update_method=async_update_data,
        update_interval=timedelta(minutes=update_interval_minutes),
    )
    coordinator._cached_purchase_prices_today = None
    coordinator._cached_prosumer_prices_today = None
    coordinator._date_prices_today_fetched = None
    coordinator._cached_purchase_prices_tomorrow = None
    coordinator._cached_prosumer_prices_tomorrow = None
    coordinator._date_prices_tomorrow_valid_for = None

    await coordinator.async_config_entry_first_refresh()
    
    if not coordinator.last_update_success:
         _LOGGER.warning("Pierwsze odświeżenie danych w koordynatorze nie powiodło się.")

    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client, 
        COORDINATOR_KEY_MAIN: coordinator, 
    }

    entry.async_on_unload(entry.add_update_listener(async_update_options_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    _LOGGER.info(f"Pomyślnie skonfigurowano wpis Pstryk AIO dla {entry.title} (Klucz API).")
    return True


async def async_update_options_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Obsługuje aktualizacje opcji konfiguracyjnych."""
    _LOGGER.debug(f"Opcje dla {entry.entry_id} zostały zaktualizowane: {entry.options}, ponowne ładowanie integracji.")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Zwalnia zasoby, gdy wpis konfiguracyjny jest usuwany."""
    _LOGGER.info(f"Rozpoczynanie usuwania wpisu Pstryk AIO dla {entry.title}")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
            _LOGGER.info(f"Pomyślnie usunięto integrację Pstryk AIO dla {entry.title}")
    else:
        _LOGGER.error(f"Nie udało się odładować platform dla wpisu {entry.title}.")

    return unload_ok
