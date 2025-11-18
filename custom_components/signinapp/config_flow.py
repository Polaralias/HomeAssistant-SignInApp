from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import CannotConnect, InvalidCompanionCode, SignInAppClient
from .const import (
    CONF_COMPANION_CODE,
    CONF_DEVICE_TRACKER,
    CONF_OFFICE_SITE,
    CONF_REMOTE_SITE,
    CONF_TOKEN,
    CONF_VISITOR_ID,
    CONF_VISITOR_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def build_site_choices(sites: List[Dict[str, Any]], site_type: str) -> Dict[int, str]:
    choices: Dict[int, str] = {}
    for site in sites:
        if site.get("type") != site_type:
            continue
        site_id = site.get("id") or site.get("siteId")
        name = site.get("name") or str(site_id)
        if site_id is not None:
            choices[int(site_id)] = name
    return choices


async def fetch_sites(hass: HomeAssistant, client: SignInAppClient) -> Tuple[Dict[int, str], Dict[int, str], Dict[str, Any]]:
    config = await client.async_get_config()
    sites = config.get("sites") or []
    office_choices = build_site_choices(sites, "standard")
    remote_choices = build_site_choices(sites, "remote")
    return office_choices, remote_choices, config


class SignInAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._config: Dict[str, Any] = {}
        self._office_choices: Dict[int, str] = {}
        self._remote_choices: Dict[int, str] = {}
        self._reauth_entry: Optional[config_entries.ConfigEntry] = None

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_COMPANION_CODE]
            client = SignInAppClient(self.hass)
            try:
                await client.async_connect(code)
                self._token = client.token
                self._office_choices, self._remote_choices, self._config = await fetch_sites(self.hass, client)
            except InvalidCompanionCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during pairing")
                errors["base"] = "unknown"
            else:
                if visitor := self._config.get("returningVisitor"):
                    await self.async_set_unique_id(str(visitor.get("id")))
                    self._abort_if_unique_id_configured()
                return await self.async_step_select_site_and_tracker()
        schema = vol.Schema({vol.Required(CONF_COMPANION_CODE): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_site_and_tracker(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if not self._office_choices and not self._remote_choices:
            errors["base"] = "no_sites_found"
        if user_input is not None and not errors:
            office_site = user_input[CONF_OFFICE_SITE]
            remote_site = user_input.get(CONF_REMOTE_SITE)
            tracker = user_input[CONF_DEVICE_TRACKER]
            visitor = self._config.get("returningVisitor", {})
            title = visitor.get("name") or self._config.get("accountName") or "Sign In App"
            data = {
                CONF_TOKEN: self._token,
                CONF_OFFICE_SITE: office_site,
                CONF_REMOTE_SITE: remote_site,
                CONF_DEVICE_TRACKER: tracker,
                CONF_VISITOR_ID: visitor.get("id"),
                CONF_VISITOR_NAME: visitor.get("name"),
            }
            return self.async_create_entry(title=title, data=data)
        office_selector = selector.selector({"select": {"options": [
            {"label": name, "value": site_id} for site_id, name in self._office_choices.items()
        ]}})
        remote_selector = selector.selector({"select": {"options": [
            {"label": name, "value": site_id} for site_id, name in self._remote_choices.items()
        ], "custom_value": True, "mode": "dropdown"}})
        schema = vol.Schema(
            {
                vol.Required(CONF_OFFICE_SITE): office_selector,
                vol.Optional(CONF_REMOTE_SITE): remote_selector,
                vol.Required(CONF_DEVICE_TRACKER): selector.selector({"entity": {"domain": "device_tracker"}}),
            }
        )
        return self.async_show_form(step_id="select_site_and_tracker", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Dict[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None and self._reauth_entry:
            client = SignInAppClient(self.hass)
            try:
                await client.async_connect(user_input[CONF_COMPANION_CODE])
                self._office_choices, self._remote_choices, self._config = await fetch_sites(self.hass, client)
            except InvalidCompanionCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                office_site = self._reauth_entry.data.get(CONF_OFFICE_SITE)
                remote_site = self._reauth_entry.data.get(CONF_REMOTE_SITE)
                if office_site not in self._office_choices:
                    office_site = next(iter(self._office_choices)) if self._office_choices else None
                if remote_site not in self._remote_choices:
                    remote_site = next(iter(self._remote_choices)) if self._remote_choices else None
                new_data = {
                    **self._reauth_entry.data,
                    CONF_TOKEN: client.token,
                    CONF_OFFICE_SITE: office_site,
                    CONF_REMOTE_SITE: remote_site,
                }
                self.hass.config_entries.async_update_entry(self._reauth_entry, data=new_data)
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        schema = vol.Schema({vol.Required(CONF_COMPANION_CODE): str})
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return SignInAppOptionsFlow(config_entry)


class SignInAppOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._office_choices: Dict[int, str] = {}
        self._remote_choices: Dict[int, str] = {}

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if not self._office_choices and not self._remote_choices:
            try:
                client = SignInAppClient(self.hass, self.config_entry.data[CONF_TOKEN])
                self._office_choices, self._remote_choices, _ = await fetch_sites(self.hass, client)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Option site load failed: %s", err)
        if user_input is not None and not errors:
            return self.async_create_entry(title="Sign In App options", data=user_input)
        office_selector = selector.selector({"select": {"options": [
            {"label": name, "value": site_id} for site_id, name in self._office_choices.items()
        ], "custom_value": True}})
        remote_selector = selector.selector({"select": {"options": [
            {"label": name, "value": site_id} for site_id, name in self._remote_choices.items()
        ], "custom_value": True}})
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OFFICE_SITE,
                    default=self.config_entry.options.get(CONF_OFFICE_SITE, self.config_entry.data.get(CONF_OFFICE_SITE)),
                ): office_selector,
                vol.Optional(
                    CONF_REMOTE_SITE,
                    default=self.config_entry.options.get(CONF_REMOTE_SITE, self.config_entry.data.get(CONF_REMOTE_SITE)),
                ): remote_selector,
                vol.Required(
                    CONF_DEVICE_TRACKER,
                    default=self.config_entry.options.get(CONF_DEVICE_TRACKER, self.config_entry.data.get(CONF_DEVICE_TRACKER)),
                ): selector.selector({"entity": {"domain": "device_tracker"}}),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
