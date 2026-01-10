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

# Default values
DEFAULT_POLL_INTERVAL: Final = 30  # seconds
DEFAULT_MACHINE_DISCOVERY_INTERVAL: Final = 300  # 5 minutes

# Event names
EVENT_NAYAX_SALE: Final = "nayax_sale"

# Manufacturer info
MANUFACTURER: Final = "Nayax"
MODEL: Final = "Vending Machine"

# Sensor types
SENSOR_TYPE_LAST_SALE_AMOUNT: Final = "last_sale_amount"
SENSOR_TYPE_LAST_SALE_PRODUCT: Final = "last_sale_product"
SENSOR_TYPE_LAST_SALE_TIME: Final = "last_sale_time"
SENSOR_TYPE_LAST_TRANSACTION_ID: Final = "last_transaction_id"

# Attribution
ATTRIBUTION: Final = "Data provided by Nayax Lynx API"

