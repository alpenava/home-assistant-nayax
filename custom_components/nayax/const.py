"""Constants for the Nayax integration."""

from typing import Final

DOMAIN: Final = "nayax"

# API endpoints
API_BASE_URL: Final = "https://lynx.nayax.com"
API_MACHINES_ENDPOINT: Final = "/v1/machines"
API_LAST_SALES_ENDPOINT: Final = "/operational/v1/machines/{machine_id}/lastSales"

# Configuration keys
CONF_ACTOR_ID: Final = "actor_id"
CONF_API_TOKEN: Final = "api_token"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_INCLUDE_RAW_DATA: Final = "include_raw_data"
CONF_FIRST_DAY_OF_WEEK: Final = "first_day_of_week"

# Default values
DEFAULT_POLL_INTERVAL: Final = 30  # seconds
DEFAULT_MACHINE_DISCOVERY_INTERVAL: Final = 300  # 5 minutes
DEFAULT_INCLUDE_RAW_DATA: Final = True  # Include raw transaction in events
DEFAULT_FIRST_DAY_OF_WEEK: Final = 0  # Monday (0=Mon, 6=Sun)

# First day of week options (value = Python weekday, 0=Monday, 6=Sunday)
WEEKDAY_OPTIONS: Final = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# Event names
EVENT_NAYAX_SALE: Final = "nayax_sale"

# Manufacturer info
MANUFACTURER: Final = "Nayax"
MODEL: Final = "Vending Machine"

# Sensor types - Last sale (existing)
SENSOR_TYPE_LAST_SALE_AMOUNT: Final = "last_sale_amount"
SENSOR_TYPE_LAST_SALE_PRODUCT: Final = "last_sale_product"
SENSOR_TYPE_LAST_SALE_TIME: Final = "last_sale_time"
SENSOR_TYPE_LAST_TRANSACTION_ID: Final = "last_transaction_id"

# Sensor types - Period totals (amount)
SENSOR_TYPE_SALES_TODAY: Final = "sales_today"
SENSOR_TYPE_SALES_THIS_WEEK: Final = "sales_this_week"
SENSOR_TYPE_SALES_THIS_MONTH: Final = "sales_this_month"
SENSOR_TYPE_SALES_LAST_WEEK: Final = "sales_last_week"
SENSOR_TYPE_SALES_LAST_MONTH: Final = "sales_last_month"
SENSOR_TYPE_SALES_6_MONTHS: Final = "sales_6_months"
SENSOR_TYPE_SALES_THIS_YEAR: Final = "sales_this_year"
SENSOR_TYPE_SALES_LAST_YEAR: Final = "sales_last_year"

# Sensor types - Period totals (count)
SENSOR_TYPE_SALES_TODAY_COUNT: Final = "sales_today_count"
SENSOR_TYPE_SALES_THIS_WEEK_COUNT: Final = "sales_this_week_count"
SENSOR_TYPE_SALES_THIS_MONTH_COUNT: Final = "sales_this_month_count"
SENSOR_TYPE_SALES_LAST_WEEK_COUNT: Final = "sales_last_week_count"
SENSOR_TYPE_SALES_LAST_MONTH_COUNT: Final = "sales_last_month_count"
SENSOR_TYPE_SALES_6_MONTHS_COUNT: Final = "sales_6_months_count"
SENSOR_TYPE_SALES_THIS_YEAR_COUNT: Final = "sales_this_year_count"
SENSOR_TYPE_SALES_LAST_YEAR_COUNT: Final = "sales_last_year_count"

# Attribution
ATTRIBUTION: Final = "Data provided by Nayax Lynx API"

