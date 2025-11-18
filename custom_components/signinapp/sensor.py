from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT_SITE,
    ATTR_STATE,
    ATTR_STATUS_COLOR,
    ATTR_STATUS_NAME,
    CONF_VISITOR_NAME,
    DATA_COORDINATOR,
    DATA_ENTITY_MAP,
    DOMAIN,
)
from . import derive_sensor_state


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    sensor = SignInAppStatusSensor(coordinator, entry)
    async_add_entities([sensor])


class SignInAppStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:badge-account"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        name = entry.data.get(CONF_VISITOR_NAME) or entry.title
        self._attr_name = f"Sign In App {name}" if not name.lower().startswith("sign in app") else name
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        data = derive_sensor_state(self.coordinator.data or {})
        return {
            ATTR_CURRENT_SITE: data.get(ATTR_CURRENT_SITE),
            ATTR_STATUS_NAME: data.get(ATTR_STATUS_NAME),
            ATTR_STATUS_COLOR: data.get(ATTR_STATUS_COLOR),
        }

    @property
    def native_value(self) -> Any:
        data = derive_sensor_state(self.coordinator.data or {})
        return data.get(ATTR_STATE)

    @property
    def device_info(self) -> DeviceInfo:
        name = self._entry.data.get(CONF_VISITOR_NAME) or self._entry.title
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=name,
            manufacturer="Sign In App",
            model="Companion Device",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        entity_map = self.hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
        entity_map[self.entity_id] = self._entry.entry_id

    async def async_will_remove_from_hass(self) -> None:
        entity_map = self.hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
        entity_map.pop(self.entity_id, None)
        await super().async_will_remove_from_hass()
