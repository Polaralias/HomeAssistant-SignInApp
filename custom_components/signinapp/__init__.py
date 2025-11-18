from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CURRENT_SITE,
    ATTR_STATE,
    ATTR_STATUS_COLOR,
    ATTR_STATUS_NAME,
    CONF_DEVICE_TRACKER,
    CONF_OFFICE_SITE,
    CONF_REMOTE_SITE,
    CONF_TOKEN,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_ENTITY_MAP,
    DATA_LISTENER,
    DEFAULT_BASE_URL,
    DOMAIN,
    PLATFORMS,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_IN_AUTO,
    SERVICE_SIGN_OUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
    if not hass.data[DOMAIN].get("services_registered"):
        register_services(hass)
        hass.data[DOMAIN]["services_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = SignInAppClient(hass, entry.data[CONF_TOKEN])
    coordinator = SignInAppCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    undo_listener = entry.add_update_listener(async_reload_entry)
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
        DATA_LISTENER: undo_listener,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        undo_listener = hass.data[DOMAIN][entry.entry_id][DATA_LISTENER]
        undo_listener()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


class SignInAppCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, client: SignInAppClient, entry: ConfigEntry) -> None:
        self.client = client
        self.entry = entry
        super().__init__(hass, _LOGGER, name=f"Sign In App {entry.title}", update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            data = await self.client.async_get_config()
            return data
        except ConfigEntryAuthFailed:
            raise
        except ClientError as err:
            raise UpdateFailed(f"Sign In App request failed: {err}") from err


class SignInAppClient:
    def __init__(self, hass: HomeAssistant, token: Optional[str] = None, base_url: str = DEFAULT_BASE_URL) -> None:
        self.hass = hass
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = async_get_clientsession(hass)

    @property
    def timezone(self) -> str:
        return self.hass.config.time_zone or "Europe/London"

    def update_token(self, token: str) -> None:
        self.token = token

    async def async_connect(self, code: str) -> Dict[str, Any]:
        url = f"{self.base_url}/connect"
        async with self.session.post(url, json={"code": code}, timeout=20) as resp:
            if resp.status != 200:
                raise HomeAssistantError("Invalid companion code")
            data = await resp.json()
        token = self._extract_token(data)
        if not token:
            raise HomeAssistantError("Token not found in response")
        self.token = token
        return data

    async def async_reconnect(self) -> Dict[str, Any]:
        return await self._request("GET", "/reconnect")

    async def async_get_config(self) -> Dict[str, Any]:
        return await self._request("GET", "/config-v2")

    async def async_sign_in(self, site_id: int, location: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "method": "sign-in",
            "automated": True,
            "location": location,
            "siteId": site_id,
            "additional": [],
            "personalFields": {},
            "notifyId": None,
            "messages": [],
        }
        return await self._request("POST", "/sign-in", payload)

    async def async_sign_out(self, site_id: int, location: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "automated": True,
            "location": location,
            "siteId": site_id,
            "additional": [],
            "personalFields": {},
            "notifyId": None,
            "messages": [],
        }
        return await self._request("POST", "/sign-out", payload)

    async def _request(self, method: str, path: str, json: Optional[dict] = None) -> Dict[str, Any]:
        if not self.token:
            raise ConfigEntryAuthFailed("Missing token")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-timezone": self.timezone,
            "x-app-version": "HomeAssistant integration/1.0.0",
        }
        url = f"{self.base_url}{path}"
        async with self.session.request(method, url, headers=headers, json=json, timeout=20) as resp:
            if resp.status == 401:
                raise ConfigEntryAuthFailed("Token expired")
            if resp.status >= 400:
                text = await resp.text()
                raise HomeAssistantError(f"API error {resp.status}: {text}")
            if resp.content_type == "application/json":
                return await resp.json()
            return {}

    def _extract_token(self, data: Dict[str, Any]) -> Optional[str]:
        for key in ["token", "jwt", "accessToken", "access_token", "deviceToken"]:
            if token := data.get(key):
                return token
        for value in data.values():
            if isinstance(value, str) and len(value) > 10:
                return value
        return None


def register_services(hass: HomeAssistant) -> None:
    async def handle(call: ServiceCall, action: str) -> None:
        entity_ids = async_extract_entity_ids(hass, call)
        entry = await resolve_entry_from_call(hass, call, entity_ids)
        stored = hass.data[DOMAIN].get(entry.entry_id)
        if not stored:
            raise HomeAssistantError("Integration not ready")
        client: SignInAppClient = stored[DATA_CLIENT]
        coordinator: SignInAppCoordinator = stored[DATA_COORDINATOR]
        tracker_entity = entry.options.get(CONF_DEVICE_TRACKER, entry.data.get(CONF_DEVICE_TRACKER))
        location = get_location(hass, tracker_entity)
        site_id = call.data.get("site_id") if action != SERVICE_SIGN_IN_AUTO else None
        if site_id is None:
            site_id = select_site_id(hass, entry)
        if site_id is None:
            raise HomeAssistantError("Unable to determine site")
        if action == SERVICE_SIGN_IN:
            await client.async_sign_in(site_id, location)
        else:
            await client.async_sign_out(site_id, location)
        await coordinator.async_request_refresh()
        for entity_id in entity_ids:
            await async_update_entity(hass, entity_id)

    async def async_sign_in(call: ServiceCall) -> None:
        await handle(call, SERVICE_SIGN_IN)

    async def async_sign_out(call: ServiceCall) -> None:
        await handle(call, SERVICE_SIGN_OUT)

    async def async_sign_in_auto(call: ServiceCall) -> None:
        await handle(call, SERVICE_SIGN_IN_AUTO)

    hass.services.async_register(DOMAIN, SERVICE_SIGN_IN, async_sign_in)
    hass.services.async_register(DOMAIN, SERVICE_SIGN_OUT, async_sign_out)
    hass.services.async_register(DOMAIN, SERVICE_SIGN_IN_AUTO, async_sign_in_auto)


async def resolve_entry_from_call(hass: HomeAssistant, call: ServiceCall, entity_ids: set[str]) -> ConfigEntry:
    if entry_id := call.data.get("entry_id"):
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry:
            return entry
        raise HomeAssistantError("Invalid entry_id")
    if not entity_ids and CONF_ENTITY_ID in call.data:
        entity_ids = {call.data[CONF_ENTITY_ID]}
    if not entity_ids:
        raise HomeAssistantError("entity_id is required")
    entity_id = next(iter(entity_ids))
    entity_map: Dict[str, str] = hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
    if entry_id := entity_map.get(entity_id):
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry:
            return entry
    registry = er.async_get(hass)
    if entity_entry := registry.async_get(entity_id):
        if entry := hass.config_entries.async_get_entry(entity_entry.config_entry_id):
            return entry
    raise HomeAssistantError("Config entry for entity not found")


def get_location(hass: HomeAssistant, entity_id: Optional[str]) -> Dict[str, Any]:
    latitude = 0.0
    longitude = 0.0
    accuracy = 50.0
    if not entity_id:
        return {"lat": latitude, "lng": longitude, "accuracy": accuracy}
    state = hass.states.get(entity_id)
    if state:
        latitude = state.attributes.get("latitude", latitude) or latitude
        longitude = state.attributes.get("longitude", longitude) or longitude
        accuracy = (
            state.attributes.get("gps_accuracy")
            or state.attributes.get("accuracy")
            or state.attributes.get("location_accuracy")
            or accuracy
        )
    return {"lat": latitude, "lng": longitude, "accuracy": accuracy}


def select_site_id(hass: HomeAssistant, entry: ConfigEntry) -> Optional[int]:
    tracker_entity = entry.options.get(CONF_DEVICE_TRACKER, entry.data.get(CONF_DEVICE_TRACKER))
    zone_state = hass.states.get(tracker_entity) if tracker_entity else None
    zone = zone_state.state.lower() if zone_state and isinstance(zone_state.state, str) else None
    office_site = entry.options.get(CONF_OFFICE_SITE, entry.data.get(CONF_OFFICE_SITE))
    remote_site = entry.options.get(CONF_REMOTE_SITE, entry.data.get(CONF_REMOTE_SITE))
    if zone in {"work", "office"} and office_site is not None:
        return int(office_site)
    if zone == "home" and remote_site is not None:
        return int(remote_site)
    if remote_site is not None:
        return int(remote_site)
    if office_site is not None:
        return int(office_site)
    return None


def derive_sensor_state(data: Dict[str, Any]) -> Dict[str, Any]:
    state = "unknown"
    current_site = None
    status_name = None
    status_color = None
    if visit := data.get("currentVisit"):
        state = "signed_in"
        current_site = visit.get("site", {}).get("name") or visit.get("site", {}).get("id")
    elif data.get("currentStatus"):
        status_name = data.get("currentStatus", {}).get("name") if isinstance(data.get("currentStatus"), dict) else str(data.get("currentStatus"))
        state = "signed_in" if status_name and status_name.lower() in {"working", "in"} else "signed_out"
        status_color = data.get("currentStatus", {}).get("colour") if isinstance(data.get("currentStatus"), dict) else None
    return {
        ATTR_STATE: state,
        ATTR_CURRENT_SITE: current_site,
        ATTR_STATUS_NAME: status_name,
        ATTR_STATUS_COLOR: status_color,
    }
