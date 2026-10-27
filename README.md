# Smart Utility Meter

A Home Assistant helper that accumulates daily increases from a cumulative source sensor, such as an IHD (In-Home Display) gas or electricity total. It resets to zero at midnight in Home Assistant's configured timezone and filters unusually large increases.

The helper exposes a `total_increasing` sensor. Gas, energy and water sources with suitable units and device classes can be used with long-term statistics and the Energy dashboard. This helper does not integrate power readings into energy.

## Installation

### Marketplace (preferred)

Home Assistant's built-in Marketplace is available starting with **2026.11**. Earlier versions use HACS. This release supports Home Assistant **2026.10.0 or newer**; the regression suite runs against **2026.10.4**.

[![Open Smart Utility Meter in Marketplace or HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=haveyourphil&repository=homeassistant-smartutilitymeter&category=integration)

1. Open the link above, or find **Smart Utility Meter** in **Settings → Marketplace**.
2. Until the repository is accepted into the catalog, add `haveyourphil/homeassistant-smartutilitymeter` as a custom repository with category **Integration**. Custom repositories require a GitHub connection in Marketplace.
3. Install the latest published release. Restart Home Assistant if prompted; updates to an already loaded integration require a restart.

The link opens HACS on older installations and Marketplace on 2026.11 and later. See the [official Marketplace guide](https://contributors.home-assistant.io/marketplace/how-it-works/).

### Switching from a manual installation

**Keep your existing Smart Utility Meter helpers/config entries. Do not delete and recreate them.**

1. Make a Home Assistant backup, including its configuration/storage and recorder database.
2. Add this repository to Marketplace (or HACS) and download the release over the existing integration at `config/custom_components/smart_utility_meter/`.
3. Restart Home Assistant normally so it can save and restore the running entities.
4. Check the same helper entity IDs, daily totals, `last_source_value` attributes and Energy/statistics views.

The installation method changes who manages the code files. The integration domain, config entries, sensor unique IDs (the config entry IDs), and entity IDs remain the same. Home Assistant keeps config entries, entity registry identity and restore data outside `custom_components`; recorder keeps history/statistics separately. Replacing this integration's files does not move or delete any of those stores. No `persistent_directory` is needed.

### Manual installation

1. Copy `custom_components/smart_utility_meter/` into `config/custom_components/`, preserving that folder name.
2. Restart Home Assistant.
3. For updates, replace only that integration's code folder, keep your existing helpers, and restart normally.

## Setup and options

1. Go to **Settings → Devices & services → Helpers → Create helper**, or **Add integration**.
2. Select **Smart Utility Meter**.
3. Enter a name, choose the cumulative source sensor, and set the maximum single-step increase.

The name suggests the entity ID on first creation, for example `Daily Gas Usage` suggests `sensor.daily_gas_usage`. Existing registry IDs are respected. You can customize the entity name/display settings in Home Assistant. One helper per source entity is allowed.

Open the helper's **Configure** options to adjust the threshold. Saving a changed threshold reloads the helper and retains its accumulated total, source baseline and identity. The threshold uses the source sensor's displayed unit; its default is `10`, and `0` disables filtering.

## How readings are handled

| Source reading | Action |
| --- | --- |
| First valid reading without a restored baseline | Establish a baseline; add nothing |
| Positive delta at or below the threshold | Add the delta to the daily total |
| Positive delta above the threshold | Ignore the delta and update the baseline |
| Zero or negative delta | Add nothing and update the baseline |
| Unavailable, unknown, removed, non-numeric, NaN or infinite | Keep the last valid baseline and total |

At local midnight, the total resets to zero and the baseline remains intact. Home Assistant's local-time scheduler handles DST, including 23- and 25-hour days.

Decreases are treated as source meter resets. The next increase counts from that lower baseline. A temporary erroneous dip followed by recovery can therefore count the recovery; the spike threshold may filter it, but cannot distinguish every glitch from a genuine meter reset. Use a reliable cumulative consumption source.

### Persistence and restarts

The integration uses **`RestoreSensor`/`RestoreEntity` restore-state storage**, normally `config/.storage/core.restore_state`, **not recorder**, to recover the native daily total and `last_source_value`. Recorder is independently responsible for history and statistics. No runtime files are written into the integration folder.

Home Assistant snapshots restore state periodically and during a normal shutdown; an abrupt crash can lose changes since the last snapshot. A valid restored baseline is retained, so repeated readings do not count usage twice. If the baseline is missing or invalid, the current/first valid reading seeds a fresh one. Invalid or negative saved totals fall back to zero; native restore data avoids confusing a converted display value with the original unit.

If Home Assistant was stopped across midnight, yesterday's total is cleared while the source baseline is kept. A stored `accumulation_date` identifies the local day; older installations use the saved state's local update date on their first upgrade. Usage while Home Assistant was stopped cannot be split across days: the next delta is allocated to the current day and remains subject to the spike threshold. A missing/replaced restore store cannot recover the old total from recorder.

## Sensor and statistics

| Property/attribute | Meaning |
| --- | --- |
| State class | `total_increasing`; the daily drop to zero is an expected meter reset |
| Unit | Copied from the source sensor's state; native unit restored while the source is unavailable |
| Device class | Copied when compatible with `total_increasing`, such as `gas`, `energy` or `water` |
| Display precision | Suggested from the source entity registry settings (or a legacy precision attribute); the helper's own display settings take precedence |
| `last_source_value` | Last valid raw source reading, retained for restart continuity |
| `accumulation_date` | Local date of the daily accumulator |
| `source_entity` | Configured source entity ID |
| `max_increase_threshold` | Effective spike threshold |

The helper retains its numeric accumulated state while the source is unavailable. That value is the last known daily usage; it is not a fresh source measurement. Source metadata is copied when a valid source becomes available. Keep the source's units stable; changing what a source measures needs deliberate handling of its existing statistics. If readings stop after renaming the source, restore its original entity ID; automatic source-registry tracking is not provided.

## Troubleshooting and removal

- **Total stays zero:** check the source is numeric and cumulative. The first reading seeds the baseline. Check whether the threshold is filtering every increase.
- **Source is unavailable:** inspect its integration first. Smart Utility Meter keeps the valid baseline until readings resume.
- **Usage missing after an outage:** inspect the source delta and threshold. Large downtime deltas are filtered just like live spikes.
- **Energy dashboard cannot find the helper:** verify the source has the appropriate gas/energy/water device class and supported unit, and check **Developer tools → Statistics** for unit issues.
- **Debugging:** enable debug logging for `custom_components.smart_utility_meter`; skipped invalid readings and spikes are logged at debug level.

To permanently remove a helper, delete its config entry in Home Assistant. To remove the integration's code too, uninstall the repository through Marketplace/HACS and restart. Deleting entries is for intentional removal, **not installation-method changes or ordinary upgrades**.

## Development and releases

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements_test.txt
.venv/bin/pytest -q
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
```

CI runs regression tests, hassfest and the HACS integration validator on pushes, pull requests, scheduled runs and manual dispatches. No validation checks are ignored. See [the audit notes](docs/AUDIT.md) and [release checklist](docs/RELEASING.md).

The first published release is intended to be **`1.0.0`**, matching `manifest.json` and the existing unpublished version. Keeping it is appropriate because there are no earlier GitHub Releases, no replacement entities and no new config-entry schema. Future releases must advance both the manifest version and the matching GitHub release tag. Config-flow version `2` is a separate schema version.

## License

[MIT](LICENSE). The bundled meter icon is original artwork under the same license.
