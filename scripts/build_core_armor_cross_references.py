#!/usr/bin/env python3
"""Link verified legacy SRD armor families to their playable 2024 counterparts."""
import collections
import json
import re
import sqlite3
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
LEGACY = 'open5e-srd-2014'
CURRENT = 'open5e-srd-2024'
MAGIC = 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z'
EQUIPMENT = 'https://www.dndbeyond.com/sources/dnd/br-2024/equipment#Armor'
FAMILIES = {
    'Adamantine Armor': (
        'any critical hit against you becomes a normal hit',
        'Critical hits against you become normal hits while worn.',
    ),
    'Armor of Resistance': (
        'resistance to one type of damage while you wear this armor',
        'While worn, resist the damage type chosen or rolled by the DM.',
    ),
    'Mithral Armor': (
        'stealth',
        'Removes the base armor’s Strength minimum and Stealth disadvantage. It can be worn under normal clothes in the 2024 rules.',
    ),
}
ARMOR_FIELDS = ('ac_base', 'ac_add_dexmod', 'ac_cap_dexmod',
                'grants_stealth_disadvantage', 'strength_score_required')


def key(name):
    name = re.sub(r'[^a-z0-9]+', ' ', name.casefold()).strip()
    return re.sub(r'\b(padded|leather|studded leather|hide|half plate|plate|splint) armor\b', r'\1', name)


def same_base(left, right):
    a = left['mechanics'].get('armor') or {}
    b = right['mechanics'].get('armor') or {}
    if a and b:
        return (key(a['name']) == key(b['name'])
                and all(a[field] == b[field] for field in ARMOR_FIELDS))
    return (not a and left['name'] == right['name'] == 'Shield' and b.get('ac_base') == 2
            and 'increases your Armor Class by 2' in left['description'])


def build(catalog):
    database = (catalog / 'indexes/items.sqlite3').resolve()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        items = [json.loads(raw) for (raw,) in db.execute(
            "SELECT data_json FROM items WHERE type IN ('armor', 'shield') AND source_id IN (?, ?) ORDER BY id",
            (LEGACY, CURRENT))]
    modern = collections.defaultdict(list)
    for item in items:
        if item['source_id'] == CURRENT:
            modern[key(item['name'])].append(item)
    records = {}
    for item in items:
        if item['source_id'] != LEGACY:
            continue
        family = item['name'].partition(' (')[0]
        matches = modern[key(item['name'])]
        if len(matches) != 1:
            continue
        target = matches[0]
        if (item['magic'] != target['magic'] or item['requires_attunement'] != target['requires_attunement']
                or not same_base(item, target)):
            continue
        effect = ''
        if item['magic']:
            if family not in FAMILIES or item['rarity'] != target['rarity']:
                continue
            phrase, effect = FAMILIES[family]
            if not all(phrase in (row['description'] or '').casefold() for row in (item, target)):
                continue
        records[item['id']] = {
            'target_id': target['id'], 'source': MAGIC if effect else EQUIPMENT,
            'effect': effect, 'mithral': family == 'Mithral Armor',
        }
    return {'schema_version': 1, 'records': records}


if __name__ == '__main__':
    output = build(CATALOG)
    (CATALOG / 'supplements/core-armor-cross-references.json').write_text(
        json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"Verified {len(output['records'])} legacy armor records against published 2024 counterparts.")
