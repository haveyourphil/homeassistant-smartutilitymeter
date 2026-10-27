# Releasing Smart Utility Meter

Recommended first release: **`1.0.0`**, with the exact Git tag **`1.0.0`** and manifest version **`1.0.0`**. There is no earlier public release to supersede, and this release preserves the config-entry schema and entity identities. The original manually installed manifest already used this version; Marketplace management is established when the repository is installed.

## Before the first release

1. Review `docs/AUDIT.md`, including the author email addresses already present in Git history. Repository visibility has not been changed by this work.
2. Confirm GitHub metadata before publishing the release. At audit time the repository is already public, has a description/topics and has Issues enabled; no settings were changed. The README already declared MIT; `LICENSE` now contains its full text and must be pushed for GitHub to recognize it.
3. Push the reviewed changes and enable GitHub Actions. Require all three validation jobs to pass. The remote HACS check needs the public repository and GitHub metadata; do not skip checks to qualify for the catalog.
4. Test an upgrade of a backed-up existing Home Assistant installation. Keep its helpers and registry entries. Check the entity IDs, daily value, baseline, statistics and threshold options after restarting normally.
5. Create tag `1.0.0` on the validated commit and publish a **GitHub Release**, not just a tag. The tag workflow checks that its name equals the manifest version. Wait for that run too. GitHub's generated source archive is sufficient; no ZIP release asset or build step is needed.
6. Use the release notes below. Do not mark this release as a pre-release when publishing the stable version.
7. Test installing the released repository as a custom integration in Marketplace/HACS. If desired, submit it to the integration list in [`hacs/default`](https://github.com/hacs/default) for catalog inclusion. Acceptance is a separate review and is not automatic.

## Suggested release notes

Smart Utility Meter is now packaged for Home Assistant Marketplace and HACS.

**Existing users: keep all Smart Utility Meter helper/config entries.** Back up Home Assistant, download this release over `custom_components/smart_utility_meter`, and restart normally. Do not delete/recreate helpers. The domain, sensor unique IDs and existing entity IDs are preserved, keeping existing recorder history/statistics and valid restore-state data associated with the same entities.

- Adds Marketplace metadata, bundled icons, validation workflows and behavioural regression tests.
- Uses the current options flow and reloads once when the threshold changes, retaining usage and baseline.
- Ignores invalid/non-finite source and restored values safely.
- Handles a missed midnight during shutdown, retaining the source baseline. Yesterday's total resets as part of the normal daily cycle; downtime usage is assigned to the current day on the next reading, subject to the spike filter.
- Copies compatible device classes and registry display precision, and retains restored native units while the source is unavailable.
- Corrects persistence documentation: restore-state storage preserves runtime values; recorder preserves history/statistics.

Requires Home Assistant 2026.10.0 or newer. The built-in Marketplace is available from 2026.11; 2026.10 users can use HACS or manual installation.

## Later releases

Increment `manifest.json`'s version and publish a release with the same tag. Keep previous releases available. If the code needs a newer Home Assistant version, update `homeassistant` in that release's `hacs.json`. Never change domain, entity unique IDs or persisted keys without an explicit compatibility migration and regression tests.

Official references: [release versions](https://contributors.home-assistant.io/marketplace/guides/releases/), [validation](https://contributors.home-assistant.io/marketplace/reference/validation/), [catalog submission](https://contributors.home-assistant.io/marketplace/guides/catalog/).
