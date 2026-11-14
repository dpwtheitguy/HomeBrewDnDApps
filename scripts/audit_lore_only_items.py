#!/usr/bin/env python3
"""Report lore-only exclusion candidates without changing the catalog."""
import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_TYPES = {'book', 'scroll', 'misc', 'other', 'key', 'gear', 'adventuring-gear', 'map', 'quest-item'}
RULE_FIELDS = {'activation', 'damage', 'special powers', 'effects', 'use as armor',
               'attack bonus', 'saving throw', 'crafting', 'teaches', 'unlocks'}


def classify(item, native, curated, reviewed):
    mechanics = item.get('mechanics') or {}
    if item.get('magic') is True or any(
        mechanics.get(field) for field in ('weapon', 'armor', 'automated_effects', 'original_adaptation_rules')
    ):
        return 'retain', 'Structured gameplay evidence'
    if any(
        variant.get('effects') or variant.get('conditions') or variant.get('has_rule_text')
        or any(key.casefold() in RULE_FIELDS and value for key, value in variant.get('facts', {}).items())
        or variant.get('recipe_refs') or variant.get('stats', {}).get('usage cost')
        for variant in native.get('variants', [])
    ) or any(
        key.casefold() in RULE_FIELDS and value
        for entry in curated for key, value in entry.get('fields', {}).items()
    ):
        return 'retain', 'Supplement contains a gameplay lead'
    if item['type'] in {'key', 'scroll', 'map', 'quest-item'}:
        return 'review', 'Potential quest or exploration use. Verify the exact use.'
    if reviewed and (item.get('provenance') or {}).get('source_url') == reviewed['source_url']:
        if type(reviewed.get('revision')) is int and native.get('revision') == reviewed['revision']:
            return 'candidate', reviewed['reason']
        return 'review', 'Source revision changed since the lore-only review'
    return 'review', 'Verify that the item has no mechanical, quest, or exploration use'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-dir', type=Path, default=ROOT / 'catalog')
    parser.add_argument('--source', default='bg3-wiki', help='catalog source ID')
    args = parser.parse_args()
    catalog = args.catalog_dir
    uri = (catalog / 'indexes/items.sqlite3').resolve().as_uri() + '?mode=ro'
    native = json.loads((catalog / 'supplements/bg3-item-rules.json').read_text())['records']
    curated = json.loads((catalog / 'supplements/curated-item-details.json').read_text())['records']
    reviewed_facts = json.loads((catalog / 'supplements/bg3-armor-effects.json').read_text())['reviewed_item_facts']
    reviewed = json.loads((Path(__file__).with_name('lore_only_reviews.json')).read_text())
    with sqlite3.connect(uri) as db:
        if not db.execute('SELECT 1 FROM items WHERE source_id=? LIMIT 1', (args.source,)).fetchone():
            parser.error(f'unknown catalog source: {args.source}')
        writer = csv.writer(sys.stdout)
        writer.writerow(('id', 'name', 'type', 'disposition', 'source_url', 'source_revision', 'reason'))
        for (raw,) in db.execute('SELECT data_json FROM items WHERE source_id=? ORDER BY name_key,id', (args.source,)):
            item = json.loads(raw)
            item_id = item['id']
            if item['type'] not in REVIEW_TYPES and item_id not in reviewed:
                continue
            entries = curated.get(item_id, []) + [{'fields': reviewed_facts.get(item_id, {})}]
            record = native.get(item_id, {})
            disposition, reason = classify(item, record, entries, reviewed.get(item_id))
            writer.writerow((item_id, item['name'], item['type'], disposition,
                             item['provenance'].get('source_url'), record.get('revision'), reason))


if __name__ == '__main__':
    main()
