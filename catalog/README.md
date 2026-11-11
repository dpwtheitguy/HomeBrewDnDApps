# Shared item catalog

Shared item data for Complete Guide to Fighters, Complete Guide to Wizard, Complete Guide to Ninja, Arms and Equipment Guide, and future titles. Build an [independent catalog release](../docs/SHARED-CATALOG.md) from this workspace for app integration.

Start with [the measured counts](reports/COUNTS.md), [source manifests](sources.json), [Mystara research](settings/mystara/README.md), and [shared schemas and pricing](../shared/README.md).

## Files and search

- `normalized/<ruleset>/<source>/<type>.json` and matching `.yaml`: equivalent readable packs.
- `items.jsonl`: one combined source record per line.
- `indexes/items.sqlite3`: indexed catalog plus SQLite FTS5 search and tag tables.
- `indexes/tags.json`: reverse lookup from tags to IDs.
- `indexes/same-name-groups.json`: potentially related records. Shared names do not prove identical mechanics.
- `raw/`: pinned upstream item fixtures or projected public metadata, preserving provenance.
- `images/types/`: reusable SVG icons, with authors and source URLs in `images/manifest.json`.
- `licenses/`: upstream notices. Repository software licenses do not license every included game text or image.
- `settings/mystara/`: source inventory, research references, conversions and cultural associations.

Examples from the project root:

```sh
python3 scripts/search_catalog.py dagger --ruleset dnd-2024
python3 scripts/search_catalog.py --tag property:finesse --tag magic
python3 scripts/search_catalog.py --tag mystara --limit 100
python3 scripts/search_catalog.py --tag variant:bg3-inspired --json
```

Tags include ruleset, source, type, rarity, damage, extracted weapon properties, setting and culture where supported. Inferred or incomplete proficiency interactions remain visibly marked. Unknown fields are null, not invented defaults.

## Counting and coverage

Current totals are calculated from the downloaded data, not estimates of all D&D publication history. Source records include editions, reprints, named variants and overlapping catalogs. Distinct normalized names are a text comparison, not a verified count of distinct designs. No arbitrary +1/+2/+3 cross-product has been generated to meet a target number.

Open5e packs include both SRD editions, Vault of Magic, Level Up Advanced 5e, Tome of Heroes and the single Tal'Dorei entry available there. V2 is preferred; V1 copies of those same sources are not counted twice. Weapon and armor relational tables are not added to the item count again. Third-party/A5E material is labeled separately from official D&D.

BG3 records are factual metadata, one per wiki page, with multiple literal item templates/UUID variants retained inside the record. They include books, notes, keys, food and miscellaneous items. Their price and game facts are not ready-made 2024 tabletop rules. No BG3 descriptive prose or game artwork has been copied into the app assets.

D&D Beyond entries are public listing metadata only: names, rarity, type, attunement flag and links. Their cards do not identify books or edition reliably, so those fields remain unknown. Full descriptions and paid sourcebook content were not imported. Images are references only.

Mystara entries are explicitly labeled draft reskins, original adaptations or optional BG3-inspired variants. Original setting books have not been fully inspected; internet source claims and original draft rules are distinguished. Discovery references, unconverted complex items, cultural associations and bibliography entries are not counted as additional playable items.

The current objective is coverage of every requested resource with no item-count ceiling; source-record totals, distinct names and reviewed tabletop conversions must be reported separately. There is no verified global “magic number.” Adding arbitrary homebrew makes 20,000 or more possible but does not establish completeness, quality or novelty. Track separate totals for source records, item families, edition variants, culture associations, conversion status and usable mechanics.

## Value and images

Each item retains a `valuation` object with its original price evidence and economy. The [shared price supplement](supplements/item-prices.json) supplies base cost, buy, and sell values for every catalog ID. It records the estimate method, economy, assumptions, and unit scope. Use [the pricing coverage report](reports/ITEM-PRICE-COVERAGE.md) to see how many records use each basis. Regenerate the supplement with `python3 scripts/build_item_prices.py` after rebuilding the catalog.

Every record has a generic image. These images represent item types, not unique official illustrations. `specific_art` is an optional override. A future specific image must retain author, source, reuse terms, hash and modification status. Existing BG3 and D&D Beyond art URLs/filenames are research references; no license for reuse in this app is claimed.

## Rebuilding

The collection was built using Python 3 and PyYAML (the host's system package), with no local LLM calls. A local LM Studio status check was unavailable. Upstream revisions are pinned in `sources.json` and `images/manifest.json`.

To restore upstream checkouts, clone `https://github.com/open5e/open5e-api.git` into `.cache/upstream/open5e` and `https://github.com/game-icons/icons.git` into `.cache/upstream/game-icons`, then check out the recorded commits. Do not substitute a moving branch when reproducing a snapshot.

```sh
python3 scripts/fetch_bg3.py
python3 scripts/fetch_ddb_index.py
python3 scripts/seed_mystara.py
python3 scripts/expand_mystara.py
python3 scripts/seed_taxonomy.py
python3 scripts/seed_research_queue.py
python3 scripts/record_research_pass.py
python3 scripts/build_catalog.py
python3 scripts/research_report.py
python3 -m unittest discover -s tests -v
```

Fetchers cache successful responses. Refresh deliberately; public indexes can change while paging. New importers should fail visibly on missing pages/schema changes. `build_catalog.py` replaces only generated normalized files and search indexes. Original collected snapshots and editorial research data are retained.

## Attribution

SRD 5.1 and 5.2 material is by Wizards of the Coast LLC and available under Creative Commons Attribution 4.0. Source: https://www.dndbeyond.com/srd. This catalog reorganizes and tags community transcriptions; it has not been fully audited against the official PDFs. The 2024 upstream document calls itself SRD 5.2; do not claim a verified SRD 5.2.1 transcription without that audit.

This work includes material taken from the A5E System Reference Document (A5ESRD) by EN Publishing, available at https://a5esrd.com/a5esrd, based on Level Up: Advanced 5th Edition. The A5ESRD is licensed under CC BY 4.0. Additional sources retain their own OGL and copyright notices in the source manifests and raw documents; those obligations must be carried into any distributed pack.

Icons made by Lorc, Delapouite, Carl Olsen, Willdabeast, LucasMS, Sbed, and Pierre Leducq, available through https://game-icons.net under CC BY 3.0. Exact per-file attribution and pinned source paths are in `images/manifest.json`; `licenses/game-icons.txt` preserves the upstream notice.

Mystara research credits and fan authors are in `settings/mystara/research-sources.json`. Baseline mappings and new effects are this project's draft choices, not official publisher conversions or the fan authors' approved 2024 rules.

## Known gaps

- Not every D&D sourcebook, Mystara book, BG3 internal object or online homebrew item is represented.
- Public index records do not contain complete mechanics. Descriptive prerequisites, charges and effects have not been comprehensively converted to executable effects.
- There are 36 upstream weapon-category records without resolved weapon relations. They are reported in `reports/quality-warnings.json`; no attack statistics have been guessed.
- Mystara conversions are not playtested. Distinctive legacy mechanics often need a dedicated adaptation rather than a reskin. Culture associations must not imply ethnicity grants a proficiency or automatic access to an item.
- More specific art, reliable per-book coverage and a modern rules audit remain outstanding.
- Curse of Strahd/Ravenloft and Planescape are queued after Mystara, not imported as completed setting packs.

## Expanded search and source roadmap

Typed aliases and saved profiles are in `taxonomy/` and `filters/`. The persisted research matrix is in `research/queue.json`. See [search and research design](../docs/SEARCH-AND-RESEARCH.md) for working CLI commands and the separate Android UI contract. [source-roadmap.json](source-roadmap.json) records the expanded game/book requests with Mystara first.

The current Mystara export contains 62 drafts: 52 equipment mappings, eight original magic-item drafts and two BG3-inspired variants. Additional regional/source mentions remain separate research data. The source inventory still does not represent exhaustive extraction.

## Ninja and game-reference expansion

See [the ninja workbench](settings/ninja/README.md) for selected handbook/OA conversion drafts, source limitations and search profiles. Additional game indexes use `game-reference` ruleset with `adaptation-needed` status. They contain names/types/links and grouped variant IDs, not executable 2024 rules. Raw indexes and pinned d3planner revision metadata are included; cached HTML and upstream code are excluded from the export.

Every compiled record also has `research_metadata.source_refs` and `research_metadata.change_log`; see [the provenance contract](../docs/RECORD-PROVENANCE.md). Construction proposals and source building pieces are tagged separately from portable equipment. See [worldbuilding](settings/worldbuilding/README.md), [Mystara frontiers](settings/mystara-frontiers/README.md), and [continuing source audits](settings/backlog/README.md).
