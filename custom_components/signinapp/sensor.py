"""Sensor platform for Sign In App."""
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1) # Check every minute

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sign In App sensor."""
    _LOGGER.debug("Setting up Sign In App sensor for entry: %s", entry.entry_id)
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    async def async_update_data():
        """Fetch data from API."""
        _LOGGER.debug("Fetching sensor data from API")
        try:
            data = await api.get_config()
            _LOGGER.debug("Sensor data fetched successfully")
            return data
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="signinapp_sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([SignInAppSensor(coordinator, entry)], True)

class SignInAppSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sign In App Sensor."""

    _attr_translation_key = "status"
    _attr_has_entity_name = True
    _attr_icon = "mdi:account-badge"

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entry = entry

        # Use entry.unique_id if available (Visitor ID), else fallback to entry_id
        unique_id_base = entry.unique_id if entry.unique_id else entry.entry_id
        self._attr_unique_id = f"{unique_id_base}_status"
        self._attr_name = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        returning_visitor = data.get("returningVisitor")
        if returning_visitor:
            status = returning_visitor.get("status")
            if status:
                return status.lower()
        return "unknown"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        returning_visitor = data.get("returningVisitor")
        if not returning_visitor:
            return {}

        return {
            "last_in": returning_visitor.get("lastIn"),
            "last_out": returning_visitor.get("lastOut"),
            "site_id": returning_visitor.get("siteId"),
            "name": returning_visitor.get("name"),
            "group_id": returning_visitor.get("groupId"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self.coordinator.data
        name = "Sign In App"
        if data and "returningVisitor" in data:
             name = data["returningVisitor"].get("name", name)

        # Use entry.unique_id if available, else fallback to entry_id
        identifier_id = self.entry.unique_id if self.entry.unique_id else self.entry.entry_id

        return DeviceInfo(
            identifiers={(DOMAIN, identifier_id)},
            name=name,
            manufacturer="Sign In App",
        )
