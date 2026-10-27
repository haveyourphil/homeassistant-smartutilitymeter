"""Protect accumulation, legacy restore data, statistics metadata and lifecycle."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import restore_state
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from .conftest import ENTITY, SOURCE, SOURCE_ATTRIBUTES


async def update_source(hass, value, attributes=None):
    """Publish through the real event bus rather than calling sensor internals."""
    hass.states.async_set(SOURCE, value, attributes or SOURCE_ATTRIBUTES)
    await hass.async_block_till_done()
    return hass.states.get(ENTITY)


@pytest.mark.parametrize(
    ("readings", "expected", "baseline"),
    [
        (["102", "105"], 5, 105),
        (["100", "100"], 0, 100),
        (["98", "99"], 1, 99),  # Decreases rebase; recovery is a new increase.
        (["0", "2"], 2, 2),  # Source meter reset.
        (["150", "152"], 2, 152),  # Spike ignored, subsequent increment counted.
        (["110"], 10, 110),  # Threshold is inclusive.
    ],
)
async def test_deltas(hass, setup_meter, readings, expected, baseline):
    """Positive bounded deltas accumulate; other finite readings rebase."""
    await setup_meter()
    for reading in readings:
        state = await update_source(hass, reading)
    assert float(state.state) == expected
    assert state.attributes["last_source_value"] == baseline


async def test_zero_threshold_disables_filter(hass, entry, setup_meter):
    """Zero keeps the original unlimited-delta behaviour."""
    await setup_meter()
    hass.config_entries.async_update_entry(entry, options={"max_increase": 0})
    assert await hass.config_entries.async_reload(entry.entry_id)
    state = await update_source(hass, "1100")
    assert float(state.state) == 1000


@pytest.mark.parametrize(
    "invalid", ["unknown", "unavailable", "bad", "nan", "inf", "-inf"]
)
async def test_invalid_reading_keeps_baseline(hass, setup_meter, invalid):
    """Missing/invalid readings leave the accumulated total and baseline intact."""
    await setup_meter()
    await update_source(hass, "102")
    state = await update_source(hass, invalid)
    assert float(state.state) == 2
    assert state.attributes["last_source_value"] == 102
    state = await update_source(hass, "104")
    assert float(state.state) == 4


async def test_removed_source(hass, setup_meter):
    """Removing the source doesn't erase the helper's known total."""
    await setup_meter()
    await update_source(hass, "102")
    hass.states.async_remove(SOURCE)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert float(state.state) == 2
    assert state.attributes["last_source_value"] == 102


async def test_no_initial_source(hass, setup_meter):
    """The first finite reading establishes a baseline without counting it."""
    await setup_meter(source=None)
    await update_source(hass, "nan")
    state = await update_source(hass, "300")
    assert float(state.state) == 0
    state = await update_source(hass, "301")
    assert float(state.state) == 1
    assert state.attributes["device_class"] == "gas"


@pytest.mark.parametrize("display_precision", [None, 2])
async def test_metadata_and_identity(hass, entry, setup_meter, display_precision):
    """Keep the original entity identity, name, units and statistics semantics."""
    registry = er.async_get(hass)
    source = registry.async_get_or_create(
        "sensor", "test", "gas", suggested_object_id="gas_total"
    )
    registry.async_update_entity_options(
        source.entity_id,
        "sensor",
        {"suggested_display_precision": 3, "display_precision": display_precision},
    )
    await setup_meter()
    state = hass.states.get(ENTITY)
    entity = registry.async_get(ENTITY)
    assert entity.unique_id == entry.entry_id
    assert entity.config_entry_id == entry.entry_id
    assert state.attributes["friendly_name"] == "Daily Gas Usage"
    assert state.attributes["unit_of_measurement"] == "m³"
    assert state.attributes["device_class"] == "gas"
    assert state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING
    assert entity.options["sensor"]["suggested_display_precision"] == (
        3 if display_precision is None else display_precision
    )


async def test_incompatible_source_device_class(hass, setup_meter):
    """An accumulator must not inherit a measurement-only device class."""
    await setup_meter(
        attributes={"device_class": "temperature", "unit_of_measurement": "°C"}
    )
    assert "device_class" not in hass.states.get(ENTITY).attributes


@pytest.mark.parametrize(
    ("start", "midnights"),
    [
        (
            "2026-03-28 12:00:00+00:00",
            ["2026-03-29T00:00:00+00:00", "2026-03-29T23:00:00+00:00"],
        ),
        (
            "2026-10-24 12:00:00+00:00",
            ["2026-10-24T23:00:00+00:00", "2026-10-26T00:00:00+00:00"],
        ),
    ],
)
async def test_local_midnight_and_dst(hass, setup_meter, freezer, start, midnights):
    """Real HA timers follow 23/25-hour local days and keep the baseline."""
    freezer.move_to(start)
    await hass.config.async_set_time_zone("Europe/London")
    await setup_meter()
    baseline = 100
    for midnight in midnights:
        baseline += 2
        state = await update_source(hass, str(baseline))
        assert float(state.state) == 2
        instant = dt_util.parse_datetime(midnight)
        before = instant - timedelta(seconds=1)
        freezer.move_to(before)
        async_fire_time_changed(hass, before)
        await hass.async_block_till_done()
        assert float(hass.states.get(ENTITY).state) == 2
        freezer.move_to(instant)
        async_fire_time_changed(hass, instant)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY)
        assert float(state.state) == 0
        assert state.attributes["last_source_value"] == baseline
        assert (
            state.attributes["accumulation_date"]
            == dt_util.as_local(instant).date().isoformat()
        )
    state = await update_source(hass, str(baseline + 1))
    assert float(state.state) == 1


def seed_restore(hass, total=4.5, baseline=102, attributes=None, last_updated=None):
    """Use the legacy RestoreSensor format, including a converted display state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    ENTITY,
                    "999",
                    {"last_source_value": baseline, **(attributes or {})},
                    last_updated=last_updated,
                ),
                {"native_value": total, "native_unit_of_measurement": "m³"},
            )
        ],
    )


async def test_legacy_restart_restore(hass, setup_meter):
    """Restore the native total and raw baseline without replaying old usage."""
    seed_restore(hass)
    await setup_meter(source="102")
    state = hass.states.get(ENTITY)
    assert float(state.state) == 4.5  # Not the converted state string '999'.
    assert state.attributes["last_source_value"] == 102
    state = await update_source(hass, "102")
    assert float(state.state) == 4.5
    state = await update_source(hass, "103")
    assert float(state.state) == 5.5


async def test_downtime_delta_counted_once(hass, setup_meter):
    """A reading newer than the stored baseline is counted only once."""
    seed_restore(hass, total=4.5, baseline=100)
    await setup_meter(source="102")
    state = await update_source(hass, "103")
    assert float(state.state) == 7.5
    state = await update_source(hass, "103")
    assert float(state.state) == 7.5


@pytest.mark.parametrize("total", [None, "bad", "nan", "inf", -1])
@pytest.mark.parametrize("baseline", [None, "bad", "nan", "inf"])
async def test_invalid_restore(hass, setup_meter, total, baseline):
    """Invalid historic values cannot poison future finite readings."""
    seed_restore(hass, total=total, baseline=baseline)
    await setup_meter()
    state = await update_source(hass, "101")
    assert float(state.state) == 1
    assert state.attributes["last_source_value"] == 101


async def test_unavailable_source_does_not_erase_restored_unit(hass, setup_meter):
    """Keep native units until the source is ready to provide metadata."""
    seed_restore(hass, attributes={"device_class": "gas", "icon": "mdi:meter-gas"})
    await setup_meter(source="unavailable", attributes={"icon": "mdi:gauge"})
    assert hass.states.get(ENTITY).attributes["unit_of_measurement"] == "m³"
    assert hass.states.get(ENTITY).attributes["device_class"] == "gas"
    state = await update_source(hass, "103")
    assert float(state.state) == 5.5
    assert state.attributes["device_class"] == "gas"


async def test_existing_registry_entity_is_reused(hass, entry, setup_meter):
    """An existing user-renamed entity keeps identity and restores its own state."""
    registry = er.async_get(hass)
    entry.add_to_hass(hass)
    original = registry.async_get_or_create(
        "sensor",
        "smart_utility_meter",
        entry.entry_id,
        config_entry=entry,
        suggested_object_id="my_existing_gas",
    )
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(original.entity_id, "7", {"last_source_value": 102}),
                {"native_value": 7, "native_unit_of_measurement": "m³"},
            )
        ],
    )
    await setup_meter(source="102")
    assert hass.states.get(ENTITY) is None
    assert float(hass.states.get(original.entity_id).state) == 7
    assert registry.async_get(original.entity_id).id == original.id
    assert registry.async_get(original.entity_id).unique_id == entry.entry_id


@pytest.mark.parametrize("marker", [None, "2026-10-26", "invalid"])
async def test_restart_after_missed_midnight(hass, setup_meter, marker):
    """Yesterday's total resets, including states from before date tracking."""
    attributes = {} if marker is None else {"accumulation_date": marker}
    seed_restore(
        hass,
        attributes=attributes,
        last_updated=dt_util.utcnow() - timedelta(days=1),
    )
    await setup_meter(source="102")
    state = hass.states.get(ENTITY)
    assert float(state.state) == 0
    assert state.attributes["last_source_value"] == 102
    state = await update_source(hass, "103")
    assert float(state.state) == 1


async def test_serialized_restore_storage(hass, entry, setup_meter, hass_storage):
    """Round-trip HA's restore storage without relying on recorder or code files."""
    await setup_meter()
    await update_source(hass, "103")
    store = restore_state.async_get(hass)
    await store.async_dump_states()
    assert "core.restore_state" in hass_storage
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Discard the in-memory unload cache and load the serialized snapshot.
    await store.async_load()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert float(state.state) == 3
    assert state.attributes["last_source_value"] == 103
    state = await update_source(hass, "104")
    assert float(state.state) == 4


async def test_unload_reload_cleans_listeners(hass, entry, setup_meter):
    """Every reload cancels both subscriptions before registering replacements."""
    from custom_components.smart_utility_meter import sensor

    original_state = sensor.async_track_state_change_event
    original_time = sensor.async_track_time_change
    cancels = []

    def track(original, *args, **kwargs):
        cancel = original(*args, **kwargs)
        wrapped = Mock(wraps=cancel)
        cancels.append(wrapped)
        return wrapped

    with (
        patch.object(
            sensor,
            "async_track_state_change_event",
            side_effect=lambda *a, **kw: track(original_state, *a, **kw),
        ),
        patch.object(
            sensor,
            "async_track_time_change",
            side_effect=lambda *a, **kw: track(original_time, *a, **kw),
        ),
    ):
        await setup_meter()
        await update_source(hass, "102")
        registry_id = er.async_get(hass).async_get(ENTITY).id
        for _ in range(3):
            previous = list(cancels)
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            for cancel in previous:
                cancel.assert_called_once_with()
        state = await update_source(hass, "103")
        assert float(state.state) == 3
        assert er.async_get(hass).async_get(ENTITY).id == registry_id
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        for cancel in cancels:
            cancel.assert_called_once_with()
