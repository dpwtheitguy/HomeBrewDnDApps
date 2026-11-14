---
name: check-all-records
description: Run full-catalog Armory acceptance with the Player, DM, Rules Lawyer, Database Admin and Visual Presentation reviewers.
---

Use the exact packaged ZIP and matching installed APK. Run `python3 scripts/check_all_records.py RELEASE.zip APP.apk --output OUTPUT_DIR` from the repository root to audit database structure and write the stable-ID inventory. Add `--serial EMULATOR` for an exact-search, stable-ID Android capture of every item. Use the WebSocket dependency from the existing Android QA harness. Use separate emulator sessions or run captures sequentially.

Give each reviewer the same inventory. Player and DM screen every live card and inspect flagged behavior. Rules Lawyer checks the exact SRD and pinned BG3 sources and logs unresolved source claims. Database Admin reconciles the packaged data, indices, and APK. Visual Presentation scans every rendered card for overflow and literal markup, then inspects representative screenshots in wide and compact views. A full-catalog capture does not prove every rule was manually reconciled.

Compare each role's evidence IDs with the inventory and identify omissions explicitly. Record the release, results and open issues. End the report with onboarding improvements for skills, agents and scripts. Apply a deterministic gate only where the assertion captures the actual source rule.

Use the release capture to compare the exact visible panel against the source. On wide Android layouts, flag inspection width exceeding its scroll container even when compact rendering passes. For BG3, verify acquisition markers and mode-specific replacement before calling a variant ready. The import checks can flag either omission before packaging.

For a BG3 batch, log findings by individual grant and condition, including exact triggers, qualifiers, and item-specific behavior. Scan the visible rarity label separately from legitimate footnotes in rules text. Run the capture on both viewport sizes and treat reported overflow and leaked markup as acceptance failures.

For follow-up imports, rerun prior source-backed regressions on the live APK. Link the letter inventory with a disposition for every discovered stable ID. Check duplicate display names by stable ID and verify that canonical rarity agrees across SQLite and the rendered header.

For a letter-only acceptance run, pass `--batch-inventory catalog/research/bg3-batch-LETTER.json` to report and capture only imported IDs in that ledger. Reconcile every selected ID and keep reviewer findings scoped to that letter.

A combined ledger can use a letters array, for example [D, E]. For a scoped build verify excluded IDs are absent. Regress cited gameplay changes in the rendered row that a player will actually use. Report source-comparison coverage separately from automated all-ID checks.

For BG3 cards, compare the entire named rules panel against the packaged curated fields after the normal unit formatting. Keep targeted source assertions as a separate check. A correct rendered value can still be wrong against the source.
