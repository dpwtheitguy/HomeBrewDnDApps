# Requested source coverage

The source ledger enumerates requested settings, books, boxed sets and game series in `catalog/resources/requested-resources.json`. The compiled report is `catalog/reports/RESOURCE-COVERAGE.md`; machine-readable results are beside it. Broad families remain open to further source discovery.

Each resource distinguishes direct or inspired item links, regional context, selected conversion drafts and an original-publication audit. A related regional item does not establish its appearance in a particular book. Parent-series totals are unions of child links, not additional item definitions. A registered resource with no item links is an explicit gap.

```sh
.venv/bin/python scripts/list_resources.py Mystara
.venv/bin/python scripts/list_resources.py --gaps
.venv/bin/python scripts/search_catalog.py --resource PHBR15 --json
```

Resource filters use explicit associations and reported source codes; regional-context-only links are excluded. Reported book codes from fan indexes remain unverified until checked against the publication. Each item carries `resource_ids`, also included in its research metadata; SQLite stores the relationship basis in `resource_items`.

Reference-only records preserve selected names and evidence without pretending that legacy or video-game mechanics are playable 2024 rules. Unknown powers, prices and rarity stay unknown. Original conversions and construction proposals are identified separately. Counts include reprints, source overlaps and construction components, so total records do not measure unique playable equipment.

New gap-pass notes live in `catalog/research/mystara-gap-pass-2026-11-08.json`. A contextual article or search excerpt is recorded as a lead rather than converted into an invented item.
