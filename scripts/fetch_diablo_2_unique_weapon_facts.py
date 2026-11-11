#!/usr/bin/env python3
"""Import native numeric Diablo II unique-weapon facts from the Arreat Summit."""
import collections
import concurrent.futures
import json
import re
import sqlite3
from pathlib import Path

from lxml import etree

from fetch_ninja_references import clean, fetch

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
TABLE_URL = re.compile(
    r'https://classic\.battle\.net/diablo2exp/items/(?:normal|exceptional|elite)/u[a-z]+\.shtml'
)
DAMAGE_VALUE = re.compile(r'(?:\(?[\d.]+(?:\s*-\s*[\d.]+)?\)?)\s+to\s+'
                          r'(?:\(?[\d.]+(?:\s*-\s*[\d.]+)?\)?)(?:\s+\([\d.\s-]+avg\))?', re.I)
DAMAGE_LABELS = {
    'damage': 'Damage', 'one-hand damage': 'One-handed damage', 'two-hand damage': 'Two-handed damage',
    'throw damage': 'Throw damage', 'throwing damage': 'Throw damage',
}
INTEGER_FIELDS = {
    'required level': 'Required level', 'required strength': 'Required Strength',
    'required dexterity': 'Required Dexterity', 'durability': 'Durability',
    'base weapon speed': 'Base weapon speed modifier', 'quantity': 'Quantity',
}


def stat_lines(cell):
    """Collect displayed stat lines separated by HTML line breaks."""
    fragments = []
    for event, element in etree.iterwalk(cell, events=('start', 'end')):
        if event == 'start':
            if element.tag == 'br':
                yield clean(''.join(fragments))
                fragments.clear()
            if isinstance(element.tag, str) and element.text:
                fragments.append(element.text)
        elif element is not cell and element.tail:
            fragments.append(element.tail)
    if fragments:
        yield clean(''.join(fragments))


def table_rows(url):
    rows = collections.defaultdict(list)
    for row in fetch(url).xpath('//tr[td[img or .//img]][count(td)=2]'):
        name_cell, stats = row.xpath('./td')
        names = name_cell.xpath('.//b')
        if len(names) != 1 or stats.xpath('.//table'):
            continue
        name = clean(names[0].text_content())
        damage, facts = {}, {}
        for line in stat_lines(stats):
            label, _, value = line.partition(':')
            label, value = label.casefold(), value.strip()
            if label in DAMAGE_LABELS and DAMAGE_VALUE.fullmatch(value):
                damage[DAMAGE_LABELS[label]] = value
            elif label in INTEGER_FIELDS:
                if re.fullmatch(r'\[-?\d+\]|\d+', value):
                    facts[INTEGER_FIELDS[label]] = value.strip('[]')
            elif label == 'indestructible':
                facts['Durability'] = 'Indestructible'
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
            "SELECT data_json FROM items WHERE type = 'weapon' AND source_id = 'diablo-2-reference' ORDER BY id"
        )]
    candidates = [
        item for item in items if item['provenance'].get('evidence', {}).get('kind') == 'official-unique-name-index'
    ]
    if not candidates:
        raise SystemExit('No Diablo II unique-weapon index records found')
    urls = sorted({item['provenance']['source_url'].strip() for item in candidates})
    if any(not TABLE_URL.fullmatch(url) for url in urls):
        raise SystemExit('Unexpected unique-weapon source URL')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        pages = dict(zip(urls, executor.map(table_rows, urls)))
    records, skipped = {}, []
    for item in candidates:
        url = item['provenance']['source_url'].strip()
        matches = pages[url][clean(item['name']).casefold()]
        if len(matches) != 1 or not matches[0]:
            skipped.append({'id': item['id'], 'name': item['name'], 'source': url,
                            'reason': 'No unique exact-name row with recognized native numeric stats'})
            continue
        records[item['id']] = {
            'game': 'Diablo II (classic Arreat Summit)',
            'variants': [{'fields': {**matches[0], 'Quality': 'Unique'}, 'source': url}],
        }
    if not records:
        raise SystemExit('No Diablo II unique weapons matched')
    output = {
        'schema_version': 1,
        'source_scope': 'Classic Diablo II unique-item facts. Game values retain their native meaning.',
        'records': records,
        'skipped': skipped,
    }
    path = CATALOG / 'supplements/diablo-2-unique-weapon-facts.json'
    path.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Imported {len(records)} of {len(candidates)} unique weapons from {len(pages)} Arreat Summit tables.')
    for item in skipped:
        print(f'Skipped {item["name"]} ({item["source"]})')


if __name__ == '__main__':
    main()
