#!/usr/bin/env python3
"""Verify plain 2014 +N weapons against their 2024 SRD counterparts."""
import argparse
import collections
import json
import re
import sqlite3
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
LEGACY = 'open5e-srd-2014'
CURRENT = 'open5e-srd-2024'
NAME = re.compile(r'(.+) \(\+([123])\)')
RARITY = {'1': 'uncommon', '2': 'rare', '3': 'very rare'}
LEGACY_RULE = (
    "You have a bonus to attack and damage rolls made with this magic weapon. "
    "The bonus is determined by the weapon's rarity."
)
CURRENT_RULE = LEGACY_RULE.replace('attack and damage rolls', 'attack rolls and damage rolls')
# Open5e spells these variant names differently across the two SRD snapshots.
BASE_ALIASES = {
    'Crossbow-Hand': ('Crossbow, Hand', 'Hand Crossbow'),
    'Crossbow-Heavy': ('Crossbow, Heavy', 'Heavy Crossbow'),
    'Crossbow-Light': ('Crossbow, Light', 'Light Crossbow'),
    'Light-Hammer': ('Light Hammer', 'Light Hammer'),
    'War-Pick': ('War Pick', 'War Pick'),
}
COMPARABLE_FIELDS = ('damage_dice', 'damage_type', 'range', 'long_range', 'is_simple')


def modern_variant_name(legacy_name):
    match = NAME.fullmatch(legacy_name)
    if not match:
        return legacy_name
    legacy_variant, bonus = match.groups()
    _, modern_base = BASE_ALIASES.get(legacy_variant, (legacy_variant, legacy_variant))
    return f'{modern_base} (+{bonus})'


def weapon_fields(weapon):
    return tuple(weapon.get(key) for key in COMPARABLE_FIELDS)


def properties(item):
    result = []
    for entry in item['mechanics'].get('properties') or []:
        prop = entry['property']
        if prop['type'] == 'Mastery':
            continue
        name = prop['name'].casefold()
        detail = (entry['assignment'].get('detail') or '').casefold()
        if name == 'ammunition':
            # Modern metadata appends the projectile type after the unchanged range.
            detail = detail.partition(';')[0].strip()
        result.append((name, detail))
    return sorted(result)


def mundane_base(item, indexed):
    mechanics = item['mechanics']
    source_fields = mechanics.get('source_fields') or {}
    base_key = source_fields.get('weapon')
    base = indexed.get((item['source_id'], base_key))
    if base is None or base['magic'] is not False:
        return None
    weapon = mechanics.get('weapon')
    if not weapon or weapon != base['mechanics'].get('weapon') or properties(item) != properties(base):
        return None
    return base


def build(catalog):
    index = (catalog / 'indexes/items.sqlite3').resolve()
    with sqlite3.connect(index.as_uri() + '?mode=ro', uri=True) as db:
        items = [json.loads(raw) for (raw,) in db.execute(
            "SELECT data_json FROM items WHERE type='weapon' AND source_id IN (?, ?) ORDER BY id",
            (LEGACY, CURRENT),
        )]
    by_source_key = {(item['source_id'], item['provenance']['upstream_pk']): item for item in items}
    modern_names = collections.defaultdict(list)
    for item in items:
        if item['source_id'] == CURRENT:
            modern_names[item['name'].casefold()].append(item)
    records = {}
    outcomes = collections.Counter()
    for legacy in items:
        match = NAME.fullmatch(legacy['name'])
        if legacy['source_id'] != LEGACY or not match:
            continue
        legacy_variant, bonus = match.groups()
        expected_bases = BASE_ALIASES.get(legacy_variant, (legacy_variant, legacy_variant))
        candidates = modern_names[modern_variant_name(legacy['name']).casefold()]
        if len(candidates) != 1:
            outcomes['no_unique_variant_match'] += 1
            continue
        modern = candidates[0]
        pair = (legacy, modern)
        if (legacy['description'] != LEGACY_RULE or modern['description'] != CURRENT_RULE
                or any(item['magic'] is not True or item['requires_attunement'] is not False
                       or (item.get('rarity') or '').replace('-', ' ').casefold() != RARITY[bonus] for item in pair)):
            outcomes['enhancement_rule_mismatch'] += 1
            continue
        legacy_base, modern_base = (mundane_base(item, by_source_key) for item in pair)
        if not legacy_base or not modern_base or any(
            base['name'].casefold() != expected.casefold()
            or base['mechanics']['weapon']['name'].casefold() != expected.casefold()
            for base, expected in zip((legacy_base, modern_base), expected_bases)
        ):
            outcomes['unverified_base'] += 1
            continue
        if (weapon_fields(legacy_base['mechanics']['weapon']) != weapon_fields(modern_base['mechanics']['weapon'])
                or properties(legacy_base) != properties(modern_base)):
            outcomes['changed_base_rules'] += 1
            continue
        records[legacy['id']] = {
            'target_id': modern['id'],
            'base_id': modern_base['id'],
            'bonus': int(bonus),
        }
        outcomes['verified_alias' if legacy_variant in BASE_ALIASES else 'verified_exact'] += 1
    return {'schema_version': 1, 'source': 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z#Weapon12or3',
            'method': 'Unique variant and base name or explicit naming alias, identical enhancement and rarity, unchanged base damage, range, category, and comparable non-Mastery properties.',
            'counts': dict(outcomes), 'records': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-dir', type=Path, default=CATALOG)
    args = parser.parse_args()
    result = build(args.catalog_dir)
    output = args.catalog_dir / 'supplements/core-enhancement-cross-references.json'
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(', '.join(f'{name.replace("_", " ")}: {count}' for name, count in result['counts'].items()))


if __name__ == '__main__':
    main()
