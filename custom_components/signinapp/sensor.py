"""Sensor platform for Sign In App."""
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    async def async_update_data():
        """Fetch data from API."""
        try:
            data = await api.get_config()
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="signinapp_sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([SignInAppSensor(coordinator, entry.entry_id)], True)

class SignInAppSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sign In App Sensor."""

    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Sign In App Status"
        self._attr_unique_id = f"{entry_id}_status"
        self._attr_icon = "mdi:account-badge"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # The PS script shows config-v2 returns `returningVisitor` object with `status`
        # "status": "signed_out"
        data = self.coordinator.data
        if not data:
            return None

        returning_visitor = data.get("returningVisitor")
        if returning_visitor:
            return returning_visitor.get("status")
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
