# Baldur’s Gate 3 item coverage

Source: [BG3 Wiki item index](https://bg3.wiki/wiki/Items).

All 4,395 cached item pages reconcile to catalog records by page and revision ID. Counts use the first item template and its source category.

In-game completeness, equivalent named variants, and 5.5e conversions still require review. The cache includes pages for unobtainable items.

The [BG3 Forge crosscheck](../research/bg3-forge-crosscheck.json) compares 3,139 exported stats rows from game build 4.8.700.7143220 against the wiki-derived catalog. The first pass yielded 2,308 single-record identifier matches, 19 identifier conflicts, 263 name-only candidates, and 549 unmatched rows. Follow-up checks in the audit retain observed wiki revision IDs, historical placement evidence, and unresolved cases. The [Forge source index](../raw/game-reference-indexes/baldurs-gate-3-forge-reference.json) records Raw Sun Crystal and Imperfectly Cut Sun Gem as reported unobtainable.

| Template group | Source category | Records |
|---|---|---:|
| Equipment | Amulets | 84 |
| Equipment | Boots | 70 |
| Equipment | Camp Clothing | 110 |
| Equipment | Camp Shoes | 39 |
| Equipment | Cloaks | 22 |
| Equipment | Clothing | 36 |
| Equipment | Gloves | 87 |
| Equipment | Heavy Armour | 27 |
| Equipment | Helmets | 102 |
| Equipment | Light Armour | 28 |
| Equipment | Medium Armour | 47 |
| Equipment | Musical Instruments | 15 |
| Equipment | Rings | 97 |
| Equipment | Shields | 39 |
| Equipment | Underwear | 25 |
| Miscellaneous and consumables | Alchemical Extracts | 31 |
| Miscellaneous and consumables | Alchemical Ingredients | 27 |
| Miscellaneous and consumables | Alchemy Extracts | 33 |
| Miscellaneous and consumables | Alchemy Ingredients | 41 |
| Miscellaneous and consumables | Arrows | 28 |
| Miscellaneous and consumables | Books | 735 |
| Miscellaneous and consumables | Coatings | 21 |
| Miscellaneous and consumables | Consumables | 31 |
| Miscellaneous and consumables | Containers | 88 |
| Miscellaneous and consumables | Drinks | 47 |
| Miscellaneous and consumables | Dyes | 42 |
| Miscellaneous and consumables | Elixirs | 44 |
| Miscellaneous and consumables | Food | 138 |
| Miscellaneous and consumables | Grenades | 36 |
| Miscellaneous and consumables | Keys | 287 |
| Miscellaneous and consumables | Misc | 503 |
| Miscellaneous and consumables | Notes | 790 |
| Miscellaneous and consumables | Potions | 39 |
| Miscellaneous and consumables | Scrolls | 137 |
| Miscellaneous and consumables | Slates | 39 |
| Miscellaneous and consumables | Unspecified | 1 |
| Miscellaneous and consumables | consumables | 1 |
| Weapons | Battleaxes | 11 |
| Weapons | Clubs | 18 |
| Weapons | Daggers | 35 |
| Weapons | Darts | 3 |
| Weapons | Flails | 14 |
| Weapons | Glaives | 11 |
| Weapons | Greataxes | 12 |
| Weapons | Greatclubs | 9 |
| Weapons | Greatswords | 18 |
| Weapons | Halberds | 9 |
| Weapons | Hand Crossbows | 9 |
| Weapons | Handaxes | 8 |
| Weapons | Heavy Crossbows | 13 |
| Weapons | Javelins | 3 |
| Weapons | Light Crossbows | 5 |
| Weapons | Light Hammers | 6 |
| Weapons | Longbows | 10 |
| Weapons | Longswords | 28 |
| Weapons | Maces | 17 |
| Weapons | Mauls | 9 |
| Weapons | Morningstars | 7 |
| Weapons | Pikes | 9 |
| Weapons | Quarterstaves | 36 |
| Weapons | Rapiers | 13 |
| Weapons | Scimitars | 19 |
| Weapons | Shortbows | 11 |
| Weapons | Shortswords | 29 |
| Weapons | Sickles | 7 |
| Weapons | Slings | 1 |
| Weapons | Spears | 16 |
| Weapons | Tridents | 10 |
| Weapons | War Picks | 6 |
| Weapons | Warhammers | 16 |

## Public list cross-check

The [cross-check ledger](../research/bg3-index-crosscheck.json) covers all 28 item-category links from the wiki’s Items page. The extraction matched 367 melee weapon titles, 186 camp supply titles, 89 container titles, and 366 story item titles. Every extracted title matched the import, resolved to an existing record through a wiki redirect, or was classified as a related non-item link.

The counts cover links found through the documented extraction method. They do not establish that the category pages or the game are exhaustive. The act-specific magic-equipment lists also matched all extracted titles, with 235 for Act One, 163 for Act Two, and 201 for Act Three. Titles can appear in more than one act.

## Independent game-data cross-check

The [level export ledger](../research/bg3-level-export-crosscheck.json) compares named instances in Krazplay’s game-data export with the wiki import. It found Pendulum of Malagard outside the wiki import. The catalog now includes it as a separate game-data reference. The export supplies a root-template UUID and a level-instance UUID, while availability in normal play remains unverified. The object export also includes scenery and triggers. Its unmatched rows require classification before they can count as catalog gaps.

The object export identifies two key instances by distinct lock IDs, for the crèche treasure room and the Steel Watch Foundry welcome-office safe. Both are cataloged as historical game-data references with normal-play availability unverified. The exported Eyepatch was reconciled to the existing Mol’s Eyepatch record.
## Remaining placement questions

The historical level export yielded five added references covering ten named instances. A separate export instance was reconciled with the existing Mol’s Eyepatch entry. All six catalog links resolve in SQLite, and the five new references retain their matching instance UUIDs.

Thirteen instances remain in the placement queue. The unresolved evidence is grouped below. The ledger retains the instance IDs, templates, and stats comparisons. Looters’ Trunk is tracked separately as a placed container whose wiki redirect targets a different template.

| Placement name | Instances | Evidence still needed |
|---|---:|---|
| Crate of Fruit | 1 | Resolve the conflict between the placed and stats root templates. |
| G-Cube Lube | 1 | Distinguish the immovable named vase from the trade good mentioned in an in-game report. |
| Jewellery Box | 1 | Confirm pickup and whether the box has distinct inventory behavior. |
| Lost Backpack | 1 | Confirm pickup and distinguish this placement from the indexed Backpack. |
| Skull on Marble Stand | 1 | Verify pickup or distinct inventory identity. |
| Urn | 1 | Verify pickup or distinct inventory identity. |
| Well-Stitched Satchel | 1 | Confirm pickup and distinguish the stash from the indexed Burlap Sack. |
| Wheelbarrow | 1 | Verify pickup or distinct inventory identity. |
| Wicker Basket | 2 | Verify pickup or distinct inventory identity. |
| Wooden Box | 1 | Verify pickup or distinct inventory identity. |
| Wooden Boxes | 2 | Verify pickup or distinct inventory identity. |
