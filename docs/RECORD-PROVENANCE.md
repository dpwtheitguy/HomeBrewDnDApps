# Sources and changes on every record

Every normalized JSON/YAML record, JSONL entry and SQLite `data_json` record has `research_metadata`. The original source-specific `provenance`, `conversion` and `associations` fields remain intact.

- `source_refs`: source-record URLs, permanent revision links, research references, association evidence, and pinned base-rule fixtures where available. Open5e fixture references include the repository commit, upstream primary key, exported local file and SHA-256.
- `change_log`: typed, individually identified transformations. Each supplies a description, affected field and whether it changes gameplay. Rules-adaptation entries retain the actual authored conversion note. Other types distinguish cosmetic reskins, metadata projection, omitted source prose, generic art, original flavor, creative suggestions, price estimates and construction policy.
- `verification_status`, `original_publication_verified`, `source_page_verified`: separate parsing/import status from actual original-book verification. A visually checked page of a fan compilation is not verification of a TSR original.
- `record_content_sha256`: fingerprint of the normalized record before this metadata block. Useful for comparing releases and detecting later content changes; not a signature or proof of correctness.
- `editorial_event_ids`: pointers to historical corrections in `catalog/changes/editorial-events.json`. The Buffalo clan correction retains before/after tags and its evidence.
- `pipeline_version`: identifies the context builder.

A change log is a statement of the transformations applied to the current snapshot, not a fabricated line-by-line comparison with an unavailable book. Metadata-only references explicitly say that full rules were not imported. Unknown dates, pages, editions and properties stay unknown. Source fixtures are preserved separately rather than rewritten to look like converted source material.

To inspect one entry:

```sh
python3 scripts/search_catalog.py 'Mist-Raven' --profile ninja-2024-drafts --json
```

All construction budgets, modern homebrew mechanics, thematic cultural associations and lesser artifact versions remain draft project choices. This metadata does not certify balance, official status, image reuse rights, original-book completeness or Android effect automation.

Publisher-preview references may verify only an item name and its appearance on a selected page. Their `verified_fields` and `verification_scope` explicitly limit that claim. This does not verify powers, pricing, 2024 balance or a full sourcebook audit. Multiple NPC equipment appearances retain their individual URLs and reported page numbers in both reference metadata and the source-reference ledger.

User-provided PDF checks retain file SHA-256 plus separate PDF-page and printed-page numbers. `source_verifications` can upgrade an existing reference without creating a duplicate item. The exact checked fields are listed; full-book audits remain independent. Legacy construction costs and market ranges live in `mechanics.verified_legacy_facts` and do not automatically become 2024 merchant prices or Charisma quotes. Original PDF binaries and extracted page text stay outside catalog archives.
