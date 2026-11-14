#!/usr/bin/env python3
"""Reconcile native BG3 item template pages with indexed alphabet batches."""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path

from fetch_bg3 import ROOT, TEMPLATES, extract_templates, request
from onboard_bg3_item import CACHE

ITEM_TEMPLATES = {'weaponpage', 'equipmentpage', 'miscitempage'}
READING_EFFECT = re.compile(
    r'\b(?:inspiration|unlocks?|advance[sd]?|progress(?:es)?|password|passphrase|recipe|'
    r'grants?|opens?|quest)\b', re.IGNORECASE)


def fetch_candidates(ids):
    rows = {}
    ids = sorted(int(key.split(':')[1]) for key in ids)
    for start in range(0, len(ids), 40):
        batch = '|'.join(map(str, ids[start:start + 40]))
        source = request(dict(action='query', pageids=batch, prop='revisions',
                              rvprop='ids|content', rvslots='main'))
        for page in source['query']['pages']:
            if not page.get('revisions'):
                raise ValueError(f"Missing item revision for page {page['pageid']}")
            revision = page['revisions'][0]
            raw = revision['slots']['main']['content']
            cached = CACHE / f"{revision['revid']}.json"
            if not cached.exists():
                CACHE.mkdir(parents=True, exist_ok=True)
                payload = dict(pageid=page['pageid'], title=page['title'], revisions=[revision],
                               sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest())
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=CACHE, delete=False) as temp:
                    json.dump(payload, temp, ensure_ascii=False)
                Path(temp.name).replace(cached)
            templates = extract_templates(raw, ITEM_TEMPLATES, lambda _: True)
            rows[f"bg3-wiki:{page['pageid']}"] = [page['title'], revision['revid'], raw, templates]
    return rows


def discover(letters):
    found = {}
    for template in TEMPLATES.values():
        continuation = {}
        while True:
            result = request(dict(action='query', list='embeddedin', eititle=template,
                                  einamespace=0, eilimit=500, **continuation))
            for page in result['query']['embeddedin']:
                if page['title'][0].casefold() in letters:
                    found[f"bg3-wiki:{page['pageid']}"] = page['title']
            if 'continue' not in result:
                break
            continuation = result['continue']
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('letters', help='One or more initial letters, such as DE')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--local-evidence', type=Path,
                        help='Fetch exact candidate revisions into a local research file')
    parser.add_argument('--worklist', type=Path,
                        help='Write candidate IDs and indexed types to a TSV for reviewers')
    args = parser.parse_args()
    if not args.letters.isascii() or not args.letters.isalpha():
        parser.error('Use ASCII letters')
    letters = set(args.letters.casefold())
    candidates = discover(letters)
    database = ROOT / 'catalog/indexes/items.sqlite3'
    with sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True) as db:
        indexed = {key: (name, kind) for key, name, kind in
                   db.execute("SELECT id,name,type FROM items WHERE source_id='bg3-wiki'")}
    names = {key: row[0] for key, row in indexed.items()}
    matching = {key for key, name in names.items() if name and name[0].casefold() in letters}
    report = {'letters': sorted(letter.upper() for letter in letters), 'wiki': candidates,
              'wiki_title_only': {key: candidates[key] for key in sorted(candidates.keys() - matching)},
              'indexed_title_only': {key: names[key] for key in sorted(matching - candidates.keys())}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    rows = None
    if args.local_evidence:
        rows = fetch_candidates(candidates.keys() | matching)
        args.local_evidence.parent.mkdir(parents=True, exist_ok=True)
        args.local_evidence.write_text(json.dumps(rows, ensure_ascii=False) + '\n', encoding='utf-8')
    if args.worklist:
        args.worklist.parent.mkdir(parents=True, exist_ok=True)
        with args.worklist.open('w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file, delimiter='\t')
            writer.writerow(('id', 'wiki_title', 'indexed_name', 'indexed_type', 'reading_clues'))
            for key in sorted(candidates.keys() | matching,
                              key=lambda item_id: (names.get(item_id) or candidates[item_id]).casefold()):
                name, kind = indexed.get(key, ('', ''))
                clues = set()
                if rows and kind == 'book':
                    for template in rows[key][3]:
                        for field in ('description', 'usage', 'effect', 'notes'):
                            clues.update(match.group().casefold() for match in
                                         READING_EFFECT.finditer(template['facts'].get(field, '')))
                writer.writerow((key, candidates.get(key, ''), name, kind, ', '.join(sorted(clues))))
    print(f"{len(candidates)} pinned-source title candidates; "
          f"{len(report['wiki_title_only'])} wiki-title-only; "
          f"{len(report['indexed_title_only'])} indexed-title-only")


if __name__ == '__main__':
    main()
