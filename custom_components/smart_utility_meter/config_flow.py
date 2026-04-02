"""Config flow and options flow for Smart Utility Meter."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import selector

from .const import CONF_MAX_INCREASE, CONF_SOURCE_ENTITY, DEFAULT_MAX_INCREASE, DOMAIN


def _build_schema(
    default_source: str = "",
    default_max_increase: float = DEFAULT_MAX_INCREASE,
    *,
    include_source: bool = True,
) -> vol.Schema:
    """Build the shared schema for both config and options flows.

    Source entity is omitted from the options flow — changing the source would
    invalidate the accumulated total and is better handled by creating a new entry.
    """
    fields: dict = {}

    if include_source:
        fields[vol.Required(CONF_SOURCE_ENTITY, default=default_source)] = (
            selector.EntitySelector(
                selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
            )
        )

    fields[vol.Required(CONF_MAX_INCREASE, default=default_max_increase)] = (
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=0.001,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    )

    return vol.Schema(fields)


class SmartUtilityMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup from the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the setup form and create an entry on submission."""
        if user_input is not None:
            # Use the source entity ID as the unique ID so the user cannot
            # accidentally add the same source twice.
            await self.async_set_unique_id(user_input[CONF_SOURCE_ENTITY])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Smart Utility Meter — {user_input[CONF_SOURCE_ENTITY]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartUtilityMeterOptionsFlow:
        """Return an options flow so the threshold can be adjusted post-setup."""
        return SmartUtilityMeterOptionsFlow(config_entry)


class SmartUtilityMeterOptionsFlow(config_entries.OptionsFlow):
    """Allow the user to adjust options (e.g. max_increase) after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the options form pre-populated with current values."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_max = self._config_entry.options.get(
            CONF_MAX_INCREASE,
            self._config_entry.data.get(CONF_MAX_INCREASE, DEFAULT_MAX_INCREASE),
        )

        return self.async_show_form(
            step_id="init",
            # Source entity is intentionally excluded — see _build_schema docstring.
            data_schema=_build_schema(
                default_max_increase=float(current_max),
                include_source=False,
            ),
        )
