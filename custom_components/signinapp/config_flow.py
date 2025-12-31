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

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = SignInAppApi(session)
            try:
                self.token = await api.connect(user_input[CONF_COMPANION_CODE])

                # Try to fetch sites to help the user
                api.set_token(self.token)
                try:
                    config_data = await api.get_config()
                    if "sites" in config_data:
                        for site in config_data["sites"]:
                            self.sites[site["id"]] = site["name"]
                except Exception:
                    _LOGGER.warning("Could not fetch sites during config flow")

                return await self.async_step_sites()
            except Exception:
                _LOGGER.exception("Error connecting")
                errors["base"] = "connect_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_COMPANION_CODE): str
            }),
            errors=errors,
        )

    async def async_step_sites(self, user_input=None):
        """Handle the sites configuration step."""
        errors = {}
        if user_input is not None:
            data = {
                CONF_ACCESS_TOKEN: self.token,
                **user_input
            }
            return self.async_create_entry(title="Sign In App", data=data)

        schema = vol.Schema({
            vol.Required(CONF_REMOTE_SITE_ID): int,
            vol.Required(CONF_OFFICE_SITE_ID): int,
            vol.Required(CONF_DEVICE_TRACKER): EntitySelector(
                EntitySelectorConfig(domain="device_tracker")
            ),
            vol.Optional(CONF_OFFICE_DISTANCE, default=DEFAULT_OFFICE_DISTANCE): NumberSelector(
                NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX, unit_of_measurement="m")
            ),
        })

        description_placeholders = {}
        if self.sites:
            sites_text = "\n".join([f"{id}: {name}" for id, name in self.sites.items()])
            description_placeholders["sites_list"] = sites_text

        return self.async_show_form(
            step_id="sites",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
