#!/usr/bin/env python3
"""Identify unresolved 2024 rules and link matching published SRD entries."""
import collections
import csv
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
REVIEW = {'adaptation-needed', 'full-source-mechanics-needed', 'supplement-review-required', 'draft-dm-review-required'}
PENDING = re.compile(r'\bpending\b', re.I)


def key(value):
    return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def marker_fields(item):
    research = item.get('research_metadata') or {}
    reference = (item.get('mechanics') or {}).get('reference_metadata') or {}
    conversion = item.get('conversion') or {}
    values = {
        'content status': item.get('content_status'),
        'tabletop status': item.get('tabletop_status'),
        'source verification': research.get('verification_status'),
        'source note': reference.get('source_note'),
        'conversion status': conversion.get('conversion_status'),
        'conversion note': conversion.get('conversion_note'),
    }
    return [label for label, text in values.items() if isinstance(text, str) and PENDING.search(text)]


def main():
    with sqlite3.connect(CATALOG / 'indexes/items.sqlite3') as db:
        items = [json.loads(data) for (data,) in db.execute('SELECT data_json FROM items ORDER BY id')]
    profiles = json.loads((CATALOG / 'supplements/weapon-profiles-2024.json').read_text())['records']
    native_path = CATALOG / 'supplements/legacy-game-weapon-facts.json'
    native = json.loads(native_path.read_text())['records'] if native_path.exists() else {}
    curated = json.loads((CATALOG / 'supplements/curated-item-details.json').read_text())['records']
    known = collections.defaultdict(list)
    for item in items:
        if item['source_id'] == 'open5e-srd-2024' and item.get('description'):
            known[item['type'], key(item['name'])].append(item['id'])
    links = {}
    totals = collections.Counter()
    review = collections.Counter()
    with (CATALOG / 'reports/pending-2024-rules.csv').open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(('id', 'name', 'type', 'ruleset', 'source', 'tabletop_status', 'pending_fields',
                         'weapon_profile', 'published_2024_cross_reference', 'native_game_stats', 'item_specific_draft', 'curated_2024_reference'))
        for item in items:
            markers = marker_fields(item)
            status = item.get('tabletop_status') or ''
            if not markers and status not in REVIEW:
                continue
            item_id = item['id']
            profile = profiles.get(item_id, {}).get('kind', '')
            matches = known[item['type'], key(item['name'])]
            target = ''
            if len(matches) == 1 and item['ruleset'] not in ('bg3', 'dnd-2024'):
                target = matches[0]
                links[item_id] = target
            draft = any(entry['status'] == 'original-draft' for entry in curated.get(item_id, []))
            published = any(entry['status'] == 'published-reference' for entry in curated.get(item_id, []))
            native_stats = item_id in native
            totals['native_stats'] += native_stats
            totals['draft'] += draft
            totals['explicit_without_rules_or_draft'] += bool(markers and not target and not draft and not published)
            writer.writerow((item_id, item['name'], item['type'], item['ruleset'], item['source_id'], status,
                             ' | '.join(markers), profile, target, native_stats, draft, published))
            totals['queued'] += 1
            totals['explicit'] += bool(markers)
            review[status] += 1
    output = {'schema_version': 1, 'basis': 'Unique exact normalized name and matching item type in the 2024 SRD',
              'records': links}
    (CATALOG / 'supplements/dnd-2024-item-cross-references.json').write_text(
        json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    lines = [
        '# Pending 2024 rules', '',
        f'Scanned {len(items):,} catalog records. Found {totals["explicit"]:,} with an explicit pending marker.',
        f'The broader [review queue](pending-2024-rules.csv) contains {totals["queued"]:,} records with an explicit marker or a rules-review status.',
        'BG3 native game rules and original-edition source rules retain their own evidence.',
        '', '| Tabletop status | Records in queue |', '|---|---:|'
    ]
    lines.extend(f'| {status} | {count:,} |' for status, count in review.most_common())
    lines += ['', f'Linked {len(links):,} older or unverified records to a unique same-name, same-type 2024 SRD entry.',
              'The app shows this as a published 2024 cross-reference. The source edition and pending status remain visible.',
              f'{totals["explicit_without_rules_or_draft"]:,} explicitly marked records still have neither a published cross-reference nor an item-specific draft.',
              f'{totals["native_stats"]:,} queued records now show native video game statistics and {totals["draft"]:,} have an item-specific draft in the curated supplement.',
              '', 'Weapon profile kinds in the queue distinguish published mechanics, documented base profiles, family drafts, and provisional improvised rules.', '']
    (CATALOG / 'reports/PENDING-2024-RULES.md').write_text('\n'.join(lines))
    print(f'{totals["explicit"]:,} explicit pending markers; {totals["queued"]:,} review records; {len(links):,} exact 2024 links.')


if __name__ == '__main__':
    main()
