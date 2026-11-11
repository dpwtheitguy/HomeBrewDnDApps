#!/usr/bin/env python3
"""Match legacy game weapon facts to catalog records without copying descriptions."""
import collections
import json
import re
import sqlite3

from build_weapon_profiles import CATALOG, words
from fetch_next_indexes import fetch, public_items

BG1 = 'https://baldursgateee.th.gl/db/inventory'
CONAN = 'https://conanexiles.th.gl/db/inventory'
FORGE = 'https://forgeofexiles.app/weapons'
BG_FAMILY = {
    'Axe': 'battleaxe', 'Dagger': 'dagger', 'Long Sword': 'longsword',
    'Quarterstaff': 'quarterstaff', 'Short Sword': 'shortsword',
    'Two-Handed Sword': 'greatsword', 'Longbow': 'longbow', 'War Hammer': 'warhammer',
    'Dart': 'dart', 'Club': 'club', 'Mace': 'mace', 'Spear': 'spear',
    'Bastard Sword': 'longsword', 'Shortbow': 'shortbow', 'Halberd': 'halberd',
    'Sling': 'sling', 'Katana': 'longsword',
}
BG_AMBIGUOUS = {'Crossbow', 'Scimitar / Wakizashi / Ninjatō', 'Flail / Morning Star', 'Large Sword'}
DAMAGE_TYPES = {'Slashing', 'Missile', 'Crushing', 'Piercing', 'Piercing/Slashing'}
CONAN_FAMILY = {
    'Axe': 'battleaxe', 'Dagger': 'dagger', 'Mace': 'mace', 'Mace2H': 'maul',
    'Spear': 'spear', 'Spear2H': 'pike', 'Bow': 'longbow',
}


def bg_facts(row):
    parts = row.get('text', '').split(' · ')
    category = next((part for part in parts if part in BG_FAMILY or part in BG_AMBIGUOUS), '')
    damage = next((part for part in parts if re.fullmatch(r'\d+d\d+(?:[+-]\d+)?', part)), '')
    damage_type = next((part for part in parts if part in DAMAGE_TYPES), '')
    fields = {label: value for label, value in [
        ('Damage', damage), ('Damage type', damage_type), ('Weapon group', category)
    ] if value}
    if damage and re.fullmatch(r'[+-]\d+', parts[0]):
        fields['Enchantment'] = parts[0]
    base = BG_FAMILY.get(category)
    if category == 'Axe' and (damage_type == 'Missile' or 'throwing axe' in words(row['name'])):
        base = 'handaxe'
    return fields, base, None


def forge_rows(tree):
    rows = collections.defaultdict(list)
    for node in tree.xpath('//div[contains(@class,"cursor-pointer grid gap-3") and contains(@style,"grid-template-columns:")]'):
        cells = node.xpath('./div|./span')
        if len(cells) != 7:
            continue
        name, category, light, heavy, penetration, weight, _ = [
            ' '.join(cell.text_content().split()) for cell in cells
        ]
        if not all(re.fullmatch(r'\d+(?:\.\d+)?', value) for value in (light, heavy, weight)):
            continue
        if not re.fullmatch(r'\d+(?:\.\d+)?%', penetration):
            continue
        effects = [' '.join(span.text_content().split()) for span in cells[-1].xpath('.//span')]
        fields = {'Weapon group': category, 'Light attack damage': light,
                  'Heavy attack damage': heavy, 'Armor penetration': penetration, 'Weight': weight}
        if any(effects):
            fields['Effects'] = ', '.join(dict.fromkeys(filter(None, effects)))
        rows[words(name)].append(fields)
    if not rows:
        raise ValueError('Forge weapon table format changed')
    return rows


def conan_facts(row, forge, names):
    parts = row.get('text', '').split(' · ')
    handling = next((part for part in parts if part in
                     {'One Handed', 'Two Handed', 'Two Handed Ranged', 'Shield', 'Ammunition'}), '')
    penetration = next((part for part in parts if re.fullmatch(r'\d+(?:\.\d+)?%', part)), '')
    key = words(row['name'])
    matches = forge.get(key, [])
    fields = {}
    if len(matches) == 1 and names[key] == 1:
        candidate = matches[0]
        if not penetration or float(penetration[:-1]) == float(candidate['Armor penetration'][:-1]):
            fields = candidate.copy()
    category = fields.get('Weapon group')
    base = CONAN_FAMILY.get(category)
    if category == 'Axe' and handling == 'Two Handed':
        base = 'greataxe'
    if category == 'Sword':
        base = {'One Handed': 'longsword', 'Two Handed': 'greatsword'}.get(handling)
    if handling:
        fields['Handling'] = handling
    if penetration:
        fields['Armor penetration'] = penetration
    kind = {'Shield': 'reference-shield', 'Ammunition': 'launcher'}.get(handling)
    return fields, base, kind


def main():
    source_urls = {'baldurs-gate-1-reference': BG1, 'conan-exiles-reference': CONAN}
    upstream = {url: {row['id']: row for row in public_items(fetch(url))}
                for url in source_urls.values()}
    names = collections.Counter(words(row['name']) for row in upstream[CONAN].values()
                                if row['groupId'] == 'inventory_group_weapon')
    forge = forge_rows(fetch(FORGE))
    with sqlite3.connect(CATALOG / 'indexes/items.sqlite3') as db:
        items = [json.loads(raw) for (raw,) in db.execute(
            "SELECT data_json FROM items WHERE type='weapon' ORDER BY id")]
    records = {}
    for item in items:
        url = source_urls.get(item['source_id'])
        if not url:
            continue
        ids = item['mechanics']['reference_metadata']['upstream_ids']
        variants = []
        for upstream_id in ids:
            row = upstream[url].get(upstream_id)
            if not row or words(row['name']) != words(item['name']):
                continue
            fields, base, kind = (bg_facts(row) if url == BG1 else conan_facts(row, forge, names))
            if not fields:
                continue
            variant = {'fields': fields, 'source': f'{url}/{upstream_id}'}
            if 'Light attack damage' in fields:
                variant['additional_source'] = FORGE
            if base:
                variant['base'] = base
            if kind:
                variant['kind'] = kind
            variants.append(variant)
        if variants:
            records[item['id']] = {
                'game': 'Baldur’s Gate: Enhanced Edition' if url == BG1 else 'Conan Exiles',
                'variants': variants,
            }
    output = {'schema_version': 1, 'records': records}
    (CATALOG / 'supplements/legacy-game-weapon-facts.json').write_text(
        json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(collections.Counter(record['game'] for record in records.values()))
    print('Conan attack damage records:', sum(any('Light attack damage' in v['fields']
          for v in record['variants']) for record in records.values()))


if __name__ == '__main__':
    main()
