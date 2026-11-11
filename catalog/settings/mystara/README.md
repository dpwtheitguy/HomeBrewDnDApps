# Mystara research and 2024 adaptation pack

Mystara / the Known World is the first setting priority. Research is internet-only for now, per the user. Curse of Strahd / Ravenloft and Planescape are the next setting requests.

## Current material

- `source-inventory.json` / `.yaml`: all 14 GAZ titles, 11 identified setting/adventure boxes, and supplementary/core/adjacent sources, 56 entries total. This is a research checklist, not a claim that every book has been inspected or that the box list is globally exhaustive.
- `research-sources.json` / `.yaml`: 19 identified archives, articles, indexes and collections, with authors and inspection status.
- `discovery-index.json`: 417 directory references collected from the full Pandius Items directory. Some are collections, duplicates by different authors, vehicles, rules discussions or multi-item articles. They are leads, not 417 verified item definitions. Direct article URLs still need resolving for these directory-only leads.
- `conversion-inputs.json` / `.yaml`: 43 selected equipment reskins based on internet evidence, mapped to 2024 SRD base items.
- `complex-item-references.json` / `.yaml`: 30 named items/materials needing further work. These are not counted as converted catalog entries.
- `cultural-associations.json` / `.yaml`: 24 commodity/region associations from John Hare's fan trade table. Coffee in two regions remains one commodity with two associations, not two new magic items.
- Playable-reference drafts are exported into `catalog/normalized/dnd-2024/mystara-draft-conversions/`: 52 reskins, eight original magic-item adaptations and two optional BG3-inspired variants. “Playable-reference” means that rule text/base references are supplied, not that an Android effect engine or playtesting is complete.

Every exported entry has the plain `mystara` tag, `setting:mystara`, a source reference, conversion status and 2024 target. Culture associations are evidence, not character ancestry restrictions.

## Conversion policy

Preserve original source identity and distinguish TSR/Wizards material, fan creations, reported canon and our original draft. Do not claim a verified sourcebook page when only a fan article was read. A 3E conversion is evidence of an earlier conversion, not proof of BECMI canon or modern balance.

Use 2024 base equipment where a reskin is reasonable. Modern weapon properties, mastery and armor training follow the base record. Do not mechanically port THAC0, descending AC, saving-throw categories, size-dependent damage or old skill percentages. Specific legacy behavior may be lost by a reskin; the conversion note must state this. Examples: a baseline buckler uses the modern shield rules; a baseline specialized shield does not automatically gain a new off-hand attack. Horns, blades and cultural styling are not free bonus attacks.

Distinctive items should receive explicit modern action cost, target, range, save/DC, duration, recharge, attunement and stacking rules. Keep conversions in draft until reviewed. Soul crystals, the Radiance, the Red Curse, cinnabryl depletion, Legacies, skyships and Blackmoor technology depend on larger setting systems. Do not claim these are complete because their names are indexed.

BG3-inspired enhancements are optional child records. They may add readable passives and limited-use tactical actions with original flavor, but their rules must be distinguished from baseline 2024 adaptations. The first two examples are Watchkeeper’s Claymore and Caravan Sentinel’s Lamellar. Both require attunement, compete for the user's Reaction, and recharge on a Short or Long Rest. They remain unplaytested homebrew. Normal cultural equipment is not silently upgraded.

Prices on reskins reference the 2024 base equipment value; new magic-item prices are labeled author estimates. Legacy prices and regional supply are separate evidence, not a guaranteed modern fair-market value. Character-specific buy/sell quotes use the shared policy and total Persuasion. Trade tables do not establish exact per-unit values for every commodity.

## Research findings and next audit

The [Pandius item directory](https://www.pandius.com/items.html) is a broad discovery point, including fan collections of swords, weapons, armor, jewels and cultural goods. The [blade index](https://pandius.com/swrdbld.html) directly reports several gazetteer/Hollow World blade names. Its cutlass/Minrothad association is expressly uncertain, so that suggestion was not imported as verified equipment.

[Håvard's armor article](https://www.pandius.com/mystarmr.html) identifies regional armor and cites sources for several examples, but also proposes its own 5E rules. This project uses independent base-item mappings and marks the book evidence as indirect. [Savage Coast equipment](https://pandius.com/sc_equip.html) supplies named equipment and unusual materials; its legacy figures are not automatically compatible with 2024 rules. [John Hare's trade table](https://pandius.com/exp_imp.html) supplies cultural trade associations and explicitly describes itself as incomplete fan work.

The BECMI equipment index download returned HTTP 403. The trade-goods DOCX, arcane-books workbook and Armoury PDF were discovered but have not been fully inspected. These limits remain visible rather than being treated as successful extraction.

Next steps: resolve directory leads, verify each item against accessible source evidence, map items to exact books/pages, expand cultural associations without inventing traditions, complete complex setting rules, and review/playtest each adaptation. Item extraction for GAZ1–GAZ14 and each boxed set is still open. The full bibliography is not an item completeness certificate.

## Expanded region/people research pass

`additional-research-sources.json`, `additional-reskins.json`, `additional-drafts.json`, and `additional-complex-references.json` retain subsequent evidence and draft work. `five-shires-item-mentions.json` records 26 distinctive GAZ8 mentions, with reported page references but no claim that the original pages were checked. `item-associations.json` records supported Rakasta weapon relationships. `people-research-index.json` holds the fan index headings and Hollow World culture names, not automatically playable 2024 races.

The new Karameikos sword and Glantrian staff/robes are independent homebrew drafts inspired by credited fan articles. The Minrothad and Atruaghin mappings omit legacy ancestry/guild bonuses rather than granting universal cultural proficiency. See [the research queue](../../research/queue.json) and [search design](../../../docs/SEARCH-AND-RESEARCH.md).
