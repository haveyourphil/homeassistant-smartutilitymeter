"""Smart Utility Meter integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import CONF_SOURCE_ENTITY, DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry and forward it to the sensor platform."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-load the sensor when the user changes options (e.g. max_increase).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up the sensor platform."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entries from older schema versions.

    Called by HA before async_setup_entry when the stored version is lower than
    the version declared in the ConfigFlow class, so broken entries are healed
    on the next restart without user intervention.
    """
    if config_entry.version < 2:
        # v2 added CONF_NAME. Derive a readable default from the source entity ID
        # so existing entries get a sensible name without the user having to do anything.
        # e.g. "sensor.gas_total" → "Gas Total"
        source: str = config_entry.data.get(CONF_SOURCE_ENTITY, "")
        object_id = source.split(".")[-1] if "." in source else source
        default_name = object_id.replace("_", " ").title()

        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_NAME: default_name},
            version=2,
        )

    return True
