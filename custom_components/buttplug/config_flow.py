"""Config flow for Buttplug integration."""
from __future__ import annotations

import voluptuous as vol
from buttplug.client import (
    ButtplugClient,
    ButtplugClientConnectorError,
    ButtplugClientWebsocketConnector,
)
from buttplug.core.errors import ButtplugHandshakeError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from typing import Any

from .const import DEFAULT_NAME, DEFAULT_SERVER, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("name", default=DEFAULT_NAME): str,
    vol.Required("server", default=DEFAULT_SERVER): str
})

# TODO https://buttplug-developer-guide.docs.buttplug.io/cookbook/connector-setup-in-depth.html#buttplug-ping when supported


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, name: str, address: str) -> None:
        """Initialize."""
        self.name = name
        self.address = address

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        return True
        client = ButtplugClient(self.name)
        connector = ButtplugClientWebsocketConnector(self.address)
        # TODO should add listeners?
        # TODO make it clear what the exact address being used is in the errors.
        try:
            await client.connect(connector)
        except ButtplugClientConnectorError as error:
            raise CannotConnect(
                f"Could not connect to buttplug server, exiting: {error.message}"
            ) from error
        except ButtplugHandshakeError as error:
            raise CannotConnect(
                f"Handshake with buttplug server failed, exiting: {error.message}"
            ) from error
        except Exception as error:
            LOGGER.exception("Unexpected exception")
            raise CannotConnect(
                "Unexpected Exception when trying to connect."
            ) from error
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["name"], address
    # )
    # TODO check if buttplug is built with async as described above.
    # TODO possible to use existing websocket thing that would handle the lifecycle of the connection for me?

    hub = PlaceholderHub(data["name"], data["server"])

    if not await hub.authenticate():
        raise CannotConnect

    return {"title": f"Buttplug ({data['name']})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Buttplug."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        # await self.async_set_unique_id(user_input["address"]) # TODO when is user_input None? this would block addition of another instance. TODO need to use something else; per guidelines https://developers.home-assistant.io/docs/config_entries_config_flow_handler#example-acceptable-sources-for-a-unique-id
        # self._abort_if_unique_id_configured()
        # TODO add basic auth stuff? does it work with the port/websocket?

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


# TODO add quality_scale, supported_brands, dependencies, and after_dependencies to manifest.json?
# TODO add translations?
# TODO support https://developers.home-assistant.io/docs/config_entries_options_flow_handler
# TODO unique ID? can get mac of bluetooth adapter? wouldn't be totally unique.
