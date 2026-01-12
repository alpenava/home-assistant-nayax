"""Config flow for Nayax integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NayaxApiClient, NayaxAuthError, NayaxConnectionError
from .const import (
    CONF_ACTOR_ID,
    CONF_API_TOKEN,
    CONF_FIRST_DAY_OF_WEEK,
    CONF_INCLUDE_RAW_DATA,
    CONF_POLL_INTERVAL,
    DEFAULT_FIRST_DAY_OF_WEEK,
    DEFAULT_INCLUDE_RAW_DATA,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    WEEKDAY_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACTOR_ID): str,
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
        vol.Optional(CONF_FIRST_DAY_OF_WEEK, default="monday"): vol.In(
            list(WEEKDAY_OPTIONS.keys())
        ),
    }
)


class NayaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nayax."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if we already have this actor configured
            await self.async_set_unique_id(user_input[CONF_ACTOR_ID])
            self._abort_if_unique_id_configured()

            # Validate credentials by attempting to fetch machines
            session = async_get_clientsession(self.hass)
            client = NayaxApiClient(
                actor_id=user_input[CONF_ACTOR_ID],
                api_token=user_input[CONF_API_TOKEN],
                session=session,
            )

            try:
                machines = await client.get_machines()
                _LOGGER.debug("Found %d machines", len(machines))
            except NayaxAuthError:
                errors["base"] = "invalid_auth"
            except NayaxConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config validation")
                errors["base"] = "unknown"
            else:
                # Create a descriptive title
                title = f"Nayax ({user_input[CONF_ACTOR_ID]})"

                # Convert weekday name to number
                first_dow_name = user_input.get(CONF_FIRST_DAY_OF_WEEK, "monday")
                first_dow_value = WEEKDAY_OPTIONS.get(first_dow_name, DEFAULT_FIRST_DAY_OF_WEEK)

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ACTOR_ID: user_input[CONF_ACTOR_ID],
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    },
                    options={
                        CONF_POLL_INTERVAL: user_input.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                        CONF_FIRST_DAY_OF_WEEK: first_dow_value,
                        CONF_INCLUDE_RAW_DATA: DEFAULT_INCLUDE_RAW_DATA,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return NayaxOptionsFlow()


class NayaxOptionsFlow(OptionsFlow):
    """Handle options flow for Nayax."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Convert weekday name to number if provided as string
            first_dow = user_input.get(CONF_FIRST_DAY_OF_WEEK)
            if isinstance(first_dow, str):
                user_input[CONF_FIRST_DAY_OF_WEEK] = WEEKDAY_OPTIONS.get(
                    first_dow, DEFAULT_FIRST_DAY_OF_WEEK
                )
            return self.async_create_entry(title="", data=user_input)

        # Get current first day of week value and convert to name for display
        current_first_dow = self.config_entry.options.get(
            CONF_FIRST_DAY_OF_WEEK, DEFAULT_FIRST_DAY_OF_WEEK
        )
        # Convert number back to name for the dropdown
        current_first_dow_name = "monday"
        for name, value in WEEKDAY_OPTIONS.items():
            if value == current_first_dow:
                current_first_dow_name = name
                break

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                    vol.Optional(
                        CONF_INCLUDE_RAW_DATA,
                        default=self.config_entry.options.get(
                            CONF_INCLUDE_RAW_DATA, DEFAULT_INCLUDE_RAW_DATA
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_FIRST_DAY_OF_WEEK,
                        default=current_first_dow_name,
                    ): vol.In(list(WEEKDAY_OPTIONS.keys())),
                }
            ),
        )

