---
name: armory-weapon-audit
description: Audit weapon, ammunition, and siege entries in the HomeBrewDnDApps shared catalog for schema integrity, source fidelity, and playable rules. Use for Arms and Equipment Guide weapon audits, incomplete combat stats, edition conversions, or regression checks after weapon data changes.
---

# Armory weapon audit

Run from the repository root. The catalog has a SQLite index, generated weapon profiles, and source-specific detail supplements. A single item can have a native record and a separate tabletop comparison.

## Find and rank gaps

- Run `python3 scripts/audit_weapon_playability.py`. Read `catalog/reports/WEAPON-PLAYABILITY.md` for totals and filter `catalog/reports/weapon-playability.csv` by stable item ID, source, evidence, and open review gaps. Use `--strict` to detect structural errors. A clean structural run still allows content gaps.
- Use `scripts/audit_item_details.py` for field coverage and ammunition gaps and `scripts/audit_pending_rules.py` for pending 2024 rules and published cross-references. These reports answer different questions. For each count, identify which report and status it represents.
- Begin with user-reported items. When the request spans the full catalog, triage core D&D, Mystara, and BG3 before secondary catalogs unless the user supplies another order. Check related records with the same failure mode. Distinct editions can share a name and have different rules.

## Review a playable record

- Identify the ruleset, the exact variant, the source locator, and what the item does. Find the publication's page, an official reference, or an upstream game record with a stable ID. Mark fan material and authored conversions with their actual provenance. Record what changed and why.
- For a weapon attack, check the damage and type, attack modifier or normal attack formula, reach or normal/long range in feet, category, properties, mastery, and any exception to the normal attack. Check what triggers a special effect, its action cost, targets, save and DC, area, duration, uses, and recharge where applicable. Preserve each edition's terminology and variant-specific facts.
- For ammunition, state compatible launchers and what damage, attack bonus, range, or effect the projectile changes. Identify inherited launcher rules when known. For siege equipment, check the engine's defenses and operating sequence and link the ammunition when both records exist. Upgrades, props, schematics, and objects need their own use rules or reference classification.
- Keep published mechanics, source-reported game facts, authored drafts for DM review, and unresolved leads identifiable in the record and the app. A name match, family profile, or improvised fallback gives context and leaves item-specific gaps open. A normal action or inherited value can satisfy a field when the relationship is clear. Mark genuinely inapplicable fields explicitly where useful and keep unsupported values open.

## Apply and verify changes

- Edit the maintained input, such as a source pack, a profile rule in `scripts/build_weapon_profiles.py`, or a reviewed entry in `catalog/supplements/curated-item-details.json`. Preserve stable IDs and citations. Rebuild the catalog when inputs change and regenerate the affected profiles and reports. Avoid hand-editing the SQLite output.
- Run the structural audit and relevant catalog tests. With the research dependencies installed, run `python3 scripts/validate_catalog_schema.py` to validate the published item and structure schemas. Compare before and after counts for the affected source and statuses. Look at individual rows to confirm the audit recognized what changed.
- For an app deliverable, package a new catalog version, build the APK, and inspect representative cards on the headless Android emulator. Check source links, damage and range, variant or related-item navigation, and the absence of an improvised fallback on reviewed records. Use the `armory-filter-qa` skill when category, source, properties, or proficiency indexing changes.
- For authorized delegation, give each agent an independent source or evidence task and a non-overlapping edit scope. Consolidate findings by stable ID and verify their citations and rule interpretations before marking anything closed. Report structural errors, remaining content gaps, and emulator results separately.
