"""Config flow for Sign In App integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_COMPANION_CODE,
    CONF_REMOTE_SITE_ID,
    CONF_OFFICE_SITE_ID,
    CONF_DEVICE_TRACKER,
    CONF_OFFICE_DISTANCE,
    DEFAULT_OFFICE_DISTANCE,
)
from .api import SignInAppApi

_LOGGER = logging.getLogger(__name__)

class SignInAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sign In App."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.token = None
        self.sites = {}
        self.config_unique_id = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        _LOGGER.debug("Starting user step in config flow")
        errors = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = SignInAppApi(session)
            try:
                _LOGGER.debug("Attempting to connect with provided code")
                self.token = await api.connect(user_input[CONF_COMPANION_CODE])
                _LOGGER.debug("Connection successful, token received")

                api.set_token(self.token)
                _LOGGER.debug("Fetching sites and config for validation and unique ID")
                config_data = await api.get_config()

                if "returningVisitor" in config_data and "id" in config_data["returningVisitor"]:
                    self.config_unique_id = str(config_data["returningVisitor"]["id"])
                    await self.async_set_unique_id(self.config_unique_id)
                    self._abort_if_unique_id_configured()
                else:
                    _LOGGER.warning("Could not find unique ID in config data")

                if "sites" in config_data:
                    for site in config_data["sites"]:
                        self.sites[site["id"]] = site["name"]
                    _LOGGER.debug("Fetched %d sites", len(self.sites))

                return await self.async_step_sites()
            except Exception as e:
                _LOGGER.exception("Error connecting: %s", e)
                errors["base"] = "connect_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_COMPANION_CODE): str
            }),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle the reconfiguration step."""
        _LOGGER.debug("Starting reconfigure step")
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry:
            self.token = entry.data.get(CONF_ACCESS_TOKEN)

            # Fetch sites again to ensure we have the latest list
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = SignInAppApi(session)
            api.set_token(self.token)
            try:
                config_data = await api.get_config()
                if "sites" in config_data:
                    for site in config_data["sites"]:
                        self.sites[site["id"]] = site["name"]

                # Attempt to update unique ID during reconfiguration if available
                if "returningVisitor" in config_data and "id" in config_data["returningVisitor"]:
                    visitor_id = str(config_data["returningVisitor"]["id"])
                    if entry.unique_id != visitor_id:
                        _LOGGER.debug("Updating entry unique ID to: %s", visitor_id)
                        self.hass.config_entries.async_update_entry(entry, unique_id=visitor_id)
            except Exception as e:
                _LOGGER.warning("Could not fetch sites during reconfigure: %s", e)

        return await self.async_step_sites()

    async def async_step_sites(self, user_input=None):
        """Handle the sites configuration step."""
        _LOGGER.debug("Starting sites step in config flow")
        errors = {}

        if user_input is not None:
            _LOGGER.debug("Creating entry with data: %s", user_input)
            data = {
                CONF_ACCESS_TOKEN: self.token,
                **user_input
            }

            if self.context.get("source") == config_entries.SOURCE_RECONFIGURE:
                entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                if entry:
                    self.hass.config_entries.async_update_entry(entry, data=data)
                    return self.async_abort(reason="reconfigure_successful")

            return self.async_create_entry(title="Sign In App", data=data)

        # Pre-fill values if reconfiguring
        defaults = {}
        if self.context.get("source") == config_entries.SOURCE_RECONFIGURE:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            if entry:
                defaults = entry.data

        # When reconfiguring, if the previous device_tracker is not a person, it might be invalid for the person selector.
        # But we want to force the user to pick a person. So we can keep the default if it looks like a person,
        # or just let the selector handle it (it might show blank if invalid).
        default_tracker = defaults.get(CONF_DEVICE_TRACKER)

        schema = vol.Schema({
            vol.Required(CONF_REMOTE_SITE_ID, default=defaults.get(CONF_REMOTE_SITE_ID)): int,
            vol.Required(CONF_OFFICE_SITE_ID, default=defaults.get(CONF_OFFICE_SITE_ID)): int,
            vol.Required(CONF_DEVICE_TRACKER, default=default_tracker): EntitySelector(
                EntitySelectorConfig(domain="person")
            ),
            vol.Optional(CONF_OFFICE_DISTANCE, default=defaults.get(CONF_OFFICE_DISTANCE, DEFAULT_OFFICE_DISTANCE)): NumberSelector(
                NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX, unit_of_measurement="m")
            ),
        })

        description_placeholders = {}
        if self.sites:
            sites_text = "\n".join([f"{id}: {name}" for id, name in self.sites.items()])
            description_placeholders["sites_list"] = sites_text
        else:
             description_placeholders["sites_list"] = "No sites found."

        return self.async_show_form(
            step_id="sites",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
