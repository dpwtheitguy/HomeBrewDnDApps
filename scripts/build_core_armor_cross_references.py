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
REVIEWED_VARIANTS = {
    'Animated Shield': 'The 2024 activation uses a Bonus Action without a command word.',
    'Armor of Invulnerability': 'The 2024 resistance and temporary immunity cover Bludgeoning, Piercing, and Slashing damage.',
    'Arrow-Catching Shield': 'The 2024 bonus and interception apply to ranged attack rolls.',
    'Dragon Scale Mail': 'The 2024 saving throw advantage applies to dragon breath weapons. Locating a dragon uses a Magic action.',
    'Glamoured Studded Leather': 'The 2024 appearance change uses a Bonus Action without a command word.',
    'Shield of Missile Attraction': 'The 2024 curse redirects attacks made with Ranged weapons.',
    'Spellguard Shield': 'The 2024 protection applies to saves against spells and other magical effects, and to incoming spell attack rolls.',
}
REVIEWED_STRUCTURED = {
    'Dwarven Plate': (2, 'Use a Reaction to reduce forced movement along the ground by up to 10 ft.', ''),
    'Elven Chain Mail': (1, 'The wearer is treated as trained with this armor.', 'Wearer counts as trained'),
    'Elven Chain Shirt': (1, 'The wearer is treated as trained with this armor.', 'Wearer counts as trained'),
    'Plate Armor of Etherealness': (0, 'Once per dawn, use a Magic action and the command word for Etherealness. Removing the armor or repeating the command word as a Magic action ends the effect.', ''),
}
CURSED_FAMILIES = (
    ('Armor of Vulnerability (', 'while cursed, you have vulnerability', 0,
     'While worn, resist one DM-selected type among Bludgeoning, Piercing, and Slashing. Attunement curses you with vulnerability to the other two. Identify or attunement reveals the curse. Remove Curse or similar magic ends it; doffing alone leaves it in effect.'),
    ('Demon ', 'clawed gauntlets', 1,
     'While worn, you know Abyssal. Your Unarmed Strikes can deal 1d8 Slashing in place of their normal damage and gain +1 to attack and damage. After donning, Remove Curse or similar magic is needed to doff the armor. While wearing it, you have Disadvantage on attacks against demons and saves against their spells and special abilities.'),
)
STRUCTURED_LEGACY = {
    'Armor of Vulnerability': ('Armor of Vulnerability (Plate Armor)', 'Plate Armor matches this legacy entry. The 2024 item is also available on other Light, Medium, or Heavy bases.'),
    'Demon Armor': ('Demon Plate Armor', 'Plate Armor matches this legacy entry. The 2024 gauntlets modify Unarmed Strikes.'),
    'Dwarven Plate': ('Dwarven Plate', ''),
    'Elven Chain': ('Elven Chain Shirt', 'The Chain Shirt is the matching base for this 2014 entry. The 2024 rules also publish a separate Chain Mail variant.'),
    'Plate Armor of Etherealness': ('Plate Armor of Etherealness', 'The 2024 entry uses the Etherealness spell duration and activates with a Magic action.'),
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
    published = json.loads((catalog / 'supplements/published-2024-armor-facts.json').read_text())
    armor_facts = published['records']
    current_families = {}
    for item in items:
        family = item['name'].partition(' (')[0]
        if item['source_id'] == CURRENT and item['name'] in REVIEWED_STRUCTURED and item['mechanics'].get('armor'):
            bonus, effect, training = REVIEWED_STRUCTURED[item['name']]
            current_families[item['id']] = {'source': MAGIC, 'bonus': bonus, 'effect': effect,
                                            'training': training, 'mithral': False}
        if item['source_id'] == CURRENT and item['mechanics'].get('armor') and item['requires_attunement'] is True:
            for prefix, phrase, bonus, effect in CURSED_FAMILIES:
                if item['name'].startswith(prefix) and phrase in (item.get('description') or '').casefold():
                    current_families[item['id']] = {'source': MAGIC, 'bonus': bonus,
                                                    'effect': effect, 'mithral': False}
        if item['source_id'] == CURRENT and family in FAMILIES and item['mechanics'].get('armor'):
            phrase, effect = FAMILIES[family]
            if phrase in (item.get('description') or '').casefold():
                current_families[item['id']] = {'source': MAGIC, 'effect': effect, 'mithral': family == 'Mithral Armor'}
    records = {}
    for item in items:
        if item['source_id'] != LEGACY:
            continue
        family = item['name'].partition(' (')[0]
        structured = STRUCTURED_LEGACY.get(item['name'])
        matches = modern[key(structured[0] if structured else item['name'])]
        if len(matches) != 1:
            continue
        target = matches[0]
        if (item['name'] in REVIEWED_VARIANTS and item['name'] == target['name']
                and target['id'] in armor_facts and item['description'] and target['description']):
            records[item['id']] = {
                'target_id': target['id'], 'source': published['source'],
                'change': REVIEWED_VARIANTS[item['name']], 'mithral': False,
                'effect': armor_facts[target['id']]['effects'], 'bonus': armor_facts[target['id']]['bonus'],
            }
            continue
        if (item['magic'] != target['magic'] or item['requires_attunement'] != target['requires_attunement']
                or not same_base(item, target)):
            continue
        if structured and target['id'] in current_families:
            records[item['id']] = {
                'target_id': target['id'], **current_families[target['id']], 'change': structured[1],
            }
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
    return {'schema_version': 1, 'records': records, 'modern': current_families}


if __name__ == '__main__':
    output = build(CATALOG)
    (CATALOG / 'supplements/core-armor-cross-references.json').write_text(
        json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"Verified {len(output['records'])} legacy armor records against published 2024 counterparts.")
