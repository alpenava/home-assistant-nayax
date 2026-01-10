"""Data coordinator for Nayax integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NayaxApiClient, NayaxApiError
from .const import (
    DEFAULT_MACHINE_DISCOVERY_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    EVENT_NAYAX_SALE,
    MANUFACTURER,
    MODEL,
)

_LOGGER = logging.getLogger(__name__)


class NayaxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for polling Nayax machines and sales."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NayaxApiClient,
        entry: ConfigEntry,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            client: Nayax API client.
            entry: Config entry.
            poll_interval: Polling interval in seconds.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.entry = entry
        self._machines: dict[str, dict[str, Any]] = {}
        self._last_transactions: dict[str, str] = {}
        self._last_sales_data: dict[str, dict[str, Any]] = {}
        self._last_machine_discovery: float = 0
        self._machine_discovery_interval = DEFAULT_MACHINE_DISCOVERY_INTERVAL

        # Load persisted last transactions from entry data
        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        """Load persisted state from config entry."""
        stored_transactions = self.entry.data.get("last_transactions", {})
        if isinstance(stored_transactions, dict):
            self._last_transactions = stored_transactions.copy()
            _LOGGER.debug(
                "Loaded %d persisted transaction IDs", len(self._last_transactions)
            )

        stored_sales = self.entry.data.get("last_sales_data", {})
        if isinstance(stored_sales, dict):
            self._last_sales_data = stored_sales.copy()
            _LOGGER.debug(
                "Loaded %d persisted last sale records", len(self._last_sales_data)
            )

    async def _persist_state(self) -> None:
        """Persist current state to config entry."""
        new_data = {
            **self.entry.data,
            "last_transactions": self._last_transactions,
            "last_sales_data": self._last_sales_data,
        }
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Nayax API.

        This method is called by the coordinator at the configured interval.
        It handles both machine discovery and sales polling.
        """
        try:
            # Check if we need to discover machines
            current_time = asyncio.get_event_loop().time()
            if (
                not self._machines
                or current_time - self._last_machine_discovery
                > self._machine_discovery_interval
            ):
                await self._discover_machines()
                self._last_machine_discovery = current_time

            # Poll sales for each machine
            await self._poll_all_sales()

            return {
                "machines": self._machines,
                "last_transactions": self._last_transactions,
                "last_sales_data": self._last_sales_data,
            }

        except NayaxApiError as err:
            raise UpdateFailed(f"Error communicating with Nayax API: {err}") from err

    async def _discover_machines(self) -> None:
        """Discover and register machines from the API."""
        _LOGGER.debug("Discovering machines")

        try:
            machines_data = await self.client.get_machines()
        except NayaxApiError as err:
            _LOGGER.error("Failed to discover machines: %s", err)
            return

        device_registry = dr.async_get(self.hass)
        new_machines: dict[str, dict[str, Any]] = {}

        for machine in machines_data:
            # Extract machine info - handle different API response formats
            machine_id = str(
                machine.get("MachineID")
                or machine.get("MachineId")
                or machine.get("machineId")
                or machine.get("id")
                or ""
            )

            if not machine_id:
                _LOGGER.warning("Machine without ID found, skipping: %s", machine)
                continue

            machine_name = (
                machine.get("MachineName")
                or machine.get("machineName")
                or machine.get("name")
                or f"Nayax Machine {machine_id}"
            )

            # Store machine data
            new_machines[machine_id] = {
                "id": machine_id,
                "name": machine_name,
                "raw": machine,
            }

            # Register device in Home Assistant
            device_registry.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, machine_id)},
                name=machine_name,
                manufacturer=MANUFACTURER,
                model=MODEL,
            )

            _LOGGER.debug("Registered machine: %s (%s)", machine_name, machine_id)

        # Log any removed machines
        removed = set(self._machines.keys()) - set(new_machines.keys())
        for machine_id in removed:
            _LOGGER.info(
                "Machine %s no longer found in API response",
                self._machines[machine_id].get("name", machine_id),
            )

        # Log any new machines
        added = set(new_machines.keys()) - set(self._machines.keys())
        for machine_id in added:
            _LOGGER.info(
                "New machine discovered: %s (%s)",
                new_machines[machine_id]["name"],
                machine_id,
            )

        self._machines = new_machines
        _LOGGER.debug("Machine discovery complete: %d machines", len(self._machines))

    async def _poll_all_sales(self) -> None:
        """Poll sales for all machines."""
        if not self._machines:
            _LOGGER.debug("No machines to poll")
            return

        for machine_id, machine_info in self._machines.items():
            await self._poll_machine_sales(machine_id, machine_info)

        # Persist state after polling
        await self._persist_state()

    async def _poll_machine_sales(
        self, machine_id: str, machine_info: dict[str, Any]
    ) -> None:
        """Poll sales for a specific machine.

        Args:
            machine_id: The machine ID.
            machine_info: Machine information dictionary.
        """
        try:
            sales = await self.client.get_last_sales(machine_id)
        except NayaxApiError as err:
            _LOGGER.warning(
                "Failed to get sales for machine %s: %s",
                machine_info.get("name", machine_id),
                err,
            )
            return

        if not sales:
            _LOGGER.debug("No sales data for machine %s", machine_id)
            return

        # Find the first successful transaction (SettlementValue > 0)
        successful_sale = None
        for sale in sales:
            settlement_value = self._get_settlement_value(sale)
            if settlement_value is not None and settlement_value > 0:
                successful_sale = sale
                break

        if successful_sale is None:
            _LOGGER.debug("No successful sales found for machine %s", machine_id)
            return

        # Get transaction ID
        transaction_id = str(
            successful_sale.get("TransactionID")
            or successful_sale.get("transactionId")
            or successful_sale.get("id")
            or ""
        )

        if not transaction_id:
            _LOGGER.warning("Transaction without ID found for machine %s", machine_id)
            return

        # Extract and store sale data for sensors (always, even if not new)
        sale_data = self._extract_sale_data(machine_id, machine_info, successful_sale)
        self._last_sales_data[machine_id] = sale_data

        # Check if this is a new transaction
        last_seen = self._last_transactions.get(machine_id)
        if last_seen == transaction_id:
            _LOGGER.debug(
                "No new transactions for machine %s (last: %s)",
                machine_id,
                transaction_id,
            )
            return

        # New transaction detected!
        _LOGGER.info(
            "New sale detected for %s: Transaction %s",
            machine_info.get("name", machine_id),
            transaction_id,
        )

        # Fire the event
        self._fire_sale_event(machine_id, machine_info, successful_sale)

        # Update last seen transaction
        self._last_transactions[machine_id] = transaction_id

    def _get_settlement_value(self, sale: dict[str, Any]) -> float | None:
        """Extract settlement value from a sale record.

        Args:
            sale: Sale data dictionary.

        Returns:
            Settlement value as float, or None if not found.
        """
        value = (
            sale.get("SettlementValue")
            or sale.get("settlementValue")
            or sale.get("amount")
        )

        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid settlement value: %s", value)
            return None

    def _extract_sale_data(
        self,
        machine_id: str,
        machine_info: dict[str, Any],
        sale: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract sale data for sensors.

        Args:
            machine_id: The machine ID.
            machine_info: Machine information dictionary.
            sale: Sale transaction data.

        Returns:
            Dictionary with extracted sale data.
        """
        transaction_id = str(
            sale.get("TransactionID")
            or sale.get("transactionId")
            or sale.get("id")
            or ""
        )

        amount = self._get_settlement_value(sale) or 0.0

        currency = (
            sale.get("Currency")
            or sale.get("currency")
            or sale.get("CurrencyCode")
            or "EUR"
        )

        product_name = (
            sale.get("ProductName")
            or sale.get("productName")
            or sale.get("Product")
            or sale.get("product")
            or "Unknown Product"
        )

        payment_method = (
            sale.get("PaymentMethod")
            or sale.get("paymentMethod")
            or sale.get("PaymentType")
            or sale.get("paymentType")
            or "Unknown"
        )

        timestamp = (
            sale.get("AuthorizationTimeGMT")
            or sale.get("authorizationTimeGmt")
            or sale.get("Timestamp")
            or sale.get("timestamp")
            or sale.get("DateTime")
            or sale.get("dateTime")
            or ""
        )

        return {
            "machine_id": machine_id,
            "machine_name": machine_info.get("name", f"Machine {machine_id}"),
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "product_name": product_name,
            "payment_method": payment_method,
            "timestamp": timestamp,
        }

    def _fire_sale_event(
        self,
        machine_id: str,
        machine_info: dict[str, Any],
        sale: dict[str, Any],
    ) -> None:
        """Fire a Home Assistant event for a new sale.

        Args:
            machine_id: The machine ID.
            machine_info: Machine information dictionary.
            sale: Sale transaction data.
        """
        # Get the already extracted sale data
        sale_data = self._last_sales_data.get(machine_id, {})

        event_data = {
            **sale_data,
            "raw": sale,
        }

        self.hass.bus.async_fire(EVENT_NAYAX_SALE, event_data)

        _LOGGER.debug(
            "Fired %s event: %s - %s %s for %s",
            EVENT_NAYAX_SALE,
            sale_data.get("machine_name", machine_id),
            sale_data.get("amount", 0),
            sale_data.get("currency", "EUR"),
            sale_data.get("product_name", "Unknown"),
        )

    @property
    def machines(self) -> dict[str, dict[str, Any]]:
        """Get the current machines."""
        return self._machines

    @property
    def last_sales_data(self) -> dict[str, dict[str, Any]]:
        """Get the last sale data for all machines."""
        return self._last_sales_data

    def get_last_sale(self, machine_id: str) -> dict[str, Any] | None:
        """Get the last sale data for a specific machine.

        Args:
            machine_id: The machine ID.

        Returns:
            Sale data dictionary or None if no data available.
        """
        return self._last_sales_data.get(machine_id)

