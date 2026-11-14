---
name: armory-combat-qa
description: Verify combat rules and design unit and Android regression checks for a batch of up to ten Arms and Equipment Guide items.
---

Use stable IDs and review up to ten items together. Start with the [100 metadata red flags](../armory-alphabet-audit/red-flags.md). Refresh the weapon, armor, and item-detail reports as described in the alphabet audit skill, then run:

```sh
python3 scripts/audit_catalog_by_letter.py --item-id bg3-wiki:12161
python3 -m unittest discover -s tests -p test_combat_readiness.py
```

Repeat `--item-id` for each item in the batch. An empty findings column means the script found no known failure pattern. Source and rendered-card review still apply.

Assign the `armory_combat_reviewer` subagent the same IDs for an independent read-only check when delegation is requested. Give it the sources and current build, without sharing the proposed verdict. For each ID, record the exact variant, ruleset, source locator, missing or incorrect field, expected value, and whether the card was inspected. Record verdicts as verified, incomplete, or unverified. Authored conversions retain their DM-review label.

- For unit tests, assert exact values and roles. Cover an applicable case and an exclusion, a missing field or false placeholder, and valid inherited or inapplicable fields. For effects, check trigger, target scope, modifier channel, duration and owner, and relevant save, stacking, consumption, or recharge.
- For Android regression tests, open the actual stable ID and check the summary and drill-down. Check source links, applicability, and missing-rule copy. Use Oil of Accuracy to check active-set scope, dual-wield coverage, separate ranged application, exclusivity, +2 to hit, no damage bonus, and no thrown-weapon bonus.
- When visibility changes are requested, test default browse and exact search, explicit opt-in, reset, result counts and pagination, merchant stock, and related-item navigation. Check a known playable control and a convincing but incomplete fallback.

For a source-only import, use the official publication as the rules authority. Treat upstream text and the rendered stat panel as separate evidence. Inventory the renderer's supplement dependencies and inspect the packaged ZIP and APK before certifying a record. Filter nested rule maps by stable ID and preserve required base links. Compare the text, structured stats, filters, and rendered card. Include a mundane chassis control, a magic AC modifier, an armor exception, a magic consumable, and launcher-dependent ammunition. Report source coverage separately from import fidelity.

Before onboarding a new source, apply the [item-type onboarding checklist](item-onboarding.md) and run its regression step on the installed Android build before marking onboarding complete.

For strict SRD reimports, assign the Rules Lawyer agent in `.codex/agents/armory-rules-lawyer.toml` and apply the Rules Lawyer review in the onboarding checklist. Report its source fidelity findings independently of Player and DM usability.

For reimport acceptance, use the 200-card role sampling step in the onboarding checklist. Validate the packaged SQLite and item schema before reviewing human-readable rules. Reconcile heading coverage with the official source and record exact wording and player interpretation as separate verdicts.

For data-structure review, use `.codex/agents/armory-database-admin.toml`. Check the stable ID, item and variant fields, SQL columns, tags, search index, supplements, and applicable links against the rendered card. Retest a sibling variant and a family-level card.

For formatting and visual presentation, assign `.codex/agents/armory-visual-reviewer.toml`. Review actual Android rendering in compact and wide layouts and inspect exported charts and reports at their intended display size. Keep the visual verdict independent of gameplay and source fidelity.

End every personality report with **Onboarding improvements**. For each material finding, state the new or proposed skill check, reviewer instruction, and deterministic script or regression check. Identify which changes were applied and tested and which remain open. If a layer needs no change, say why briefly.
