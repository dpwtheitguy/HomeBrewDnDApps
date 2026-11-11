# Ninja equipment workbench

This pass adds **62 original 2024 drafts**: 38 approximate equipment reskins and 24 original utility / magical adaptations. These are selected conversions, not complete imports of either requested sourcebook and not an implemented ninja class. Every item supplies a generic icon, TLDR, detailed rules, flavor, a creative-use suggestion, proficiency interactions where a base item exists, and an explicitly estimated modern value.

## Source distinctions

- **The Complete Ninja’s Handbook**: PHBR15 / TSR 2155, Aaron Allston, AD&D 2e. Publisher preview confirms the book and chapter structure. Selected weapon names come from a separately labeled third-party indexed equipment table. The miscellaneous equipment and magic chapters still need an original-page audit.
- **Oriental Adventures (2001)**: James Wyatt, D&D **3.0**, WTC12015. Distinct from the 1985 1e book and the later Dragon #318 3.5 update. Selected modern gear mappings use a secondary fan index; original 2001 page verification remains pending.
- **Mixed OA magic**: the secondary magic list explicitly combines 1e and 3e. The Spider Nekode, Courtier’s Obi, Writing Set, lantern and other lesser drafts are not silently asserted to be 3e originals. Their rules here are independent project designs, not the fan author’s converted text.
- **Game inspiration**: Sekiro, Tenchu, Ninja Gaiden, Nioh 2 and Diablo II Assassin equipment. Game references and original tabletop adaptations are separate records. Effects, charges and power levels have deliberately changed.

No invented clan/culture assignment or class allowlist is inferred from an item’s style. A katana reskin uses the selected Longsword profile’s training and mastery rules; it does not require a fictional “Japanese ancestry” or grant ninja proficiency. Rokugan has a setting entry, but every Asian-inspired implement is not automatically assigned to Rokugan or Kara-Tur.

## Examples

- **Metsubishi Dust Packet**: single-use, close-range attack disruption, not automatic long-duration blindness.
- **Mist-Raven Mantle**: limited reaction teleport; the triggering hit still applies.
- **Guardian’s Folding Umbrella**: a shield with one limited damage-reduction reaction.
- **Returning Wind Star**: reusable thrown dart; no free extra attacks.
- **Jade-Talon Ward**: limited Poison resistance, without importing Diablo class levels or mana leech.
- **Courtier’s Obi (Lesser)**: one bounded social bonus; no forced cooperation.

All require DM review and playtesting. Mechanical effects remain textual; the app does not yet execute them.

## Search

```sh
python3 scripts/search_catalog.py --profile ninja-workbench
python3 scripts/search_catalog.py --profile ninja-2024-drafts
python3 scripts/search_catalog.py --origin PHBR15 --relationship inspired-by
python3 scripts/search_catalog.py --origin 'Sekiro: Shadows Die Twice'
```

The workbench includes directly relevant game references. Nioh’s adjacent samurai weapons and the broader Diablo / BG backlog remain available in their game filters, without falsely labeling every sword “ninja gear.”

## Reference import coverage

The companion `catalog/raw/game-reference-indexes` contains public **names, types, source links and variant IDs only**. No copied game descriptions, powers, flavor text, prices or artwork are included. Each reference uses `game-reference` ruleset and `adaptation-needed` status; unknown values stay unknown.

- Nioh 2: names from weapon smithing tables; continuation rows containing enemy/mission names are excluded. Armor-set names are not multiplied into invented individual pieces.
- Sekiro: ten base prosthetics and named upgrades from the public tool index.
- Tenchu / Ninja Gaiden: selected names from indexed excerpts, not complete series inventories.
- Diablo II: 78 base-equipment pages plus the official alphabetical unique index; historical Arreat Summit coverage, not the current Resurrected patch.
- Diablo III: pinned d3planner metadata. Same-name/type legacy IDs collapse into one reference with variant identifiers. No generated affix products, Ancient/Primal duplication, or current-patch completeness claim.
- BG I: public Enhanced Edition inventory index; includes expansion/engine entries as indexed. Normal-play obtainability and original-vs-EE differences are not verified.
- BG II: historical item resource-code index. Same-name/type IDs collapse; scroll records represent inventory scrolls, not standalone spell imports.
- Diablo I: selected unique tables from a secondary database; not a complete Hellfire/mod inventory.

Fetch research with the bundled Python runtime (lxml is already available there):

```sh
/home/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/fetch_ninja_references.py
python3 scripts/seed_ninja.py
python3 scripts/build_catalog.py
```

Game HTML and upstream repositories remain in `.cache` and are excluded from the distributable. The full public-book scans are not bundled. Mark of Amber is tracked in the Mystara boxed-adventure queue, with publisher-preview evidence and its original item audit pending.
