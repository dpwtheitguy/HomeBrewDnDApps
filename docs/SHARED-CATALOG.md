# Shared item catalog releases

Complete Guide to Fighters, Complete Guide to Wizard, Complete Guide to Ninja, and Arms and Equipment Guide can pin the same offline catalog release. Each app ships its own code and can move to a newer compatible catalog on its own schedule. New titles can adopt the same release without changing the catalog.

## Build a release

Run from the project root after rebuilding the catalog if source data changed.

```sh
.venv/bin/python scripts/build_catalog.py
.venv/bin/python scripts/package_catalog.py --version 2026-11-11.2
```

The packager writes `outputs/shared-item-catalog-2026-11-11.2.zip`. Use a new content version whenever a packaged file changes. This package contains the SQLite search index, generic SVG icons and credits, source and license notices, taxonomy, filter presets, and schemas. Source fixtures and research reports stay in the workspace. Packaged notices preserve provenance for the current internal data snapshot. Review redistribution terms before publishing the full snapshot with a public app.

## App integration contract

- Read the root `manifest.json` for the catalog ID, format version, content version, database path, and per-file byte counts and SHA-256 hashes. Content versions identify snapshots. Increment the format version when an incompatible change requires reader updates.
- An app can bundle a pinned version at build time. For an optional post-install update, the app should validate the format and files in a staging directory, then activate the new directory as a unit. Keep the previous usable version available until the new copy opens successfully. The hashes verify file integrity. A future online updater also needs an authenticated release source.
- Store the catalog in its own app-private directory and open SQLite read-only. Keep characters, inventory instances, preferences, and history in the app's writable database. Store stable item IDs and the catalog version used by saved builds. Keep the referenced snapshot or preserve the item data a historical build needs before removing an older catalog.
- Resolve an item's `image_path` relative to the extracted `catalog/` directory. The SQLite index uses FTS5. Verify FTS5 availability with the chosen Android SQLite runtime on the target LineageOS build.
- The complete SQLite snapshot is about 366 MiB after extraction. Each app gets its own copy under this integration plan. Measure install space and search performance on the tablet before choosing the default bundled content.

Android catalog loading and post-install update handling are future app implementation work.
