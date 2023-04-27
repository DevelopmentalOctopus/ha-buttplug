"""The Buttplug integration."""
from __future__ import annotations

import asyncio
from async_timeout import timeout
from buttplug.client import (
    ButtplugClient,
    ButtplugClientConnectorError,
    ButtplugClientDevice,
    ButtplugClientWebsocketConnector,
)
from buttplug.core.errors import ButtplugDeviceError, ButtplugHandshakeError
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from websockets.exceptions import ConnectionClosedError

from .const import (
    DATA_CLIENT,
    DATA_PLATFORM_SETUP,
    DOMAIN,
    EVENT_DEVICE_ADDED_TO_REGISTRY,
    LOGGER,
)

# from homeassistant.helpers.aiohttp_client import async_get_clientsession


# TODO device identifiers are being turned from a list with one string to lists of individual characters when the server is restarted via ui. need to see whether it happens on stop or start. With buttplug disabled, ui restart mangles the identifiers AND sets "disabled_by": "config_entry"
# TODO make a scanning-finished handler that restarts the scanning.

# TODO set appropriate log levels instead of all warning

# TODO setup auto-reconnecting when the buttplug server is stopped and started

CONNECT_TIMEOUT = 10
DATA_CLIENT_LISTEN_TASK = "client_listen_task"
DATA_START_PLATFORM_TASK = "start_platform_task"

DATA_KEY_NAME = "name"
DATA_KEY_SERVER = "server"

BUTTPLUG_CMD_VIBRATE = "VibrateCmd"
BUTTPLUG_CMD_ROTATE = "RotateCmd"
BUTTPLUG_CMD_LINEAR = "LinearCmd"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Buttplug component."""
    hass.data[DOMAIN] = {}
    return True


async def ping_buttplug(dev: ButtplugClientDevice) -> None:
    """Ping device."""
    allowed_messages = set(dev.allowed_messages.keys())
    if BUTTPLUG_CMD_ROTATE in allowed_messages:
        # Putting rotate first because it takes longer to activate
        await dev.send_rotate_cmd((0.1, True))
    if BUTTPLUG_CMD_LINEAR in allowed_messages:
        await dev.send_linear_cmd((300, 0.1))
    if BUTTPLUG_CMD_VIBRATE in allowed_messages:
        await dev.send_vibrate_cmd(0.1)
    await asyncio.sleep(0.3)
    if BUTTPLUG_CMD_ROTATE in allowed_messages:
        await dev.send_rotate_cmd((0.5, True))
    if BUTTPLUG_CMD_LINEAR in allowed_messages:
        await dev.send_linear_cmd((400, 0))
    if BUTTPLUG_CMD_VIBRATE in allowed_messages:
        await dev.send_vibrate_cmd(0.5)
    await asyncio.sleep(0.1)
    if BUTTPLUG_CMD_ROTATE in allowed_messages:
        await dev.send_rotate_cmd((0.1, True))
    if BUTTPLUG_CMD_LINEAR in allowed_messages:
        await dev.send_linear_cmd((200, 0))
    if BUTTPLUG_CMD_VIBRATE in allowed_messages:
        await dev.send_vibrate_cmd(0.1)
    await asyncio.sleep(0.3)
    await dev.send_stop_device_cmd()


@callback
def register_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    dev_reg: device_registry.DeviceRegistry,
    dev: ButtplugClientDevice,
) -> device_registry.DeviceEntry:
    """Register node in dev reg."""
    name = dev.name

    device = dev_reg.async_get_or_create(  # TODO not working as desired
        config_entry_id=entry.entry_id,
        identifiers={name},
        name=name,
        model=name,
        # suggested_area=UNDEFINED,
    )
    if (
        device.disabled
        and device.disabled_by != device_registry.DeviceEntryDisabler.USER
    ):
        dev_reg.async_update_device(device.id, disabled_by=None)

    async_dispatcher_send(hass, EVENT_DEVICE_ADDED_TO_REGISTRY, device)  # TODO needed?

    return device


async def device_added(
    hass: HomeAssistant,
    entry: ConfigEntry,
    dev_reg: device_registry.DeviceRegistry,
    dev: ButtplugClientDevice,
) -> None:
    """Add device to registry."""
    register_device(hass, entry, dev_reg, dev)
    LOGGER.warning("Device added: %s", dev.name)
    if dev.name not in ["WeVibe Moxie", "WeVibe Chorus"]:
        # Avoid pinging devices that have no real off button; they might vibrate while in storage.
        # TODO turn this into a user-configurable whitelist.
        hass.async_create_task(ping_buttplug(dev))


async def device_disconnected(
    dev_reg: device_registry.DeviceRegistry,
    dev_index: int,
    client: ButtplugClient,
    entry: ConfigEntry,
) -> None:
    """Disable disconnected device."""
    await prune_devices(dev_reg, client, entry)
    # dev_reg.async_update_device(
    #     dev.name, disabled_by=device_registry.DeviceEntryDisabler.INTEGRATION
    # )  # TODO use this when buttplug-py gives device object instead of int id.
    # LOGGER.info("Device removed: %s", dev.name)


async def prune_devices(
    dev_reg: device_registry.DeviceRegistry,
    client: ButtplugClient,
    entry: ConfigEntry,
) -> None:
    """Disable missing devices."""

    known_devices = device_registry.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    )
    connected_devices = [
        dev_reg.async_get_device({dev.name}) for dev in client.devices.values()
    ]

    # Devices that are in the device registry but which are not connected can be disabled
    for device in known_devices:
        if device not in connected_devices:
            if device.disabled_by == None:
                LOGGER.warning("Disabling disconnected device: %s", device.model)
                dev_reg.async_update_device(
                    device.id,
                    disabled_by=device_registry.DeviceEntryDisabler.INTEGRATION,
                )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Buttplug from a config entry."""

    # TODO use async_get_clientsession(hass). ButtplugClient would need to use aiohttp.ClientSession like in here https://github.com/home-assistant-libs/zwave-js-server-python/blob/master/zwave_js_server/client.py
    client = ButtplugClient(entry.data[DATA_KEY_NAME])
    address = entry.data[DATA_KEY_SERVER]
    connector = ButtplugClientWebsocketConnector(address)

    # connect and throw error if connection failed
    try:
        async with timeout(CONNECT_TIMEOUT):
            await client.connect(connector)
    except ButtplugClientConnectorError as err:
        raise ConfigEntryNotReady(
            f"Could not connect to buttplug server, exiting: {err.message}"
        ) from err
    except ButtplugHandshakeError as err:
        raise ConfigEntryNotReady(
            f"Handshake with buttplug server failed, exiting: {err.message}"
        ) from err
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err
    except Exception as err:
        LOGGER.exception(f"Exception while connecting to {address}")
        raise ConfigEntryNotReady(
            "Unexpected Exception when trying to connect."
        ) from err
    else:
        LOGGER.warning("Connected to Buttplug Server")

    platform_task = hass.async_create_task(start_platforms(hass, entry, client))
    hass.data[DOMAIN].setdefault(entry.entry_id, {})[
        DATA_START_PLATFORM_TASK
    ] = platform_task

    return True


async def start_platforms(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: ButtplugClient,
) -> None:
    """Start platforms and perform discovery."""
    entry_hass_data: dict = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry_hass_data[DATA_CLIENT] = client
    entry_hass_data[DATA_PLATFORM_SETUP] = {}

    async def handle_ha_shutdown(event: Event) -> None:
        """Handle HA shutdown."""
        LOGGER.warning("Handle HA shutdown")
        await disconnect_client(hass, entry)

    listen_task = hass.async_create_task(client_listen(hass, entry, client))
    entry_hass_data[DATA_CLIENT_LISTEN_TASK] = listen_task
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
    )

    LOGGER.warning("Connection to Buttplug Server initialized")

    await setup_driver(hass, entry, client)


async def setup_driver(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: ButtplugClient,
) -> None:
    """Set up devices using the ready driver."""
    dev_reg = device_registry.async_get(hass)
    entry_hass_data: dict = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    platform_setup_tasks = entry_hass_data[DATA_PLATFORM_SETUP]

    async def async_setup_platform(platform: str) -> None:
        """Set up platform if needed."""
        if platform not in platform_setup_tasks:
            platform_setup_tasks[platform] = hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )
        await platform_setup_tasks[platform]

    async def async_on_dev_added(dev: ButtplugClientDevice) -> None:
        """Handle dev added event."""
        await async_setup_platform(NUMBER_DOMAIN)
        async_dispatcher_send(
            hass, f"{DOMAIN}_{entry.entry_id}_add_{NUMBER_DOMAIN}", dev
        )

    def device_added_handler(emitter, dev: ButtplugClientDevice) -> None:
        hass.async_create_task(async_on_dev_added(dev))
        hass.async_create_task(device_added(hass, entry, dev_reg, dev))

    def device_removed_handler(emitter, dev: ButtplugClientDevice) -> None:
        hass.async_create_task(device_disconnected(dev_reg, dev, client, entry))

    known_devices = device_registry.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    )

    # LOGGER.warning("%s", known_devices)
    # LOGGER.warning("%s", [device.id for device in known_devices])
    # LOGGER.warning("%s", [device.identifiers for device in known_devices])
    for device in known_devices:
        # Spent a long time trying to figure out what is mangling identifiers. This workaround is functional though.
        dev_reg.async_update_device(device.id, new_identifiers={device.model})

    known_devices = device_registry.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    )

    # LOGGER.warning("%s", known_devices)
    # LOGGER.warning("%s", [device.id for device in known_devices])
    # LOGGER.warning("%s", [device.identifiers for device in known_devices])

    client.device_added_handler += device_added_handler
    client.device_removed_handler += device_removed_handler

    for device in client.devices.values():
        device_added_handler(None, device)

    await prune_devices(dev_reg, client, entry)


async def client_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: ButtplugClient,
) -> None:
    """Listen with the client."""

    await client.start_scanning()

    should_reload = True
    while should_reload:
        try:
            await hass.async_create_task(
                asyncio.sleep(7 * 24 * 60 * 60)
            )  # TODO figure out a better way to do this
        except asyncio.CancelledError:
            should_reload = False
            # LOGGER.warning("WASCANCELLED")
        except Exception as err:  # pylint: disable=broad-except
            # We need to guard against unknown exceptions to not crash this task.
            LOGGER.exception("Unexpected exception: %s", err)
            LOGGER.warning("Disconnected from server. Reloading integration")
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def disconnect_client(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Disconnect client."""
    # TODO this should be imported into config flow to simplify that.
    data = hass.data[DOMAIN][entry.entry_id]
    client: ButtplugClient = data[DATA_CLIENT]

    LOGGER.warning("Disconnecting Client...")
    try:
        await client.stop_scanning()
    except ButtplugDeviceError as err:
        if (
            err.message.error_message
            == '{"ButtplugDeviceError":"DeviceScanningAlreadyStopped"}'
        ):
            LOGGER.warning("Device scanning was already stopped.")
        else:
            raise
    except asyncio.CancelledError:
        LOGGER.warning("asyncio.CancelledError")
    except asyncio.exceptions.CancelledError:
        LOGGER.warning("asyncio.exceptions.CancelledError")
    except asyncio.exceptions.CancelledError:
        LOGGER.warning("asyncio.exceptions.CancelledError")
    except ConnectionClosedError:
        LOGGER.exception(
            "Failed to stop scanning; connection between Home Assistant and Buttplug server already closed."
        )

    # TODO handle other tasks and/or listeners as needed here
    listen_task: asyncio.Task = data[DATA_CLIENT_LISTEN_TASK]
    platform_task: asyncio.Task = data[DATA_START_PLATFORM_TASK]
    listen_task.cancel()
    platform_task.cancel()
    platform_setup_tasks = data.get(DATA_PLATFORM_SETUP, {}).values()
    for task in platform_setup_tasks:
        task.cancel()

    await asyncio.gather(listen_task, platform_task, *platform_setup_tasks)

    # TODO check what happens if already disconnected.

    # TODO stop all devices? probably should.
    LOGGER.warning("About to call client.disconnect()")
    try:
        await client.disconnect()
    except ConnectionClosedError:
        LOGGER.exception(
            "Failed to disconnect; connection between Home Assistant and Buttplug server already closed."
        )
    LOGGER.warning("Disconnected from Buttplug Server")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    info = hass.data[DOMAIN][entry.entry_id]

    tasks = []
    for platform, task in info[DATA_PLATFORM_SETUP].items():
        if task.done():
            tasks.append(
                hass.config_entries.async_forward_entry_unload(entry, platform)
            )
        else:
            task.cancel()
            tasks.append(task)

    unload_ok = all(await asyncio.gather(*tasks))

    if DATA_CLIENT_LISTEN_TASK in info:
        await disconnect_client(hass, entry)

    hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    return
