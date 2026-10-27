"""Config flow and options flow for Smart Utility Meter."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_MAX_INCREASE, CONF_SOURCE_ENTITY, DEFAULT_MAX_INCREASE, DOMAIN

_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
        ),
        vol.Required(
            CONF_MAX_INCREASE, default=DEFAULT_MAX_INCREASE
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step=0.001, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)

_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAX_INCREASE): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step=0.001, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)


class SmartUtilityMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup from the UI."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the setup form and create an entry on submission."""
        if user_input is not None:
            # Prevent the same source being tracked twice.
            await self.async_set_unique_id(user_input[CONF_SOURCE_ENTITY])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                # The entry title appears in the Helpers list in the UI.
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=_CONFIG_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartUtilityMeterOptionsFlow:
        """Return an options flow so the threshold can be adjusted post-setup."""
        return SmartUtilityMeterOptionsFlow()


class SmartUtilityMeterOptionsFlow(config_entries.OptionsFlowWithReload):
    """Allow the user to adjust options (e.g. max_increase) after initial setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the options form pre-populated with current values."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **user_input}
            )

        current_max = self.config_entry.options.get(
            CONF_MAX_INCREASE,
            self.config_entry.data.get(CONF_MAX_INCREASE, DEFAULT_MAX_INCREASE),
        )

        return self.async_show_form(
            step_id="init",
            # Keep source selection fixed; names can be customized in the entity UI.
            data_schema=self.add_suggested_values_to_schema(
                _OPTIONS_SCHEMA, {CONF_MAX_INCREASE: float(current_max)}
            ),
        )
