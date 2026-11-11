#!/usr/bin/env python3
"""Project published 2024 magic weapon rules and verify their legacy counterparts."""
import json
import sqlite3

from build_core_enhancement_cross_references import CATALOG, CURRENT, LEGACY, REVIEWED_BASE_NOTES, modern_plain_name

RULES = 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z'
FAMILIES = {
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
        'Damage': f"Base {weapon['damage_dice']} {weapon['damage_type'].title()}. {rules['damage']}",
        'Range': distance,
        'Properties': ', '.join(properties) or 'None',
        'Activation': rules['activation'],
        'Category': 'Simple' if weapon['is_simple'] else 'Martial',
        'Mastery': ', '.join(prop['name'] for prop in props if prop['type'] == 'Mastery'),
        'Attunement': 'Required' if item['requires_attunement'] else 'None',
    }
    fields.update((key, value) for key, value in rules.items() if key[0].isupper())
    return {'status': 'published-reference', 'label': 'Published 2024 · ' + family,
            'source': RULES + '#' + family.replace(' ', ''), 'fields': fields}


def main():
    database = (CATALOG / 'indexes/items.sqlite3').resolve()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        items = [json.loads(raw) for (raw,) in db.execute(
            "SELECT data_json FROM items WHERE type='weapon' AND source_id IN (?, ?) ORDER BY id",
            (LEGACY, CURRENT))]
    bases = {item['name']: item['mechanics'] for item in items
             if item['source_id'] == CURRENT and item['magic'] is False and item['mechanics'].get('weapon')}
    records, targets = {}, {}
    for item in items:
        weapon = item['mechanics'].get('weapon')
        if item['source_id'] != CURRENT or item['magic'] is not True:
            continue
        for family, rules in FAMILIES.items():
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
        target = targets.get((family, modern_plain_name(weapon['name'])))
        if not target or not item.get('description'):
            continue
        target, mechanics = target
        entry = details(target, family, FAMILIES[family], mechanics)
        note = REVIEWED_BASE_NOTES.get(weapon['name'].replace('War Pick', 'War-Pick'), '')
        entry['fields']['Edition comparison'] = ' '.join(filter(None, (FAMILIES[family]['change'], note)))
        entry['related_item'] = {'id': target['id'], 'label': 'Open published 2024 item'}
        records[item['id']] = [entry]
        legacy_count += 1
    (CATALOG / 'supplements/core-magic-weapon-families.json').write_text(
        json.dumps({'schema_version': 1, 'records': records}, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'{legacy_count} legacy counterparts and {len(targets)} published 2024 variants.')


if __name__ == '__main__':
    main()
