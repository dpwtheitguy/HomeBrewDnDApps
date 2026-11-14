#!/usr/bin/env python3
"""Verify all included and excluded IDs in a BG3 batch against a release archive."""
import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from zipfile import ZipFile

from onboard_bg3_item import ROOT, pinned_pages, verify_batch_inventory, verify_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.inventory.read_text(encoding='utf-8'))
    reviews = [json.loads(path.read_text(encoding='utf-8'))
               for path in sorted((ROOT / 'catalog/research/bg3-onboarding').glob('*.json'))]
    verify_batch_inventory(batch, reviews)
    fixtures = {review['item_id']: review for review in reviews}
    issues = []
    evidence = []
    unique_revisions = set()
    candidate_revisions = {
        revision['revid']: page['pageid']
        for page in pinned_pages({entry['revision'] for entry in batch['candidates']})
        for revision in page['revisions']
    }
    with tempfile.TemporaryDirectory() as directory, ZipFile(args.archive) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        dbfile = archive.extract(manifest['database'], directory)
        with sqlite3.connect(dbfile) as db:
            if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise ValueError('Packaged database failed integrity check')
            rows = dict(db.execute("SELECT id,data_json FROM items WHERE source_id='bg3-wiki'"))
        details = json.loads(archive.read('catalog/supplements/curated-item-details.json'))['records']

    for entry in batch['candidates']:
        item_id = entry['id']
        row = rows.get(item_id)
        problems = []
        if candidate_revisions.get(entry['revision']) != int(item_id.split(':')[1]):
            problems.append('Candidate revision does not match the stable ID')
        if entry['status'] == 'out-of-scope':
            if row and json.loads(row)['name'] != entry['title']:
                problems.append('Packaged out-of-scope alias differs from canonical title')
        elif bool(row) != (entry['status'] == 'imported'):
            problems.append('Packaged selection differs from disposition')
        elif row:
            fixture = fixtures[item_id]
            record = json.loads(row)
            metadata = record.pop('research_metadata')
            references = verify_sources(fixture)
            if metadata['source_refs'] != references:
                problems.append('Packaged pinned references differ')
            unique_revisions.update(ref['revision_id'] for ref in references)
            digest = hashlib.sha256(json.dumps(
                record, sort_keys=True, ensure_ascii=False, separators=(',', ':')
            ).encode('utf-8')).hexdigest()
            if digest != metadata['record_content_sha256']:
                problems.append('Packaged record digest differs')
            rules = details.get(item_id, [])
            if (record['description'] != fixture['summary'] or len(rules) != 1 or
                    rules[0].get('fields') != fixture['fields']):
                problems.append('Packaged rules differ from fixture')
        issues.extend((item_id, problem) for problem in problems)
        evidence.append(dict(id=item_id, disposition=entry['status'], issues=problems))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as report:
        for record in evidence:
            print(json.dumps(record, ensure_ascii=False), file=report)
    print(f'{len(evidence)} candidates, {len(unique_revisions)} included rule revisions, '
          f'{len(candidate_revisions)} candidate revisions, {len(issues)} issues')
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
