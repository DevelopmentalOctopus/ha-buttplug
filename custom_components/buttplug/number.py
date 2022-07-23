"""Support for Buttplug controls using the number platform."""
from __future__ import annotations

from websockets.exceptions import ConnectionClosedError

from buttplug.client import (
    ButtplugClient,
    ButtplugClientConnectorError,
    ButtplugClientDevice,
    ButtplugClientWebsocketConnector,
)

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN, LOGGER

PARALLEL_UPDATES = 0
BUTTPLUG_CMD_VIBRATE = "VibrateCmd"
BUTTPLUG_CMD_ROTATE = "RotateCmd"
BUTTPLUG_CMD_LINEAR = "LinearCmd"
CMD_TYPE_VIBRATE = "vibrate"
CMD_TYPE_ROTATE = "rotate"
CMD_TYPE_LINEAR = "linear"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Buttplug Number entity from Config Entry."""
    client: ButtplugClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_number(dev: ButtplugClientDevice) -> None:
        """Add Buttplug number entity."""
        entities: list[ButtplugNumberEntity] = []
        for message, attributes in dev.allowed_messages.items():
            handle = True  # TODO golf the section?
            if message == BUTTPLUG_CMD_VIBRATE:
                cmd_type = CMD_TYPE_VIBRATE
            elif message == BUTTPLUG_CMD_LINEAR:
                cmd_type = CMD_TYPE_LINEAR
            elif message == BUTTPLUG_CMD_ROTATE:
                cmd_type = CMD_TYPE_ROTATE
            else:
                handle = False
            if handle:
                sole_index = attributes.feature_count == 1
                for index in range(0, attributes.feature_count):
                    # LOGGER.info()
                    entities.append(
                        ButtplugNumberEntity(dev, cmd_type, index, sole_index)
                    )
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{NUMBER_DOMAIN}",
            async_add_number,
        )
    )


# TODO use inputnumber? https://github.com/home-assistant/core/blob/2022.6.7/homeassistant/components/input_number/__init__.py
class ButtplugNumberEntity(NumberEntity):
    """Representation of a Buttplug number entity."""

    # TODO allow user to batch commands instead of doing individually for diff motors.

    icon_mapping = {
        CMD_TYPE_VIBRATE: "mdi:vibrate",
        CMD_TYPE_ROTATE: "mdi:rotate-360",
        CMD_TYPE_LINEAR: "mdi:arrow-up-down",
    }

    def __init__(
        self,
        dev: ButtplugClientDevice,
        cmd_type: str,
        index: int,
        sole_index: bool = False,
    ) -> None:
        """Initialize a ButtplugNumberEntity entity."""
        self._dev = dev
        self._cmd_type = cmd_type
        self._index = index
        self._attr_value = 0
        self._attr_max_value = 100
        self._attr_min_value = -100 if cmd_type == CMD_TYPE_ROTATE else 0
        self._attr_mode = NumberMode.SLIDER
        self._attr_step = 1

        self._attr_device_info = DeviceInfo(identifiers={dev.name})

        # TODO start index at 1 for user-friendliness?
        base_id = f"{dev.name}_{cmd_type}"
        self._attr_unique_id = base_id if sole_index else f"{base_id}_{index}"

        # self._base_unique_id = f"{client.name}.{name}"

        # Entity class attributes
        self._attr_icon = self.icon_mapping[cmd_type]
        base_attr_name = f"{dev.name}: {cmd_type.title()}"
        self._attr_name = (
            base_attr_name if sole_index else f"{base_attr_name} ({index})"
        )  # TODO client name too?

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        internal_value = value / 100
        try:
            if self._cmd_type == CMD_TYPE_VIBRATE:
                await self._dev.send_vibrate_cmd({self._index: internal_value})
            elif self._cmd_type == CMD_TYPE_ROTATE:
                await self._dev.send_rotate_cmd(
                    {self._index: (abs(internal_value), internal_value >= 0)}
                )  # negative means opposite direction
            elif self._cmd_type == CMD_TYPE_LINEAR:
                # the device can move back and forth. We can call send_linear_cmd on the device
                # and it'll tell the server to make the device move to 90% of the
                # maximum position over 1 second (1000ms).
                await self._dev.send_linear_cmd(
                    {self._index: (1000, internal_value)}
                )  # TODO figure out how to set two numbers at once from the UI for this.
                # We wait 1 second for the move, then we move it back to the 0% position.
        except ConnectionClosedError:
            LOGGER.exception(
                "Failed to send command to device; connection between Home Assistant and Buttplug server already closed."
            )
            # TODO send signal to trigger reconnection?
        except Exception as err:
            LOGGER.exception(
                "Exception while sending %s (%s) command to %s: %s",
                self._cmd_type,
                internal_value,
                self._dev.name,
                err,
            )
        else:
            self._attr_value = value

    # async def async_added_to_hass(self) -> None:
    #     """Call when entity is added."""
    #     self.async_on_remove(
    #         async_dispatcher_connect(
    #             self.hass,
    #             f"{DOMAIN}_{self._base_unique_id}_remove_entity",
    #             self.async_remove,
    #         )
    #     )
