# Marketplace and development audit

Audit date: 27 October 2026. Scope: the working tree's publishable files, all four reachable Git commits, current official Home Assistant/Marketplace guidance, and read-only GitHub repository metadata. No live Home Assistant installation was modified, no changes were pushed, and no release or visibility change was made.

## Compatibility decisions

- **Domain:** remains `smart_utility_meter`, in the single integration folder `custom_components/smart_utility_meter/`.
- **Sensor unique ID:** remains the config entry ID. There is no entity-registry migration or replacement sensor. A test pre-registers an existing entity with a customized entity ID and verifies that setup reuses its registry entry and restores its values.
- **Config-entry identity:** retains the source entity ID as its unique ID, existing entry IDs, original titles and options. The schema stays at version 2. Migration copies all data, adds a missing name without overwriting a saved custom name, remains idempotent, and refuses a future major schema.
- **Naming:** retains the full user name and `suggested_object_id`. No `has_entity_name`/translation-key conversion changes existing entity naming. Translations now clarify that the name only suggests the initial ID.
- **Restore data:** keeps the `RestoreSensor` native value/unit representation and existing `last_source_value` state attribute. Moving the baseline to a new extra-data class or another sensor would need compatibility work and offers little benefit here. No `persistent_directory` or separate store was added.
- **Statistics:** retains `TOTAL_INCREASING`, six-decimal accumulation, the midnight drop to zero, inherited units, and existing entity IDs. No new `last_reset` or alternative state class changes statistics semantics. Recorder database contents are never accessed or rewritten by this integration.
- **Delta semantics:** source decreases and filtered spikes still update the baseline. Zero disables filtering. An erroneous temporary dip can count its recovery; distinguishing that from a real meter reset would change established behaviour. This limitation is now explicit in the README.

Keeping config entries and registry/storage files means identity, associated recorder history/statistics, and valid saved daily total/baseline should survive file replacement. This is supported by the registry/reload/restore tests, not a claim that a live production upgrade or recorder statistics compilation was performed. A normal next-day reset still clears the daily total. Back up Home Assistant and restart normally; a hard crash may lose changes since Home Assistant's last restore snapshot.

## Packaging and manifest

The root `hacs.json` contains the display name and a minimum Home Assistant version, with the standard repository layout. Home Assistant 2026.10.0 is a conservative supported floor for the modern APIs/Python syntax used here; regression tests pin 2026.10.4. Marketplace itself starts with 2026.11, while 2026.10 can use HACS. Earlier Home Assistant releases have not been validated by this work.

Manifest fields `domain`, `name`, `version`, `config_flow`, `documentation`, `issue_tracker`, `codeowners`, `integration_type`, `iot_class`, `dependencies` and `requirements` are retained with their existing values. `helper` is appropriate. `local_push` matches the event-driven core Utility Meter helper's convention. Empty dependencies/requirements are correct: the integration uses Home Assistant and its existing dependencies, with no additional client package. Categories `helpers.calculate_value` and `energy.meters_monitoring` improve Marketplace discovery. Key ordering was changed because hassfest requires domain/name followed by alphabetical keys.

The integration ships its own original `brand/icon.png` and `icon@2x.png`, with an editable SVG source. The complete MIT license implements the license already declared by the README. Release archives need no build step or attached ZIP. Keep release/tag and manifest version equal: **`1.0.0`** is the first release recommendation, since no releases exist and the persisted schema/identities are unchanged. Use the release checklist before publishing.

## Restore, metadata and lifecycle findings

- `RestoreSensor.async_get_last_sensor_data()` is the correct native-value restore API. The old README's recorder claim was incorrect: Home Assistant's restore-state store saves the native value/unit and the entity state attributes independently of recorder.
- Invalid, missing, negative, NaN and infinite restored totals cannot poison the accumulator. Invalid/missing baselines seed from the current or first finite reading. Non-finite source readings and arithmetic overflows are ignored safely.
- A valid restored baseline is kept rather than blindly replaced by the source's current reading. Repeated first readings do not replay the old usage. A newer reading after downtime is counted once, subject to the unchanged threshold.
- An additive `accumulation_date` attribute handles midnight missed during shutdown. Legacy states fall back to their saved local update date. Only yesterday's total is cleared; the source baseline survives. Downtime usage cannot be accurately split between days and is assigned to the current day on the next reading.
- Restored native units and compatible saved device class/icon remain available while the source is starting. Finite source states provide units, compatible device class and icon. Measurement-only device classes are not copied onto a total. Modern display precision comes from entity registry sensor options, including the user's selected precision, with the old state-attribute fallback retained. A helper's own display overrides continue to take precedence.
- `async_track_state_change_event` and `async_track_time_change` callbacks do no blocking I/O. Both cancellation callbacks are registered with `async_on_remove`. The real platform unload path cancels them before replacements are created.
- Options use the current `self.config_entry` property without a custom constructor. `OptionsFlowWithReload` handles changed options; the former update listener was removed so the two mechanisms cannot conflict. Options still take precedence over initial data, and unrelated persisted option keys are retained.
- Midnight uses Home Assistant's local-time scheduler, rather than a fixed 24-hour interval or host timezone. Real scheduler tests cover Europe/London's spring and autumn DST changes, baseline retention, and the first following increment.
- Unavailable, unknown, removed and non-numeric source states preserve the helper's numeric last-known daily value. This existing availability behaviour is documented. Automatic registry tracking of source renames, dynamic unit conversion of accumulated values and distributing downtime usage across days were not added.

## Quality scale and proportionality

The audit follows applicable Integration Quality Scale principles: UI configuration and duplicate prevention, stable identity, automatic migration, tested setup/unload, no polling, asynchronous callbacks, useful debug logging, full English flow translations, and installation/options/removal/troubleshooting documentation. This custom helper does not claim a formal quality tier.

No coordinator, API client, runtime-data wrapper or new architectural layer is needed for one derived entity. Diagnostics would duplicate the existing source/threshold/baseline attributes; there are no credentials or remote service responses to redact. Authentication, discovery, reauthentication, devices, services, and connection retries are not applicable. No repair is created for transient missing source readings: the helper already retains its baseline and resumes on valid readings, and troubleshooting explains what to inspect. Marketplace handles restart repairs for code updates.

The English translation file remains complete and agrees with `strings.json`. Source-derived units/classes/icons remain dynamic, so entity naming was not converted to a fixed translatable sensor description. Broad exception suppression and recurring warning logs were avoided; expected invalid values and filtered spikes log at debug level.

## Validation performed

- Behavioural regression suite on Home Assistant **2026.10.4** with `pytest-homeassistant-custom-component==0.13.375`. Covers UI entry creation, duplicate sources, automatic/idempotent v1 migration, future schema rejection, bounded/unlimited deltas, source resets/spikes/invalid values, native restore and baseline continuity, invalid restore data, missed midnight, DST, existing renamed registry entities, option reload identity/continuity, and repeated listener cleanup. The restore-storage test serializes Home Assistant's actual restore store with the test storage backend; it does not substitute recorder for restore state.
- Ruff lint and formatting checks, JSON parsing, translation equality, PNG sizes, repository layout, matching manifest/release version and `git diff --check`.
- **Full standalone hassfest passes** against Home Assistant Core source commit `32a6aad1321c86488f1c607588932d1406f61e01`. The container pull was denied by GHCR in this environment, so the official Python validator ran directly from that checkout, in a separate environment with its dependencies. No plugins/checks were skipped.
- **Current HACS schemas pass** for `hacs.json`, integration manifest and categories, using HACS source commit `a15e87ec0d1c82e58f1ddbaf17669d3eaa261eb8`; bundled brand assets are present. This is local schema validation, not a full remote HACS Action run. That action reads GitHub-hosted content and needs the changes pushed plus a workflow GitHub token. The new workflow runs `hacs/action@main` with category `integration` and no ignored checks.
- GitHub Actions also runs hassfest and the regression/lint jobs on pushes (including tags), pull requests, daily schedules and manual dispatch. Tag runs reject a release tag that differs from the manifest. The HACS action has PR comments disabled and needs only read access.

CI success and a backed-up real installation upgrade remain release gates. A schema pass alone does not claim catalog acceptance or verify the production recorder database.

## Public repository readiness

**Publishing appears safe with respect to credentials and Home Assistant runtime data in the audited files/history.** Gitleaks **8.30.1**, with default rules and redacted output, found no leaks in all four reachable commits or the publishable working-tree snapshot. Manual inspection found no tokens, passwords, private keys, private endpoints, actual household readings, config-entry IDs, restore stores, recorder databases, hard-coded installation paths or environment-specific runtime configuration. The Python environment, caches and dotenv files are excluded from new commits by `.gitignore`.

Git metadata does contain the author's real name and a non-noreply email address. Those are personal identifying data and will be visible in public commit history; they were not rewritten. The GitHub handle, repository links and generic `sensor.gas_total` example are intentional public metadata/examples. A secret scan does not prove the absence of every possible sensitive value.

Both the connected GitHub tool and an unauthenticated GitHub API read reported the repository **already public** at audit time, contrary to the request's private-repository description. No visibility change was made. The repository already has a description, topics and Issues enabled. It has **zero Releases** and GitHub has not yet detected a license; pushing the new MIT `LICENSE` should address the latter. Review whether the existing author identity/email is acceptable; publishing this code does not publish Home Assistant's separate runtime storage.

## Official references

- [Marketplace installation model and the 2026.11 transition](https://contributors.home-assistant.io/marketplace/how-it-works/)
- [Custom integration packaging](https://contributors.home-assistant.io/marketplace/guides/integrations/), [hacs.json](https://contributors.home-assistant.io/marketplace/reference/hacs-json/), [validation](https://contributors.home-assistant.io/marketplace/reference/validation/)
- [Releases and updates](https://contributors.home-assistant.io/marketplace/guides/releases/), [catalog review](https://contributors.home-assistant.io/marketplace/guides/catalog/)
- [Manifest](https://contributors.home-assistant.io/core/integrations/manifest/), [categories](https://contributors.home-assistant.io/core/integrations/categories/), [local brand assets](https://contributors.home-assistant.io/core/integrations/brands/)
- [Sensor native restoration and total-increasing statistics](https://contributors.home-assistant.io/core/entities/sensor/)
- [Options flows and automatic reload](https://contributors.home-assistant.io/core/integrations/options-flow/)
- [Integration Quality Scale](https://contributors.home-assistant.io/core/quality-scale/)
