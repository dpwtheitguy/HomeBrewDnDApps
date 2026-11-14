---
name: armory-bg3-onboarding
description: Verify and import reviewed Baldur’s Gate 3 items into the shared Armory catalog from pinned bg3.wiki item, effect, and shared-rule revisions.
---

1. Find the exact item on bg3.wiki and confirm its MediaWiki page ID, UID or UUID, variant, and revision. Use the item page together with linked conditions, actions, recipes, and shared mechanics. bg3.wiki is a community source. When source claims conflict or behavior depends on a patch or game mode, verify against the game or Larian data if available and record the remaining uncertainty.
2. Create a one-item review in `catalog/research/bg3-onboarding/`. Use `oil-of-accuracy.json` as the format. Pin the revision and title of every page used, with evidence markers specific to the claim. Write the summary and rules in your own words. Keep game text and art out of the import. Keep native BG3 rules and prices distinct from any separately requested tabletop conversion.
3. Apply the item onboarding checklist at `docs/skills/armory-combat-qa/item-onboarding.md` to the card. Trace the activation, target or weapon set, modifier channel, duration, consumption, exclusions, stacking and recipe where applicable. For coatings, distinguish applying the bottle, throwing the bottle, and throwing a coated weapon. Compare both the visible summary and drill-down against the pinned evidence.
4. From the project root run `python3 scripts/onboard_bg3_item.py <review.json> [<review.json> ...] --version <new-version>`. The script checks the MediaWiki revisions, preserves their SHA-256 hashes, and packages exactly the explicitly supplied BG3 reviews alongside the SRD. Include previously approved review files when adding to an existing selection. Confirm the SQLite schema, price, source links and catalog counts. Build the Android APK with the resulting ZIP and exact-search the item. Confirm its native rules label, modifier and exclusions, and check a known excluded BG3 item as a control.

Use a new release version for a changed review. The evidence markers detect mismatches in the input. They do not replace checking what the words mean or which variant they apply to.

For thrown consumables, follow the linked area and read the rendered source panels. Check throw range separately from splash radius. Record healing and condition removal for each activation mode. Read the shared table's column headers before interpreting a number. The “3” in Glorious Vaulting’s ingredient cell counts Wispweed and gives no splash measurement.

For a batch of variants, recheck acquisition on each pinned item page. An unobtainable item can still have a price and valid mechanics. Keep it out of ordinary loot and merchant claims. For arrows, check attack roll behavior, reflect exceptions, action use, direct impact, and the created surface or status as separate rules. For elixirs, verify replacement rules separately for drinking and throwing.

Pinned wiki revisions are cached as exact MediaWiki wikitext under `.cache/bg3-revisions/` with the title, page ID, revision ID, and SHA-256. Builds reuse validated cached revisions and fetch missing ones in batches. Keep the raw cache local. New revision IDs require new evidence.

Resolve each granted action, spell, aura, and condition separately. Match the exact grant to its pinned dependency and check for item-specific overrides and reported game behavior. Compare activation, eligible targets, range or area, saving throw and DC, trigger and timing, effect and early-ending clauses, and recharge against the live card. Treat attack qualifiers such as melee and qualifying surfaces as closed lists when the source defines them. For recipes, check each ingredient category and quantity. Keep source footnotes in source notes and keep the displayed rarity to its canonical label.

Reconcile the letter inventory by stable ID before packaging. Record why every candidate was imported, excluded, or deferred. Add source-specific regressions to scripts/bg3_rule_assertions.json when the pinned rule has an unambiguous trigger, number, or qualifier. Store expected checks independently of the card summaries.

Run `python3 scripts/discover_bg3_letters.py DE --output outputs/bg3-de-discovery.json` for combined batches. Compare the source title with the index and pin the exact item revision in the ledger. Check all named effects, including Superior versus ordinary Darkvision, and distinguish a spell variant actually granted by the item from sibling variants. For thrown effects and clouds, record activation, qualifying objects, save cadence, and exclusions separately.

For generated weapons, verify melee spell versus weapon attack and whether ordinary weapon actions are available. Pin terrain separately from the spell that creates it, and distinguish the terrain save from the spell save. Record container toughness, ranged and thrown exceptions, and contradictory combat-log attribution when the pinned source supports them.

Use the location or quest as a second source when the key page leaves its use blank. Do not infer a match from a similarly named key if the location attributes it to another ID. Record indexed aliases that belong to earlier letters as out of scope. Keep same-name variants distinct by ID and note when the source title disagrees with the actual enchantment.

For a new letter, use discover_bg3_letters.py with --local-evidence and --worklist, then merge the reviewed TSVs with build_bg3_batch_inventory.py. Verify the package against cache and fixtures with check_bg3_batch_sources.py. bg3_batch_workflow.sh packages, builds, checks source evidence, and captures each explicit emulator.

For each attack with a save-dependent damage exception, state hit or miss and save success or failure separately. Distinguish creature condition duration from the persistence of its cloud. Verify status effects that share similar names, and include any additional restrictions or automatic success that the exact item variant reports.

Check quest and location sources before excluding an ordinary trade item that may double as a ritual component. When handedness and alternate damage conflict, retain the source and present the unverified value as a source note. Confirm whether summoned creatures persist on unequip or on the caster being knocked out.

For chained conditions, pin every stage through the last effect, including its duration, affected rolls, and save or renewal at expiry. Check whether Honour Mode changes the damage type or qualifying sources of a condition, and record permanent acquisition losses separately from recoverable drops.

Check each proficient weapon action as a named drill-down. Capture attack and damage, save formula, size or creature exclusions, and condition outcome. Keep item-cast spell level and recharge in the named action. Distinguish a thrown coating’s immediate blast from its lingering cloud. If the coating table and condition page disagree, preserve the difference with both pins.

For notes and books, use the worklist reading clues to prioritize review. Check linked quest journals and location pages for an exact reading trigger, access phrase, Inspiration, or recipe unlock. Receiving an epilogue letter can reflect previous outcomes without triggering a new one. Record each distinction in the stable-ID ledger.

Compare every near-identical variant against its own Camp Supply quantity, location, and availability. For multi-mode equipment, expand each granted spell separately and verify the actual cast level, activation, target, damage, save, duration, and mode exceptions. Include linked conditions’ practical effects and termination, including shatter interactions.

For multi-act quest items, check the exact page or interaction that grants each spell, passive, Inspiration, and approval change. Include later ways to consume or exchange the reward. For consumable siblings, prefer the exact item revision and state any meaningful disagreement with the parent page.

Resolve conflicting alchemy ingredients against the shared recipe table and retain item and extraction citations. For breakable containers and throwable spell objects, check their own HP, damage affinities, toughness per hit, and whether the aim preview matches the real effect radius. Verify each dialogue skill and reward branch against the quest.

For a coating, compare the item, shared coating table, and linked surface. Verify each immediate and persistent save separately, whether both apply, and whether a thrown coated weapon carries the effect. For recovery potions, check named feature and equipment recharge exceptions. For shared weapon actions with a weapon-type damage field, derive the damage from the exact weapon and record class-specific or off-hand interactions.

Check main-hand and off-hand passives as separate source fields. Read effects by behavior as well as display type: a Potion can replace an active Elixir. Add a card assertion for the equipment slot, trigger, or replacement interaction when documented.

For a condition with start-of-turn ticking, check the exact applied duration before describing when a target regains actions. For encounter-warning items, record the event prerequisite, location, and any route that bypasses the warning.

Check source notes for whether an item’s reported behavior differs from its tooltip. For versioned quest dialogue, separate current dialogue tables from Early Access footnotes. A blank template property alone does not establish a distinct rusty or cosmetic chassis.

For scrolls, compare the exact item and its cast spell with the spell's linked conditions and any item-specific overrides. Separate initial and repeat saves, Concentration, ally targeting, recast costs, wall formation and persistent hazard damage. Keep one evidence entry per revision when the same page supplies multiple claims. Check that the card summary names a distinguishing benefit and that the named ability row can stand on its own with its activation and recharge.

For linked passives, check scope beyond the tooltip, including damage rerolls that apply to other attacks, resistance exceptions, and simultaneous equipment. Compare both the action and applied-condition save DCs and preserve meaningful discrepancies. Use the weapon's actual Reach in the profile. Put the magnitude and recharge inside each named effect. Test that each packaged field appears with its full value in the Android drill-down.

For inherited item variants, read the passive notes for hidden enabling statuses before marking a shared passive effective. When reviewing an access or disarm clue, capture the consequence of failure and the separate trap save. Verify whether a teleport enters turn-based mode automatically when a timed escape condition applies.

When a repeated weapon-action finding has a shared pinned rule, scan all fixtures with that action and rerender the corrected cohort. Verify the target list from the action and creature exceptions from the condition. For temporary HP, include qualifying cantrips, repeat casts and stacking where the source documents them.

Keep a deterministic import check for recurring shared-field gaps. Lacerate must cite Bleeding and state the Ghast and Ghoul exceptions. Rush Attack must cite the exact action and include non-allied objects. Match coating entries to the shared table by name and distinguish burst and persistent saves. Check environmental spell targets as well as surfaces, including hidden and Wet creatures.

Preserve the exact item's proficiency where it differs from the generic weapon family. For extraction ingredients, trace the dependency to the finished recipe. Cite the shared save formula when showing a hybrid DC.

Verify the artwork reference against the exact item's image and icon fields. If one reference describes a different item, retain the valid references and record the specific excluded file. Cross-check recipes in both directions when a new ingredient conflicts with a preceding card.

For containers that create a hazard, verify entry damage and recurring damage separately. Include conversion triggers, the resulting terrain, and object interactions when the pinned surface page defines them. For keys with shared display names, map each carrier to its specific door and keep the lock coordinate or contents as a disambiguator.
