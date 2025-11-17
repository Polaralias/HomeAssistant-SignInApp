"""The SignInApp integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.location import distance

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_BASE_URL,
    CONF_DEVICE_TRACKER,
    CONF_AUTO_SITE,
    CONF_REFRESH_TOKEN,
    CONF_SITE_ID,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_ENTITY_MAP,
    DATA_LISTENER,
    DOMAIN,
    PLATFORMS,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SignInApp component."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})

    if not hass.data[DOMAIN].get("services_registered"):
        register_services(hass)
        hass.data[DOMAIN]["services_registered"] = True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SignInApp from a config entry."""

    client = SignInAppClient(
        hass,
        entry.data[CONF_BASE_URL],
        entry.data.get(CONF_ACCESS_TOKEN),
        entry.data.get(CONF_REFRESH_TOKEN),
    )

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
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        undo_listener = hass.data[DOMAIN][entry.entry_id][DATA_LISTENER]
        undo_listener()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


class SignInAppCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching SignInApp data."""

    def __init__(self, hass: HomeAssistant, client: "SignInAppClient", entry: ConfigEntry) -> None:
        self.client = client
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"SignInApp {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            return await self.client.async_get_status()
        except ConfigEntryAuthFailed:
            raise
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with SignInApp: {err}") from err


class SignInAppClient:
    """Thin API wrapper for SignInApp backend."""

    def __init__(
        self,
        hass: HomeAssistant,
        base_url: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> None:
        self.hass = hass
        self.base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._session = async_get_clientsession(hass)
        self._status: Dict[str, Any] = {"state": "unknown"}

    @property
    def tokens(self) -> Dict[str, Optional[str]]:
        return {
            CONF_ACCESS_TOKEN: self._access_token,
            CONF_REFRESH_TOKEN: self._refresh_token,
        }

    async def async_connect(self, code: str) -> Dict[str, str]:
        """Pair companion code with the SignInApp backend."""
        url = f"{self.base_url}/connect"
        payload = {"code": code}
        _LOGGER.debug("Connecting to %s with code ****", url)
        try:
            async with self._session.post(url, json=payload, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:
            _LOGGER.error("Failed to pair with SignInApp: %s", err)
            raise HomeAssistantError("Unable to complete pairing") from err

        self._access_token = data.get("access_token") or f"token-{slugify(code)}"
        self._refresh_token = data.get("refresh_token") or f"refresh-{slugify(code)}"
        return {
            CONF_ACCESS_TOKEN: self._access_token,
            CONF_REFRESH_TOKEN: self._refresh_token,
            CONF_ACCOUNT_ID: data.get("account_id", slugify(code)),
        }

    async def _async_request(self, method: str, path: str, json: Optional[dict] = None) -> Dict[str, Any]:
        await self._async_ensure_token()
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        _LOGGER.debug("Requesting %s %s", method, url)
        async with self._session.request(method, url, headers=headers, json=json, timeout=10) as resp:
            if resp.status == 401:
                raise ConfigEntryAuthFailed("Token expired")
            resp.raise_for_status()
            if resp.content_type == "application/json":
                return await resp.json()
            return {"status": resp.status}

    async def _async_ensure_token(self) -> None:
        if self._access_token:
            return
        if not self._refresh_token:
            raise ConfigEntryAuthFailed("Missing tokens")
        # Simulate refresh when only refresh token exists
        self._access_token = f"refreshed-{self._refresh_token}"

    async def async_refresh_tokens(self) -> None:
        if not self._refresh_token:
            raise ConfigEntryAuthFailed("Missing refresh token")
        self._access_token = f"refreshed-{self._refresh_token}"

    async def async_get_status(self) -> Dict[str, Any]:
        """Fetch latest status."""
        try:
            data = await self._async_request("GET", "/status")
            self._status = data
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Falling back to cached status due to %s", err)
        return self._status

    async def async_sign(self, action: str, site_id: Optional[str], location: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": action}
        if site_id:
            payload["site_id"] = site_id
        if location:
            payload["location"] = location

        try:
            data = await self._async_request("POST", "/attendance", json=payload)
            self._status = data
            return data
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Sign %s failed: %s", action, err)
            raise HomeAssistantError(f"Sign {action} failed") from err


async def async_get_entry_from_entity(hass: HomeAssistant, entity_id: str) -> ConfigEntry:
    """Resolve config entry for a given entity id."""
    entity_map: Dict[str, str] = hass.data[DOMAIN].setdefault(DATA_ENTITY_MAP, {})
    entry_id = entity_map.get(entity_id)
    if not entry_id:
        raise HomeAssistantError(f"Entity {entity_id} is not managed by {DOMAIN}")
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        raise HomeAssistantError(f"Config entry for entity {entity_id} not found")
    return entry


def register_services(hass: HomeAssistant) -> None:
    """Register SignInApp domain services."""

    async def _async_handle(call: ServiceCall, action: str) -> None:
        entity_ids = async_extract_entity_ids(hass, call)
        entry: Optional[ConfigEntry] = None

        if call.data.get("entry_id"):
            entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        elif entity_ids:
            entry = await async_get_entry_from_entity(hass, next(iter(entity_ids)))

        if not entry:
            raise HomeAssistantError("No config entry could be resolved for the service call")

        stored = hass.data[DOMAIN].get(entry.entry_id)
        if not stored:
            raise HomeAssistantError("Integration not ready for service call")

        client: SignInAppClient = stored[DATA_CLIENT]
        site_id: Optional[str] = call.data.get(CONF_SITE_ID)
        device_tracker: Optional[str] = entry.options.get(CONF_DEVICE_TRACKER)
        location: Optional[Dict[str, Any]] = None

        if device_tracker:
            location = extract_location(hass, device_tracker)

        auto_site = entry.options.get(CONF_AUTO_SITE, True)
        if not site_id and auto_site:
            site_id = select_site_id(
                stored[DATA_COORDINATOR].data,
                location,
                entry.options.get(CONF_SITE_ID),
            )

        if not site_id and auto_site:
            raise HomeAssistantError("Unable to determine site for SignInApp service call")

        await client.async_sign(action, site_id, location)

        coordinator: DataUpdateCoordinator = stored[DATA_COORDINATOR]
        await coordinator.async_request_refresh()

        for entity_id in entity_ids:
            await async_update_entity(hass, entity_id)

    async def async_sign_in(call: ServiceCall) -> None:
        await _async_handle(call, "in")

    async def async_sign_out(call: ServiceCall) -> None:
        await _async_handle(call, "out")

    hass.services.async_register(DOMAIN, SERVICE_SIGN_IN, async_sign_in)
    hass.services.async_register(DOMAIN, SERVICE_SIGN_OUT, async_sign_out)


def select_site_id(
    data: Optional[Dict[str, Any]],
    location: Optional[Dict[str, Any]],
    default_site: Optional[str],
) -> Optional[str]:
    """Choose a site based on coordinator data and device location."""

    if not data:
        return default_site

    sites = data.get("sites") or []
    if location:
        best_site: Optional[str] = None
        best_distance: Optional[float] = None
        for site in sites:
            latitude = site.get("latitude") or site.get("lat")
            longitude = site.get("longitude") or site.get("lon")
            if latitude is None or longitude is None:
                continue

            if location.get("latitude") is None or location.get("longitude") is None:
                break

            dist = distance(
                location.get("latitude"),
                location.get("longitude"),
                latitude,
                longitude,
            )
            radius = site.get("radius") or site.get("radius_m")
            if radius and dist > radius:
                continue

            if best_distance is None or dist < best_distance:
                best_site = site.get("id") or site.get("site_id") or site.get("name")
                best_distance = dist

        if best_site:
            return best_site

    return default_site


def extract_location(hass: HomeAssistant, entity_id: str) -> Optional[Dict[str, Any]]:
    """Extract latitude/longitude from a device_tracker entity."""
    state = hass.states.get(entity_id)
    if not state:
        _LOGGER.warning("Device tracker %s is unavailable", entity_id)
        return None

    latitude = state.attributes.get("latitude")
    longitude = state.attributes.get("longitude")
    if latitude is None or longitude is None:
        _LOGGER.debug("Device tracker %s does not provide coordinates", entity_id)
        return None

    return {"latitude": latitude, "longitude": longitude}

