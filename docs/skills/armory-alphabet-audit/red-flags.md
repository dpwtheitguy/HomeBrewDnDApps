# 100 item metadata red flags

Each flag requires a source check before marking the profile reviewed. Compare the exact variant with the stored fields and the rendered card. Record the item ID, field, source locator, expected value, and a positive and negative test where applicable. Keep verified absence, inapplicability, and unresolved facts distinct. Counts are review leads.

## Editorial and import markers

Search editorial metadata and generated copy. Search source prose only for targeted mechanic cues. A quoted word in original prose is insufficient evidence.

1. `whitelist` or `allowlist` used to describe projected fields. Compare the dropped source fields against gameplay requirements.
2. `placeholder` or `stub`. Identify which values the stand-in replaces.
3. `TODO` or `TBD`. Identify the unresolved field or decision.
4. `pending` or `legacy pending`. Check whether rules exist in a supplement and whether the player can see them.
5. `adaptation needed` on a native profile with playable rules. Verify which ruleset the label describes.
6. `factual metadata only` on a card presented as playable. Check for mechanics beyond name, type, and provenance.
7. `catalog has a reference` or `source index entry` as the only explanation. Locate and import the operative rules.
8. `provisional profile` or `improvised fallback`. Verify the identity and attack against the source.
9. `needs verification` or `unverified` on a material field. Verify the exact claim.
10. `unknown`, `N/A`, a bare dash, or a null in a required field. Establish why the field is absent.
11. `see source` as the only effect. Extract the rule the player needs.
12. `uses standard rules` with no named rule or linked base. Resolve the exact inherited rule.
13. `special properties` or `grants a bonus` with no mechanic. Identify the affected roll and magnitude.
14. `etc.` or an ellipsis at the end of a rule list. Check for omitted targets, exceptions, or outcomes.
15. `copied from` or `same as` with no variant comparison. Verify differences before inheriting.

## Source and identity

16. Source link resolves to a homepage, category, or search result. Find the exact item.
17. Source reference lacks a page, stable game ID, or revision when variants differ.
18. Game ID and item title disagree.
19. Common, Epic, diluted, or enhanced variants share one unexplained profile.
20. Early Access stats are shown as current.
21. Unobtainable or removed item is offered as normal loot.
22. Difficulty-specific behavior is shown for every difficulty.
23. Native mechanics and tabletop conversion are mixed in the same field.
24. Author-created values are attributed to the original source.
25. Source or rules revision changed after the last verification.
26. Sources disagree on a material value and the record gives no edition or patch explanation.
27. A translation changes a mechanical term such as save, check, hit, or turn.
28. Two distinct source IDs collapse into one entry because their names match.
29. One item appears twice under aliases with conflicting rules.
30. Primary source available but key claims are based solely on a secondary summary.

## Activation, targeting, and resolution

31. Action cost missing or described only as “use.”
32. Reaction lacks a triggering event or response window.
33. Passive has no condition specifying when it applies.
34. On-hit, on-attack, and on-damage triggers are treated as interchangeable.
35. Once-per-turn trigger omits whose turn.
36. Critical hit trigger omits whether it requires a natural roll or any critical hit.
37. Equipment prerequisite omits worn, held, wielded, or attuned.
38. Target scope omits self, weapon, set, ally, enemy, or object.
39. Target eligibility omits size, creature type, weapon type, or another source restriction.
40. Target count is missing for a multi-target effect.
41. Range omits its unit or uses mixed units inconsistently.
42. Area effect omits shape, origin, or size.
43. Throwing, drinking, and applying share one mode despite different mechanics.
44. Attack roll, ability check, and saving throw are conflated.
45. Save omits ability or DC formula.
46. Save omits an applicable success or failure outcome.
47. Attack or throw omits a documented effect on a miss.
48. Spell reference omits spell level, casting ability, or an item override where relevant.
49. Ordering is ambiguous when one hit can apply and trigger an effect.
50. An item says it “cures” a condition without distinguishing removing it from immunity.

## Effects and equipment

51. Normal attack has no damage dice or damage type.
52. Bonus to hit appears as bonus damage, or vice versa.
53. Conditional damage omits its qualifying attack or target.
54. Damage rider omits dice, damage type, or timing.
55. Condition name appears without a playable definition or resolved rules reference.
56. Condition duration appears without what the condition changes.
57. Resistance, immunity, and vulnerability are conflated.
58. Healing, temporary HP, and maximum HP change are conflated.
59. AC bonus is shown as a base AC formula.
60. Armor lacks a Dexterity cap or a clear statement of how Dexterity applies.
61. Shield bonus omits its training or wielding requirement.
62. Armor omits a documented Strength minimum or Stealth disadvantage.
63. Reach weapon uses generic 5 ft reach.
64. Thrown weapon lacks a range or a traceable ruleset-specific range formula.
65. Ranged weapon omits compatible ammunition or a documented Loading rule.
66. Ammunition has no launcher relationship or incorrectly replaces launcher damage.
67. Two-handed source weapon is mapped to a one-handed chassis without explanation.
68. Mastery conflicts with the chosen 2024 base weapon.
69. A set of paired weapons grants both bonuses to a single attack.
70. Off-hand focus, quiver, saddle, or costume piece is treated as a shield or independent worn armor.

## Time, stacking, and resources

71. Duration omits its unit or start event.
72. Turn duration omits which entity’s turn or the tick phase where it affects play.
73. Weapon coating lifetime and target debuff lifetime use one timer.
74. Effect omits early termination on save, damage, removal, or another source event.
75. Repeat save omits cadence or trigger.
76. Item-granted spell omits Concentration when required.
77. Reapplication omits whether it replaces, refreshes, extends, or adds an instance.
78. Stack group has no scope, such as per target or per weapon set.
79. Exclusivity or stack priority omits tie-breaking where required.
80. Stack count or duration can exceed a documented cap.
81. Additive modifiers and alternative base formulas are combined as if they were the same.
82. Charges omit maximum, cost per use, or zero-charge behavior.
83. Multiple powers use a shared pool but are tracked independently.
84. Short Rest, Long Rest, partial rest, and dawn are treated as equivalent.
85. Recharge omits the amount restored, dice formula, or event.
86. Once-per-rest or once-per-turn limit omits its owner.
87. Consumable use does not identify when the item is spent.
88. Attunement omits prerequisite, slot cost, or a documented shared-slot exception.
89. Equipped effect remains active after unequipping despite a source restriction.
90. Current charges or duration are stored in the catalog definition instead of per item instance.

## Acquisition and player-facing verification

91. Listed source value is presented as base buy or sell without the pricing policy.
92. Price is missing, zero, or contradictory without a documented reason.
93. A magic item with verified rarity falls back to mundane equipment pricing without explanation.
94. Price omits whether it is per piece, bundle, or complete set.
95. Recipe omits ingredient quantities or the meaning of “any” ingredient.
96. Crafting requirements omit a documented station, unlock, time, or restriction.
97. A vendor, drop, or recipe belongs to a different variant or availability state.
98. The TL;DR contradicts the structured data or omits a defining exception.
99. A complete supplement exists but the card renders a stale status, fallback, or source link alone.
100. A passing test checks the item name or keywords only and never tests exact values, ownership, timing, or an exclusion.
