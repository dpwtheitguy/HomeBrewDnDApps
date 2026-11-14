# Armory item onboarding checklist

Use the exact source edition, variant, and stable ID. Preserve printed rules and link the page or game record. Record inherited rules with the exact parent, and record overrides separately. Use explicit none, inapplicable, or unknown where silence changes play. Keep internal import and review states in QA output. Show a player-facing caveat for a material unresolved rule.

| Item type | What the card must communicate |
|---|---|
| Melee weapon | Training, hands, ability and attack formula, damage dice/type, reach, properties and mastery, alternate grips and damage, qualifying hits, bonus and rider, action cost, weight and base value. Separate thrown and melee modes. |
| Ranged weapon | Training, hands, ability and attack formula, normal/long range, damage, compatible ammunition and quantity spent, Loading versus Reload, capacity, properties/mastery, restrictions and on-hit or on-miss effects. |
| Ammunition | Unit or bundle size, compatible launchers, inherited damage and range, per-shot expenditure, recovery, attack/damage modifiers, target-specific riders and saves, and when magic ends. A mundane bolt has no independent attack profile. |
| Armor and shields | Armor slot and training, base AC formula or shield bonus, Dex cap, magic modifier, Strength, Stealth, don/doff and hands, attunement, prerequisites, and any conditional protection, curse or reaction. Show final AC without dropping the base or override. |
| Wand | Held or wielded requirements, attunement, charges, activation, selectable spell and level, charges per option, attack/DC and caster ability, range/area, outcomes, duration/Concentration, recharge and last-charge destruction. |
| Staff | Wand checks where applicable, plus separate melee profile, handedness, weapon bonus, spellcasting-focus eligibility, and whether wielding, holding or attuning activates each benefit. |
| Rod | Mode and command word, hands, activation, target and range, transformations or anchoring, force/weight limits, charges or per-rest uses, recharge, and separate weapon/spell profiles if present. |
| Ring | Worn and attunement requirements, passive versus activated effects, exact targets or roll modifiers, reactions, charges and recovery. For stored spells, record capacity, loading, who can cast, which caster statistics apply, and what empties the ring. |
| Potions and elixirs | Drink/administer/throw as separate modes, action cost, target and distance, healing dice or other effect, duration, stacking or replacement, consumption, variants with distinct prices, and recipe where published. |
| Oils, poisons and coatings | Application action, eligible object/weapon or set, quantity, duration, scope, exclusivity, effect channel, trigger, save and both outcomes, target effect timer, and throw restrictions. Distinguish applying a coating from exposure to the target. |
| Scrolls | Spell and level or choice, eligible reader, activation and casting time, attack/DC, check for higher-level casting and failure result, components/Concentration, consumption and interruption, plus separate scribing requirements and prices by level. |
| Wondrous items and accessories | Slot or handling, attunement, effect or role, trigger, targets, area and duration, limits and resets, curses, ownership and duplicate restrictions. For storage, include capacity, retrieval and failure conditions. |
| Tools and kits | Proficiency, ability and check/DC, Utilize options, time, materials, output, uses and refill, plus failure outcomes where specified. |
| Mundane gear and containers | Purpose, action, dimensions, capacity, contents, weight, cost, and any checks, ranges, duration or expenditure. Label equipment bundles and link constituent items where useful. |
| Mounts and vehicles | Movement and terrain, capacity, crew, cargo, handling requirements, defenses and damage thresholds where documented, upkeep, and price unit. |
| Siege and deployable gear | Setup, crew and action sequence, AC/HP, ammo, attack or save, range, damage/area, target restrictions and teardown. |
| Keys, maps and quest gear | Exact lock, destination or quest interaction and prerequisites. Send lore-only candidates to source review before exclusion. |
| Artifacts, sentient items and sets | Base profile plus prerequisites, sentience and conflict, curse, destruction, set thresholds and slots, which effects are shared or cumulative, and any DM decisions. |

## Release checks from the 40-card test

- Start with the player’s question. The first view should surface action, roll, and outcome before price. Keep details close enough to resolve the whole action.
- Compare source text, structured fields, packaged supplements, and live Android cards. Test a normal item, its magic counterpart, and an exception. A working base AC does not prove a magic AC bonus survived packaging.
- Check variant tables for actual rows, readable headers, and per-variant quantities and prices. Inspect literal markup, stale source links, and internal status labels.
- For each distinct mode, capture a positive and an exclusion case. Test launcher inheritance, on-miss effects, repeat saves, range units, attunement, zero charges, recharge and stacking where relevant.
- Use exact-title and ordinary partial search, then try the compact layout and relevant category filters. Record the tested build and scope. A card that opens is a navigation pass, not rules verification.

## Regression step before marking onboarding complete

Run this step on the installed release after the import, supplement packaging, and rendering changes. Use the official source and exact stable ID for expected values. For each applicable check, record the item, expected result, actual result, and pass or fail. Mark a check inapplicable only when the tested catalog lacks that item type or feature. Recheck failures after fixing the import or renderer.

| Previous mistake | Check during onboarding |
|---|---|
| Dwarven Plate was fixed while Dwarven Half Plate still showed its mundane AC | Test every affected family variant. Assert Dwarven Plate AC 20 and Dwarven Half Plate AC 17 + Dex (max +2) in the stat panel. Check that the forced-movement Reaction survives on both. Include mundane Half Plate at AC 15 + Dex (max +2). |
| Attunement existed in stored data but was absent from the card | For each supported item type with attunement, test one requiring it and one that does not. Assert visible requirements, including any class or spellcasting prerequisite. Include a ring, cloak, wand, staff, rod, and wondrous item. |
| Mundane ammunition only described quantity and storage | Test Arrows, Bolts, Firearm Bullets, Sling Bullets, and Needles. Open their compatible launcher links and verify damage and range are inherited. Check bundle size and compare against a magic ammunition variant. |
| Rules tables and emphasis printed as Markdown | Open a table-bearing potion, armor or ring, and a charged item. Verify real headers and rows in the compact layout. Check that a curse heading displays without markup characters. |
| The combat panel stopped at “starts burning” | Verify Alchemist’s Fire through its ongoing burn and termination, using the official rule for the expected damage and timing. For spells cast from items, verify that the charge cost, action, spell outcome, and recharge can all be found from the card. Check that Magic Missile identifies damage per dart. |
| One displayed price covered several different variants | Compare the cantrip and level 1 Spell Scroll entries or options, and the four healing potion strengths. Verify each applicable price or clearly label an estimate and the exact variant or unit it represents. |
| Warhorse received an equipment crafting estimate | Check Warhorse for source movement and carrying capacity and Galley for documented operating stats. Reject generic item-crafting guidance on living mounts. |
| SRD-only cards displayed excluded encounter references | Inspect known cross-source examples such as Thieves’ Tools. Verify that source-only cards have no excluded campaign links or encounter panels. |
| The card showed import jargon and pricing ahead of rules | Open a basic weapon, defensive item, and charged item. Check that the actionable rules precede Value and that internal labels such as “Source transcription unverified” are absent. |
| Successful search and tile open were treated as a rules pass | Record navigation, rule fidelity, and at-table usability separately. Use the hurried defender to check speed and the detail-oriented DM to check whether the card resolves an interaction. |

For a repeat-until-clean review, fix the shared import or renderer before reimporting. First rerun every known failing fixture. Then give the Player and DM 200 randomly selected cards each from their respective eligible pools, record the random seed and stable IDs, and avoid overlap. Report any newly discovered issue with the exact rendered field and source. Repeat with a new sample after fixing failures. Preserve charging and spell resolution together where applicable, distinguish per-dart from total damage, and validate that the linked launchers open rather than merely naming them.

Also compare spell-derived panels with the item's overrides. A self-only ring must show Self, an item that waives Concentration must display the waiver, and a downstream damage clause must not become the spell's main damage row. Render tables and emphasis in both item and inherited spell prose. Test every vessel in the official operating table, plain +1/+2/+3 weapon attack and damage modifiers, and the valuation unit for magic ammunition. Check excluded campaign names in the inspector header as well as encounter panels.

Open collapsed Source references and changes during SRD-only tests. Inspect every hyperlink for excluded campaign references. Include tables prefixed with blockquote markers, underscore emphasis, and inherited spell descriptions in the markup checks. Keep the original spell prose explicitly labeled when the item overrides it.

For an item that changes a spell’s area or save DC, assert both in the rendered spell panel. Use Cloak of Arachnida as a fixture. The Web panel must show twice the base area and DC 13. Damage triggered by burning webs belongs in the conditional rules text.

Use every row of the mounts and vehicle tables as fixtures, including flying vehicles. Check category, speed, carrying or cargo capacity, and crew and defenses where applicable. A Warhorse and Galley pass cannot clear Elephant and Airship.

For dual-use staves and transforming rods, open each weapon mode and verify the actual linked weapon, item bonus or damage rider, and action to switch. For Staff of Striking and Rod of Lordly Might, verify that the card can lead a DM from item-specific rules to the weapon's attack, damage, range, and mastery.

Compare the first and last sentences of imported text against the source to catch truncation and orphan fragments. Check variable-rarity family records such as Ioun Stone for magic classification, attunement, and a clearly labeled variant value instead of a generic category estimate. Apply the self-only override fixture to both Ring of Jumping and Ring of Water Walking.

Test compound spell overrides together. Cloak of the Bat requires Dim Light or Darkness, targets the wearer, fixes the form to Bat, retains mental ability scores, and recharges at dawn. Its effective card must not present the base spell's unrestricted target, form, or hostile saving throw as applicable.

Follow spell effects granted without casting. Test Potion of Mind Reading and Potion of Gaseous Form for inherited effects and their own duration, target, save DC, and Concentration override. The effective action is drinking the potion.

Check fractional quantities against the printed value. A Glass Bottle holds 1½ pints. Reject split mixed numbers such as “1 0.5 pints,” and test container capacity, weight, and travel speed in their native units.

For items that offer a list of spells, confirm each option opens its effective rules and preserves option-specific restrictions. Ring of Animal Influence restricts Fear to Beasts. For non-damaging effects, keep damage resistance and save advantage out of the damage and save-to-resist rows. Gaseous Form has no offensive damage row, and its potion ends early with a Bonus Action. Verify number–unit spacing and the item's save DC on inherited spell panels.

Test spell options listed in charge tables as well as prose. Staff of Fire must expose Burning Hands, Fireball, and Wall of Fire with their item charge costs and caster DC rule. A summon that uses a named creature stat block needs a direct rules reference.

Resolve qualified spell-table cells such as “Fireball (level 5 version)” against the base spell and its explicit cast level. Verify the effective damage. Check the entire elemental summoning family and Horn of Valhalla for direct creature stat-block references.

Include alternate spell phrasing such as “Dancing Lights or Light.” Verify every option on Ring of Shooting Stars, even when an earlier option resolves correctly.

For each qualified charge-table row, verify the spell link, charge cost, effective save DC, and the qualifier. Wand of Fear is the fixture for Command limited to flee or grovel and Fear with a 60-foot Cone. For Staff of Power, label inherited prose as base spell text when an upcast changes the damage, retain the length and width of Lightning Bolt, and keep Ray of Enfeeblement’s damage-roll penalty out of the damage row. For companion items such as Talisman of the Sphere, follow the in-app link and verify the target opens with its baseline check and failure outcome.

Search both active casting and indirect wording that applies a named spell. Test “under the effect” with Potion of Heroism, including its shared one-hour duration, 10 Temporary Hit Points and self-only Bless without Concentration. Verify Growth and Diminution select a single mode, Potion of Clairvoyance retains the sensor range, and Potion of Animal Friendship fixes the spell at level 3. Oils can apply one spell on a creature and duplicate a different spell on a surface. Test both Oil of Slipperiness modes, the Oil of Etherealness duration, and the appropriate drinking, coating or pouring action.

Validate structured spell summaries against the same edition’s rules text even when the fields come from a pinned fixture. Reject area, save, or damage fields that contradict the actual effect, such as a Cold sphere on Freedom of Movement or Bless’s attack/save bonus presented as damage. Retain legitimate conditional summon damage, such as Conjure Elemental’s initial and repeated failed-save dice. Verify that self-only Growth and Diminution do not require the unwilling target’s save. Test spell scaling at every used level, including Staff of the Magi’s level 7 Fireball and Lightning Bolt (12d6), zero-charge spells, and the three targets of Potion of Animal Friendship’s level 3 spell.

Apply the named-creature reference check to all Figurines of Wondrous Power. Silver Raven also restricts Animal Messenger to the figurine’s Raven form. A spellcasting focus that explicitly doubles as a weapon needs a usable chassis link. Preserve the 2024 Military Saddle’s ability-check wording and distinguish it from the forced-movement Dexterity saving throw.

Parse inline spell lists with named consumable components as well as charge tables. Helm of Brilliance must show all four spells and each consumed gem, distinguish spell save DC 18 from the helm destruction DC 17, and omit saves for spells without one. Test creature references in random outcome tables, including Bag of Beans, and commanded swarms, including Pipes of the Sewers. A spell that grants saving throw Advantage, such as Haste, must not show that as a save to resist the spell.

Check the meaning of dice in random spell tables. In Prismatic Spray, 1d8 selects a ray and rays 1–5 deal 12d6, halved on a successful save. Test the Manual of Golems for all four applicable creature references, including records where the source directs the DM to consult a stat block.

Follow spell-local stat blocks as well as standalone creature entries. Staff of Swarming Insects needs the Giant Insect block from the spell. When an item sets a spell attack modifier and the spell makes multiple attacks, verify the bonus per attack and the damage unit. Circlet of Blasting makes three rays at +5 to hit, each dealing 2d6 Fire on a hit.

Test higher-level healing as well as higher-level damage. Dragon Orb’s ninth-level Cure Wounds restores 18d8 plus the spellcasting ability modifier. Treat named items and spells that end an effect as rule dependencies. For Sovereign Glue, follow Universal Solvent, Oil of Etherealness, and Wish, and verify the separate storage requirement.

Resolve “detonates as” and other spell comparisons that inherit an effect without casting. Necklace of Fireballs uses a Magic action and 60-foot throw, then inherits Fireball’s 20-foot-radius Sphere, Dexterity save and half damage on success, with the necklace’s DC 15 and its own 8d6–12d6 bead scaling.

Check dash-separated spell lists and fixed-level phrases with or without “the” before a spell name. Rod of Alertness has four detection spell options. Robe of Stars casts level 5 Magic Missile, which makes seven darts at 1d4 + 1 Force each. Check all 24 Bag of Tricks outcomes with the correct color, roll, and creature reference.

Check tables and every generated link on the oldest supported Android WebView. A section heading can render before unsupported JavaScript stops its row or link generation. Require link counts and check for runtime errors as well as section titles.

Verify attuned equipment prerequisites in every chassis variant. Giant’s Bane on both Hammer of Thunderbolts forms depends on an attuned Belt of Giant Strength or Gauntlets of Ogre Power. Distinguish total charges from the per-use spending cap. Wand of Magic Missiles has seven charges total and spends one to three per cast, creating three to five darts.

Classify damage that only happens when an effect fails. On Cape of the Mountebank, Dimension Door’s 4d6 Force applies to the teleporters only when arrival is blocked and the teleport fails. Put it beside the failure condition.

## Rules Lawyer review

Run the Rules Lawyer alongside the hurried Player and detail-oriented DM after an SRD reimport. Give the Rules Lawyer 200 independently seeded random IDs and all previous fidelity failures. Compare official SRD 5.2.1 pages, the pinned transcription, packaged records and the rendered rule. Require the full text, exceptions, tables, higher-level paragraphs and rule dependencies. Check the source coverage separately from the wording of existing entries.

Compute MD5 over exact UTF-8 text before presentation transforms. Compare the preserved transcription and its hash against the pinned fixture. Check the publisher text separately and document any allowed line-wrap, pagination or hyphenation normalization. Only attest to official wording when the comparison actually used the publisher text. Record approved corrections with a page locator and keep app-generated summaries outside the source wording.

Index distinct publisher sections even if they share a title. Spell Scroll has a basic gear entry on page 99 and a magic-item entry on pages 244–245. Verify all ten rows, the interruption and higher-level casting rules, and the separate Wizard spellbook check and destruction outcomes.

Build the coverage checklist from the official publication’s headings and tables before comparing installed IDs. Track official entries missing from the upstream fixture. For table-only items, compare the printed row and keep upstream descriptive gloss labeled separately. Keep the full higher-level spell rules visible as source text and explicitly identify which levels and targets the item actually grants.

Compare boundaries between adjacent item variants. For Ivory Goats, reject text from Golden Lions, verify the three goat descriptions, and follow the Goat of Traveling to the Riding Horse stat block.

Before packaging, validate SQLite and every record against the shipped JSON Schema. Recompute the pinned and display hashes and require a source locator and retained original bytes for corrections. Compare a publication-derived heading and table inventory with stable IDs, with a documented mapping for family expansions. Record missing publisher entries even when all installed records validate.

For each inherited rule, read the rendered card as an instruction. Ask which action, target, dice and resource the item actually permits. Test the base rule and its item-specific override together, including a disallowed target, cast level or resource amount. Never collapse a qualified charge cost to its leading number. Preserve the publisher's full spell rules and label what the item's limits allow.

Random draws contain 200 unique stable IDs per role, selected without replacement with a recorded seed. Report known regression fixtures separately. The Player assesses quick decisions, the DM resolves edge cases and follows dependencies, and the Rules Lawyer compares exact wording and publisher coverage. Keep each role's verdict separate from schema and navigation results.

For a charged item, compare the complete cost in the source table against the rendered option, including per-level costs and ceilings. Staff of Healing must retain one charge per Cure Wounds spell level, up to four. For items that cast one spell through another, verify which spell owns the sensor, range origin, Concentration, and end condition. Crystal Ball of Telepathy’s Suggestion has no separate Concentration, targets through the sensor, and ends with Scrying.

For the 200-card gate, pin the same release across all three roles. Broaden a small role pool with adjacent item types it can meaningfully review, preserving the role’s criteria. Sample without replacement within each role. Review prior failures separately and require both the samples and their regressions to pass before marking the gate complete. Treat a missing publisher heading as a coverage failure even if the sampled wording is clean.

Run `python3 scripts/check_srd_onboarding.py <catalog.zip>` for packaged SQLite and exact-text checks. Add `--seed <integer>` and one `--exclude <stable-id>` per reserved fixture for a reproducible full-catalog draw. Run the JSON Schema validator and compare the publication inventory separately.

Reconcile each named outcome in a random table to the rule or stat block it invokes. Include Mysterious Deck’s Donjon, Wand of Wonder’s spell outcomes, Folding Boat’s two vessel forms, and Robe of Useful Items’ creatures. Compare variant-wide tool actions and weights to the printed family entry. Test compound attunement prerequisites from the actual card, including Staff of Power and Staff of Charming. A boolean Required does not communicate class restrictions.

Spell tables can be keyed by bead, random roll, gem or form. Verify all rows, including the spell level and item-specific action, save DC owner and reset. Necklace of Prayer Beads needs all six bead options and each bead’s dawn reset. Check the Herbalism Kit’s complete official Ability, Weight, Utilize and Craft fields as a tool-family control.

Compare the full casting-time sentence with the extracted action type. Store and render any attached trigger independently of reaction fields. Test Bead of Smiting for a Bonus Action immediately after a melee weapon or Unarmed Strike hit.

Review an item’s creature dependencies after its spell panels pass. Elemental Gem needs all four stat blocks, Wand of Wonder needs the creatures it creates and its fixed Polymorph forms, and Staff of the Python needs the Giant Constrictor Snake block for player-controlled turns.

Test positive self-target phrasing such as “cast Levitate on yourself.” When the spell’s save applies to unwilling targets, omit it from that self-only item profile and retain the spell’s Concentration.

Compare display titles with the official heading, even when the body wording matches. Retain the stable ID and prior title as a search alias when correcting an established spelling. Check service and recurring-cost table rows, including the 10 lb. and 5 CP per day for mount feed.

### Variant scope and classification

Compare the item's displayed type with its actual use and its category/filter results. Ammunition of Undead Slaying is ammunition with a fixed Undead target. The family’s random table belongs in source evidence. Compare an Anchor Feather Token against Bird. Only Bird should show a Roc link, and the main rules should describe only the chosen token. On a family record such as Horn of Valhalla, check the family rarity and every published material rarity independently. Verify positive and negative filters and keep the original source text and stable IDs available.

### Visual presentation

Screen visible card text for literal escape sequences, raw markup, unintended gaps, and broken wrapping. On Deck of Illusions, check that the table and its footnote retain the asterisk and render without a stray backslash. Confirm source evidence still preserves its original bytes. On compact and wide layouts, inspect one long table and one ordinary card for clipping, overflow, readable labels, and spacing. For reports and charts, verify readable units, legends, labels and values at the intended size.
