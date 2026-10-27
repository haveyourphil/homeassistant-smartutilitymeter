"""Smart Utility Meter integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SOURCE_ENTITY

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry and forward it to the sensor platform."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up the sensor platform."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entries from older schema versions.

    Called by HA before async_setup_entry when the stored version is lower than
    the version declared in the ConfigFlow class, so broken entries are healed
    on the next restart without user intervention.
    """
    if config_entry.version > 2:
        # Refuse to interpret a future schema when an older release is installed.
        return False

    if config_entry.version == 1:
        # v2 added CONF_NAME. Derive a readable default from the source entity ID
        # so existing entries get a sensible name without user intervention.
        # e.g. "sensor.gas_total" → "Gas Total"
        source: str = config_entry.data.get(CONF_SOURCE_ENTITY, "")
        object_id = source.split(".")[-1] if "." in source else source
        default_name = (
            config_entry.data.get(CONF_NAME)
            or object_id.replace("_", " ").title()
            or config_entry.title
            or "Smart Utility Meter"
        )

        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_NAME: default_name},
            version=2,
        )

    return True
