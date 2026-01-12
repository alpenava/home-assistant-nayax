"""Data coordinator for Nayax integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NayaxApiClient, NayaxApiError
from .const import (
    CONF_FIRST_DAY_OF_WEEK,
    CONF_INCLUDE_RAW_DATA,
    DEFAULT_FIRST_DAY_OF_WEEK,
    DEFAULT_INCLUDE_RAW_DATA,
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
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.entry = entry
        self._machines: dict[str, dict[str, Any]] = {}
        self._last_machine_discovery: float = 0
        self._machine_discovery_interval = DEFAULT_MACHINE_DISCOVERY_INTERVAL

        # Transaction history for each machine
        # Structure: {machine_id: {transaction_id: {transaction_data}, ...}}
        self._transaction_history: dict[str, dict[str, dict[str, Any]]] = {}

        # Load persisted state from entry data
        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        """Load persisted state from config entry."""
        # Load new transaction history format
        stored_history = self.entry.data.get("transaction_history", {})
        if isinstance(stored_history, dict):
            self._transaction_history = stored_history.copy()
            total_tx = sum(len(txs) for txs in self._transaction_history.values())
            _LOGGER.debug(
                "Loaded %d transactions across %d machines",
                total_tx,
                len(self._transaction_history),
            )

        # Migration: convert old format to new format if needed
        self._migrate_old_data()

    def _migrate_old_data(self) -> None:
        """Migrate from old data format to new transaction history format."""
        old_sales_data = self.entry.data.get("last_sales_data", {})

        if not old_sales_data:
            return

        migrated_count = 0
        for machine_id, sale_data in old_sales_data.items():
            if not isinstance(sale_data, dict):
                continue

            transaction_id = sale_data.get("transaction_id")
            if not transaction_id:
                continue

            # Skip if we already have this transaction
            if machine_id in self._transaction_history:
                if transaction_id in self._transaction_history[machine_id]:
                    continue

            # Initialize machine history if needed
            if machine_id not in self._transaction_history:
                self._transaction_history[machine_id] = {}

            # Migrate the transaction
            self._transaction_history[machine_id][transaction_id] = sale_data
            migrated_count += 1

        if migrated_count > 0:
            _LOGGER.info(
                "Migrated %d transactions from old format to new history format",
                migrated_count,
            )

    async def _persist_state(self) -> None:
        """Persist current state to config entry."""
        new_data = {
            **self.entry.data,
            "transaction_history": self._transaction_history,
        }
        # Remove old format keys after migration
        new_data.pop("last_transactions", None)
        new_data.pop("last_sales_data", None)
        new_data.pop("period_totals", None)

        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Nayax API."""
        try:
            current_time = asyncio.get_event_loop().time()
            if (
                not self._machines
                or current_time - self._last_machine_discovery
                > self._machine_discovery_interval
            ):
                await self._discover_machines()
                self._last_machine_discovery = current_time

            await self._poll_all_sales()
            self._cleanup_old_transactions()

            return {
                "machines": self._machines,
                "transaction_history": self._transaction_history,
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

            new_machines[machine_id] = {
                "id": machine_id,
                "name": machine_name,
                "raw": machine,
            }

            device_registry.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, machine_id)},
                name=machine_name,
                manufacturer=MANUFACTURER,
                model=MODEL,
            )

            _LOGGER.debug("Registered machine: %s (%s)", machine_name, machine_id)

        removed = set(self._machines.keys()) - set(new_machines.keys())
        for machine_id in removed:
            _LOGGER.info(
                "Machine %s no longer found in API response",
                self._machines[machine_id].get("name", machine_id),
            )

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

        await self._persist_state()

    async def _poll_machine_sales(
        self, machine_id: str, machine_info: dict[str, Any]
    ) -> None:
        """Poll sales for a specific machine and process ALL transactions."""
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

        if machine_id not in self._transaction_history:
            self._transaction_history[machine_id] = {}

        machine_history = self._transaction_history[machine_id]
        new_transactions = 0
        updated_transactions = 0

        # Process ALL transactions from the response
        for sale in sales:
            settlement_value = self._get_settlement_value(sale)
            if settlement_value is None or settlement_value <= 0:
                continue

            transaction_id = str(
                sale.get("TransactionID")
                or sale.get("transactionId")
                or sale.get("id")
                or ""
            )

            if not transaction_id:
                _LOGGER.warning(
                    "Transaction without ID found for machine %s", machine_id
                )
                continue

            sale_data = self._extract_sale_data(machine_id, machine_info, sale)

            if transaction_id not in machine_history:
                # NEW transaction
                machine_history[transaction_id] = sale_data
                new_transactions += 1

                _LOGGER.info(
                    "New sale detected for %s: Transaction %s - %.2f %s",
                    machine_info.get("name", machine_id),
                    transaction_id,
                    sale_data.get("amount", 0),
                    sale_data.get("currency", "EUR"),
                )

                self._fire_sale_event(sale_data, sale)

            else:
                # EXISTING transaction - check if data changed
                existing = machine_history[transaction_id]
                if self._transaction_changed(existing, sale_data):
                    machine_history[transaction_id] = sale_data
                    updated_transactions += 1
                    _LOGGER.debug(
                        "Updated transaction %s for machine %s",
                        transaction_id,
                        machine_id,
                    )

        if new_transactions > 0 or updated_transactions > 0:
            _LOGGER.debug(
                "Machine %s: %d new, %d updated transactions",
                machine_id,
                new_transactions,
                updated_transactions,
            )

    def _transaction_changed(
        self, existing: dict[str, Any], new_data: dict[str, Any]
    ) -> bool:
        """Check if transaction data has changed."""
        fields_to_compare = ["amount", "product_name", "timestamp"]
        for field in fields_to_compare:
            if existing.get(field) != new_data.get(field):
                return True
        return False

    def _get_settlement_value(self, sale: dict[str, Any]) -> float | None:
        """Extract settlement value from a sale record."""
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
        """Extract sale data for storage and sensors."""
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
            sale.get("AuthorizationDateTimeGMT")
            or sale.get("authorizationDateTimeGmt")
            or sale.get("AuthorizationTimeGMT")
            or sale.get("authorizationTimeGmt")
            or sale.get("MachineAuthorizationTime")
            or sale.get("machineAuthorizationTime")
            or sale.get("SettlementDateTimeGMT")
            or sale.get("settlementDateTimeGmt")
            or sale.get("Timestamp")
            or sale.get("timestamp")
            or sale.get("DateTime")
            or sale.get("dateTime")
            or ""
        )

        site_name = sale.get("SiteName") or sale.get("siteName") or None

        return {
            "machine_id": machine_id,
            "machine_name": machine_info.get("name", f"Machine {machine_id}"),
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "product_name": product_name,
            "payment_method": payment_method,
            "timestamp": timestamp,
            "site_name": site_name,
        }

    def _fire_sale_event(
        self,
        sale_data: dict[str, Any],
        raw_sale: dict[str, Any],
    ) -> None:
        """Fire a Home Assistant event for a new sale."""
        event_data = {**sale_data}

        include_raw = self.entry.options.get(
            CONF_INCLUDE_RAW_DATA, DEFAULT_INCLUDE_RAW_DATA
        )
        if include_raw:
            event_data["raw"] = raw_sale

        self.hass.bus.async_fire(EVENT_NAYAX_SALE, event_data)

        _LOGGER.debug(
            "Fired %s event: %s - %s %s for %s",
            EVENT_NAYAX_SALE,
            sale_data.get("machine_name"),
            sale_data.get("amount", 0),
            sale_data.get("currency", "EUR"),
            sale_data.get("product_name", "Unknown"),
        )

    def _cleanup_old_transactions(self) -> None:
        """Remove transactions older than prior year start."""
        now = datetime.now(timezone.utc)
        cutoff_year = now.year - 1
        cutoff_date = datetime(cutoff_year, 1, 1, tzinfo=timezone.utc)

        total_removed = 0

        for machine_id in list(self._transaction_history.keys()):
            machine_txs = self._transaction_history[machine_id]
            to_remove = []

            for tx_id, tx_data in machine_txs.items():
                timestamp_str = tx_data.get("timestamp", "")
                if not timestamp_str:
                    continue

                tx_dt = self._parse_timestamp(timestamp_str)
                if tx_dt and tx_dt < cutoff_date:
                    to_remove.append(tx_id)

            for tx_id in to_remove:
                del machine_txs[tx_id]
                total_removed += 1

        if total_removed > 0:
            _LOGGER.info("Cleaned up %d old transactions", total_removed)

    def _parse_timestamp(self, timestamp_str: str) -> datetime | None:
        """Parse a timestamp string to datetime."""
        if not timestamp_str:
            return None

        try:
            ts = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    # -------------------------------------------------------------------------
    # Public Methods for Sensors
    # -------------------------------------------------------------------------

    def get_last_sale(self, machine_id: str) -> dict[str, Any] | None:
        """Get the most recent sale for a machine (by timestamp)."""
        if machine_id not in self._transaction_history:
            return None

        machine_txs = self._transaction_history[machine_id]
        if not machine_txs:
            return None

        latest_tx = None
        latest_dt = None

        for tx_data in machine_txs.values():
            timestamp_str = tx_data.get("timestamp", "")
            tx_dt = self._parse_timestamp(timestamp_str)

            if tx_dt is None:
                continue

            if latest_dt is None or tx_dt > latest_dt:
                latest_dt = tx_dt
                latest_tx = tx_data

        return latest_tx

    def get_period_total(
        self, machine_id: str, period: str
    ) -> dict[str, Any]:
        """Calculate period total from transaction history."""
        if machine_id not in self._transaction_history:
            return {"amount": 0.0, "count": 0}

        machine_txs = self._transaction_history[machine_id]
        if not machine_txs:
            return {"amount": 0.0, "count": 0}

        start_dt, end_dt = self._get_period_date_range(period)
        if start_dt is None:
            return {"amount": 0.0, "count": 0}

        total_amount = 0.0
        total_count = 0

        for tx_data in machine_txs.values():
            timestamp_str = tx_data.get("timestamp", "")
            tx_dt = self._parse_timestamp(timestamp_str)

            if tx_dt is None:
                continue

            if start_dt <= tx_dt < end_dt:
                total_amount += tx_data.get("amount", 0.0)
                total_count += 1

        return {"amount": round(total_amount, 2), "count": total_count}

    def _get_period_date_range(
        self, period: str
    ) -> tuple[datetime | None, datetime | None]:
        """Get start and end datetime for a period."""
        # Get current time in local timezone
        now_local = dt_util.now()
        first_dow = self.entry.options.get(
            CONF_FIRST_DAY_OF_WEEK, DEFAULT_FIRST_DAY_OF_WEEK
        )

        # Calculate today boundaries in local time, then convert to UTC
        today_start_local = dt_util.start_of_local_day()
        today_start = dt_util.as_utc(today_start_local)
        tomorrow_start = today_start + timedelta(days=1)
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start

        # Week calculations (based on local time)
        days_since_week_start = (now_local.weekday() - first_dow) % 7
        this_week_start_local = today_start_local - timedelta(days=days_since_week_start)
        this_week_start = dt_util.as_utc(this_week_start_local)
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start

        # Month calculations (based on local time)
        this_month_start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_start = dt_util.as_utc(this_month_start_local)
        
        if now_local.month == 1:
            last_month_start_local = now_local.replace(
                year=now_local.year - 1, month=12, day=1,
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            last_month_start_local = now_local.replace(
                month=now_local.month - 1, day=1,
                hour=0, minute=0, second=0, microsecond=0
            )
        last_month_start = dt_util.as_utc(last_month_start_local)
        last_month_end = this_month_start

        # Year calculations (based on local time)
        this_year_start_local = now_local.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        this_year_start = dt_util.as_utc(this_year_start_local)
        last_year_start_local = now_local.replace(
            year=now_local.year - 1, month=1, day=1,
            hour=0, minute=0, second=0, microsecond=0
        )
        last_year_start = dt_util.as_utc(last_year_start_local)
        last_year_end = this_year_start

        # 6 months rolling (based on local time)
        six_months_ago_local = now_local - timedelta(days=180)
        six_months_start_local = six_months_ago_local.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        six_months_start = dt_util.as_utc(six_months_start_local)

        period_ranges = {
            "today": (today_start, tomorrow_start),
            "yesterday": (yesterday_start, yesterday_end),
            "this_week": (this_week_start, tomorrow_start),
            "this_month": (this_month_start, tomorrow_start),
            "this_year": (this_year_start, tomorrow_start),
            "last_week": (last_week_start, last_week_end),
            "last_month": (last_month_start, last_month_end),
            "last_year": (last_year_start, last_year_end),
            "6_months": (six_months_start, tomorrow_start),
        }

        return period_ranges.get(period, (None, None))

    @property
    def machines(self) -> dict[str, dict[str, Any]]:
        """Get the current machines."""
        return self._machines

    @property
    def transaction_history(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Get the transaction history for all machines."""
        return self._transaction_history

    # Backwards compatibility
    @property
    def last_sales_data(self) -> dict[str, dict[str, Any]]:
        """Get the last sale data for all machines (deprecated)."""
        result = {}
        for machine_id in self._transaction_history:
            last_sale = self.get_last_sale(machine_id)
            if last_sale:
                result[machine_id] = last_sale
        return result

    @property
    def period_totals(self) -> dict[str, dict[str, Any]]:
        """Get period totals (deprecated, calculated on demand now)."""
        return {}
