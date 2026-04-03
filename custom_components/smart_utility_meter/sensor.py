"""Smart Utility Meter sensor — accumulates daily increases from a source entity."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import slugify

from .const import CONF_MAX_INCREASE, CONF_SOURCE_ENTITY, DEFAULT_MAX_INCREASE, DOMAIN

_LOGGER = logging.getLogger(__name__)

# The key under which we stash the last raw source value in state attributes.
# This survives a restart so we can continue accumulating without a gap or jump.
_ATTR_LAST_SOURCE_VALUE = "last_source_value"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensor entity for this config entry."""
    async_add_entities([SmartUtilityMeterSensor(entry)])


class SmartUtilityMeterSensor(RestoreSensor):
    """A daily-resetting accumulator for a source sensor.

    Behaviour:
    - Listens to state changes on ``source_entity``.
    - Adds positive deltas (increases) to a running total.
    - Ignores decreases and no-change events.
    - Ignores any single increase larger than ``max_increase`` (spike filter).
    - Resets to zero at midnight in the HA-configured local timezone.
    - Persists its accumulated value and the last raw source value across restarts
      so there is no discontinuity when HA comes back up.

    State class ``TOTAL_INCREASING`` tells HA's statistics engine that this sensor
    only ever goes up (within a day) and that a drop to zero is an expected reset,
    not missing data.
    """

    # Push-based: we update via event callbacks, not polling.
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._source_entity_id: str = entry.data[CONF_SOURCE_ENTITY]

        # Options take precedence over initial data so the user can adjust the
        # threshold after setup without recreating the entry.
        self._max_increase: float = float(
            entry.options.get(
                CONF_MAX_INCREASE,
                entry.data.get(CONF_MAX_INCREASE, DEFAULT_MAX_INCREASE),
            )
        )

        self._accumulated: float = 0.0
        # The last valid numeric reading we received from the source.
        # None until the first state arrives (or until restored from storage).
        self._last_source_value: float | None = None

        # Unique ID is the config entry ID so each entry maps to exactly one entity.
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.data[CONF_NAME]

        # These are all copied from the source entity in _apply_source_attributes.
        # Declared here so the type checker knows they exist before async_added_to_hass.
        self._attr_native_unit_of_measurement: str | None = None
        self._attr_device_class: str | None = None
        self._attr_icon: str | None = None
        self._attr_suggested_display_precision: int | None = None

        # Flipped to True once we've successfully read attributes from the source.
        # Prevents redundant re-application on every state change.
        self._source_attrs_applied: bool = False

    @property
    def suggested_object_id(self) -> str:
        """Suggest an entity ID derived from the user-configured name.

        HA uses this only on first registration; the user can rename it
        afterwards via the entity registry without affecting the name.
        e.g. "Daily Gas Usage" → sensor.daily_gas_usage
        """
        return slugify(self._attr_name)

    # ------------------------------------------------------------------
    # HA lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore persisted state and register event listeners."""
        await super().async_added_to_hass()

        # --- Restore accumulated value ---
        # RestoreSensor.async_get_last_sensor_data() gives us native_value and unit.
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            try:
                self._accumulated = float(last_sensor_data.native_value or 0)
            except (TypeError, ValueError):
                self._accumulated = 0.0

            if last_sensor_data.native_unit_of_measurement:
                self._attr_native_unit_of_measurement = (
                    last_sensor_data.native_unit_of_measurement
                )

        # --- Restore last source value ---
        # This is stored in extra_state_attributes (see property below) and
        # recovered via async_get_last_state() so we don't miscount the first
        # delta after a restart.
        if (last_state := await self.async_get_last_state()) is not None:
            raw = last_state.attributes.get(_ATTR_LAST_SOURCE_VALUE)
            if raw is not None:
                try:
                    self._last_source_value = float(raw)
                except (TypeError, ValueError):
                    pass

        # --- Copy attributes and seed last_source_value from the source entity ---
        # Both operations read the source state, so we do it in one pass.
        source_state = self.hass.states.get(self._source_entity_id)
        if source_state is not None:
            self._apply_source_attributes(source_state)

            if self._last_source_value is None and source_state.state not in (
                "unavailable",
                "unknown",
            ):
                try:
                    self._last_source_value = float(source_state.state)
                except (TypeError, ValueError):
                    pass

        # --- Register listeners (cleaned up automatically via async_on_remove) ---

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._handle_source_state_change,
            )
        )

        # async_track_time_change fires in the HA-configured local timezone, so
        # hour=0, minute=0, second=0 is midnight local time — exactly what we want.
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_midnight_reset,
                hour=0,
                minute=0,
                second=0,
            )
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def _apply_source_attributes(self, source_state: Any) -> None:
        """Copy display attributes from the source entity's current state.

        HA writes device_class, unit_of_measurement, icon, and
        suggested_display_precision into the state attributes dict, so they're
        available here without touching the entity registry.

        state_class is intentionally NOT copied — this sensor is always
        TOTAL_INCREASING regardless of what the source reports.
        """
        attrs = source_state.attributes

        self._attr_native_unit_of_measurement = attrs.get("unit_of_measurement")
        self._attr_device_class = attrs.get("device_class")
        self._attr_icon = attrs.get("icon")

        raw_precision = attrs.get("suggested_display_precision")
        if raw_precision is not None:
            try:
                self._attr_suggested_display_precision = int(raw_precision)
            except (TypeError, ValueError):
                pass

        self._source_attrs_applied = True

    @property
    def native_value(self) -> float:
        """Return the accumulated total for the current day."""
        return self._accumulated

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose diagnostic attributes.

        ``last_source_value`` is used to restore continuity across restarts.
        The others are informational and make debugging easier.
        """
        return {
            _ATTR_LAST_SOURCE_VALUE: self._last_source_value,
            "source_entity": self._source_entity_id,
            "max_increase_threshold": self._max_increase,
        }

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @callback
    def _handle_source_state_change(self, event: Event) -> None:
        """React to a state change on the source entity.

        The @callback decorator marks this as a synchronous, non-blocking
        function that is safe to call from the event loop directly.
        """
        new_state = event.data.get("new_state")

        if new_state is None or new_state.state in ("unavailable", "unknown"):
            return

        try:
            new_value = float(new_state.state)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Ignoring non-numeric state %r from %s",
                new_state.state,
                self._source_entity_id,
            )
            return

        # Copy source attributes on the first valid state we receive, in case the
        # source entity wasn't ready yet when async_added_to_hass ran.
        if not self._source_attrs_applied:
            self._apply_source_attributes(new_state)

        if self._last_source_value is None:
            # No baseline yet — record this reading and wait for the next one.
            self._last_source_value = new_value
            self.async_write_ha_state()
            return

        delta = new_value - self._last_source_value

        if delta <= 0:
            # Decrease or unchanged.  Update the baseline so that if the source
            # dips and then recovers we don't double-count the recovery.
            # Decreases are NOT added to the accumulated total.
            self._last_source_value = new_value

        elif self._max_increase > 0 and delta > self._max_increase:
            # Single-step increase is suspiciously large — likely a data glitch
            # or a source reset.  Update the baseline so subsequent normal
            # readings work correctly, but don't add the spike to the total.
            _LOGGER.debug(
                "Spike ignored: delta=%.4f exceeds max_increase=%.4f for %s",
                delta,
                self._max_increase,
                self._source_entity_id,
            )
            self._last_source_value = new_value

        else:
            # Normal, bounded increase — accumulate it.
            self._accumulated = round(self._accumulated + delta, 6)
            self._last_source_value = new_value

        self.async_write_ha_state()

    @callback
    def _handle_midnight_reset(self, now: datetime) -> None:  # noqa: ARG002
        """Reset the daily accumulator at midnight local time."""
        _LOGGER.debug("Midnight reset for %s (was %.4f)", self.entity_id, self._accumulated)
        self._accumulated = 0.0
        # Keep _last_source_value intact — the source meter continues from where
        # it was, so the first delta after midnight will be calculated correctly.
        self.async_write_ha_state()
