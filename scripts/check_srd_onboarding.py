#!/usr/bin/env python3
"""Check a packaged SRD release and generate a reproducible reviewer draw."""
import argparse
import json
import random
import sqlite3
import tempfile
from pathlib import Path
from zipfile import ZipFile

from package_srd_catalog import FIXTURES, ROOT, SOURCE, md5_text

REVIEW_SIZE = 200


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--exclude', action='append', default=[], help='Stable ID reserved for regression')
    args = parser.parse_args()
    pinned = {
        f"{SOURCE}:{row['pk']}": row['fields']['desc']
        for kind in ('Item', 'MagicItem')
        for row in json.loads((ROOT / 'catalog' / FIXTURES / f'{kind}.json').read_text())
    }
    with tempfile.TemporaryDirectory() as temp, ZipFile(args.archive) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        path = bundle.extract(manifest['database'], temp)
        with sqlite3.connect(path) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise SystemExit('Packaged SQLite integrity check failed')
            rows = [json.loads(raw) for raw, in db.execute('SELECT data_json FROM items ORDER BY id')]
    if not rows:
        raise SystemExit('Packaged catalog is empty')
    errors = []
    for row in rows:
        item_id = row['id']
        evidence = row['research_metadata'].get('srd_text', {})
        description = row['description']
        if md5_text(description) != evidence.get('description_md5'):
            errors.append(f'{item_id} description MD5')
        if item_id in pinned:
            original = evidence.get('source_text', description)
            if original != pinned[item_id] or md5_text(original) != evidence.get('transcription_md5'):
                errors.append(f'{item_id} pinned text or MD5')
    if errors:
        raise SystemExit('\n'.join(errors))
    report = {'release': manifest['content_version'], 'checked': len(rows)}
    if args.seed is not None:
        excluded = set(args.exclude)
        pool = [row['id'] for row in rows if row['id'] not in excluded]
        if len(pool) < REVIEW_SIZE:
            raise SystemExit(f'Only {len(pool)} eligible IDs for {REVIEW_SIZE} cards')
        report.update(seed=args.seed, stable_ids=random.Random(args.seed).sample(pool, REVIEW_SIZE))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
