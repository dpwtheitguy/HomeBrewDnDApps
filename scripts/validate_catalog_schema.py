#!/usr/bin/env python3
"""Validate the SQLite catalog against its published JSON Schemas."""
import argparse
import json
import sqlite3
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-dir', type=Path, default=CATALOG)
    args = parser.parse_args()
    schemas = {path.name: json.loads(path.read_text()) for path in args.catalog_dir.glob('*.schema.json')}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resources(
        (name, Resource.from_contents(schema)) for name, schema in schemas.items()
    )
    validator = Draft202012Validator(schemas['item.schema.json'], registry=registry)
    checked = invalid = 0
    index = args.catalog_dir.resolve() / 'indexes/items.sqlite3'
    with sqlite3.connect(index.as_uri() + '?mode=ro', uri=True) as database:
        for item_id, payload in database.execute('SELECT id, data_json FROM items ORDER BY id'):
            checked += 1
            errors = list(validator.iter_errors(json.loads(payload)))
            invalid += bool(errors)
            for error in errors:
                location = '/'.join(map(str, error.absolute_path)) or '<record>'
                print(f'{item_id} {location}: {error.message}')
    print(f'{checked:,} records checked, {invalid:,} invalid.')
    return int(bool(invalid))


if __name__ == '__main__':
    raise SystemExit(main())
