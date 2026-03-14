"""Klient API dla Pstryk.pl (uwierzytelnianie Kluczem API bezpośrednio w Authorization, endpointy /integrations/)."""
import asyncio
import logging
import re
from datetime import datetime, timedelta 
from typing import Any, Dict, Optional

import aiohttp
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE_URL,
    API_METER_DATA_USAGE_PATH,
    API_METER_DATA_COST_PATH,
    API_PRICING_PATH,
    API_PROSUMER_PRICING_PATH,
    API_REQUEST_HEADERS,
    API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class PstrykApiError(Exception):
    """Ogólny błąd API Pstryk."""


class PstrykAuthError(PstrykApiError):
    """Błąd autoryzacji API Pstryk (nieprawidłowy Klucz API lub brak uprawnień)."""


class PstrykApiClientApiKey:
    """Asynchroniczny klient API Pstryk.pl (uwierzytelnianie Kluczem API bezpośrednio w Authorization)."""

    def __init__(
        self,
        api_key: str, 
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Inicjalizacja klienta API."""
        self._api_key = api_key 
        self._session = session or aiohttp.ClientSession()
        # Endpoint-level throttle backoff for API 429 responses.
        self._throttle_until: Dict[str, datetime] = {}

    async def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Wykonuje żądanie do API Pstryk używając Klucza API bezpośrednio w nagłówku Authorization."""
        
        full_url = f"{API_BASE_URL}{path}"

        throttle_until = self._throttle_until.get(path)
        if throttle_until and dt_util.utcnow() < throttle_until:
            _LOGGER.debug(
                "Pomijam zapytanie do %s z powodu aktywnego backoff do %s",
                full_url,
                throttle_until,
            )
            return None
        
        request_headers = API_REQUEST_HEADERS.copy()
        request_headers["Authorization"] = self._api_key 
        
        _LOGGER.debug(f"Wysyłanie żądania (API Key in Authorization): {method} {full_url}, params: {params}, headers: {request_headers}")
        response_text_for_error_log = ""

        try:
            async with self._session.request(method, full_url, headers=request_headers, params=params, timeout=API_TIMEOUT) as response:
                response_text_for_error_log = await response.text() 
                _LOGGER.debug(f"Odpowiedź z {full_url} (status: {response.status}): {response_text_for_error_log[:500]}...")

                if response.status in [401, 403]: 
                    _LOGGER.error(f"Błąd autoryzacji ({response.status}) dla {full_url}. Treść: {response_text_for_error_log[:500]}")
                    raise PstrykAuthError(f"Błąd autoryzacji ({response.status}). Sprawdź Klucz API. Treść błędu API: {response_text_for_error_log[:100]}")

                if response.status == 429:
                    cooldown_seconds = 3600
                    match = re.search(r"Expected available in (\d+) seconds", response_text_for_error_log)
                    if match:
                        try:
                            cooldown_seconds = int(match.group(1))
                        except ValueError:
                            pass
                    self._throttle_until[path] = dt_util.utcnow() + timedelta(seconds=cooldown_seconds)
                    _LOGGER.warning(
                        "API throttling (429) dla %s. Ustawiam backoff na %s sekund.",
                        full_url,
                        cooldown_seconds,
                    )
                    return None
                
                response.raise_for_status() 
                
                if 'application/json' in response.headers.get('Content-Type', ''):
                    return await response.json()
                else:
                    _LOGGER.warning(f"Odpowiedź z {full_url} nie jest typu JSON (Content-Type: {response.headers.get('Content-Type')}). Zwracam tekst: {response_text_for_error_log[:200]}")
                    return response_text_for_error_log 

        except aiohttp.ClientResponseError as err: 
            if err.status not in [401, 403]: # PstrykAuthError powinien być już rzucony
                 _LOGGER.error(f"Błąd odpowiedzi HTTP ({err.status}) dla {full_url}: {getattr(err, 'message', str(err))}. Treść: {response_text_for_error_log[:500]}")
                 raise PstrykApiError(f"Błąd API ({err.status}) dla {full_url}: {getattr(err, 'message', str(err))}") from err
            elif isinstance(err, PstrykAuthError): # Przekaż, jeśli już jest tego typu
                raise
            else: # Ogólny błąd HTTP
                _LOGGER.error(f"Błąd odpowiedzi HTTP ({err.status}) dla {full_url}: {getattr(err, 'message', str(err))}. Treść: {response_text_for_error_log[:500]}")
                raise PstrykApiError(f"Błąd API ({err.status}) dla {full_url}: {getattr(err, 'message', str(err))}") from err
        except aiohttp.ClientError as err: 
            _LOGGER.error(f"Błąd sieci (ClientError) podczas żądania do {full_url}: {err}")
            raise PstrykApiError(f"Błąd sieci: {err}") from err
        except asyncio.TimeoutError:
            _LOGGER.error(f"Przekroczono limit czasu podczas żądania do {full_url}.")
            raise PstrykApiError(f"Przekroczono limit czasu żądania do {full_url}")
        except Exception as e: 
            _LOGGER.error(f"Nieoczekiwany błąd podczas żądania do {full_url}: {e}", exc_info=True)
            if not isinstance(e, (PstrykAuthError, PstrykApiError)):
                raise PstrykApiError(f"Nieoczekiwany błąd: {e}") from e
            else:
                raise

    async def test_authentication(self) -> bool:
        """Testuje autentykację Kluczem API poprzez próbę pobrania danych z /integrations/meter-data/energy-usage/."""
        try:
            now = dt_util.utcnow()
            start_time = now - timedelta(days=1) 
            _LOGGER.debug(f"Test autoryzacji: próba pobrania danych z {API_METER_DATA_USAGE_PATH} (API Key in Authorization)")
            meter_data = await self.get_integrations_meter_data_usage(
                resolution="day", window_start=start_time, window_end=now
            )
            if meter_data is not None:
                _LOGGER.info(f"Test autoryzacji Kluczem API (w Authorization) zakończony pomyślnie. Pobrane dane (fragment): {str(meter_data)[:200]}")
                return True
            else:
                _LOGGER.warning(f"Test autoryzacji Kluczem API (w Authorization): nie udało się pobrać danych (meter_data is None).")
                return False
        except PstrykAuthError as e: 
            _LOGGER.error(f"Test autoryzacji Kluczem API (w Authorization) nie powiódł się: {e}")
            return False
        except PstrykApiError as e: 
            _LOGGER.error(f"Test autoryzacji Kluczem API (w Authorization) nie powiódł się (PstrykApiError): {e}")
            return False
        except Exception as e: 
            _LOGGER.error(f"Nieoczekiwany błąd podczas testu autoryzacji Kluczem API (w Authorization): {e}", exc_info=True)
            return False

    async def get_integrations_meter_data_usage(self, resolution: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Pobiera dane z /integrations/meter-data/energy-usage/."""
        start_str = window_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = window_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        params = {"resolution": resolution, "window_start": start_str, "window_end": end_str}
        try:
            return await self._request("GET", API_METER_DATA_USAGE_PATH, params=params)
        except PstrykApiError as e:
            _LOGGER.warning(f"Nie udało się pobrać danych z {API_METER_DATA_USAGE_PATH}: {e}")
            return None

    async def get_integrations_meter_data_cost(self, resolution: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Pobiera dane o kosztach z /integrations/meter-data/energy-cost/."""
        start_str = window_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = window_end.strftime('%Y-%m-%dT%H:%M:%SZ')   
        params = {"resolution": resolution, "window_start": start_str, "window_end": end_str}
        try:
            return await self._request("GET", API_METER_DATA_COST_PATH, params=params) 
        except PstrykApiError as e:
            _LOGGER.warning(f"Nie udało się pobrać danych z {API_METER_DATA_COST_PATH} (koszty): {e}")
            return None

    async def get_integrations_pricing_data(self, resolution: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Pobiera dane cenowe zakupu z /integrations/pricing/."""
        start_str = window_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = window_end.strftime('%Y-%m-%dT%H:%M:%SZ')   
        params = {"resolution": resolution, "window_start": start_str, "window_end": end_str}
        try:
            return await self._request("GET", API_PRICING_PATH, params=params) 
        except PstrykApiError as e:
            _LOGGER.warning(f"Nie udało się pobrać danych z {API_PRICING_PATH} (ceny zakupu): {e}")
            return None

    async def get_integrations_prosumer_pricing_data(self, resolution: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Pobiera dane cenowe sprzedaży (prosument) z /integrations/prosumer-pricing/."""
        start_str = window_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = window_end.strftime('%Y-%m-%dT%H:%M:%SZ')   
        params = {"resolution": resolution, "window_start": start_str, "window_end": end_str}
        try:
            return await self._request("GET", API_PROSUMER_PRICING_PATH, params=params) 
        except PstrykApiError as e:
            _LOGGER.warning(f"Nie udało się pobrać danych z {API_PROSUMER_PRICING_PATH} (ceny sprzedaży): {e}")
            return None
