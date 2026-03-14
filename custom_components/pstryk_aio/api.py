"""Klient API dla Pstryk.pl (uwierzytelnianie Kluczem API w Authorization)."""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp
from homeassistant.util import dt as dt_util

from .const import (
    API_BASE_URL,
    API_UNIFIED_METRICS_PATH,
    API_PROSUMER_PRICING_PATH,
    API_REQUEST_HEADERS,
    API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


UNIFIED_METRIC_METER_VALUES = "meter_values"
UNIFIED_METRIC_COST = "cost"
UNIFIED_METRIC_PRICING = "pricing"

UNIFIED_METER_VALUES_RESPONSE_KEYS = ("meterValues", "meter_values")
UNIFIED_COST_RESPONSE_KEYS = ("cost",)
UNIFIED_PRICING_RESPONSE_KEYS = ("pricing",)


def _pick_value(payload: Optional[Dict[str, Any]], *keys: str) -> Any:
    """Zwróć pierwszą dostępną wartość z payload."""
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _pick_metric_container(payload: Optional[Dict[str, Any]], keys: tuple[str, ...]) -> Dict[str, Any]:
    """Znajdź słownik metryki w odpowiedzi unified-metrics."""
    if not isinstance(payload, dict):
        return {}

    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        nested_metric = _pick_value(metrics, *keys)
        if isinstance(nested_metric, dict):
            return nested_metric

    direct_metric = _pick_value(payload, *keys)
    if isinstance(direct_metric, dict):
        return direct_metric

    return {}


def _sum_numeric_frames(frames: list[Dict[str, Any]], key: str) -> Optional[float]:
    """Zsumuj wartości liczbowe z ramek."""
    total = 0.0
    found = False
    for frame in frames:
        value = frame.get(key)
        if isinstance(value, (int, float)):
            total += float(value)
            found = True
    return round(total, 6) if found else None


class PstrykApiError(Exception):
    """Ogólny błąd API Pstryk."""


class PstrykAuthError(PstrykApiError):
    """Błąd autoryzacji API Pstryk (nieprawidłowy Klucz API lub brak uprawnień)."""


class PstrykApiClientApiKey:
    """Asynchroniczny klient API Pstryk.pl."""

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
        """Wykonuje żądanie do API Pstryk używając Klucza API w nagłówku Authorization."""
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

    async def _request_unified_metrics(
        self, metrics: str, resolution: str, window_start: datetime, window_end: datetime
    ) -> Optional[Dict[str, Any]]:
        """Pobiera dane z nowego endpointu unified-metrics."""
        start_str = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {
            "metrics": metrics,
            "resolution": resolution,
            "window_start": start_str,
            "window_end": end_str,
        }
        try:
            return await self._request("GET", API_UNIFIED_METRICS_PATH, params=params)
        except PstrykApiError as err:
            _LOGGER.warning(
                "Nie udało się pobrać danych z %s dla metrics=%s: %s",
                API_UNIFIED_METRICS_PATH,
                metrics,
                err,
            )
            return None

    def _normalize_unified_usage_response(self, response_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Mapuje unified-metrics na format oczekiwany przez integrację."""
        if not isinstance(response_data, dict):
            return response_data

        normalized_frames: list[Dict[str, Any]] = []
        for frame in response_data.get("frames", []):
            if not isinstance(frame, dict):
                continue

            meter_values = _pick_metric_container(frame, UNIFIED_METER_VALUES_RESPONSE_KEYS)
            normalized_frame: Dict[str, Any] = {
                "start": frame.get("start"),
                "end": frame.get("end"),
                "fae_usage": _pick_value(
                    meter_values,
                    "fae_usage",
                    "energy_active_import_register",
                ),
                "rae": _pick_value(
                    meter_values,
                    "rae",
                    "energy_active_export_register",
                ),
                "energy_balance": _pick_value(
                    meter_values,
                    "energy_balance",
                    "energy_balance_total",
                ),
            }
            if frame.get("is_live") is not None:
                normalized_frame["is_live"] = frame.get("is_live")
            normalized_frames.append(normalized_frame)

        summary = _pick_metric_container(response_data.get("summary"), UNIFIED_METER_VALUES_RESPONSE_KEYS)
        normalized_response: Dict[str, Any] = {
            "resolution": response_data.get("resolution"),
            "frames": normalized_frames,
        }
        if response_data.get("name") is not None:
            normalized_response["name"] = response_data.get("name")

        normalized_response["fae_total_usage"] = _pick_value(
            summary,
            "fae_total_usage",
            "energy_active_import_register_total",
        )
        normalized_response["rae_total"] = _pick_value(
            summary,
            "rae_total",
            "energy_active_export_register_total",
        )
        normalized_response["energy_balance"] = _pick_value(
            summary,
            "energy_balance",
            "energy_balance_total",
        )

        if normalized_response["fae_total_usage"] is None:
            normalized_response["fae_total_usage"] = _sum_numeric_frames(normalized_frames, "fae_usage")
        if normalized_response["rae_total"] is None:
            normalized_response["rae_total"] = _sum_numeric_frames(normalized_frames, "rae")
        if normalized_response["energy_balance"] is None:
            normalized_response["energy_balance"] = _sum_numeric_frames(normalized_frames, "energy_balance")

        return normalized_response

    def _normalize_unified_cost_response(self, response_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Mapuje unified-metrics na kosztowy format oczekiwany przez integrację."""
        if not isinstance(response_data, dict):
            return response_data

        normalized_frames: list[Dict[str, Any]] = []
        for frame in response_data.get("frames", []):
            if not isinstance(frame, dict):
                continue

            cost_values = _pick_metric_container(frame, UNIFIED_COST_RESPONSE_KEYS)
            normalized_frame: Dict[str, Any] = {
                "start": frame.get("start"),
                "end": frame.get("end"),
                "fae_cost": _pick_value(
                    cost_values,
                    "fae_cost",
                    "total_cost",
                    "energy_active_import_register_cost",
                ),
                "energy_sold_value": _pick_value(
                    cost_values,
                    "energy_sold_value",
                    "energy_active_export_register_value",
                    "energy_active_export_register_revenue",
                ),
                "energy_balance_value": _pick_value(
                    cost_values,
                    "energy_balance_value",
                    "net_cost",
                ),
            }
            if frame.get("is_live") is not None:
                normalized_frame["is_live"] = frame.get("is_live")

            if normalized_frame["energy_balance_value"] is None:
                fae_cost = normalized_frame.get("fae_cost")
                sold_value = normalized_frame.get("energy_sold_value")
                if isinstance(fae_cost, (int, float)) and isinstance(sold_value, (int, float)):
                    normalized_frame["energy_balance_value"] = round(float(fae_cost) - float(sold_value), 6)

            normalized_frames.append(normalized_frame)

        summary = _pick_metric_container(response_data.get("summary"), UNIFIED_COST_RESPONSE_KEYS)
        normalized_response: Dict[str, Any] = {
            "resolution": response_data.get("resolution"),
            "frames": normalized_frames,
        }

        normalized_response["fae_total_cost"] = _pick_value(
            summary,
            "fae_total_cost",
            "total_cost_total",
            "energy_active_import_register_cost_total",
        )
        normalized_response["total_energy_sold_value"] = _pick_value(
            summary,
            "total_energy_sold_value",
            "energy_active_export_register_value_total",
            "energy_active_export_register_revenue_total",
        )
        normalized_response["total_energy_balance_value"] = _pick_value(
            summary,
            "total_energy_balance_value",
            "net_cost_total",
        )

        if normalized_response["fae_total_cost"] is None:
            normalized_response["fae_total_cost"] = _sum_numeric_frames(normalized_frames, "fae_cost")
        if normalized_response["total_energy_sold_value"] is None:
            normalized_response["total_energy_sold_value"] = _sum_numeric_frames(normalized_frames, "energy_sold_value")
        if normalized_response["total_energy_balance_value"] is None:
            normalized_response["total_energy_balance_value"] = _sum_numeric_frames(normalized_frames, "energy_balance_value")

        return normalized_response

    def _normalize_unified_pricing_response(self, response_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Mapuje unified-metrics na płaski format cenowy."""
        if not isinstance(response_data, dict):
            return response_data

        normalized_frames: list[Dict[str, Any]] = []
        for frame in response_data.get("frames", []):
            if not isinstance(frame, dict):
                continue

            pricing_values = _pick_metric_container(frame, UNIFIED_PRICING_RESPONSE_KEYS)
            normalized_frame: Dict[str, Any] = {
                "start": frame.get("start"),
                "end": frame.get("end"),
                "price_net": _pick_value(pricing_values, "price_net", "price_net_avg"),
                "price_gross": _pick_value(pricing_values, "price_gross", "price_gross_avg"),
                "is_cheap": _pick_value(pricing_values, "is_cheap"),
                "is_expensive": _pick_value(pricing_values, "is_expensive"),
            }
            is_live = frame.get("is_live")
            if is_live is None:
                is_live = _pick_value(pricing_values, "is_live")
            if is_live is not None:
                normalized_frame["is_live"] = is_live
            normalized_frames.append(normalized_frame)

        summary = _pick_metric_container(response_data.get("summary"), UNIFIED_PRICING_RESPONSE_KEYS)
        normalized_response: Dict[str, Any] = {
            "frames": normalized_frames,
            "price_net_avg": _pick_value(summary, "price_net_avg"),
            "price_gross_avg": _pick_value(summary, "price_gross_avg"),
        }

        if normalized_response["price_net_avg"] is None:
            normalized_response["price_net_avg"] = _sum_numeric_frames(normalized_frames, "price_net")
            if normalized_response["price_net_avg"] is not None and normalized_frames:
                normalized_response["price_net_avg"] = round(
                    normalized_response["price_net_avg"] / len(normalized_frames), 6
                )

        if normalized_response["price_gross_avg"] is None:
            normalized_response["price_gross_avg"] = _sum_numeric_frames(normalized_frames, "price_gross")
            if normalized_response["price_gross_avg"] is not None and normalized_frames:
                normalized_response["price_gross_avg"] = round(
                    normalized_response["price_gross_avg"] / len(normalized_frames), 6
                )

        return normalized_response

    async def test_authentication(self) -> bool:
        """Testuje autentykację Kluczem API poprzez próbę pobrania danych unified-metrics."""
        try:
            now = dt_util.utcnow()
            start_time = now - timedelta(days=1)
            _LOGGER.debug(
                "Test autoryzacji: próba pobrania danych z %s (metrics=%s)",
                API_UNIFIED_METRICS_PATH,
                UNIFIED_METRIC_METER_VALUES,
            )
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
        """Pobiera dane zużycia z unified-metrics i normalizuje je do starego formatu."""
        response_data = await self._request_unified_metrics(
            metrics=UNIFIED_METRIC_METER_VALUES,
            resolution=resolution,
            window_start=window_start,
            window_end=window_end,
        )
        return self._normalize_unified_usage_response(response_data)

    async def get_integrations_meter_data_cost(self, resolution: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Pobiera dane kosztowe z unified-metrics i normalizuje je do starego formatu."""
        response_data = await self._request_unified_metrics(
            metrics=UNIFIED_METRIC_COST,
            resolution=resolution,
            window_start=window_start,
            window_end=window_end,
        )
        return self._normalize_unified_cost_response(response_data)

    async def get_integrations_pricing_data(self, resolution: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Pobiera dane cenowe zakupu z unified-metrics i normalizuje je do starego formatu."""
        response_data = await self._request_unified_metrics(
            metrics=UNIFIED_METRIC_PRICING,
            resolution=resolution,
            window_start=window_start,
            window_end=window_end,
        )
        return self._normalize_unified_pricing_response(response_data)

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
