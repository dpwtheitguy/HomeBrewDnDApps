#!/usr/bin/env python3
"""Import numeric Diablo II base-weapon facts from Blizzard's Arreat Summit."""
import collections
import json
import re
import sqlite3
from pathlib import Path

from fetch_ninja_references import clean, fetch

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
SOURCE_ID = 'diablo-2-reference'
TABLE_URL = re.compile(
    r'https://classic\.battle\.net/diablo2exp/items/(normal|exceptional|elite)/([a-z]+)\.shtml'
)
DAMAGE_RANGE = re.compile(r'(\d+)\s+to\s+(\d+)(?:\s+\(([\d.]+)\s+avg\))?', re.I)
STAT_LABELS = {
    'level requirement': 'Required level',
    'min strength': 'Minimum Strength',
    'min dexterity': 'Minimum Dexterity',
    'rangeadder': 'Melee range adder (game units)',
    'durability': 'Durability',
    'sockets': 'Max sockets',
    'magic level': 'Magic level',
    'quality level': 'Quality level',
    'max stack': 'Max stack',
}
DAMAGE_LABELS = {
    'min/max 1h damage': 'One-handed damage',
    'min/max 1h damage(barbarian only)': 'One-handed damage (Barbarian only)',
    'min/max 1h damage (barbarian only)': 'One-handed damage (Barbarian only)',
    'min/max 2h damage': 'Two-handed damage',
    'min/max dagger damage': 'Damage',
    'two-hand damage': 'Two-handed damage',
    'two hand damage': 'Two-handed damage',
    'throw damage': 'Throw damage',
}


def table_rows(tree):
    """Read direct table rows, with labels taken from that table's current header."""
    rows = collections.defaultdict(list)
    for table in tree.xpath('//table'):
        header = []
        for row in table.xpath('./tr|./thead/tr|./tbody/tr'):
            cells = row.xpath('./td|./th')
            labels = [clean(cell.text_content()).casefold() for cell in cells]
            if any(label in DAMAGE_LABELS for label in labels[1:]):
                header = labels
                continue
            if not header or len(cells) != len(header) or not cells[0].xpath('./img'):
                continue
            names = cells[0].xpath('.//b')
            if len(names) != 1:
                continue
            name = clean(names[0].text_content())
            damage, facts = {}, {}
            for label, cell in zip(header[1:], cells[1:]):
                value = clean(cell.text_content())
                if label in DAMAGE_LABELS and (match := DAMAGE_RANGE.fullmatch(value)):
                    low, high, avg = match.groups()
                    if int(low) <= int(high):
                        damage[DAMAGE_LABELS[label]] = f'{low}–{high}' + (f' (average {avg})' if avg else '')
                elif label in STAT_LABELS and re.fullmatch(r'\d+', value):
                    facts[STAT_LABELS[label]] = value
                elif label.startswith(('speed', 'class speed')) and (match := re.search(r'\[(-?\d+)\]', value)):
                    facts['Base weapon speed modifier'] = match.group(1)
            if damage:
                if len(damage) == 1:
                    mode, value = next(iter(damage.items()))
                    damage = {'Damage': value}
                    if mode != 'Damage':
                        damage['Attack mode'] = mode.removesuffix(' damage')
                rows[name.casefold()].append({**damage, **facts})
    return rows


def main():
    index = CATALOG / 'indexes/items.sqlite3'
    with sqlite3.connect(index.resolve().as_uri() + '?mode=ro', uri=True) as database:
        items = [json.loads(raw) for (raw,) in database.execute(
            "SELECT data_json FROM items WHERE type = 'weapon' AND source_id = ? ORDER BY id",
            (SOURCE_ID,),
        )]
    candidates = [item for item in items if
                  item['provenance'].get('evidence', {}).get('kind') == 'official-base-item-table']
    if not candidates:
        raise SystemExit('No Diablo II base-weapon index records found')
    pages = {}
    records = {}
    failures = []
    for item in candidates:
        url = item['provenance']['source_url']
        match = TABLE_URL.fullmatch(url)
        tier = item['mechanics']['reference_metadata'].get('tier')
        if not match or match[1] != tier:
            failures.append(f'{item["id"]}: source URL and tier disagree')
            continue
        if url not in pages:
            pages[url] = table_rows(fetch(url))
        matches = pages[url][clean(item['name']).casefold()]
        if len(matches) != 1:
            failures.append(f'{item["name"]} ({tier}): {len(matches)} exact rows in {url}')
            continue
        facts = {**matches[0], 'Item tier': tier.title(), 'Weapon group': match[2].title()}
        records[item['id']] = {
            'game': 'Diablo II (classic Arreat Summit)',
            'variants': [{'fields': facts, 'source': url}],
        }
    if failures:
        raise SystemExit('\n'.join(failures))
    output = {
        'schema_version': 1,
        'source_scope': 'Classic Diablo II base-item facts. Game values retain their native meaning.',
        'records': records,
    }
    path = CATALOG / 'supplements/diablo-2-base-weapon-facts.json'
    path.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Imported {len(records)} base weapons from {len(pages)} Arreat Summit tables.')


if __name__ == '__main__':
    main()
