"""Config flow for SignInApp."""

from __future__ import annotations

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_BASE_URL,
    CONF_CODE,
    CONF_AUTO_SITE,
    CONF_DEVICE_TRACKER,
    CONF_REFRESH_TOKEN,
    CONF_SITE_ID,
    DOMAIN,
)
from . import SignInAppClient

_LOGGER = logging.getLogger(__name__)


async def _async_validate_input(hass, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate companion code and return tokens."""
    client = SignInAppClient(hass, data[CONF_BASE_URL])
    tokens = await client.async_connect(data[CONF_CODE])

    title = data.get(CONF_NAME) or f"SignInApp {tokens.get(CONF_ACCOUNT_ID)}"
    return {
        "title": title,
        "data": {
            CONF_BASE_URL: data[CONF_BASE_URL],
            CONF_ACCESS_TOKEN: tokens[CONF_ACCESS_TOKEN],
            CONF_REFRESH_TOKEN: tokens[CONF_REFRESH_TOKEN],
            CONF_ACCOUNT_ID: tokens[CONF_ACCOUNT_ID],
            CONF_NAME: data.get(CONF_NAME) or title,
        },
    }


class SignInAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SignInApp."""

    VERSION = 1
    _reauth_entry = None

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _async_validate_input(self.hass, user_input)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["data"][CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=info["data"], options={})

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_CODE): str,
                vol.Optional(CONF_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_reauth(self, entry_data: Dict[str, Any]) -> FlowResult:
        """Handle re-authentication with a new code."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        assert self._reauth_entry

        if user_input is not None:
            merged = {
                CONF_BASE_URL: self._reauth_entry.data[CONF_BASE_URL],
                CONF_CODE: user_input[CONF_CODE],
                CONF_NAME: self._reauth_entry.data.get(CONF_NAME),
            }
            try:
                info = await _async_validate_input(self.hass, merged)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Reauth failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                new_data = {**self._reauth_entry.data, **info["data"]}
                self.hass.config_entries.async_update_entry(self._reauth_entry, data=new_data)
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return SignInAppOptionsFlowHandler(config_entry)


class SignInAppOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SignInApp options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="Options", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEVICE_TRACKER,
                    default=self.config_entry.options.get(CONF_DEVICE_TRACKER),
                ): selector.selector({"entity": {"domain": "device_tracker"}}),
                vol.Optional(
                    CONF_AUTO_SITE,
                    default=self.config_entry.options.get(CONF_AUTO_SITE, True),
                ): bool,
                vol.Optional(
                    CONF_SITE_ID,
                    default=self.config_entry.options.get(CONF_SITE_ID, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)

