# Smart Utility Meter

A Home Assistant helper integration that tracks daily usage from any numeric sensor — designed for IHD (In-Home Display) gas or electricity totals that report a running cumulative value.

It accumulates increases throughout the day and resets to zero at midnight in your configured local timezone, exposing a `total_increasing` sensor suitable for HA's energy dashboard and long-term statistics.

---

## Features

- Tracks daily increases from any numeric source sensor
- Resets automatically at midnight (local time)
- Configurable spike filter — single-step increases above a threshold are ignored
- Persists state across HA restarts with no gap or double-counting
- Configured entirely through the UI — no YAML required

---

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install **Smart Utility Meter**.

### Manual

1. Copy the `custom_components/smart_utility_meter/` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Smart Utility Meter**.
3. Select your source sensor (e.g. your IHD total gas entity).
4. Set a maximum single-step increase threshold (see below).

### Options

After setup, open the integration's options to adjust:

| Option | Description |
|---|---|
| **Maximum single-step increase** | Any reading increase larger than this value in a single update is treated as a spike or glitch and ignored. Set to `0` to disable. |

---

## How it works

Each time the source sensor reports a new value, the integration computes the delta from the previous reading:

| Delta | Action |
|---|---|
| Positive, within threshold | Added to the daily total |
| Positive, exceeds threshold | Ignored (spike filter); baseline updated |
| Zero or negative | Ignored; baseline updated to prevent double-counting on recovery |

At midnight the daily total resets to zero. The source sensor baseline is preserved across the reset so the first reading of the new day is handled correctly.

On HA restart the accumulated total and source baseline are both restored from the recorder, so there is no discontinuity.

---

## Exposed sensor

| Attribute | Value |
|---|---|
| State class | `total_increasing` |
| Unit | Inherited from the source sensor |
| `last_source_value` | The last raw reading from the source |
| `source_entity` | The configured source entity ID |
| `max_increase_threshold` | The configured spike filter threshold |

---

## Extending

The integration is intentionally small. All logic lives in [`sensor.py`](custom_components/smart_utility_meter/sensor.py). Common extension points:

- **Different reset schedule** — replace `async_track_time_change` in `async_added_to_hass` with your own schedule (e.g. weekly, monthly).
- **Multiple sensors per source** — `async_add_entities` accepts a list; add extra `SmartUtilityMeterSensor` variants with different config.
- **Device class** — set `_attr_device_class = SensorDeviceClass.GAS` (or `ENERGY`) on the sensor class if you want HA to apply unit conversion and show the entity in the energy dashboard automatically.
- **Notifications on threshold** — add logic inside `_handle_source_state_change` after the accumulation step.

---

## License

MIT
