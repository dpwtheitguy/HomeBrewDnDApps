---
name: armory-alphabet-audit
description: Audit Arms and Equipment Guide catalog entries in reverse alphabetic order from Z to A. Use for letter slices, deterministic triage of recurring combat data mistakes, and source review handoffs.
---

Run from the HomeBrewDnDApps repository root. Refresh the weapon, armor, and item detail reports after catalog edits.

```sh
python3 scripts/audit_weapon_playability.py --strict
python3 scripts/audit_armor_playability.py --strict
python3 scripts/audit_item_details.py
python3 scripts/audit_catalog_by_letter.py --start Z > /tmp/armory-audit-Z.csv
```

Use `--start Z --end A` for the complete descending queue. Without `--end` the script audits a single letter. The CSV includes every record in scope, stable IDs, provenance, audit evidence, and findings. Counts go to stderr.

Review weapons, armor, shields, and ammunition first. Check classification candidates outside those types as well. Flagged names are source lookup leads. A blank findings cell is not source verification. Compare the exact item and variant against its cited source before editing. Use the armory weapon audit workflow to record the source facts, implement the tabletop mapping where needed, and verify the built app.

Finish the current letter before advancing. Keep explicit source gaps and DM-review drafts visible. When a recurring omission can be detected from structured evidence, add the detection to the script and confirm it against a known example and a nearby legitimate record. Use stable IDs in findings and distinguish full slice coverage from items individually source-verified.

The report flags placeholder copy, improvised fallback, missing weapon damage or range, missing worn armor AC or shield bonus, and explicitly magical fallback records without known item effects. A placeholder can survive after a rules supplement is added. Check the rendered detail and supplement before deciding whether the missing work is rules or copy. Search editorial fields for pending language and keep original rules prose out of that search. Check ammunition through its launcher, and respect explicit reference objects and equipment with a save in place of a damage roll.

BG3 effects are checked against the same item and armor effect dictionaries the app uses. Prioritize ammunition and protection effects with a source link but no mechanic. A curated source-reported card can replace the generated BG3 panel.
