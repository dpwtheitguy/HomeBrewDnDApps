#!/usr/bin/env python3
"""Merge reviewed BG3 letter dispositions into the release inventory."""
import argparse
import csv
import json
from pathlib import Path

from fetch_bg3 import ROOT
from onboard_bg3_item import verify_batch_inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('discovery', type=Path)
    parser.add_argument('revisions', type=Path, help='Local candidate evidence from discover_bg3_letters.py')
    parser.add_argument('dispositions', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    discovery = json.loads(args.discovery.read_text(encoding='utf-8'))
    candidates = discovery['wiki'] | discovery['indexed_title_only']
    revisions = json.loads(args.revisions.read_text(encoding='utf-8'))
    dispositions = {}
    for path in args.dispositions:
        with path.open(encoding='utf-8', newline='') as file:
            for row in csv.DictReader(file, delimiter='\t'):
                item_id = row['id']
                if item_id in dispositions:
                    parser.error(f'Duplicate disposition for {item_id}')
                dispositions[item_id] = row
    if candidates.keys() != dispositions.keys():
        parser.error(f'Missing IDs: {sorted(candidates.keys() - dispositions.keys())}. '
                     f'Extra IDs: {sorted(dispositions.keys() - candidates.keys())}')
    entries = []
    for item_id in sorted(candidates, key=lambda key: (candidates[key].casefold(), key)):
        title, revision, *_ = revisions[item_id]
        row = dispositions[item_id]
        if row['status'] == 'out-of-scope' and item_id not in discovery['indexed_title_only']:
            parser.error(f'Only indexed aliases can have out-of-scope status: {item_id}')
        entries.append(dict(id=item_id, title=row['title'] if row['status'] == 'imported' else title,
                            revision=revision, status=row['status'], reason=row['reason']))
    inventory = {'letters': discovery['letters'], 'candidates': entries}
    reviews = [json.loads(path.read_text(encoding='utf-8'))
               for path in (ROOT / 'catalog/research/bg3-onboarding').glob('*.json')]
    verify_batch_inventory(inventory, reviews)
    args.output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    imported = sum(row['status'] == 'imported' for row in entries)
    excluded = sum(row['status'] == 'excluded' for row in entries)
    print(f'{imported} imported, {excluded} excluded, {len(entries) - imported - excluded} out of scope')


if __name__ == '__main__':
    main()
