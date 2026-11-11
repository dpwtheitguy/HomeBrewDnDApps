#!/usr/bin/env python3
"""Project published 2024 magic weapon rules and verify their legacy counterparts."""
import json
import sqlite3

from build_core_enhancement_cross_references import CATALOG, CURRENT, LEGACY, REVIEWED_BASE_NOTES, modern_plain_name

RULES = 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z'
FAMILIES = {
    'Dancing Sword': {
        'published_bases': ('Greatsword', 'Longsword', 'Rapier', 'Scimitar', 'Shortsword'),
        'damage': 'The hovering sword uses your attack roll and adds your ability modifier to its damage.',
        'activation': 'Use a Bonus Action to toss the sword, move it up to 30 ft, and attack a creature within 5 ft of it. Further Bonus Actions can each move it up to 30 ft to a spot within 30 ft of you and make another attack.',
        'change': 'The 2024 variant uses the matching base sword. Scimitar is explicitly eligible.',
        'Duration': 'Hovering ends after the fourth attack, if you grasp it, or if you move more than 30 ft from it.',
        'Special powers': 'After its fourth attack it returns to your free hand or falls in your space. If blocked, it moves as close as possible before falling.',
    },
    'Sword of Life Stealing': {
        'published_bases': ('Glaive', 'Greatsword', 'Longsword', 'Rapier', 'Scimitar', 'Shortsword'),
        'damage': 'A natural 20 adds 15 Necrotic damage against a creature other than a Construct or Undead.',
        'activation': 'When the attack die rolls 20 against an eligible creature.',
        'change': 'The 2024 extra damage is 15 Necrotic. Temporary HP tracks damage actually taken.',
        'Special powers': 'Gain temporary HP equal to the Necrotic damage the target actually takes.',
    },
    'Sword of Sharpness': {
        'published_bases': ('Glaive', 'Greatsword', 'Longsword', 'Scimitar'),
        'damage': 'Maximize weapon damage dice when you hit an object. A natural 20 against a creature adds 14 Slashing.',
        'activation': 'On a hit against an object, or a natural 20 on an attack against a creature.',
        'change': 'The 2024 natural-20 effect inflicts Exhaustion.',
        'Special powers': 'A creature targeted by the natural-20 effect also gains 1 Exhaustion level.',
    },
    'Sword of Wounding': {
        'published_bases': ('Glaive', 'Greatsword', 'Longsword', 'Rapier', 'Scimitar', 'Shortsword'),
        'damage': 'Add 2d6 Necrotic on a hit against a creature.',
        'activation': 'On a weapon hit against a creature.',
        'change': 'The 2024 version applies extra damage on the hit and can block all healing for a limited duration.',
        'Saving throw': 'DC 15 Constitution. On failure the creature cannot regain HP for 1 hour. Repeat at the end of each of its turns to end the effect on a success.',
    },
    'Vorpal Sword': {
        'published_bases': ('Glaive', 'Greatsword', 'Longsword', 'Scimitar'),
        'damage': 'Add 3 to normal damage and ignore Slashing Resistance. A qualifying natural 20 can sever a head or deal an extra 30 Slashing instead.',
        'activation': 'On a natural 20 when attacking a creature with at least one head. Losing the head kills a creature that needs it to survive.',
        'change': 'In 2024 a creature can spend a use of Legendary Resistance to avoid losing its head and take the extra damage instead.',
        'Attack bonus': '+3 to attack and damage rolls.',
        'Exceptions': 'A creature immune to Slashing, one that does not need its head, or one the DM judges too large to decapitate takes the extra damage instead.',
    },
    'Luck Blade': {
        'prefix': 'Luck Blade (', 'evidence': 'reroll one failed',
        'damage': 'Add 1 to normal damage.',
        'activation': 'While carrying it, reroll a failed D20 Test without an action if you are not Incapacitated. Use the new roll. While holding it, spend a Wish charge to cast Wish.',
        'change': 'The 2024 Luck reroll requires a failed D20 Test and is unavailable while Incapacitated.',
        'Attack bonus': '+1 to attack and damage rolls.',
        'Special powers': '+1 to saving throws while the weapon is on your person.',
        'Charges': 'The reroll refreshes at dawn. Wish starts with 1d3 charges, is usable once per dawn, and is lost when the last charge is spent.',
    },
    'Nine Lives Stealer': {
        'prefix': 'Nine Lives Stealer (', 'evidence': 'fewer than 100 hit points',
        'damage': 'Add 2 to normal damage.',
        'activation': 'When you roll a natural 20 on an attack against a creature with fewer than 100 HP.',
        'change': 'The 2024 enchantment can apply to any simple or martial weapon and uses the matching base and mastery.',
        'Attack bonus': '+2 to attack and damage rolls.',
        'Saving throw': 'DC 15 Constitution or die instantly. Constructs and Undead succeed automatically.',
        'Charges': 'Starts with 1d8 + 1 charges. Spend one only if the effect kills the target. The effect is lost at zero charges.',
    },
    'Dragon Slayer': {
        'name': 'Dragon Slayer', 'any_base': True, 'evidence': 'extra 3d6 damage of the weapon',
        'damage': 'Add 1 to normal damage, plus 3d6 of the weapon’s damage type on a hit against a Dragon.',
        'activation': 'Extra damage on a weapon hit against a Dragon.',
        'change': 'The 2024 enchantment can apply to any simple or martial weapon. This card uses the legacy variant’s matching 2024 base.',
        'Attack bonus': '+1 to attack and damage rolls.',
    },
    'Dwarven Thrower': {
        'name': 'Dwarven Thrower', 'base': 'Warhammer', 'evidence': 'extra 1d8 force damage',
        'damage': 'Add 3 to normal damage. A ranged hit adds 1d8 Force, or 2d8 Force against a Giant.',
        'activation': 'Make a melee or thrown weapon attack. After a throw, it returns to your hand on a hit or miss.',
        'change': 'The extra thrown damage is Force. Attunement now also works through a Belt of Dwarvenkind.',
        'Attack bonus': '+3 to attack and damage rolls.',
        'Range': '5 ft melee; 20/60 ft thrown',
        'Added property': 'Thrown (20/60 ft)',
        'Attunement': 'Required by a Dwarf or a creature attuned to a Belt of Dwarvenkind.',
    },
    'Javelin of Lightning': {
        'name': 'Javelin of Lightning', 'base': 'Javelin', 'evidence': 'forgo making a ranged attack roll',
        'damage': 'On a normal hit, choose Piercing or Lightning. The bolt deals 4d6 Lightning, halved on a successful save.',
        'activation': 'When throwing at a target within 120 ft, replace the ranged attack roll with the bolt.',
        'change': 'The 2024 bolt uses a saving throw for the target as well as intervening creatures.',
        'Area': 'A 5 ft wide line from you to the target, excluding you.',
        'Saving throw': 'DC 13 Dexterity for the target and each other creature in the line.',
        'Recharge': 'The bolt recharges at dawn. The javelin reappears in your hand after the bolt resolves.',
    },
    'Mace of Disruption': {
        'name': 'Mace of Disruption', 'base': 'Mace', 'evidence': '25 hit points or fewer',
        'damage': 'Add 2d6 Radiant on a hit against a Fiend or Undead.',
        'activation': 'On a hit against a Fiend or Undead, check its remaining HP after damage.',
        'change': 'The 2024 mace uses the matching base weapon and Sap mastery.',
        'Saving throw': 'If the target has 25 HP or fewer, DC 15 Wisdom. Failure destroys it. Success leaves it Frightened until the end of your next turn.',
        'Area': 'While held, 20 ft Bright Light and another 20 ft Dim Light.',
    },
    'Mace of Smiting': {
        'name': 'Mace of Smiting', 'base': 'Mace', 'evidence': 'extra 7 bludgeoning damage',
        'damage': 'Add 1 to damage, or 3 against a Construct. A natural 20 adds another 7 Bludgeoning, or 14 against a Construct.',
        'activation': 'When you roll a 20 on an attack, a Construct at 25 HP or fewer after the damage is destroyed.',
        'change': 'The 2024 natural-20 damage is fixed at 7 or 14, replacing the legacy dice.',
        'Attack bonus': '+1 to attack and damage, increasing to +3 against Constructs.',
    },
    'Mace of Terror': {
        'name': 'Mace of Terror', 'base': 'Mace', 'evidence': 'make opportunity attacks',
        'source': 'https://www.dndbeyond.com/magic-items/9228835-mace-of-terror',
        'damage': 'The fear effect deals no damage.',
        'activation': 'While holding the mace, use a Magic action and spend 1 charge.',
        'change': 'The 2024 effect forbids Opportunity Attacks specifically. The 2014 version prohibited all reactions.',
        'Area': 'Choose creatures within 30 ft of you.',
        'Saving throw': 'DC 15 Wisdom. Repeat at the end of each affected turn to end the effect on a success.',
        'Duration': 'Up to 1 minute. Frightened targets try to move away and cannot make Opportunity Attacks. Their action is limited to Dash or trying to escape restraint on movement. If they cannot move anywhere, they can Dodge.',
        'Charges': '3 charges. Regain 1d3 spent charges at dawn.',
    },
    'Scimitar of Speed': {
        'name': 'Scimitar of Speed', 'base': 'Scimitar', 'evidence': 'as a bonus action on each of your turns',
        'damage': 'Add 2 to normal damage.',
        'activation': 'You can attack once with this weapon using a Bonus Action on each of your turns.',
        'change': 'The 2024 scimitar has Nick mastery. The item’s Bonus Action attack is a separate feature.',
        'Attack bonus': '+2 to attack and damage rolls.',
    },
    'Sun Blade': {
        'name': 'Sun Blade', 'base': 'Longsword', 'evidence': 'blade of radiance',
        'activation': 'While gripping the hilt, use a Bonus Action to create or dismiss the blade. While it exists, use a Magic action to adjust the light.',
        'change': 'The 2024 Sun Blade uses the Longsword’s Sap mastery and a Magic action to adjust its sunlight.',
        'Damage': '1d8 Radiant one-handed or 1d10 Radiant two-handed, plus 2. Add 1d8 Radiant on a hit against an Undead.',
        'Attack bonus': '+2 to attack and damage rolls.',
        'Properties': 'Finesse, Versatile (1d10)',
        'Training': 'Longsword or Shortsword proficiency applies.',
        'Area': 'Sunlight. 15 ft Bright Light plus another 15 ft Dim Light. Adjust both bands in 5 ft steps, from 10 ft to 30 ft each.',
    },
    'Defender': {
        'prefix': 'Defender (', 'evidence': 'transfer some or all of the weapon',
        'damage': 'Add the portion of the +3 bonus retained for attacks.',
        'activation': 'When you first attack with it on your turn, choose how much of its +3 to transfer to AC.',
        'change': 'The 2024 item permits any melee weapon and uses the matching base weapon and its mastery.',
        'Attack bonus': '+3 to attack and damage, reduced by any amount assigned to AC.',
        'Duration': 'Until the start of your next turn. Hold the weapon to benefit from its AC bonus.',
        'melee_only': True,
    },
    'Holy Avenger': {
        'prefix': 'Holy Avenger (', 'evidence': 'extra 2d10 radiant damage',
        'damage': 'Add 3 to normal damage, plus 2d10 Radiant on a hit against a Fiend or Undead.',
        'activation': 'Extra damage on a qualifying hit. The aura is active while you hold the drawn weapon.',
        'change': 'The 2024 item permits any simple or martial weapon and uses the matching base weapon and its mastery.',
        'Attack bonus': '+3 to attack and damage rolls.',
        'Area': '10 ft Emanation centered on you, increasing to 30 ft at Paladin level 17.',
        'Special powers': 'You and Friendly creatures in the aura have Advantage on saves against spells and other magical effects.',
        'Attunement': 'Required by a Paladin',
    },
    'Dagger of Venom': {
        'name': 'Dagger of Venom', 'base': 'Dagger', 'evidence': 'dc 15 constitution saving throw',
        'damage': 'Add 1 to normal damage. A failed save against the coating adds 2d10 Poison damage.',
        'activation': 'Use a Bonus Action to coat the dagger. The first hit against a creature expends the coating.',
        'change': 'Coating the blade takes a Bonus Action in 2024, and it recharges at dawn.',
        'Attack bonus': '+1 to attack and damage rolls.',
        'Saving throw': 'DC 15 Constitution. On a failure the target also has the Poisoned condition for 1 minute.',
        'Duration': 'Coating lasts up to 1 minute. Recharge at the next dawn.',
    },
    'Vicious Weapon': {
        'prefix': 'Vicious ', 'evidence': 'extra 2d6 damage to any creature it hits',
        'damage': 'Add 2d6 of the weapon’s normal damage type on a hit against a creature.',
        'activation': 'On a weapon hit against a creature.',
        'change': 'The 2014 effect triggered on a natural 20. The 2024 effect triggers on every hit against a creature.',
    },
    'Giant Slayer': {
        'prefix': 'Giant Slayer (', 'evidence': 'dc 15 strength saving throw',
        'damage': 'Add 1 to normal damage. A Giant takes an additional 2d6 of the weapon’s damage type.',
        'activation': 'Make a weapon attack. The extra damage and save apply on a hit against a Giant.',
        'change': 'The 2024 variant uses the matching base weapon and its mastery.',
        'Attack bonus': '+1 to attack and damage rolls.',
        'Saving throw': 'Giant target only: DC 15 Strength or the target is Prone.',
    },
    'Flame Tongue': {
        'prefix': 'Flame Tongue ', 'melee_only': True, 'evidence': 'extra 2d6 fire damage on a hit',
        'damage': 'Add 2d6 Fire on a hit while the weapon is ablaze.',
        'activation': 'While holding it, use a Bonus Action and the command word to light or extinguish it.',
        'change': 'The 2024 variant uses the matching base weapon and its mastery.',
        'Area': '40 ft of Bright Light and another 40 ft of Dim Light while lit.',
        'Duration': 'Remains lit until dismissed, dropped, stowed, or sheathed.',
    },
    'Frost Brand': {
        'prefix': 'Frost Brand (', 'evidence': 'extra 1d6 cold damage',
        'damage': 'Add 1d6 Cold on a hit.',
        'activation': 'On a weapon hit. Drawing it can also extinguish nonmagical flames within 30 ft, once per hour.',
        'change': 'The 2024 variant uses the matching base weapon and its mastery.',
        'Special powers': 'Resistance to Fire damage while held.',
        'Area': 'In freezing temperatures, 10 ft of Bright Light and another 10 ft of Dim Light.',
    },
}


def is_ranged_weapon(mechanics):
    # Dart is ranged despite having Thrown instead of Ammunition.
    return mechanics['weapon']['name'] == 'Dart' or any(
        row['property']['name'] == 'Ammunition' for row in mechanics['properties']
    )


def details(item, family, rules, mechanics):
    weapon = mechanics['weapon']
    props = [row['property'] for row in mechanics['properties']]
    reach = '10 ft melee' if any(prop['name'] == 'Reach' for prop in props) else '5 ft melee'
    normal, long = weapon['range'], weapon['long_range']
    distance = f'{normal:g}/{long:g} ft' if normal else reach
    if normal and any(prop['name'] == 'Thrown' for prop in props):
        distance = f'{distance} thrown' if weapon['name'] == 'Dart' else f'{reach}; {distance} thrown'
    properties = []
    for row in mechanics['properties']:
        prop = row['property']
        if prop['type'] != 'Mastery':
            detail = row['assignment'].get('detail')
            properties.append(f"{prop['name']} ({detail})" if detail else prop['name'])
    fields = {
        'Base weapon': weapon['name'],
        'Damage': rules.get('Damage') or f"Base {weapon['damage_dice']} {weapon['damage_type'].title()}. {rules['damage']}",
        'Range': distance,
        'Properties': ', '.join(properties) or 'None',
        'Activation': rules['activation'],
        'Category': 'Simple' if weapon['is_simple'] else 'Martial',
        'Mastery': ', '.join(prop['name'] for prop in props if prop['type'] == 'Mastery'),
        'Attunement': 'Required' if item is None or item['requires_attunement'] else 'None',
    }
    fields.update((key, value) for key, value in rules.items() if key[0].isupper())
    return {'status': 'published-reference', 'label': 'Published 2024 · ' + family,
            'source': rules.get('source') or RULES + '#' + family.replace(' ', ''), 'fields': fields}


def main():
    database = (CATALOG / 'indexes/items.sqlite3').resolve()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        items = [json.loads(raw) for (raw,) in db.execute(
            "SELECT data_json FROM items WHERE type='weapon' AND source_id IN (?, ?) ORDER BY id",
            (LEGACY, CURRENT))]
    bases = {item['name']: item['mechanics'] for item in items
             if item['source_id'] == CURRENT and item['magic'] is False and item['mechanics'].get('weapon')}
    records, targets, generic_targets = {}, {}, {}
    for item in items:
        weapon = item['mechanics'].get('weapon')
        if item['source_id'] != CURRENT or item['magic'] is not True:
            continue
        for family, rules in FAMILIES.items():
            if 'published_bases' in rules:
                continue
            if rules.get('any_base') and not weapon and item['name'] == rules['name']:
                if rules['evidence'] in (item.get('description') or '').casefold():
                    generic_targets[family] = item
                continue
            base = weapon['name'] if weapon else rules.get('base')
            if not base or (rules.get('base') and base != rules['base']):
                continue
            prefix = rules.get('prefix', '')
            title = rules.get('name') or prefix + base + (')' if prefix.endswith('(') else '')
            if item['name'] != title or rules['evidence'] not in (item.get('description') or '').casefold():
                continue
            mechanics = item['mechanics'] if weapon else bases[base]
            if rules.get('melee_only') and is_ranged_weapon(mechanics):
                continue
            key = family, base
            if key in targets:
                raise ValueError(f'Ambiguous published weapon variant: {key}')
            targets[key] = item, mechanics
            records[item['id']] = [details(item, family, rules, mechanics)]
    legacy_count = 0
    for item in items:
        weapon = item['mechanics'].get('weapon')
        family = item['name'].partition(' (')[0]
        if item['source_id'] != LEGACY or item['magic'] is not True or family not in FAMILIES or not weapon:
            continue
        base = modern_plain_name(weapon['name'])
        target = targets.get((family, base))
        if not target and family in generic_targets and base in bases:
            target = generic_targets[family], bases[base]
        if not target and base in FAMILIES[family].get('published_bases', ()) and base in bases:
            # Official DMG rules can cover a legacy variant even when Open5e has no matching record.
            target = None, bases[base]
        if not target or not item.get('description'):
            continue
        target, mechanics = target
        entry = details(target, family, FAMILIES[family], mechanics)
        note = REVIEWED_BASE_NOTES.get(weapon['name'].replace('War Pick', 'War-Pick'), '')
        entry['fields']['Edition comparison'] = ' '.join(filter(None, (FAMILIES[family]['change'], note)))
        if target:
            entry['related_item'] = {'id': target['id'], 'label': 'Open published 2024 item'}
        records[item['id']] = [entry]
        legacy_count += 1
    (CATALOG / 'supplements/core-magic-weapon-families.json').write_text(
        json.dumps({'schema_version': 1, 'records': records}, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'{legacy_count} legacy counterparts and {len(targets)} published 2024 variants.')


if __name__ == '__main__':
    main()
