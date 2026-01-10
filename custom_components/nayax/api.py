"""Nayax Lynx API client."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_LAST_SALES_ENDPOINT,
    API_MACHINES_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class NayaxApiError(Exception):
    """Base exception for Nayax API errors."""


class NayaxAuthError(NayaxApiError):
    """Authentication error."""


class NayaxConnectionError(NayaxApiError):
    """Connection error."""


class NayaxApiClient:
    """Async client for the Nayax Lynx API."""

    def __init__(
        self,
        actor_id: str,
        api_token: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            actor_id: The Nayax Actor ID.
            api_token: The Nayax API token.
            session: Optional aiohttp session to use.
        """
        self._actor_id = actor_id
        self._api_token = api_token
        self._session = session
        self._own_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for API requests."""
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request to the Nayax API.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            JSON response data.

        Raises:
            NayaxAuthError: If authentication fails.
            NayaxConnectionError: If connection fails.
            NayaxApiError: For other API errors.
        """
        session = await self._get_session()
        url = f"{API_BASE_URL}{endpoint}"

        try:
            async with session.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
            ) as response:
                if response.status == 401 or response.status == 403:
                    raise NayaxAuthError(
                        f"Authentication failed: {response.status}"
                    )

                if response.status == 429:
                    raise NayaxApiError("Rate limit exceeded")

                if response.status >= 400:
                    text = await response.text()
                    raise NayaxApiError(
                        f"API error {response.status}: {text}"
                    )

                return await response.json()

        except aiohttp.ClientError as err:
            raise NayaxConnectionError(f"Connection error: {err}") from err

    async def get_machines(self) -> list[dict[str, Any]]:
        """Get list of machines for the actor.

        Returns:
            List of machine data dictionaries.
        """
        _LOGGER.debug("Fetching machines list")
        response = await self._request("GET", API_MACHINES_ENDPOINT)

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "machines" in response:
            return response["machines"]
        if isinstance(response, dict) and "data" in response:
            return response["data"]

        _LOGGER.warning("Unexpected machines response format: %s", type(response))
        return []

    async def get_last_sales(self, machine_id: str) -> list[dict[str, Any]]:
        """Get last sales for a specific machine.

        Args:
            machine_id: The machine ID to get sales for.

        Returns:
            List of transaction data dictionaries, newest first.
        """
        endpoint = API_LAST_SALES_ENDPOINT.format(machine_id=machine_id)
        _LOGGER.debug("Fetching last sales for machine %s", machine_id)

        response = await self._request("GET", endpoint)

        # Handle different response formats
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "transactions" in response:
            return response["transactions"]
        if isinstance(response, dict) and "sales" in response:
            return response["sales"]
        if isinstance(response, dict) and "data" in response:
            return response["data"]

        _LOGGER.warning(
            "Unexpected sales response format for machine %s: %s",
            machine_id,
            type(response),
        )
        return []

    async def validate_connection(self) -> bool:
        """Validate the API connection and credentials.

        Returns:
            True if connection is valid.

        Raises:
            NayaxAuthError: If authentication fails.
            NayaxConnectionError: If connection fails.
        """
        await self.get_machines()
        return True

