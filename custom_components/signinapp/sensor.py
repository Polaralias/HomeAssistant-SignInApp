"""Sensor platform for SignInApp."""

from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BASE_URL, DATA_COORDINATOR, DATA_ENTITY_MAP, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SignInApp sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    sensor = SignInAppStatusSensor(coordinator, entry)
    async_add_entities([sensor])


class SignInAppStatusSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SignInApp status sensor."""

    _attr_icon = "mdi:badge-account"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = f"{entry.title} Status"
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        data = self.coordinator.data or {}
        return {k: v for k, v in data.items() if k != "state"}

    @property
    def native_value(self) -> Any:
        return (self.coordinator.data or {}).get("state")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="SignInApp",
            model=self._entry.data.get(CONF_BASE_URL, "Cloud"),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        entity_map = self.hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
        entity_map[self.entity_id] = self._entry.entry_id

    async def async_will_remove_from_hass(self) -> None:
        entity_map = self.hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
        entity_map.pop(self.entity_id, None)
        await super().async_will_remove_from_hass()

