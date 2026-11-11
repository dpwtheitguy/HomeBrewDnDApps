# Shared data for the Complete Guide apps

The app family shares one versioned item catalog, proficiency vocabulary, effect vocabulary, pricing rules and exchange protocol. Each character app supplies its own class progression and UI. Arms and Equipment Guide can use the same catalog on its own. Open identifier namespaces allow new titles to join the family. See the [catalog release and integration contract](../docs/SHARED-CATALOG.md).

An item definition is not an inventory instance. A future inventory instance references an exact item and pack version and stores owner, quantity, condition, charges, attunement, identification state, custom name and overrides. A character snapshot pins class/rules/content versions. Cross-app exchanges transfer inventory instances by stable IDs and acknowledged events.

Proficiency comes from source-tracked grants: class, subclass, background, species, feats, items and campaign changes. Resolved skill ranks use the highest applicable multiplier rather than summing proficiency twice. Expertise doubles one proficiency bonus. Half proficiency rounds down. Explicit extra bonuses remain separate effects. Conditional grants and choice sets must be resolved before aggregation. Language and armor training are flags, not bonuses applied to arbitrary rolls.

Items express proficiency interactions without listing allowed classes. A martial weapon can be used without proficiency, with the applicable rules consequence; lack of proficiency does not prohibit ownership. Attunement and spellcasting conditions are separate predicates. Current extracted interactions are partial and visibly marked; parsing every descriptive prerequisite remains outstanding.

## Pricing

Store intrinsic/list values separately from contextual quotes. Base values retain source economy, edition, units and variant. Do not interpret unknown/placeholder zero prices as free items. A BG3 gp and a tabletop gp do not imply economically equivalent values; using BG3-style quotes on tabletop values is an explicit campaign house rule.

`economy.py` implements a reference estimate:

- Balanced baseline 2.5; Explorer 2; Tactician/Honour 3.
- Multiplier = max(1, baseline − total Persuasion / 10 − merchant attitude / 200).
- Buy = base × multiplier; sell = base / multiplier.
- Use the final Persuasion bonus, including Charisma, training/expertise and other effects. Never add Charisma twice. Character skill calculation is separate, including any BG3 Explorer-specific proficiency changes.
- Exact decimal values are retained. Whole-gp display uses explicit half-up rounding, an app convention rather than verified BG3 engine behavior. Stack rounding, individual item exceptions, specific merchant behavior and patch differences are not replicated.

The BG3 wiki's trading article contains inconsistent summary wording about difficulty, but its detailed modifier section and worked examples support the baselines above. Treat the implementation as a tested reference estimate pending actual game validation, not an exact engine port.

Source: https://bg3.wiki/wiki/Trading_and_item_pricing

For example, a base value of 100 gp with Persuasion +5, attitude 0 and Balanced pricing yields buy 200 gp and sell 50 gp. Changing to +10 Persuasion and attitude 100 yields buy/sell 100 gp, at the multiplier floor.

2024 magic-item rarity values are reference guidelines, not a universal sale quote. Base-equipment costs, consumables, spell-scroll exceptions and priceless artifacts need explicit handling before applying a rarity estimate. The separate market-price index uses source evidence first, followed by explicit estimates based on comparable equipment, rarity, scroll level, or item category. `item_pricing.py` records the basis and economy for every price triplet.

## Conversion flavor

Keep three independently selectable layers: original source, baseline 2024 conversion, and optional BG3-inspired variant. A variant has its own stable ID, parent reference, version, flavor, effects and price estimate. Add tactical passives, actions or limited-use synergies only with explicit activation, targeting, resource recovery and stacking rules. Do not silently improve every cultural reskin. All new effects are homebrew and need playtesting.
