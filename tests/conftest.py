"""Use real Home Assistant platforms and config-entry lifecycle in tests."""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_utility_meter.const import DOMAIN

SOURCE = "sensor.gas_total"
ENTITY = "sensor.daily_gas_usage"
SOURCE_ATTRIBUTES = {"unit_of_measurement": "m³", "device_class": "gas"}


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations, freezer):
    """Enable our integration and make restore dates deterministic."""
    freezer.move_to("2026-10-27 12:00:00+00:00")


@pytest.fixture
def entry() -> MockConfigEntry:
    """An existing v2 entry, with the original unique ID convention."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Daily Gas Usage",
        unique_id=SOURCE,
        version=2,
        data={
            "name": "Daily Gas Usage",
            "source_entity": SOURCE,
            "max_increase": 10.0,
        },
    )


@pytest.fixture
async def setup_meter(hass: HomeAssistant, entry: MockConfigEntry):
    """Set up an entry, optionally after seeding restore storage/source state."""

    async def setup(source="100", attributes=None):
        if source is not None:
            hass.states.async_set(SOURCE, source, attributes or SOURCE_ATTRIBUTES)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return setup
