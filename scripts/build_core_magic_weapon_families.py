#!/usr/bin/env python3
"""Project published 2024 magic weapon rules and verify their legacy counterparts."""
import json
import sqlite3

from build_core_enhancement_cross_references import CATALOG, CURRENT, LEGACY, REVIEWED_BASE_NOTES, modern_plain_name

RULES = 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z'
FAMILIES = {
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
        'prefix': 'Flame Tongue ', 'evidence': 'extra 2d6 fire damage on a hit',
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


def details(item, family, rules):
    mechanics = item['mechanics']
    weapon = mechanics['weapon']
    props = [row['property'] for row in mechanics['properties']]
    reach = '10 ft melee' if any(prop['name'] == 'Reach' for prop in props) else '5 ft melee'
    normal, long = weapon['range'], weapon['long_range']
    distance = f'{normal:g}/{long:g} ft' if normal else reach
    if normal and any(prop['name'] == 'Thrown' for prop in props) and not any(prop['name'] == 'Ammunition' for prop in props):
        distance = f'{reach}; {distance} thrown'
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
    records, targets = {}, {}
    for item in items:
        weapon = item['mechanics'].get('weapon')
        if item['source_id'] != CURRENT or item['magic'] is not True or not weapon:
            continue
        base = weapon['name']
        for family, rules in FAMILIES.items():
            title = rules['prefix'] + base + (')' if rules['prefix'].endswith('(') else '')
            if item['name'] != title or rules['evidence'] not in (item.get('description') or '').casefold():
                continue
            key = family, base
            if key in targets:
                raise ValueError(f'Ambiguous published weapon variant: {key}')
            targets[key] = item
            records[item['id']] = [details(item, family, rules)]
    legacy_count = 0
    for item in items:
        weapon = item['mechanics'].get('weapon')
        family = item['name'].partition(' (')[0]
        if item['source_id'] != LEGACY or item['magic'] is not True or family not in FAMILIES or not weapon:
            continue
        target = targets.get((family, modern_plain_name(weapon['name'])))
        if not target or not item.get('description'):
            continue
        entry = details(target, family, FAMILIES[family])
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
