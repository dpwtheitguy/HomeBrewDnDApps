#!/usr/bin/env python3
"""Publish explicit 2024 reference profiles for weapons with unresolved rules."""
import collections
import json
import re
import sqlite3
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
RULES = 'https://www.dndbeyond.com/sources/dnd/br-2024/equipment#Weapons'
IMPROVISED = 'https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary#ImprovisedWeapons'
CURATED = {
    'gaz1-karameikos-local:27cdce0f822ed6d3': {
        'base': 'scimitar',
        'bonus': 0,
        'basis': 'GAZ1, printed p. 49, identifies a bejewelled scimitar and lists no enhancement.',
        'source': 'https://www.dmsguild.com/product/16974/GAZ1-The-Grand-Duchy-of-Karameikos-Basic',
        'notes': [
            'The jewels are decorative in this profile. The original entry supplies no item-specific power.',
            'GAZ1 gives Abdallah’s sword attack as 1d8 + 3 in his NPC combat profile. That modifier belongs to the NPC stat block.',
            'Gary Davies’s separate fan conversion gives it a +2 enhancement. That is a different version.'
        ],
        'related_source': 'https://www.pandius.com/ibnhamid.html',
    }
}
ALIASES = {
    'bastard sword': 'longsword', 'two handed sword': 'greatsword', 'short sword': 'shortsword',
    'long sword': 'longsword', 'great sword': 'greatsword', 'broad sword': 'longsword',
    'battle axe': 'battleaxe', 'great axe': 'greataxe', 'hand axe': 'handaxe', 'war axe': 'battleaxe',
    'war hammer': 'warhammer', 'great hammer': 'maul', 'morning star': 'morningstar', 'short swords': 'shortsword', 'sai': 'dagger',
    'long bow': 'longbow', 'short bow': 'shortbow', 'war bow': 'longbow',
    'throwing knife': 'dagger', 'throwing axe': 'handaxe', 'throwing spear': 'javelin',
    'quarter staff': 'quarterstaff', 'staff': 'quarterstaff', 'war staff': 'quarterstaff',
    'knife': 'dagger', 'dirk': 'dagger', 'tanto': 'dagger', 'wakizashi': 'shortsword',
    'katana': 'longsword', 'naginata': 'glaive', 'shuriken': 'dart', 'kunai': 'dagger',
    'sabre': 'scimitar', 'saber': 'scimitar', 'shamshir': 'scimitar',
    'falchion': 'scimitar', 'cutlass': 'scimitar', 'sword': 'longsword',
    'axe': 'battleaxe', 'hammer': 'warhammer', 'bow': 'shortbow', 'crossbow': 'light crossbow',
}
ICON_FAMILIES = {
    'dagger': 'dagger', 'sword': 'longsword', 'axe': 'battleaxe', 'hammer': 'warhammer',
    'flail': 'flail', 'spear': 'spear', 'bow': 'shortbow', 'crossbow': 'light crossbow',
    'staff': 'quarterstaff',
}
NON_WEAPON = re.compile(r'\b(?:weapon schematic|recipe|blueprint|weapon rack|scabbard|sheath|weapon stand)\b')
AMMO = re.compile(r'^(?:ammunition|arrows?\b|bolts?\b|crossbow bolts?\b|bullets?\b|sling bullets?\b)')


def words(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


def build():
    with sqlite3.connect(CATALOG / 'indexes/items.sqlite3') as db:
        items = [json.loads(raw) for (raw,) in db.execute("SELECT data_json FROM items WHERE type='weapon' ORDER BY id")]
    bases = {words(item['name']): item['id'] for item in items
             if item['source_id'] == 'open5e-srd-2024' and item['mechanics'].get('weapon')
             and item['name'] == item['mechanics']['weapon']['name'] and item['magic'] is False}
    aliases = {**{label: label for label in bases}, **ALIASES}
    patterns = [(re.compile(r'\b' + re.escape(label) + r'\b'), base)
                for label, base in sorted(aliases.items(), key=lambda pair: -len(pair[0]))
                if base in bases]
    native_path = CATALOG / 'supplements/legacy-game-weapon-facts.json'
    native = json.loads(native_path.read_text())['records'] if native_path.exists() else {}
    details = json.loads((CATALOG / 'supplements/curated-item-details.json').read_text())['records']
    known_base_ids = set(bases.values())
    profiles = {}
    for item in items:
        item_id = item['id']
        mechanics = item['mechanics']
        name = words(item['name'])
        source_type = str(mechanics.get('source_type') or '').lower()
        explicit_kind = next((entry['profile_kind'] for entry in details.get(item_id, [])
                              if entry.get('profile_kind') in {'siege-engine', 'custom-2024-draft'}), None)
        if explicit_kind:
            profiles[item_id] = {'kind': explicit_kind}
            continue
        if item['ruleset'] == 'bg3':
            profiles[item_id] = {'kind': 'native-bg3'}
            continue
        if item['ruleset'] == 'dnd-2024' and (mechanics.get('weapon') or item.get('description')):
            profiles[item_id] = {'kind': 'native-2024' if mechanics.get('weapon') else 'source-2024-text'}
            continue
        if NON_WEAPON.search(name):
            profiles[item_id] = {'kind': 'reference-object', 'basis': 'This entry describes an accessory, recipe, or fixture. Any weapon it describes uses its own rules.'}
            continue
        if source_type in ('ammo', 'ammunition') or AMMO.search(name):
            profiles[item_id] = {'kind': 'launcher', 'basis': 'Use a compatible launcher’s damage, attack modifier, and range. Apply only the ammunition effects verified in its source.'}
            continue
        curated = CURATED.get(item_id)
        base_id = item.get('base_item_id')
        if curated:
            profiles[item_id] = {**curated, 'kind': 'source-based-2024', 'base_id': bases[curated['base']]}
            continue
        if base_id in known_base_ids:
            profiles[item_id] = {'kind': 'draft-2024-base', 'base_id': base_id, 'basis': 'Documented base item.'}
            continue
        reference = mechanics.get('reference_metadata') or {}
        variants = native.get(item_id, {}).get('variants', [])
        kinds = {variant.get('kind') for variant in variants}
        if kinds == {'reference-shield'}:
            profiles[item_id] = {'kind': 'reference-object', 'basis': 'The source game classifies this item as a shield. The 2024 Shield reference grants +2 AC while wielded. Shield training governs other penalties.'}
            continue
        if kinds == {'launcher'}:
            profiles[item_id] = {'kind': 'launcher', 'basis': 'The source game classifies this as ammunition. Use the compatible launcher’s 2024 attack and range.'}
            continue
        if item['name'].endswith('(weapon property)') or (
            item['source_id'] in {'adventurers-vault-1-reference', 'adventurers-vault-2-reference'}
            and re.search(r'\bweapons?$', name)
        ):
            profiles[item_id] = {'kind': 'weapon-upgrade', 'basis': 'Use an eligible base weapon for attack, damage, and range. The upgrade’s item-specific 2024 rules still require review.'}
            continue
        native_bases = {variant.get('base') for variant in variants}
        if len(native_bases) == 1 and (native_base := next(iter(native_bases))) in bases:
            profiles[item_id] = {'kind': 'draft-2024-base', 'base_id': bases[native_base],
                                 'basis': '2024 comparison based on the verified source-game weapon group. Source-game powers and damage are listed separately when available.'}
            continue
        category = str(reference.get('weapon_type') or reference.get('source_type') or source_type)
        search = name + ' ' + words(category)
        base = next((base for pattern, base in patterns if pattern.search(search)), None)
        basis = '2024 weapon family matched to the catalog name or source type.'
        note = words(str(reference.get('source_note') or '')).split()
        if not base and note and item['source_id'] in {
            'savage-coast-local', 'wrath-of-the-immortals-local', 'mystara-fan-names-reference',
            'gazetteer-equipment-reference', 'atruaghin-local',
        }:
            phrase = ' '.join(note[:8])
            matches = [(match.start(), match.end(), family) for pattern, family in patterns
                       if (match := pattern.search(phrase))]
            candidate_families = {family for start, end, family in matches
                                  if not any(left <= start and end <= right and (left, right) != (start, end)
                                             for left, right, _ in matches)}
            if len(candidate_families) == 1:
                base = candidate_families.pop()
                basis = '2024 comparison based on the weapon description in the original source note.'
        if not base:
            icon_type = Path(item['image']['path']).stem
            base = ICON_FAMILIES.get(icon_type)
            basis = 'Provisional family suggested by the catalog category.'
        if base and base in bases:
            profiles[item_id] = {'kind': 'draft-2024-base', 'base_id': bases[base], 'basis': basis}
        else:
            profiles[item_id] = {'kind': 'improvised-2024', 'basis': 'The source has insufficient evidence for a weapon family. Use the 2024 improvised profile only as a temporary DM ruling.'}
    counts = collections.Counter(profile['kind'] for profile in profiles.values())
    return {'schema_version': 1, 'rules': RULES, 'improvised_rules': IMPROVISED,
            'records': profiles, 'counts': dict(counts)}


if __name__ == '__main__':
    data = build()
    (CATALOG / 'supplements/weapon-profiles-2024.json').write_text(
        json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Classified {len(data["records"]):,} weapon records. {data["counts"]}')
