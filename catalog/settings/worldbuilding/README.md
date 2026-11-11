# Worldbuilding construction workbench

The first 2024-compatible house-rule pack contains **48 original proposals** for camps, forts, castles, villages, cities and dungeons. These are data templates, not an implemented building simulator or official Bastion special facilities.

Each proposal separates footprint, construction cost, materials, worker count, duration, occupancy, maintenance and unresolved defenses. Costs are authored campaign estimates; they exclude land, permits, exceptional terrain work, ongoing staff, supplies and taxes. Walls are segments rather than entire perimeters. An empty armory does not include weapons, a library does not include all books, and a workshop does not grant proficiency or free crafting output.

Building sale value and discounts require a local DM appraisal. The portable-item merchant Charisma formula is not automatically applied to buildings, wages or upkeep. Armor Class, Hit Points and damage thresholds remain unresolved until a vehicle/object/siege rules review.

References and queued books:

- The Castle Guide (DMGR2, AD&D 2e).
- Stronghold Builder’s Guidebook (D&D 3.0).
- 2024 DMG Bastions: official overview checked; these proposals do not grant official orders or special-facility rewards.
- Rules Cyclopedia stronghold and dominion rules.
- Hero Builder’s Guidebook: separately queued as a character-building source, not mistaken for the stronghold book.
- Valheim and Conan Exiles: public building and inventory names are reference-only and retain their source-game categories. Stronghold, Dungeon Keeper and Dwarf Fortress remain further construction-research leads.

`record_kind: structure` identifies a project proposal. `record_kind: construction-component` identifies a source building piece, installed fixture or construction reference. Pet tokens and standalone NPC records are not counted as equipment. The overall catalog reports construction separately from portable/other records.

```sh
python3 scripts/search_catalog.py --profile worldbuilding-workbench
python3 scripts/search_catalog.py --source worldbuilding-2024-drafts
python3 scripts/search_catalog.py --tag construction-scale:dungeon
```

All records include source context and explicit applied changes. A blueprint, a completed instance at a map location, ownership, staffing, utility connections, permissions and construction progress will need separate app state. The catalog must not pretend that purchasing a template instantly creates a fortified settlement.
