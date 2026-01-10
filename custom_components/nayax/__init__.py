"""The Nayax Vending Machines integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NayaxApiClient
from .const import (
    CONF_ACTOR_ID,
    CONF_API_TOKEN,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import NayaxCoordinator

_LOGGER = logging.getLogger(__name__)

# No platforms needed for MVP - we only fire events
# Can add Platform.SENSOR here later for phase 2
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nayax from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.

    Returns:
        True if setup was successful.
    """
    hass.data.setdefault(DOMAIN, {})

    # Get configuration
    actor_id = entry.data[CONF_ACTOR_ID]
    api_token = entry.data[CONF_API_TOKEN]
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    _LOGGER.debug(
        "Setting up Nayax integration for actor %s with poll interval %ds",
        actor_id,
        poll_interval,
    )

    # Create API client with shared session
    session = async_get_clientsession(hass)
    client = NayaxApiClient(
        actor_id=actor_id,
        api_token=api_token,
        session=session,
    )

    # Create coordinator
    coordinator = NayaxCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        poll_interval=poll_interval,
    )

    # Perform initial data fetch (discovers machines)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for access by platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    # Set up platforms (none for MVP)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    _LOGGER.info(
        "Nayax integration setup complete. Monitoring %d machines.",
        len(coordinator.machines),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being unloaded.

    Returns:
        True if unload was successful.
    """
    _LOGGER.debug("Unloading Nayax integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up stored data
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # Clean up domain data if no entries remain
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_options_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update.

    Args:
        hass: Home Assistant instance.
        entry: Config entry that was updated.
    """
    _LOGGER.debug("Options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)

