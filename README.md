# HomeBrewDnDApps

## Android test download

[Download Arms and Equipment Guide 0.4.9 (APK)](https://raw.githubusercontent.com/dpwtheitguy/HomeBrewDnDApps/android-test-builds/arms-and-equipment-guide-0.4.9-debug.apk) · [SHA-256 checksum](https://raw.githubusercontent.com/dpwtheitguy/HomeBrewDnDApps/android-test-builds/arms-and-equipment-guide-0.4.9-debug.apk.sha256)

Open the downloaded APK on your Android device. If prompted, allow installs from the app that opened the file. This debug build bundles the offline catalog. It passed emulator testing. Physical-tablet testing is pending.

[Android build and testing guide](apps/arms-and-equipment/README.md)

## Project overview

A family of planned offline Android apps for the Galaxy Tab A 8.0 (SM-T290). **Arms and Equipment Guide** is the first app. **Complete Guide to Fighters**, **Complete Guide to Wizard**, and **Complete Guide to Ninja** are planned character apps. Additional titles can use the same catalog.

The [shared item catalog release](docs/SHARED-CATALOG.md) has its own version and can be included by any title. Each character app owns its progression rules, saves, and release schedule.

The public repository tracks the app source, catalog tooling, and original project data. Local reference PDFs, source snapshots, and generated indexes stay in the workspace. The downloadable test APK is published on a separate branch. Building the full Android app requires a compatible shared catalog ZIP. See [the catalog build guide](docs/SHARED-CATALOG.md).

Current deliverable: [searchable item catalog](catalog/README.md), including separate 2014/2024 sources, third-party packs, BG3 metadata, generic art, contextual price estimates and the first Mystara adaptation drafts.

- [Measured catalog counts](catalog/reports/COUNTS.md)
- [Mystara research and conversions](catalog/settings/mystara/README.md)
- [Shared data, proficiency and pricing design](shared/README.md)
- [Search filters and research loop](docs/SEARCH-AND-RESEARCH.md)
- [Weapon audit workflow](docs/skills/armory-weapon-audit/SKILL.md)
- [Expanded source roadmap](catalog/source-roadmap.json)
- [Product scope](docs/PRODUCT.md)
- [BG3-inspired interface direction](docs/UI-DIRECTION.md)
- [Pop!_OS headless testing workflow](docs/ANDROID-DEVELOPMENT.md)

The current boxed-adventure research pass covers Zanzer, Goblin’s Lair, Haunted Tower, Dragon’s Den and Hail the Heroes with selected drafts and references; Night of the Vampire has checked bibliography and a fan-reported existing-item appearance; its original-book item audit remains pending. See [the research pack](catalog/settings/thunder-rift/README.md).

The [ninja equipment workbench](catalog/settings/ninja/README.md) adds selected 2e / 3e equipment updates and game-inspired 2024 drafts, alongside explicitly unconverted game-reference indexes. Mark of Amber is now queued under Mystara / Glantri.

Every normalized entry now carries [source references and an explicit change log](docs/RECORD-PROVENANCE.md). [Worldbuilding](catalog/settings/worldbuilding/README.md) and [Mystara frontiers](catalog/settings/mystara-frontiers/README.md) extend the data beyond portable equipment.

The [requested-source coverage ledger](docs/RESOURCE-COVERAGE.md) tracks individual resources, explicit item links and outstanding original-book audits.

[Source import charts and publication coverage](catalog/reports/SOURCE-MATERIAL.md) distinguish additive source-pack totals from overlapping book references.

[Gazetteer research progress](catalog/reports/GAZETTEER-PROGRESS.md) separates selected publisher-preview checks, secondary equipment references, trade categories and construction. [Mystara game and novel research](catalog/settings/mystara-media/README.md) is queued after this pass.
