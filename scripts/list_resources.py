#!/usr/bin/env python3
"""Inspect every requested source and its explicit gaps from the SQLite database."""
import argparse,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('query',nargs='?',default='');p.add_argument('--gaps',action='store_true');p.add_argument('--json',action='store_true');a=p.parse_args()
 db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3')
 rows=[json.loads(r[0]) for r in db.execute('SELECT data_json FROM resources ORDER BY label COLLATE NOCASE')];db.close()
 if a.query:rows=[r for r in rows if a.query.casefold() in (' '.join([r['id'],r['label'],*r['aliases']])).casefold()]
 if a.gaps:rows=[r for r in rows if r['original_item_audit_status']!='complete']
 if a.json:print(json.dumps(rows,ensure_ascii=False,indent=2))
 else:
  for r in rows:print(f"{r['label']} | {r['coverage_status']} | {r['direct_or_inspired_records']} direct/inspired, {r['context_only_records']} context | audit {r['original_item_audit_status']}")
  print(f'{len(rows)} resource(s). Registered does not mean fully imported or verified.')
if __name__=='__main__':main()
