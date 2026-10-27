"""Config flow and migration preserve existing config-entry identity/data."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_utility_meter import async_migrate_entry
from custom_components.smart_utility_meter.const import DOMAIN

from .conftest import ENTITY, SOURCE


async def test_user_flow(hass):
    """Create the helper and keep the source ID as config-entry unique ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    data = {"name": "Daily Gas Usage", "source_entity": SOURCE, "max_increase": 10}
    with patch(
        "custom_components.smart_utility_meter.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Daily Gas Usage"
    assert result["data"] == data
    assert result["result"].unique_id == SOURCE
    assert result["result"].version == 2


async def test_duplicate_source(hass, entry):
    """A differently named helper cannot track the same source twice."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Another name", "source_entity": SOURCE, "max_increase": 5},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("existing_name", [None, "My custom name"])
async def test_v1_migration(hass, existing_name):
    """Migration adds only the missing name and is idempotent."""
    data = {"source_entity": SOURCE, "max_increase": 4, "extra": "preserve"}
    if existing_name:
        data["name"] = existing_name
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Original title",
        unique_id=SOURCE,
        version=1,
        data=data,
        options={"max_increase": 7},
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert dict(entry.data) == {**data, "name": existing_name or "Gas Total"}
    assert dict(entry.options) == {"max_increase": 7}
    assert entry.unique_id == SOURCE
    assert entry.entry_id == entry_id
    assert entry.title == "Original title"
    assert await async_migrate_entry(hass, entry)
    assert dict(entry.data) == {**data, "name": existing_name or "Gas Total"}


async def test_v1_migrates_during_setup(hass):
    """Normal setup automatically migrates without recreating the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Original title",
        unique_id=SOURCE,
        version=1,
        data={"source_entity": SOURCE},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert hass.states.get("sensor.gas_total") is not None


async def test_future_schema_rejected(hass):
    """An older release must not downgrade future config-entry data."""
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={"future": True})
    entry.add_to_hass(hass)
    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 3
    assert dict(entry.data) == {"future": True}


async def test_options_reload_preserves_state_and_identity(hass, entry, setup_meter):
    """One automatic reload retains usage, baseline, registry ID and entity ID."""
    from homeassistant.helpers import entity_registry as er

    await setup_meter()
    hass.states.async_set(SOURCE, "103")
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    original = registry.async_get(ENTITY)
    assert original.unique_id == entry.entry_id
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"max_increase": 1}
        )
        await hass.async_block_till_done()
        reload_entry.assert_awaited_once_with(entry.entry_id)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["max_increase"] == 1
    assert entry.data["max_increase"] == 10
    assert registry.async_get(ENTITY).id == original.id
    assert registry.async_get(ENTITY).unique_id == entry.entry_id
    state = hass.states.get(ENTITY)
    assert float(state.state) == 3
    assert state.attributes["last_source_value"] == 103
    hass.states.async_set(SOURCE, "105")  # Filter now uses the new threshold.
    await hass.async_block_till_done()
    assert float(hass.states.get(ENTITY).state) == 3


async def test_options_fallback_and_unchanged_options(hass, entry, setup_meter):
    """The initial data is the default; saving it reloads at most once."""
    await setup_meter()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    key = next(iter(schema.schema))
    assert key.description["suggested_value"] == 10
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload_entry:
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"max_increase": 10}
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"max_increase": 10}
        )
        await hass.async_block_till_done()
        assert reload_entry.await_count == 1
