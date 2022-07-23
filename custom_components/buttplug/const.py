"""Constants for the Buttplug integration."""
import logging

DOMAIN = "buttplug"

DEFAULT_NAME = "Home Assistant"
DEFAULT_SERVER = "ws://localhost:12345"


DATA_CLIENT = "client"
DATA_PLATFORM_SETUP = "platform_setup"

EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"

LOGGER = logging.getLogger(__package__)
