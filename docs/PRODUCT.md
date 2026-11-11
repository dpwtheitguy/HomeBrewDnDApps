# Complete Guide to Fighters

## Confirmed direction

Native Android app for Samsung Galaxy Tab A 8.0 (2019), SM-T290. User expects to install LineageOS; exact Android/API version remains to be confirmed. Development host is Pop!_OS with COSMIC/Wayland. As of November 7, 2026, the tablet has not arrived; the user expects it in about a week. Development and headless verification can proceed before physical-device acceptance testing. Work offline, without accounts or Google Play Services. D&D 2024 revised fifth edition (user calls it 5.5e), fighter only, levels 1–20. No multiclassing in the first release. The planned app family includes Complete Guide to Fighters, Complete Guide to Wizard, Complete Guide to Ninja, and Arms and Equipment Guide, with more titles as needed. Use the [independently versioned catalog](SHARED-CATALOG.md) and shared proficiency, pricing, and exchange definitions across titles.

## Release requirements

- Multiple independent characters with autosave, names, portraits/optional local images, and delete/restore safeguards.
- Named immutable character snapshots, automatic snapshots before level-up, compare versions, restore as a new current revision, and branch a character into another build. Preserve choices and the rules/content version used to calculate each snapshot.
- Guided creation: ability score method, origin/background/species, proficiencies, starting equipment, and every fighter choice. Explain why choices are available or unavailable.
- Guided advancement through level 20 with a preview before applying changes. Track ability improvements/feats, fighting styles, weapon mastery, subclass progression and resources. Complete fighter support includes Champion, Battle Master, Eldritch Knight, and Psi Warrior as the intended 2024 core subclass scope; source availability must be tracked explicitly. Eldritch Knight requires spell selection, slots, concentration and casting support even though this is a fighter-only app.
- Play dashboard: HP/max/temp HP, AC, initiative, speed, attacks, saving throws, skills, conditions, death saves, hit dice, rests and feature uses. Derived statistics must show their contributing modifiers.
- Dice: tap attacks, damage, saves, skills and initiative to roll; manual dice tray, advantage/disadvantage, critical damage, transparent modifiers and roll history. Do not spend limited resources merely by opening an explanation. Allow undo of resource use.
- Every ability, item and statistic opens a brief plain-language TLDR, detailed mechanics with source reference, and creative usage suggestions. Distinguish rules-supported tactics from ideas requiring a DM ruling. Keep explanations available offline; curate suggestions rather than require an online AI call.
- Equipment: searchable catalog, filters, inventory quantities, currency, weight, equipping, attunement, charges, consumables, weapon properties/mastery and item-granted actions. Include complete core-book coverage as a catalog goal, original expanded items, and an extensive BG3-derived/adapted pack. Track coverage rather than label partial catalogs complete.
- PDF export for current or historical character versions: readable character sheet, optional ability reference pages, source/content version and snapshot label. Android print/share/save workflow. Also export/import structured backups; a PDF is not a restorable backup.

## Content design

Use separate versioned packs: SRD 5.2.1, additional core content, original/homebrew content, BG3 tabletop adaptations, and user-provided content. Store stable identifiers, source references, attribution/license metadata, original rules context, and adaptation notes. The SRD is a reusable baseline, not a substitute for the full core catalog. Verify redistribution permissions for each additional pack before distributing it. Owning a book is not itself a redistribution license.

Never silently treat a BG3 mechanic as a tabletop rule. Each adapted item needs an explicit action cost, targets/range, duration, recovery/charges, saving throw/DC when applicable, stacking/attunement and balance notes. Mark adaptations in search results, character calculations and PDF output. Campaign-level toggles control enabled packs.

## Tablet interaction

Design for the 8-inch 1280×800 physical display in portrait and landscape, using Android density-independent sizing rather than treating pixels as dp. Use large touch targets (design goal: at least 48dp), readable/scalable text, clear contrast, restrained animation and no hover-only controls. Portrait uses bottom navigation; landscape can show the sheet alongside the explanation panel. Preserve state across rotation and process recreation. Large catalogs must use indexed search and lazy lists. Actual tablet measurements decide performance budgets.

Primary areas: Characters, Play, Abilities, Equipment, History. Character creation/level-up are guided flows. A persistent dice entry point is available during play.

## Suggested implementation architecture

Kotlin with Jetpack Compose; local Room database for characters, inventory and immutable snapshots. Separate pure Kotlin rules engine from Android UI/storage. Data-driven content with validated schemas and explicit effects rather than arbitrary executable pack scripts. Use Android platform PDF/printing APIs. These are proposed implementation choices, not dependencies already installed or validated.

Test rules calculations independently from UI: fighter progression at every level, feature recovery, equipment effects, subclass choices and Eldritch Knight spellcasting. Test snapshot restore/branch, database migrations, backup round trips, process recreation and PDF pagination. Reconcile implemented coverage against a versioned rules checklist before describing fighter support as complete.

## Delivery sequence

1. Confirm tablet OS and prepare reproducible Android build/test tooling; prove a small native shell runs on device.
2. Deliver character creation/storage, version history, basic play dashboard and dice as a usable vertical slice.
3. Complete level 1–20 progression and all intended fighter subclasses with reviewed rules coverage.
4. Finish explanation/reference content, equipment behavior, backup and PDF output.
5. Expand core and BG3 adaptation catalogs with explicit coverage and source checks.
6. Add opt-in nearby multiplayer after single-device reliability is established.

## Bluetooth stretch feature

Shared protocol for this app and future class-specific sister apps, with discovery, user-approved session joining and version negotiation. Items, healing and spell effects are offers that the recipient reviews and accepts. Use stable event IDs and acknowledgements to prevent duplicated transfers/healing; item transfer needs ownership/quantity reconciliation and failure recovery. Keep an audit trail and permit corrections. Do not allow nearby devices to overwrite character state directly. Test on real devices, including the actual LineageOS Bluetooth stack. Discovery transport and OS permissions require a separate prototype.

## Open inputs

- Installed LineageOS version / Android API level (stock compatibility is a proposed baseline).
- Availability and permitted distribution of non-SRD core and BG3 content.
- Prior Jogging app source location: not found in the current workspace or local Codex history inspected so far.

## References

- https://www.dndbeyond.com/srd
- https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf
- https://www.samsung.com/us/business/support/owners/product/galaxy-tab-a-8-0-2019-wi-fi/

## Additional confirmed directions, November 7, 2026

- Use BG3 as a close visual and navigation reference, adapted to tablet touch controls. See UI-DIRECTION.md.
- Generic artwork per item type is acceptable; upgrade to specific art as suitable sources become available.
- Each item needs a contextual approximate buy/sell value. The BG3-inspired pricing option uses total Persuasion, merchant attitude and difficulty; tabletop use is an explicit campaign policy. Preserve unknown values.
- Deep setting research priority: Mystara / Known World, all GAZ gazetteers and setting boxes first, then Curse of Strahd / Ravenloft and Planescape. Internet and fan archives are authorized research sources.
- Conversions may change mechanics and add flavor to evoke BG3. Preserve a baseline 2024 conversion and independently labeled optional enhancements, with provenance and review status.
- Current work is the data collection stage. Initial imports do not establish complete sourcebook coverage or tested Android gameplay.

## Source expansion and search, November 7, 2026

Add Baldur's Gate I–III, Forgotten Realms, Return to the Temple of Elemental Evil (Greyhawk), likely Zanzer's Dungeon, Diablo I–IV, and edition-appropriate equipment guides to the source roadmap. Mystara remains first. The user proposes nation/people/culture loops across item categories; implement a persistent coverage matrix rather than claim an exhaustive worldwide list. Search, typed origin/culture facets and saved defaults are first-class design requirements. See SEARCH-AND-RESEARCH.md.
