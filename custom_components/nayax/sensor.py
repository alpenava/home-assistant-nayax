"""Sensor platform for Nayax integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SENSOR_TYPE_LAST_SALE_AMOUNT,
    SENSOR_TYPE_LAST_SALE_PRODUCT,
    SENSOR_TYPE_LAST_SALE_TIME,
    SENSOR_TYPE_LAST_TRANSACTION_ID,
)
from .coordinator import NayaxCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NayaxSensorEntityDescription(SensorEntityDescription):
    """Describes a Nayax sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSOR_DESCRIPTIONS: tuple[NayaxSensorEntityDescription, ...] = (
    NayaxSensorEntityDescription(
        key=SENSOR_TYPE_LAST_SALE_AMOUNT,
        name="Last Sale Amount",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash",
        value_fn=lambda data: data.get("amount"),
    ),
    NayaxSensorEntityDescription(
        key=SENSOR_TYPE_LAST_SALE_PRODUCT,
        name="Last Sale Product",
        icon="mdi:food",
        value_fn=lambda data: data.get("product_name"),
    ),
    NayaxSensorEntityDescription(
        key=SENSOR_TYPE_LAST_SALE_TIME,
        name="Last Sale Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda data: _parse_timestamp(data.get("timestamp")),
    ),
    NayaxSensorEntityDescription(
        key=SENSOR_TYPE_LAST_TRANSACTION_ID,
        name="Last Transaction ID",
        icon="mdi:identifier",
        value_fn=lambda data: data.get("transaction_id"),
    ),
)


def _parse_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse a timestamp string to datetime.

    Args:
        timestamp_str: Timestamp string from the API.

    Returns:
        Parsed datetime or None if parsing fails.
    """
    if not timestamp_str:
        return None

    # Try different timestamp formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

    _LOGGER.warning("Could not parse timestamp: %s", timestamp_str)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nayax sensors from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.
        async_add_entities: Callback to add entities.
    """
    coordinator: NayaxCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[NayaxSensor] = []

    # Create sensors for each machine
    for machine_id, machine_info in coordinator.machines.items():
        for description in SENSOR_DESCRIPTIONS:
            entities.append(
                NayaxSensor(
                    coordinator=coordinator,
                    description=description,
                    machine_id=machine_id,
                    machine_name=machine_info.get("name", f"Machine {machine_id}"),
                )
            )

    async_add_entities(entities)

    _LOGGER.debug(
        "Added %d sensors for %d machines",
        len(entities),
        len(coordinator.machines),
    )


class NayaxSensor(CoordinatorEntity[NayaxCoordinator], SensorEntity):
    """Representation of a Nayax sensor."""

    entity_description: NayaxSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NayaxCoordinator,
        description: NayaxSensorEntityDescription,
        machine_id: str,
        machine_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator.
            description: Sensor description.
            machine_id: The machine ID.
            machine_name: The machine display name.
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._machine_id = machine_id
        self._machine_name = machine_name

        # Create unique ID
        self._attr_unique_id = f"{DOMAIN}_{machine_id}_{description.key}"

        # Set entity name (will be combined with device name)
        self._attr_name = description.name

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info to link this entity to the machine device."""
        return {
            "identifiers": {(DOMAIN, self._machine_id)},
            "name": self._machine_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        sale_data = self.coordinator.get_last_sale(self._machine_id)
        if sale_data is None:
            return None
        return self.entity_description.value_fn(sale_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        sale_data = self.coordinator.get_last_sale(self._machine_id)
        if sale_data is None:
            return None

        # Only add extra attributes for the amount sensor to avoid duplication
        if self.entity_description.key == SENSOR_TYPE_LAST_SALE_AMOUNT:
            return {
                "currency": sale_data.get("currency", "EUR"),
                "payment_method": sale_data.get("payment_method"),
                "product": sale_data.get("product_name"),
                "transaction_id": sale_data.get("transaction_id"),
            }

        return None

