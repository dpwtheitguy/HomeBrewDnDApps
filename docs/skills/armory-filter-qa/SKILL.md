---
name: armory-filter-qa
description: Validate Arms and Equipment Guide Android search, filters, pagination, and item-card regressions against the installed catalog scope.
---

# Armory filter QA

1. Identify the installed app version and catalog content version from Android and its embedded manifest. Use the SQLite index, price supplement, sources, and taxonomy from that exact release as the expected dataset.
2. Choose cases for that release. The existing `apps/arms-and-equipment/tests/filter_matrix.py` main runner assumes the full workspace catalog and fixtures from BG3, Mystara, and shops. For an SRD-only build, reuse its WebView helpers and applicable cases with an oracle extracted from the matching release ZIP. Treat intentionally excluded features as out of scope for positive checks and test their absence separately. Stop interpreting aggregate results if the expected and installed catalog scopes differ.
3. Exercise browse totals, exact and partial names, search scope, relevant category and source filters, A–Z, price limits, sorts, pagination, and clear/reset. Include positive controls and expected exclusions. Use the existing headless AVD and ADB WebView debugging with Python `websocket-client`. Pass `--serial` when running the full matrix on a different emulator. Keep separate emulator sessions when running simultaneous reviews.
4. Run the [item onboarding regression step](../armory-combat-qa/item-onboarding.md) in both layouts where available. Assert fields within their rendered panel or row. For example, compare Dwarven Half Plate’s displayed AC with its SRD bonus. Searching the entire card for “+2” can pass when the prose is right and the stat panel is wrong.
5. Report navigation, structured rules, and usability separately. List passed, failed, and out-of-scope checks with the build and dataset. A count mismatch against the wrong oracle is a harness problem. A contradiction reproduced in a rendered card against its exact source is an app defect. An excluded-source test still matters when its purpose is to verify absence.
