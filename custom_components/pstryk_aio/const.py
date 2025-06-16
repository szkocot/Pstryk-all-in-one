"""Stałe dla integracji Pstryk AIO."""

DOMAIN = "pstryk_aio"
PLATFORMS = ["sensor"] 
# --- Konfiguracja ---
CONF_API_KEY = "api_key" # Dla Klucza API
CONF_CHEAP_PURCHASE_PRICE_THRESHOLD = "cheap_purchase_price_threshold"
CONF_EXPENSIVE_PURCHASE_PRICE_THRESHOLD = "expensive_purchase_price_threshold"
CONF_CHEAP_SALE_PRICE_THRESHOLD = "cheap_sale_price_threshold"
CONF_EXPENSIVE_SALE_PRICE_THRESHOLD = "expensive_sale_price_threshold"

CONF_CHEAP_PRICE_THRESHOLD = "cheap_price_threshold" 
CONF_EXPENSIVE_PRICE_THRESHOLD = "expensive_price_threshold"
# Domyślne wartości
DEFAULT_NAME = "Pstryk AIO"
DEFAULT_UPDATE_INTERVAL_MINUTES = 15
DEFAULT_CHEAP_PURCHASE_PRICE_THRESHOLD = 0.40 
DEFAULT_EXPENSIVE_PURCHASE_PRICE_THRESHOLD = 0.80 
DEFAULT_CHEAP_SALE_PRICE_THRESHOLD = 0.20 
DEFAULT_EXPENSIVE_SALE_PRICE_THRESHOLD = 0.60 
DEFAULT_CHEAP_PRICE_THRESHOLD = 0.50 
DEFAULT_EXPENSIVE_PRICE_THRESHOLD = 1.00 
# Klucze dla koordynatora danych
COORDINATOR_KEY_MAIN = "main_data_coordinator" 
KEY_METER_DATA_USAGE = "meter_data_usage"
KEY_METER_DATA_COST = "meter_data_cost"
KEY_PRICING_DATA_PURCHASE_TODAY = "pricing_data_purchase_today"
KEY_PRICING_DATA_PURCHASE_TOMORROW = "pricing_data_purchase_tomorrow"
KEY_PRICING_DATA_PROSUMER_TODAY = "pricing_data_prosumer_today"
KEY_PRICING_DATA_PROSUMER_TOMORROW = "pricing_data_prosumer_tomorrow"
KEY_LAST_UPDATE = "last_api_update"
# API (api.pstryk.pl)
API_BASE_URL = "https://api.pstryk.pl" 
API_TIMEOUT = 20
# Ścieżki API dla endpointów /integrations/
API_METER_DATA_USAGE_PATH = "/integrations/meter-data/energy-usage/"
API_METER_DATA_COST_PATH = "/integrations/meter-data/energy-cost/"
API_PRICING_PATH = "/integrations/pricing/" 
API_PROSUMER_PRICING_PATH = "/integrations/prosumer-pricing/" 
# Nagłówki
DEFAULT_USER_AGENT = "Mozilla/5.0 (Home Assistant Pstryk AIO Integration v4 APIKeyBearer)"
API_REQUEST_HEADERS = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}


# --- Definicje sensorów ---
SENSOR_TODAY_PURCHASE_PRICE = "today_purchase_price" # Obecna cena zakupu (dziś)
SENSOR_TOMORROW_PURCHASE_PRICE = "tomorrow_purchase_price" # Pierwsza cena zakupu (jutro)
SENSOR_TODAY_SALE_PRICE = "today_sale_price" # Obecna cena sprzedaży (dziś)
SENSOR_TOMORROW_SALE_PRICE = "tomorrow_sale_price" # Pierwsza cena sprzedaży (jutro)
SENSOR_CONSUMPTION_DAILY_COST = "daily_consumption_cost" 
SENSOR_PRODUCTION_DAILY_YIELD = "daily_production_yield"
SENSOR_BILLING_BALANCE_MONTHLY_PLN = "billing_balance_monthly_pln"
SENSOR_ENERGY_BALANCE_MONTHLY_KWH = "energy_balance_monthly_kwh"
SENSOR_BILLING_BALANCE_DAILY_PLN = "billing_balance_daily_pln"
SENSOR_ENERGY_BALANCE_DAILY_KWH = "energy_balance_daily_kwh"
# Stałe dla sensorów dziennego zużycia/produkcji w kWh
SENSOR_CONSUMPTION_DAILY_KWH = "consumption_daily_kwh"
SENSOR_PRODUCTION_DAILY_KWH = "production_daily_kwh"
# Stałe dla sensorów miesięcznego zużycia/produkcji (kWh i PLN)
SENSOR_CONSUMPTION_MONTHLY_KWH = "consumption_monthly_kwh"
SENSOR_PRODUCTION_MONTHLY_KWH = "production_monthly_kwh"
SENSOR_CONSUMPTION_MONTHLY_COST_PLN = "consumption_monthly_cost_pln"
SENSOR_PRODUCTION_MONTHLY_YIELD_PLN = "production_monthly_yield_pln"

FRIENDLY_NAME_PURCHASE_PRICE = "Obecna cena zakupu prądu"  # Przywrócona nazwa
FRIENDLY_NAME_SALE_PRICE = "Obecna cena sprzedaży prądu"    # Przywrócona nazwa
FRIENDLY_NAME_CONSUMPTION_DAILY_COST = "Dzienne koszty zużycia energii"
FRIENDLY_NAME_PRODUCTION_DAILY_YIELD = "Dzienna wartość produkcji energii"
FRIENDLY_NAME_BILLING_BALANCE_MONTHLY_PLN = "Saldo rozliczeniowe miesięczne (PLN)" # Zmieniona nazwa
FRIENDLY_NAME_ENERGY_BALANCE_MONTHLY_KWH = "Saldo energetyczne miesięczne (kWh)"
FRIENDLY_NAME_BILLING_BALANCE_DAILY_PLN = "Saldo rozliczeniowe dzienne (PLN)"
FRIENDLY_NAME_ENERGY_BALANCE_DAILY_KWH = "Saldo energetyczne dzienne (kWh)"
FRIENDLY_NAME_CONSUMPTION_DAILY_KWH = "Dzienne zużycie energii (kWh)"
FRIENDLY_NAME_PRODUCTION_DAILY_KWH = "Dzienna produkcja energii (kWh)"
FRIENDLY_NAME_CONSUMPTION_MONTHLY_KWH = "Miesięczne zużycie energii (kWh)"
FRIENDLY_NAME_PRODUCTION_MONTHLY_KWH = "Miesięczna produkcja energii (kWh)"
FRIENDLY_NAME_CONSUMPTION_MONTHLY_COST_PLN = "Miesięczne koszty zużycia energii (PLN)"
FRIENDLY_NAME_PRODUCTION_MONTHLY_YIELD_PLN = "Miesięczna wartość produkcji energii (PLN)"
# Atrybuty dla sensorów cenowych
ATTR_PRICE_TODAY = "today_prices" 
ATTR_PRICE_TOMORROW = "tomorrow_prices" 
ATTR_PRICE_START_TIME = "start" 
ATTR_PRICE_END_TIME = "end"     
ATTR_PRICE_VALUE_NET = "price_net" 
ATTR_PRICE_VALUE_GROSS = "price_gross"
ATTR_PRICE_IS_CHEAP = "is_cheap"         # Flaga taniej ceny w ramce godzinowej
ATTR_PRICE_IS_EXPENSIVE = "is_expensive"   # Flaga drogiej ceny w ramce godzinowej
ATTR_PRICE_UNIT = "PLN/kWh" 
# Atrybuty dla sensorów zużycia/produkcji/kosztów
ATTR_DAILY_KWH_CONSUMPTION = "daily_kwh_consumption" 
ATTR_DAILY_KWH_PRODUCTION = "daily_kwh_production"  
ATTR_ENERGY_BALANCE_KWH = "energy_balance_kwh" 
ATTR_MONTHLY_KWH_CONSUMPTION = "monthly_kwh_consumption" 
ATTR_MONTHLY_KWH_PRODUCTION = "monthly_kwh_production"  
ATTR_MONTHLY_PLN_COST = "monthly_pln_cost" 
ATTR_MONTHLY_PLN_YIELD = "monthly_pln_yield" 
ATTR_HOURLY_COST_CONSUMPTION = "hourly_fae_cost" 
ATTR_HOURLY_YIELD_PRODUCTION = "hourly_energy_sold_value"
ATTR_DATA_TIMESTAMP = "data_timestamp"
ATTR_DAILY_BREAKDOWN_CURRENT_MONTH = "daily_breakdown_current_month"
ATTR_DAILY_BREAKDOWN_PREVIOUS_MONTH = "daily_breakdown_previous_month"
ATTR_HOURLY_BREAKDOWN_CURRENT_DAY = "hourly_breakdown_current_day"
ATTR_DATA_STATUS_MESSAGE = "data_status"
ATTR_AVERAGE_PRICE = "average_price" # Nowy atrybut dla średniej ceny
ATTR_LAST_MONTH_VALUE = "last_month_value" # Podsumowanie zeszłego miesiąca

USAGE_FAE_TOTAL = "fae_total_usage" 
USAGE_RAE_TOTAL = "rae_total" 
USAGE_ENERGY_BALANCE = "energy_balance" 
USAGE_MONTHLY_FAE = "monthly_fae_usage" 
USAGE_MONTHLY_RAE = "monthly_rae_usage" 
USAGE_MONTHLY_FAE_COST = "monthly_fae_cost" 
USAGE_MONTHLY_RAE_YIELD = "monthly_rae_yield" 
USAGE_FRAME_FAE_KWH = "fae_usage" 
USAGE_FRAME_RAE_KWH = "rae"
COST_FRAME_FAE_COST = "fae_cost"
COST_FRAME_RAE_YIELD = "energy_sold_value"
COST_FRAME_ENERGY_BALANCE_VALUE = "energy_balance_value"
 
