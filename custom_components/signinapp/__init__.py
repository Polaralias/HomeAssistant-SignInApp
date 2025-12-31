"""The Sign In App integration."""
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    CONF_REMOTE_SITE_ID,
    CONF_OFFICE_SITE_ID,
    CONF_DEVICE_TRACKER,
    CONF_OFFICE_DISTANCE,
)
from .api import SignInAppApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_SIGN_IN = "sign_in"
SERVICE_SIGN_OUT = "sign_out"

ATTR_SITE_TYPE = "site_type"
SITE_TYPE_OFFICE = "office"
SITE_TYPE_REMOTE = "remote"

SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_SITE_TYPE): vol.In([SITE_TYPE_OFFICE, SITE_TYPE_REMOTE])
})

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sign In App component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sign In App from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    # Use HA's timezone
    timezone = hass.config.time_zone
    api = SignInAppApi(session, timezone=timezone)
    api.set_token(entry.data[CONF_ACCESS_TOKEN])

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "config": entry.data
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_sign_in(call: ServiceCall):
        """Handle the sign in service."""
        site_type = call.data[ATTR_SITE_TYPE]
        config_data = entry.data

        if site_type == SITE_TYPE_OFFICE:
            site_id = config_data[CONF_OFFICE_SITE_ID]
            tracker_entity = config_data[CONF_DEVICE_TRACKER]
            distance = config_data[CONF_OFFICE_DISTANCE]

            state = hass.states.get(tracker_entity)
            if state:
                lat = float(state.attributes.get("latitude", 0))
                lng = float(state.attributes.get("longitude", 0))
                # Use configured distance as accuracy for the request, as per prompt interpretation
                accuracy = float(distance)
            else:
                _LOGGER.warning("Device tracker %s not found, using 0", tracker_entity)
                lat = 0.0
                lng = 0.0
                accuracy = 0.0
        else: # Remote
            site_id = config_data[CONF_REMOTE_SITE_ID]
            lat = 0.0
            lng = 0.0
            accuracy = 0.0

        await api.sign_in(site_id, lat, lng, accuracy)
        # Force update of sensor?
        # We can't easily force update the sensor from here without reference to it.
        # But the sensor polls, so it will update eventually.

    async def handle_sign_out(call: ServiceCall):
        """Handle the sign out service."""
        site_type = call.data[ATTR_SITE_TYPE]
        config_data = entry.data

        if site_type == SITE_TYPE_OFFICE:
            site_id = config_data[CONF_OFFICE_SITE_ID]
            tracker_entity = config_data[CONF_DEVICE_TRACKER]
            distance = config_data[CONF_OFFICE_DISTANCE]

            state = hass.states.get(tracker_entity)
            if state:
                lat = float(state.attributes.get("latitude", 0))
                lng = float(state.attributes.get("longitude", 0))
                accuracy = float(distance)
            else:
                lat = 0.0
                lng = 0.0
                accuracy = 0.0
        else: # Remote
            site_id = config_data[CONF_REMOTE_SITE_ID]
            lat = 0.0
            lng = 0.0
            accuracy = 0.0

        await api.sign_out(site_id, lat, lng, accuracy)

    hass.services.async_register(DOMAIN, SERVICE_SIGN_IN, handle_sign_in, schema=SERVICE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SIGN_OUT, handle_sign_out, schema=SERVICE_SCHEMA)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
