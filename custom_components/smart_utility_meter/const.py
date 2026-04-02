"""Constants for the Smart Utility Meter integration."""

DOMAIN = "smart_utility_meter"

CONF_SOURCE_ENTITY = "source_entity"
CONF_MAX_INCREASE = "max_increase"

# A generous default — most gas readings won't jump more than 10 m³ per interval.
# Set to 0 to disable the threshold check entirely.
DEFAULT_MAX_INCREASE = 10.0
