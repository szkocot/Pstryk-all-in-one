"""Definicje sensorów dla integracji Pstryk AIO (uwierzytelnianie Kluczem API, endpointy /integrations/)."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    COORDINATOR_KEY_MAIN,
    KEY_METER_DATA_USAGE,
    KEY_METER_DATA_COST,
    KEY_PRICING_DATA_PURCHASE_TODAY,
    KEY_PRICING_DATA_PURCHASE_TOMORROW,
    KEY_PRICING_DATA_PROSUMER_TODAY,
    KEY_PRICING_DATA_PROSUMER_TOMORROW,
    KEY_LAST_UPDATE,
    SENSOR_TODAY_PURCHASE_PRICE,
    SENSOR_TOMORROW_PURCHASE_PRICE,
    SENSOR_TODAY_SALE_PRICE,
    SENSOR_TOMORROW_SALE_PRICE,
    SENSOR_CONSUMPTION_DAILY_COST,
    SENSOR_PRODUCTION_DAILY_YIELD, 
    SENSOR_BILLING_BALANCE_MONTHLY_PLN,
    SENSOR_ENERGY_BALANCE_MONTHLY_KWH,
    SENSOR_BILLING_BALANCE_DAILY_PLN,
    SENSOR_ENERGY_BALANCE_DAILY_KWH,
    FRIENDLY_NAME_PURCHASE_PRICE,
    FRIENDLY_NAME_SALE_PRICE,
    FRIENDLY_NAME_CONSUMPTION_DAILY_COST,
    FRIENDLY_NAME_PRODUCTION_DAILY_YIELD,
    CONF_CHEAP_PURCHASE_PRICE_THRESHOLD,
    CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD,
    CONF_CHEAP_SALE_PRICE_THRESHOLD,
    CONF_EXPENSIVE_SALE_PRICE_THRESHOLD,
    ATTR_PRICE_TODAY,
    ATTR_PRICE_TOMORROW,
    ATTR_PRICE_START_TIME,
    ATTR_PRICE_END_TIME,
    ATTR_PRICE_VALUE_NET,
    ATTR_PRICE_VALUE_GROSS,
    ATTR_PRICE_IS_CHEAP,
    ATTR_PRICE_IS_EXPENSIVE,
    ATTR_PRICE_UNIT, 
    ATTR_DAILY_KWH_CONSUMPTION,
    ATTR_DAILY_KWH_PRODUCTION,
    ATTR_ENERGY_BALANCE_KWH,
    ATTR_MONTHLY_KWH_CONSUMPTION,
    ATTR_MONTHLY_KWH_PRODUCTION,
    ATTR_MONTHLY_PLN_COST,
    ATTR_MONTHLY_PLN_YIELD,
    ATTR_HOURLY_COST_CONSUMPTION,
    ATTR_HOURLY_YIELD_PRODUCTION,
    ATTR_AVERAGE_PRICE,
    ATTR_DAILY_BREAKDOWN_CURRENT_MONTH,
    ATTR_DAILY_BREAKDOWN_PREVIOUS_MONTH,
    ATTR_HOURLY_BREAKDOWN_CURRENT_DAY,
    ATTR_DATA_TIMESTAMP,
    ATTR_DATA_STATUS_MESSAGE,
    USAGE_FAE_TOTAL,
    USAGE_RAE_TOTAL,
    USAGE_ENERGY_BALANCE,
    USAGE_MONTHLY_FAE,
    USAGE_MONTHLY_RAE,
    USAGE_MONTHLY_FAE_COST,
    USAGE_MONTHLY_RAE_YIELD,
    COST_FRAME_FAE_COST, # Zmieniony import
    COST_FRAME_RAE_YIELD, # Zmieniony import
    COST_FRAME_ENERGY_BALANCE_VALUE,
    DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD,
    DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD,
    DEFAULT_CHEAP_SALE_PRICE_THRESHOLD,
    DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD,
    FRIENDLY_NAME_BILLING_BALANCE_MONTHLY_PLN,
    FRIENDLY_NAME_ENERGY_BALANCE_MONTHLY_KWH,
    FRIENDLY_NAME_BILLING_BALANCE_DAILY_PLN,
    FRIENDLY_NAME_ENERGY_BALANCE_DAILY_KWH,
    SENSOR_CONSUMPTION_DAILY_KWH,
    SENSOR_PRODUCTION_DAILY_KWH,
    FRIENDLY_NAME_CONSUMPTION_DAILY_KWH,
    FRIENDLY_NAME_PRODUCTION_DAILY_KWH,
    USAGE_FRAME_FAE_KWH,
    USAGE_FRAME_RAE_KWH,
    SENSOR_CONSUMPTION_MONTHLY_KWH,
    SENSOR_PRODUCTION_MONTHLY_KWH,
    SENSOR_CONSUMPTION_MONTHLY_COST_PLN,
    SENSOR_PRODUCTION_MONTHLY_YIELD_PLN,
    FRIENDLY_NAME_CONSUMPTION_MONTHLY_KWH,
    FRIENDLY_NAME_PRODUCTION_MONTHLY_KWH,
    FRIENDLY_NAME_CONSUMPTION_MONTHLY_COST_PLN,
    FRIENDLY_NAME_PRODUCTION_MONTHLY_YIELD_PLN,
)
from .const import ATTR_LAST_MONTH_VALUE # Dodano import dla nowego atrybutu
from homeassistant.helpers.event import async_track_time_change
_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS_MAP = {
    SENSOR_TODAY_PURCHASE_PRICE: (FRIENDLY_NAME_PURCHASE_PRICE, SensorDeviceClass.MONETARY, None, ATTR_PRICE_UNIT, "mdi:transmission-tower-import"),
    SENSOR_TOMORROW_PURCHASE_PRICE: ("Cena zakupu prądu (jutro)", SensorDeviceClass.MONETARY, None, ATTR_PRICE_UNIT, "mdi:transmission-tower-import"),
    SENSOR_TODAY_SALE_PRICE: (FRIENDLY_NAME_SALE_PRICE, SensorDeviceClass.MONETARY, None, ATTR_PRICE_UNIT, "mdi:transmission-tower-export"),
    SENSOR_TOMORROW_SALE_PRICE: ("Cena sprzedaży prądu (jutro)", SensorDeviceClass.MONETARY, None, ATTR_PRICE_UNIT, "mdi:transmission-tower-export"),
    SENSOR_CONSUMPTION_DAILY_COST: (FRIENDLY_NAME_CONSUMPTION_DAILY_COST, SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "PLN", "mdi:cash-minus"),
    SENSOR_PRODUCTION_DAILY_YIELD: (FRIENDLY_NAME_PRODUCTION_DAILY_YIELD, SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "PLN", "mdi:cash-plus"),
    SENSOR_BILLING_BALANCE_MONTHLY_PLN: (FRIENDLY_NAME_BILLING_BALANCE_MONTHLY_PLN, SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "PLN", "mdi:scale-balance"),
    SENSOR_ENERGY_BALANCE_MONTHLY_KWH: (FRIENDLY_NAME_ENERGY_BALANCE_MONTHLY_KWH, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt-circle"),
    SENSOR_BILLING_BALANCE_DAILY_PLN: (FRIENDLY_NAME_BILLING_BALANCE_DAILY_PLN, SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "PLN", "mdi:cash-clock"),
    SENSOR_ENERGY_BALANCE_DAILY_KWH: (FRIENDLY_NAME_ENERGY_BALANCE_DAILY_KWH, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt"),
    SENSOR_CONSUMPTION_DAILY_KWH: (FRIENDLY_NAME_CONSUMPTION_DAILY_KWH, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt"),
    SENSOR_PRODUCTION_DAILY_KWH: (FRIENDLY_NAME_PRODUCTION_DAILY_KWH, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-panel"),
    SENSOR_CONSUMPTION_MONTHLY_KWH: (FRIENDLY_NAME_CONSUMPTION_MONTHLY_KWH, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:lightning-bolt-outline"),
    SENSOR_PRODUCTION_MONTHLY_KWH: (FRIENDLY_NAME_PRODUCTION_MONTHLY_KWH, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-panel-large"),
    SENSOR_CONSUMPTION_MONTHLY_COST_PLN: (FRIENDLY_NAME_CONSUMPTION_MONTHLY_COST_PLN, SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "PLN", "mdi:cash-minus"),
    SENSOR_PRODUCTION_MONTHLY_YIELD_PLN: (FRIENDLY_NAME_PRODUCTION_MONTHLY_YIELD_PLN, SensorDeviceClass.MONETARY, SensorStateClass.TOTAL, "PLN", "mdi:cash-plus"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguruje sensory Pstryk AIO na podstawie wpisu konfiguracyjnego."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_KEY_MAIN]
    config_entry_title = entry.title 

    entities = []
    for sensor_key, (name_suffix, device_class, state_class, unit, icon) in SENSOR_DESCRIPTIONS_MAP.items():
        entities.append(
            PstrykUniversalSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id, 
                sensor_key=sensor_key,
                name_suffix=name_suffix,
                device_class=device_class,
                state_class=state_class,
                unit_of_measurement=unit,
                icon=icon,
                config_entry_title=config_entry_title,
            )
        )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"Utworzono {len(entities)} encji sensorów Pstryk AIO dla '{config_entry_title}'.")
    else:
        _LOGGER.warning(f"Nie utworzono żadnych encji sensorów dla '{config_entry_title}'.")


class PstrykUniversalSensor(CoordinatorEntity, SensorEntity):
    """Uniwersalna klasa sensora Pstryk AIO."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str, 
        sensor_key: str,
        name_suffix: str,
        device_class: Optional[SensorDeviceClass],
        state_class: Optional[SensorStateClass],
        unit_of_measurement: Optional[str],
        icon: Optional[str],
        config_entry_title: str, 
    ):
        """Inicjalizacja sensora."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{self._sensor_key}" 
        self._attr_name = f"{DEFAULT_NAME} {name_suffix}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_icon = icon
        self._attr_extra_state_attributes = {}
        self._attr_device_info = None
        self._update_state() 

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to Home Assistant."""
        await super().async_added_to_hass() # Essential for CoordinatorEntity
        if self._sensor_key in [SENSOR_TODAY_PURCHASE_PRICE, SENSOR_TODAY_SALE_PRICE]:
            _LOGGER.debug(f"Sensor {self.name} ({self._sensor_key}): Setting up hourly state refresh.")
            self.async_on_remove(
                async_track_time_change(
                    self.hass, self._hourly_refresh_state, hour=range(24), minute=0, second=0
                )
            )

    async def _hourly_refresh_state(self, now: datetime) -> None:
        """Called at the top of the hour to refresh the sensor's state from existing coordinator data."""
        if self.coordinator.last_update_success and self.coordinator.data:
            _LOGGER.debug(f"Sensor {self.name} ({self._sensor_key}): Hourly refresh triggered at {now}. Re-evaluating state from coordinator data.")
            self._update_state()
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Zwraca true, jeśli koordynator ma dane i ostatnia aktualizacja była pomyślna."""
        if self._sensor_key in [SENSOR_TOMORROW_PURCHASE_PRICE, SENSOR_TOMORROW_SALE_PRICE]:
            return self.coordinator.last_update_success
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Obsługuje aktualizacje danych z koordynatora."""
        self._update_state()
        self.async_write_ha_state()

    def _get_current_price_frame(self, pricing_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Finds the current price frame based on the current UTC time.
        """
        if not pricing_data or not isinstance(pricing_data.get("frames"), list):
            _LOGGER.debug(f"({self.name}) No price frames in pricing_data to process.")
            return None

        now_utc = dt_util.utcnow()
        _LOGGER.debug(f"({self.name}) Searching for current price frame for time: {now_utc}")

        for frame in pricing_data["frames"]:
            try:
                start_time_str = frame.get(ATTR_PRICE_START_TIME)  # Powinno być "start"
                end_time_str = frame.get(ATTR_PRICE_END_TIME)      # Powinno być "end"
                
                if not start_time_str or not end_time_str:
                    _LOGGER.debug(f"({self.name}) Skipping frame with missing start/end time: {frame}")
                    continue

                start_time = dt_util.parse_datetime(start_time_str)
                end_time = dt_util.parse_datetime(end_time_str)

                if start_time and end_time and start_time <= now_utc < end_time:
                    _LOGGER.debug(f"({self.name}) Found active price frame by time match: {frame}. API 'is_live': {frame.get('is_live')}")
                    return frame
            except (TypeError, ValueError) as e:
                _LOGGER.warning(f"({self.name}) Error parsing time for price frame: {frame}, error: {e}")
                continue
        _LOGGER.debug(
            f"({self.name}) Could not find current price frame for {now_utc} by precise time match. "
            "The sensor value will be None if no frame is active."
        )
        return None

    def _format_price_frames_for_attributes(
        self, 
        pricing_data: Optional[Dict[str, Any]],
        cheap_threshold: Optional[float],
        expensive_threshold: Optional[float]
    ) -> List[Dict[str, Any]]:
        """Formatuje ramki cenowe do atrybutów, konwertując czas na lokalny i upraszczając pola."""
        formatted_frames = []
        if not pricing_data or not isinstance(pricing_data.get("frames"), list):
            return formatted_frames

        _LOGGER.debug(f"({self.name}) Formatowanie ramek cenowych z progami: Tani={cheap_threshold}, Drogi={expensive_threshold}")


        for frame in pricing_data["frames"]:
            try:
                start_local_str = None
                end_local_str = None
                
                start_utc_str = frame.get(ATTR_PRICE_START_TIME)
                if start_utc_str:
                    start_utc_dt = dt_util.parse_datetime(start_utc_str)
                    if start_utc_dt:
                        start_local_str = dt_util.as_local(start_utc_dt).isoformat(timespec='seconds')
                
                end_utc_str = frame.get(ATTR_PRICE_END_TIME)
                if end_utc_str:
                    end_utc_dt = dt_util.parse_datetime(end_utc_str)
                    if end_utc_dt:
                        end_local_str = dt_util.as_local(end_utc_dt).isoformat(timespec='seconds')

                price_value = frame.get(ATTR_PRICE_VALUE_GROSS)
                is_cheap_flag = False
                is_expensive_flag = False

                if price_value is not None:
                    if cheap_threshold is not None and price_value <= cheap_threshold:
                        is_cheap_flag = True
                    if expensive_threshold is not None and price_value >= expensive_threshold:
                        is_expensive_flag = True

                frame_info = {
                    "start": start_local_str, 
                    "end": end_local_str,     
                    "price": price_value,
                    ATTR_PRICE_IS_CHEAP: is_cheap_flag,
                    ATTR_PRICE_IS_EXPENSIVE: is_expensive_flag,
                }
                frame_info_cleaned = {k: v for k, v in frame_info.items() if v is not None}
                formatted_frames.append(frame_info_cleaned)
            except Exception as e:
                _LOGGER.warning(f"({self.name}) Błąd podczas formatowania ramki cenowej dla atrybutów: {frame}, błąd: {e}")
        return formatted_frames

    def _calculate_average_price(self, pricing_data: Optional[Dict[str, Any]]) -> Optional[float]:
        """Oblicza średnią cenę brutto z ramek cenowych."""
        if not pricing_data or not isinstance(pricing_data.get("frames"), list):
            return None
        
        total_price = 0.0
        count = 0
        for frame in pricing_data["frames"]:
            price_gross = frame.get(ATTR_PRICE_VALUE_GROSS)
            if price_gross is not None:
                total_price += price_gross
                count += 1
        return round(total_price / count, 4) if count > 0 else None

    def _format_cost_frames_for_attributes(self, cost_data: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Formatuje ramki kosztów do atrybutów, konwertując czas na lokalny."""
        attributes = {
            ATTR_HOURLY_COST_CONSUMPTION: [],
            ATTR_HOURLY_YIELD_PRODUCTION: []
        }
        if not cost_data or not isinstance(cost_data.get("frames"), list):
            return attributes

        for frame in cost_data["frames"]:
            try:
                start_local_str = None
                end_local_str = None
                start_utc_str = frame.get(ATTR_PRICE_START_TIME)
                end_utc_str = frame.get(ATTR_PRICE_END_TIME)

                if start_utc_str:
                    start_utc_dt = dt_util.parse_datetime(start_utc_str)
                    if start_utc_dt:
                        start_local_str = dt_util.as_local(start_utc_dt).isoformat(timespec='seconds')
                if end_utc_str:
                    end_utc_dt = dt_util.parse_datetime(end_utc_str)
                    if end_utc_dt:
                        end_local_str = dt_util.as_local(end_utc_dt).isoformat(timespec='seconds')

                fae_frame_info = {
                    "start": start_local_str,
                    "end": end_local_str,
                    COST_FRAME_FAE_COST: frame.get(COST_FRAME_FAE_COST)
                }
                if fae_frame_info[COST_FRAME_FAE_COST] is not None:
                    attributes[ATTR_HOURLY_COST_CONSUMPTION].append(fae_frame_info)

                rae_frame_info = {
                    "start": start_local_str,
                    "end": end_local_str,
                    COST_FRAME_RAE_YIELD: frame.get(COST_FRAME_RAE_YIELD)
                }
                if rae_frame_info[COST_FRAME_RAE_YIELD] is not None:
                    attributes[ATTR_HOURLY_YIELD_PRODUCTION].append(rae_frame_info)
            except Exception as e:
                _LOGGER.warning(f"({self.name}) Błąd podczas formatowania ramki kosztów: {frame}, błąd: {e}")
        return attributes

    def _aggregate_daily_data(
        self, 
        frames_data: Optional[List[Dict[str, Any]]], 
        data_key: str,
        target_month_dt: datetime
    ) -> tuple[Optional[float], List[Dict[str, Any]]]:
        """Agreguje dane dzienne dla bieżącego miesiąca."""
        current_month_sum = 0.0
        current_month_breakdown: Dict[str, float] = {}
        
        if not frames_data:
            return None, []

        for frame in frames_data:
            try:
                start_utc_str = frame.get(ATTR_PRICE_START_TIME)
                value = frame.get(data_key)

                if start_utc_str is None or value is None:
                    continue

                start_utc_dt = dt_util.parse_datetime(start_utc_str)
                if not start_utc_dt:
                    continue
                
                start_local_dt = dt_util.as_local(start_utc_dt)
                day_str = start_local_dt.strftime("%Y-%m-%d")

                if start_local_dt.year == target_month_dt.year and start_local_dt.month == target_month_dt.month:
                    current_month_sum += float(value)
                    current_month_breakdown[day_str] = current_month_breakdown.get(day_str, 0.0) + float(value)

            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"({self.name}) Błąd podczas agregacji danych dziennych dla ramki {frame} i klucza {data_key}: {e}")
                continue
        formatted_current_breakdown = [{"date": date, "value": round(val, 3)} for date, val in sorted(current_month_breakdown.items())]

        return round(current_month_sum, 3) if current_month_breakdown else None, formatted_current_breakdown

    def _aggregate_hourly_data_for_day(
        self,
        frames_data: Optional[List[Dict[str, Any]]],
        data_key: str,
        target_day_dt: datetime
    ) -> tuple[Optional[float], List[Dict[str, Any]]]:
        """Agreguje dane godzinowe dla określonego dnia i sumuje je."""
        daily_sum = 0.0
        hourly_breakdown: List[Dict[str, Any]] = []
        data_found_for_day = False

        if not frames_data:
            return None, []

        for frame in frames_data:
            try:
                start_utc_str = frame.get(ATTR_PRICE_START_TIME)
                end_utc_str = frame.get(ATTR_PRICE_END_TIME)
                value = frame.get(data_key)

                if start_utc_str is None or value is None:
                    continue

                start_utc_dt = dt_util.parse_datetime(start_utc_str)
                if not start_utc_dt:
                    continue

                start_local_dt = dt_util.as_local(start_utc_dt)

                if start_local_dt.year == target_day_dt.year and \
                   start_local_dt.month == target_day_dt.month and \
                   start_local_dt.day == target_day_dt.day:
                    
                    data_found_for_day = True
                    daily_sum += float(value)
                    
                    end_local_str = None
                    if end_utc_str and (end_utc_dt := dt_util.parse_datetime(end_utc_str)):
                        end_local_str = dt_util.as_local(end_utc_dt).isoformat(timespec='seconds')

                    hourly_breakdown.append({
                        "start": start_local_dt.isoformat(timespec='seconds'),
                        "end": end_local_str,
                        "value": round(float(value), 3)
                    })
            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"({self.name}) Błąd podczas agregacji danych godzinowych dla ramki {frame} i klucza {data_key}: {e}")
                continue
        
        return round(daily_sum, 3) if data_found_for_day else None, sorted(hourly_breakdown, key=lambda x: x["start"])

    def _update_state(self) -> None:
        """Aktualizuje stan sensora na podstawie danych z koordynatora."""
        data = self.coordinator.data
        if data is None:
            if self._sensor_key not in [SENSOR_TOMORROW_PURCHASE_PRICE, SENSOR_TOMORROW_SALE_PRICE]:
                self._attr_native_value = None
                self._attr_extra_state_attributes = {ATTR_DATA_TIMESTAMP: None}
                return
        meter_usage_data = data.get(KEY_METER_DATA_USAGE) if data else None
        meter_cost_data = data.get(KEY_METER_DATA_COST) if data else None
        pricing_purchase_today = data.get(KEY_PRICING_DATA_PURCHASE_TODAY) if data else None
        pricing_purchase_tomorrow = data.get(KEY_PRICING_DATA_PURCHASE_TOMORROW) if data else None
        pricing_prosumer_today = data.get(KEY_PRICING_DATA_PROSUMER_TODAY) if data else None
        pricing_prosumer_tomorrow = data.get(KEY_PRICING_DATA_PROSUMER_TOMORROW) if data else None
        last_api_update = data.get(KEY_LAST_UPDATE) if data else None

        _LOGGER.debug(f"Sensor {self.name} ({self._sensor_key}): Aktualizacja. "
                      f"Usage: {'OK' if meter_usage_data else 'BRAK'}, "
                      f"Cost: {'OK' if meter_cost_data else 'BRAK'}, "
                      f"PurchaseToday: {'OK' if pricing_purchase_today else 'BRAK'}, "
                      f"ProsumerToday: {'OK' if pricing_prosumer_today else 'BRAK'}, Data from coordinator: {'OK' if data else 'BRAK'}")

        new_value: Any = None 
        attributes = {ATTR_DATA_TIMESTAMP: last_api_update}

        options = self.coordinator.config_entry.options
        cheap_purchase_thresh = options.get(CONF_CHEAP_PURCHASE_PRICE_THRESHOLD, DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD)
        expensive_purchase_thresh = options.get(CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD, DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD)
        cheap_sale_thresh = options.get(CONF_CHEAP_SALE_PRICE_THRESHOLD, DEFAULT_CHEAP_SALE_PRICE_THRESHOLD)
        expensive_sale_thresh = options.get(CONF_EXPENSIVE_SALE_PRICE_THRESHOLD, DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD)

        now_local = dt_util.now()
        current_month_dt = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Oblicz pierwszy dzień poprzedniego miesiąca dla agregacji
        previous_month_target_dt = (current_month_dt - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


        current_cheap_thresh = None
        current_expensive_thresh = None


        try:
            if self._sensor_key == SENSOR_TODAY_PURCHASE_PRICE:
                current_frame = self._get_current_price_frame(pricing_purchase_today)
                if current_frame:
                    price_gross = current_frame.get(ATTR_PRICE_VALUE_GROSS)
                    price_net = current_frame.get(ATTR_PRICE_VALUE_NET)
                    if price_gross is not None and price_gross != 0.0:
                        new_value = price_gross
                    else:
                        new_value = price_net
                else:
                    _LOGGER.debug(f"({self.name}) Nie znaleziono aktualnej ramki cenowej dla ceny zakupu.")
                    new_value = None
                
                current_cheap_thresh = cheap_purchase_thresh
                current_expensive_thresh = expensive_purchase_thresh
                attributes[ATTR_PRICE_TODAY] = self._format_price_frames_for_attributes(
                    pricing_purchase_today, current_cheap_thresh, current_expensive_thresh
                )
                avg_price_today = self._calculate_average_price(pricing_purchase_today)
                if avg_price_today is not None:
                    attributes[f"{ATTR_AVERAGE_PRICE}_today"] = avg_price_today

            elif self._sensor_key == SENSOR_TOMORROW_PURCHASE_PRICE:
                frames_tomorrow = pricing_purchase_tomorrow.get("frames") if pricing_purchase_tomorrow and isinstance(pricing_purchase_tomorrow, dict) else None
                has_real_data_tomorrow = False
                if frames_tomorrow and isinstance(frames_tomorrow, list):
                    for frame in frames_tomorrow:
                        if frame.get(ATTR_PRICE_VALUE_GROSS) is not None and frame.get(ATTR_PRICE_VALUE_GROSS) != 0.0:
                            has_real_data_tomorrow = True
                            break
                if has_real_data_tomorrow:
                    avg_price_tomorrow = self._calculate_average_price(pricing_purchase_tomorrow)
                    if avg_price_tomorrow is not None:
                        new_value = round(avg_price_tomorrow, 4)
                    else:
                        new_value = None
                    attributes[ATTR_PRICE_TOMORROW] = self._format_price_frames_for_attributes(
                        pricing_purchase_tomorrow, cheap_purchase_thresh, expensive_purchase_thresh
                    )
                else:
                    new_value = None
                    attributes[ATTR_DATA_STATUS_MESSAGE] = "Dane przeważnie są dostępne po godzinie 16:00"
                    _LOGGER.debug(f"({self.name}) Brak danych o cenach zakupu na jutro, ustawiam stan na None i komunikat w atrybutach.")
                if has_real_data_tomorrow and (avg_price_tomorrow := self._calculate_average_price(pricing_purchase_tomorrow)) is not None:
                    attributes[f"{ATTR_AVERAGE_PRICE}_tomorrow"] = avg_price_tomorrow


            elif self._sensor_key == SENSOR_TODAY_SALE_PRICE:
                current_frame = self._get_current_price_frame(pricing_prosumer_today)
                if current_frame:
                    price_gross = current_frame.get(ATTR_PRICE_VALUE_GROSS)
                    price_net = current_frame.get(ATTR_PRICE_VALUE_NET)
                    if price_gross is not None and price_gross != 0.0:
                        new_value = price_gross
                    else:
                        new_value = price_net
                else:
                    _LOGGER.debug(f"({self.name}) Nie znaleziono aktualnej ramki cenowej dla ceny sprzedaży.")
                    new_value = None
                
                current_cheap_thresh = cheap_sale_thresh
                current_expensive_thresh = expensive_sale_thresh
                attributes[ATTR_PRICE_TODAY] = self._format_price_frames_for_attributes(
                    pricing_prosumer_today, current_cheap_thresh, current_expensive_thresh
                )
                avg_price_today = self._calculate_average_price(pricing_prosumer_today)
                if avg_price_today is not None:
                    attributes[f"{ATTR_AVERAGE_PRICE}_today"] = avg_price_today

            elif self._sensor_key == SENSOR_TOMORROW_SALE_PRICE:
                frames_tomorrow_sale = pricing_prosumer_tomorrow.get("frames") if pricing_prosumer_tomorrow and isinstance(pricing_prosumer_tomorrow, dict) else None
                has_real_data_tomorrow_sale = False
                if frames_tomorrow_sale and isinstance(frames_tomorrow_sale, list):
                    for frame in frames_tomorrow_sale:
                        if frame.get(ATTR_PRICE_VALUE_GROSS) is not None and frame.get(ATTR_PRICE_VALUE_GROSS) != 0.0:
                            has_real_data_tomorrow_sale = True
                            break

                if has_real_data_tomorrow_sale:
                    avg_price_tomorrow = self._calculate_average_price(pricing_prosumer_tomorrow)
                    if avg_price_tomorrow is not None:
                        new_value = round(avg_price_tomorrow, 4)
                    else:
                        new_value = None
                    attributes[ATTR_PRICE_TOMORROW] = self._format_price_frames_for_attributes(
                        pricing_prosumer_tomorrow, cheap_sale_thresh, expensive_sale_thresh
                    )
                else:
                    new_value = None
                    attributes[ATTR_DATA_STATUS_MESSAGE] = "Dane przeważnie są dostępne po godzinie 16:00"
                    _LOGGER.debug(f"({self.name}) Brak danych o cenach sprzedaży na jutro, ustawiam stan na None i komunikat w atrybutach.")
                if has_real_data_tomorrow_sale and (avg_price_tomorrow := self._calculate_average_price(pricing_prosumer_tomorrow)) is not None:
                    attributes[f"{ATTR_AVERAGE_PRICE}_tomorrow"] = avg_price_tomorrow


            elif self._sensor_key == SENSOR_CONSUMPTION_DAILY_COST:
                cost_frames = meter_cost_data.get("frames") if meter_cost_data else None
                daily_total_cost, hourly_breakdown = self._aggregate_hourly_data_for_day(
                    cost_frames, COST_FRAME_FAE_COST, now_local
                )
                new_value = round(daily_total_cost, 2) if daily_total_cost is not None else 0.0
                
                if hourly_breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = hourly_breakdown
                if meter_usage_data:
                    attributes[ATTR_MONTHLY_KWH_CONSUMPTION] = meter_usage_data.get(USAGE_MONTHLY_FAE) 
                    attributes[ATTR_MONTHLY_PLN_COST] = meter_usage_data.get(USAGE_MONTHLY_FAE_COST) 


            elif self._sensor_key == SENSOR_PRODUCTION_DAILY_YIELD:
                cost_frames = meter_cost_data.get("frames") if meter_cost_data else None
                daily_total_yield, hourly_breakdown = self._aggregate_hourly_data_for_day(
                    cost_frames, COST_FRAME_RAE_YIELD, now_local
                )
                new_value = round(daily_total_yield, 2) if daily_total_yield is not None else 0.0

                if hourly_breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = hourly_breakdown
                if meter_usage_data:
                    attributes[ATTR_MONTHLY_KWH_PRODUCTION] = meter_usage_data.get(USAGE_MONTHLY_RAE) 
                    attributes[ATTR_MONTHLY_PLN_YIELD] = meter_usage_data.get(USAGE_MONTHLY_RAE_YIELD) 

            elif self._sensor_key == SENSOR_CONSUMPTION_DAILY_KWH:
                usage_frames = meter_usage_data.get("frames") if meter_usage_data else None
                daily_kwh, hourly_breakdown = self._aggregate_hourly_data_for_day(
                    usage_frames, USAGE_FRAME_FAE_KWH, now_local
                )
                new_value = round(daily_kwh, 3) if daily_kwh is not None else 0.0
                if hourly_breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = hourly_breakdown

            elif self._sensor_key == SENSOR_PRODUCTION_DAILY_KWH:
                usage_frames = meter_usage_data.get("frames") if meter_usage_data else None
                daily_kwh, hourly_breakdown = self._aggregate_hourly_data_for_day(
                    usage_frames, USAGE_FRAME_RAE_KWH, now_local
                )
                new_value = round(daily_kwh, 3) if daily_kwh is not None else 0.0
                if hourly_breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = hourly_breakdown

            elif self._sensor_key == SENSOR_BILLING_BALANCE_MONTHLY_PLN:
                cost_frames = meter_cost_data.get("frames") if meter_cost_data else None
                new_value, current_breakdown = self._aggregate_daily_data(
                    cost_frames, COST_FRAME_ENERGY_BALANCE_VALUE, now_local
                )
                if current_breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = current_breakdown

            elif self._sensor_key == SENSOR_ENERGY_BALANCE_MONTHLY_KWH:
                usage_frames = meter_usage_data.get("frames") if meter_usage_data else None
                new_value, current_breakdown = self._aggregate_daily_data(
                    usage_frames, USAGE_ENERGY_BALANCE, now_local
                )
                if current_breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = current_breakdown

            elif self._sensor_key == SENSOR_BILLING_BALANCE_DAILY_PLN:
                cost_frames = meter_cost_data.get("frames") if meter_cost_data else None
                new_value, hourly_breakdown = self._aggregate_hourly_data_for_day(
                    cost_frames, COST_FRAME_ENERGY_BALANCE_VALUE, now_local 
                )
                if hourly_breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = hourly_breakdown
            
            elif self._sensor_key == SENSOR_ENERGY_BALANCE_DAILY_KWH:
                usage_frames = meter_usage_data.get("frames") if meter_usage_data else None
                new_value, hourly_breakdown = self._aggregate_hourly_data_for_day(
                    usage_frames, USAGE_ENERGY_BALANCE, now_local
                )
                if hourly_breakdown:
                    attributes[ATTR_HOURLY_BREAKDOWN_CURRENT_DAY] = hourly_breakdown

            elif self._sensor_key == SENSOR_CONSUMPTION_MONTHLY_KWH:
                usage_frames = meter_usage_data.get("frames") if meter_usage_data else None
                new_value, current_breakdown = self._aggregate_daily_data(
                    usage_frames, USAGE_FRAME_FAE_KWH, now_local
                )
                if current_breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = current_breakdown

            elif self._sensor_key == SENSOR_PRODUCTION_MONTHLY_KWH:
                usage_frames = meter_usage_data.get("frames") if meter_usage_data else None
                new_value, current_breakdown = self._aggregate_daily_data(
                    usage_frames, USAGE_FRAME_RAE_KWH, current_month_dt # Główna wartość dla bieżącego miesiąca
                )
                if current_breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = current_breakdown
                
                # Oblicz sumę dla poprzedniego miesiąca
                last_month_total_kwh, _ = self._aggregate_daily_data(
                    usage_frames, USAGE_FRAME_RAE_KWH, previous_month_target_dt
                )
                if last_month_total_kwh is not None:
                    attributes[ATTR_LAST_MONTH_VALUE] = round(last_month_total_kwh, 3)

            elif self._sensor_key == SENSOR_CONSUMPTION_MONTHLY_COST_PLN:
                cost_frames = meter_cost_data.get("frames") if meter_cost_data else None
                new_value, current_breakdown = self._aggregate_daily_data(
                    cost_frames, COST_FRAME_FAE_COST, current_month_dt # Główna wartość dla bieżącego miesiąca
                )
                if current_breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = current_breakdown

            elif self._sensor_key == SENSOR_PRODUCTION_MONTHLY_YIELD_PLN:
                cost_frames = meter_cost_data.get("frames") if meter_cost_data else None
                new_value, current_breakdown = self._aggregate_daily_data(
                    cost_frames, COST_FRAME_RAE_YIELD, current_month_dt # Główna wartość dla bieżącego miesiąca
                )
                if current_breakdown:
                    attributes[ATTR_DAILY_BREAKDOWN_CURRENT_MONTH] = current_breakdown

                # Oblicz sumę dla poprzedniego miesiąca
                last_month_total_pln, _ = self._aggregate_daily_data(
                    cost_frames, COST_FRAME_RAE_YIELD, previous_month_target_dt
                )
                if last_month_total_pln is not None:
                    attributes[ATTR_LAST_MONTH_VALUE] = round(last_month_total_pln, 2)

            _LOGGER.debug(f"({self.name}) Przed ustawieniem _attr_native_value, new_value: '{new_value}' (typ: {type(new_value)})")
            self._attr_native_value = new_value

            if self._sensor_key in [SENSOR_TOMORROW_PURCHASE_PRICE, SENSOR_TOMORROW_SALE_PRICE] and new_value is None:
                attributes.pop(ATTR_PRICE_TOMORROW, None)
                attributes.pop(f"{ATTR_AVERAGE_PRICE}_tomorrow", None)
            self._attr_extra_state_attributes = {k: v for k, v in attributes.items() if v is not None and (not isinstance(v, list) or v)}

        except Exception as e: # pragma: no cover
            _LOGGER.error(f"({self.name}) Błąd podczas aktualizacji stanu ({self._sensor_key}): {e}", exc_info=True)
            self._attr_native_value = None
            self._attr_extra_state_attributes = {
                ATTR_DATA_TIMESTAMP: last_api_update,
                ATTR_DATA_STATUS_MESSAGE: f"Błąd podczas aktualizacji: {e}"
            }

        _LOGGER.info(f"Sensor: {self.name}, Stan końcowy: {self._attr_native_value}, Liczba atrybutów: {len(self._attr_extra_state_attributes)}")
