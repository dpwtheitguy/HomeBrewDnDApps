#!/usr/bin/env python3
"""Package the shared catalog for offline app consumption."""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
CATALOG_ID = 'shared-item-catalog'
FORMAT_VERSION = 1
ASSET_FILES = (
    'indexes/items.sqlite3',
    'images/manifest.json',
    'sources.json',
    'taxonomy/entities.json',
    'filters/presets.json',
    'item.schema.json',
    'structure.schema.json',
)
ASSET_DIRECTORIES = ('images/types', 'licenses')


def digest(stream):
    checksum = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        checksum.update(chunk)
    return checksum.hexdigest()


def verify_archive(path, manifest_bytes, entries):
    with ZipFile(path) as bundle:
        if bundle.read('manifest.json') != manifest_bytes:
            raise ValueError('This version already exists with different content. Choose a new version.')
        if sorted(bundle.namelist()) != sorted(['manifest.json', *entries]):
            raise ValueError(f'Unexpected archive contents: {path}')
        for name, entry in entries.items():
            with bundle.open(name) as stream:
                if bundle.getinfo(name).file_size != entry['bytes'] or digest(stream) != entry['sha256']:
                    raise ValueError(f'Asset failed integrity verification: {name}')


def package(version, output):
    catalog = ROOT / 'catalog'
    files = [catalog / name for name in ASSET_FILES]
    files.extend(sorted((catalog / 'supplements').glob('*.json')))
    for directory in ASSET_DIRECTORIES:
        files.extend(path for path in (catalog / directory).iterdir() if path.is_file())
    files = {path.relative_to(ROOT).as_posix(): path for path in sorted(files)}

    entries = {}
    for name, path in files.items():
        with path.open('rb') as stream:
            entries[name] = {'sha256': digest(stream), 'bytes': path.stat().st_size}
    manifest = {
        'catalog_id': CATALOG_ID,
        'format_version': FORMAT_VERSION,
        'content_version': version,
        'database': 'catalog/indexes/items.sqlite3',
        'files': entries,
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()

    output.mkdir(parents=True, exist_ok=True)
    destination = output / f'{CATALOG_ID}-{version}.zip'
    if destination.exists():
        verify_archive(destination, manifest_bytes, entries)
        return destination

    with tempfile.TemporaryDirectory(dir=output) as staging:
        archive = Path(staging) / destination.name
        with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=6) as bundle:
            bundle.writestr('manifest.json', manifest_bytes)
            for name, path in files.items():
                bundle.write(path, name)

        verify_archive(archive, manifest_bytes, entries)
        try:
            destination.hardlink_to(archive)
        except FileExistsError:
            verify_archive(destination, manifest_bytes, entries)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, help='Content version such as 2026-11-11.1')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+(?:[.-][0-9]+)*', args.version):
        parser.error('--version must use digits separated by dots or hyphens')
    try:
        print(package(args.version, args.output).resolve())
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
