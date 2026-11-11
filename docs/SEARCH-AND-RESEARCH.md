# Catalog search and the research loop

## User direction

Use BG3's useful inventory browsing and filtering as a close interaction reference, adapted for touch. Search is a primary screen in every class app, not a secondary settings page. Keep Mystara / the Known World / gazetteers / Karameikos and Glantri boxes first in research priority. The larger source roadmap includes Planescape, Curse of Strahd/Ravenloft, Baldur's Gate I–III, Forgotten Realms, Return to the Temple of Elemental Evil, likely Zanzer's Dungeon, Diablo I–IV, and edition-appropriate equipment books.

30,000 records is an expansion target, not an audited count of unique item designs. Do not manufacture rarity tiers, affix combinations, cultural reskins or named ship instances just to reach it. Count source records, named designs, declared variants, game rolls, research mentions and converted mechanics separately. A same-name index is not semantic deduplication.

## Typed attribution

Use stable entities for setting, region/nation, cultural identity, people/creature group, faction, game and source publication. Each item association includes role, evidence and status. Roles distinguish setting membership, origin, cultural association, use, location, availability and inspiration. Being mentioned in a regional book is not proof of local manufacture or exclusive availability.

Karameikos is a region. Karameikan is a regional identity. Traladaran and Thyatian are distinct cultural identities found in its context. Thayan belongs to Forgotten Realms/Thay and is not Thyatian. Red Wizards of Thay is a faction rather than an alias for every Thayan. Never derive weapon training, alignment, ownership or access solely from an ethnic or people tag.

The initial people index is mixed: some headings are ancestries, some monsters, broad categories or fan additions. It is a discovery vocabulary, not a list of automatically playable 2024 species. Preserve setting/date/source differences, including extinct or relocated nations. A culture can have diaspora associations; geographic containment does not make a culture exclusive to that country.

## Working search implementation

`shared/catalog_search.py` evaluates the saved profile JSON and composes parameterized SQLite queries. Values OR within a facet and facets AND across each other. Repeated literal tags AND. Search terms are literal FTS prefix tokens; they are not executed as user-provided query syntax. Sort by name, rarity, text relevance or base value.

```sh
python3 scripts/search_catalog.py --profile mystara-workbench
python3 scripts/search_catalog.py --setting Mystara --region Karameikos
python3 scripts/search_catalog.py --culture Glantrian --magic yes
python3 scripts/search_catalog.py --people Rakasta
python3 scripts/search_catalog.py --people Rakasta --relationship used-by
python3 scripts/search_catalog.py dag --ruleset dnd-2024 --sort relevance
python3 scripts/search_catalog.py --rarity uncommon --attunement yes
python3 scripts/search_catalog.py --min-value 1 --max-value 20 --value-economy dnd-2024 --sort value
```

Unknown provenance is excluded by a requested origin facet unless `--include-unattributed` is supplied. Unknown magic or attunement can be selected explicitly; null is not false. Thayan aliases resolve even when no currently imported items have verified Thayan associations; an empty result must not cause invented tags.

Saved profiles currently include All Research, 2024 Tabletop References, Mystara Workbench and BG3 References. A profile is a versioned JSON definition evaluated by the CLI, not an Android preference screen. Current search arguments override the corresponding profile facet. The tabletop profile excludes metadata-only items and original conversion drafts but does not certify source transcriptions as rules-audited.

## Android interaction contract

Keep search visible above the inventory. Use a category row, filter drawer, active-filter chips with individual removal, Reset, and a visible result count. Do not hide that a campaign profile is excluding content. Search results retain scroll position and filters when inspecting or comparing items. Provide clear zero-result recovery: remove a chip, change profile, or explicitly include unknown attribution.

Facet priorities:

1. Type/subtype, name, rarity, magic, attunement, equipped/owned state.
2. Campaign setting, region, culture/people, faction, source book, edition and source game.
3. Usability for the acting character, including proficiency, attunement, spellcasting and existing item state. Requires the shared rules evaluator, not a hardcoded class list.
4. Base value and contextual merchant buy/sell estimate, weight, properties, damage, action/resource/recharge and synergy tags.
5. Canon/fan/original status, conversion completeness, playtest status, specific/generic art and duplication display.

Save defaults at global, campaign and character scope; current search is a temporary override. Name presets so the player understands the scope. Separate content enabled for play from content visible for research. Android persistence, inventory ownership filtering, live merchant quotes, facet counts and visual chips still need implementation.

## Research loop

The persisted queue is `catalog/research/queue.json`. It crosses registered nations/regions, peoples and cultures against weapons, armor, clothing, tools/gear, trade goods, consumables, magic/relics and vehicles. Other settings start with entity-discovery tasks. The current registry is a seed, not a claim of complete coverage.

```sh
python3 scripts/research_queue.py --next --entity region:karameikos --limit 4
python3 scripts/research_queue.py --next --category consumables --limit 4
python3 scripts/research_queue.py
```

Execute a search, inspect the relevant source, and record its URL, author/type, item names, context and source page where genuinely checked. Follow bibliographies, neighboring regions, guilds, crafts, religions and equipment sections when relevant. Record a lead even when it is only a trade table or a use association; do not label it a finished item definition.

Status advances from unsearched to evidence leads, source inspection, conversion draft and reviewed. Negative searches mean no evidence found in that pass, never proof of cultural absence. Rebuilding the queue preserves existing progress. Do not mark every category complete because one source mentions a sword.

Conversions maintain original edition identity, explicit 2024 adjustments, source provenance and optional BG3-inspired variants. Depot inventory, shipping instances, livestock, world infrastructure and ordinary commodities should be linked to shared definitions when suitable. Material variants, Diablo affixes/runewords/sets and rolled item instances need their own schemas and counts.

## Findings from the first pass

- GAZ8's [fan item index](https://www.pandius.com/5shritems.html) gives numerous equipment and alchemical mentions, often with reported page numbers. It warns that some originate outside the Five Shires. Twenty-six distinctive mentions are recorded separately and are not counted as converted items.
- [GAZ9 options](https://www.pandius.com/gz9pcopt.html) supplies Minrothad guild equipment leads. Legacy guild-only bonuses are not automatically carried into new 2024 mechanics.
- [Atruaghin equipment](https://www.pandius.com/atruitem.html) distinguishes reported gazetteer equipment from the author's additions. The source uses “Horse Clan” in places; that is not silently equated with Children of the Buffalo.
- [Rakasta equipment](https://pandius.com/rakasta2.html) supports specific weapon-use associations. A usage association does not grant proficiency to every character sharing a people tag.

These are fan/archived source leads with differing provenance. Full GAZ/sourcebook inspection and balance review remain open.
