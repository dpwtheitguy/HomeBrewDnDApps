#!/usr/bin/env python3
"""Audit field coverage on every SQLite item without treating leads as rules."""
import collections
import csv
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'catalog'
FIELDS = ('damage', 'bonuses', 'encounters', 'crafting', 'special_powers', 'history',
          'range', 'radius', 'casting_time', 'activation', 'duration', 'saving_throw',
          'attunement', 'weight', 'base_price', 'provenance')
PROSE_PATTERNS = {
    'damage': r'\b(?:\d+d\d+|extra|additional|deal[s]?)\b[^.\n]{0,65}\bdamage\b',
    'bonuses': r'\+\d+\s+(?:bonus|to)\b',
    'range': r'\b(?:range|within|up to)\b[^.\n]{0,25}\b\d+[- ]?(?:feet|foot|ft)\b',
    'radius': r'\bradius\b|\b\d+[- ]foot (?:sphere|cone|cube|emanation|line)\b',
    'saving_throw': r'\bsaving throw\b',
    'activation': r'\b(?:bonus|magic|attack|utilize) action\b|\bas an action\b',
    'casting_time': r'\bcasting time\b',
    'duration': r'\b(?:for|lasts?) (?:up to )?\d+ (?:turns?|rounds?|minutes?|hours?|days?)\b',
    'crafting': r'\b(?:crafting recipe|craft(?:ed)? (?:using|with)|made by combining)\b',
}


def supplement(filename):
    return json.loads((ROOT / 'supplements' / filename).read_text())


def audit(item, bg3_items, bg3_weapons, curated, spells, native_games, prices, bg3_reviewed):
    status = dict.fromkeys(FIELDS, 'unknown')

    def put(field, state='source-field'):
        if status[field] == 'unknown' or status[field] == 'source-text-lead':
            status[field] = state

    mechanics = item.get('mechanics') or {}
    weapon = mechanics.get('weapon') or {}
    raw = mechanics.get('source_fields') or {}
    meta = mechanics.get('reference_metadata') or {}
    proof = item.get('provenance') or {}
    description = item.get('description') or ''
    note = meta.get('source_note') or ''
    for field, pattern in PROSE_PATTERNS.items():
        if re.search(pattern, description + '\n' + str(note), re.I):
            put(field, 'source-text-lead')
    if weapon.get('damage_dice'):
        put('damage')
    if re.match(r'^[1-9]\d*', str(weapon.get('range') or '')):
        put('range')
    if item.get('requires_attunement') is not None:
        put('attunement')
    if re.search(r'[1-9]', str(raw.get('weight') or '')):
        put('weight')
    if (item.get('valuation') or {}).get('base_values'):
        put('base_price')
    elif item['id'] in prices:
        price = prices[item['id']]
        state = 'priced' if price['method'] in {
            'source', 'source-metadata', 'source-retail', 'source-sale', 'source-reconciled'
        } else 'draft'
        put('base_price', state)
    if proof.get('source_url') or (item.get('research_metadata') or {}).get('source_refs'):
        put('provenance')
    locators = [meta.get('locator') or {}, *(entry.get('locator') or {}
                for entry in meta.get('attested_appearances', []) if isinstance(entry, dict))]
    if any(isinstance(locator, dict) and any(locator.get(key) for key in ('area', 'room', 'encounter', 'location'))
           for locator in locators) or any(association.get('role') == 'found-in' and
           association.get('entity_id', '').startswith(('region:', 'location:'))
           for association in item.get('associations', [])):
        put('encounters', 'location-lead')
    if meta.get('history') or meta.get('lore'):
        put('history')
    if mechanics.get('original_adaptation_rules') or mechanics.get('original_variant_rules'):
        put('special_powers', 'draft')
    elif item.get('magic') is True and description:
        put('special_powers', 'source-text-lead')

    bg3_item = bg3_items.get(item['id'], {})
    for variant in bg3_item.get('variants', []):
        facts = {**variant['facts'], **bg3_reviewed.get(item['id'], {})}
        stats = variant['stats']
        if damage := facts.get('Damage'):
            put('damage', 'not-applicable' if damage[0].startswith('None.') else 'source-field')
        if stats.get('enchantment') or stats.get('armour class bonus'):
            put('bonuses')
        if facts.get('Crafting'):
            put('crafting')
        if facts.get('Range'):
            put('range')
        if stats.get('area range m') or stats.get('area range ft') or facts.get('Area'):
            put('radius')
        if facts.get('Duration') or stats.get('area duration') or any(key.endswith(' duration') for key in variant['conditions']):
            put('duration')
        if stats.get('usage cost') or facts.get('Activation'):
            put('activation')
        if facts.get('Saving throw'):
            put('saving_throw')
        if variant['effects'] or variant['conditions']:
            put('special_powers')
        elif variant['has_rule_text']:
            put('special_powers', 'source-text-lead')
        if variant['locations'] or variant['acquisition_refs']:
            put('encounters', 'location-lead')
        if variant['recipe_refs']:
            put('crafting', 'source-text-lead')
        if stats.get('weight kg'):
            put('weight')
    bg3_weapon = bg3_weapons.get(item['id'], {})
    for variant in bg3_weapon.get('variants', []):
        stats = variant['stats']
        if stats.get('damage'):
            put('damage')
        if stats.get('enchantment'):
            put('bonuses')
        if stats.get('range') or stats.get('range m') or stats.get('melee or ranged') == 'melee':
            put('range')
        if variant['features'] or variant['special_stats']:
            put('special_powers')
        if stats.get('weight kg'):
            put('weight')

    for variant in native_games.get(item['id'], {}).get('variants', []):
        fields = variant['fields']
        for labels, key in (
            (('Damage', 'Light attack damage', 'One-handed damage', 'Two-handed damage', 'Throw damage'), 'damage'), (('Enchantment',), 'bonuses'),
            (('Effects',), 'special_powers'), (('Weight',), 'weight'),
        ):
            if any(fields.get(label) for label in labels):
                put(key)

    named_spell = (meta.get('inscribed_spell') or {}).get('name')
    scroll_name = re.fullmatch(r'Spell Scroll\s*\(([^)]+)\)', item['name'], re.I)
    if not named_spell and scroll_name and item['ruleset'] == 'dnd-2024' and item['type'] == 'scroll':
        named_spell = scroll_name[1]
    if named_spell and (spell := spells.get(named_spell.casefold())):
        for field, key in (('casting_time', 'casting_time'), ('range', 'range_text'), ('radius', 'shape_size'),
                           ('damage', 'damage_roll'), ('duration', 'duration'), ('saving_throw', 'saving_throw_ability')):
            if spell.get(key):
                put(field, '2024-spell-reference')
        put('crafting', '2024-guideline')
    if item['source_id'] == 'open5e-srd-2024':
        if item.get('magic') is False and status['base_price'] == 'source-field':
            put('crafting', '2024-guideline')
        if item.get('magic') is False and weapon:
            put('casting_time', 'not-applicable')
    for entry in curated.get(item['id'], []):
        for label in entry['fields']:
            key = {
                'Damage': 'damage', 'Attack bonus': 'bonuses', 'Range': 'range', 'Surface': 'radius',
                'Radius and duration': 'radius', 'Crafting': 'crafting', 'History': 'history',
                'Acquisition and encounters': 'encounters', 'Encounter suggestion': 'encounters',
                'Special powers': 'special_powers', 'Activation': 'activation', 'Casting time': 'casting_time',
                'Weight': 'weight', 'Area': 'radius', 'Saving throw': 'saving_throw',
                'Duration': 'duration', 'Attunement': 'attunement'
            }.get(label)
            if key:
                state = 'draft' if entry['status'] == 'original-draft' else 'source-field'
                if entry['status'] == 'published-reference':
                    state = '2024-guideline'
                if label == 'Crafting' and entry['fields'][label].endswith(
                    ('supplies no recipe.', 'recipe and materials are left to the DM.')
                ):
                    state = 'unknown'
                if label == 'Casting time' and entry['fields'][label] == 'Does not cast a spell.':
                    state = 'not-applicable'
                if label == 'Area' and entry['fields'][label] == 'Single target; no radius.':
                    state = 'not-applicable'
                if label in {'Saving throw', 'Attunement'} and entry['fields'][label].startswith('None;'):
                    state = 'not-applicable'
                if state != 'unknown':
                    put(key, state)
    return status


def main():
    bg3_items = supplement('bg3-item-rules.json')['records']
    bg3_reviewed = supplement('bg3-armor-effects.json')['reviewed_item_facts']
    bg3_weapons = supplement('bg3-weapon-rules.json')['weapons']
    curated = supplement('curated-item-details.json')['records']
    curated.update(supplement('published-2024-weapon-facts.json')['records'])
    spells = supplement('dnd-2024-spell-reference.json')['spells']
    native_games = supplement('legacy-game-weapon-facts.json')['records']
    for game_facts in ('diablo-2-base-weapon-facts.json', 'diablo-2-unique-weapon-facts.json'):
        if (ROOT / 'supplements' / game_facts).is_file():
            native_games.update(supplement(game_facts)['records'])
    prices = supplement('item-prices.json')['records']
    ammunition_gaps = []
    totals = {field: collections.Counter() for field in FIELDS}
    counts = collections.Counter()
    with sqlite3.connect(ROOT / 'indexes/items.sqlite3') as db, (
        ROOT / 'reports/item-detail-audit.csv'
    ).open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['id', 'name', 'ruleset', 'source_id', 'type', *FIELDS])
        for (data,) in db.execute('SELECT data_json FROM items ORDER BY id'):
            item = json.loads(data)
            coverage = audit(item, bg3_items, bg3_weapons, curated, spells, native_games, prices, bg3_reviewed)
            if item['type'] == 'ammunition':
                fields = ('damage', 'range', 'activation')
                gaps = [field for field in fields if coverage[field] in {'unknown', 'source-text-lead'}]
                if gaps:
                    ammunition_gaps.append((item['id'], item['name'], item['source_id'], ' / '.join(gaps)))
            writer.writerow([item['id'], item['name'], item['ruleset'], item['source_id'], item['type'],
                             *(coverage[key] for key in FIELDS)])
            counts[item['ruleset']] += 1
            for key, state in coverage.items():
                totals[key][state] += 1
    with (ROOT / 'reports/ammunition-rule-gaps.csv').open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(('id', 'name', 'source_id', 'fields_without_structured_rules'))
        writer.writerows(ammunition_gaps)
    lines = [
        '# Item detail audit', '',
        f'{sum(counts.values()):,} catalog records checked against normalized data and current detail supplements.',
        'This is a field coverage scan. A source-text or location lead still requires review. '
        'A structured field or a 2024 guideline is evidence for that field only. Unknown fields may be absent from the source or inapplicable.',
        '', '| Field | Structured or catalog price | 2024 reference or guideline | Draft | Leads | Unknown | N/A |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for field, states in totals.items():
        lines.append('| ' + field.replace('_', ' ').title() + ' | ' + ' | '.join(f'{value:,}' for value in (
            states['source-field'] + states['priced'], states['2024-spell-reference'] + states['2024-guideline'], states['draft'],
            states['source-text-lead'] + states['location-lead'], states['unknown'], states['not-applicable']
        )) + ' |')
    lines.extend(['', f'{len(ammunition_gaps):,} ammunition entries have at least one unresolved damage, range, or activation field. See [ammunition-rule-gaps.csv](ammunition-rule-gaps.csv).',
                  '', 'Individual statuses are in [item-detail-audit.csv](item-detail-audit.csv).', ''])
    (ROOT / 'reports/ITEM-DETAIL-AUDIT.md').write_text('\n'.join(lines))
    print(f'Audited {sum(counts.values()):,} records.')


if __name__ == '__main__':
    main()
