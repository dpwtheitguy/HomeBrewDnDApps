#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$app_dir/../.." && pwd)"
local_tools="$root/.cache/android-tools"
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$local_tools/sdk}}"
jdk="${JAVA_HOME:-$local_tools/jdk/usr/lib/jvm/java-17-openjdk-amd64}"
if [[ -d "$jdk/bin" ]]; then export JAVA_HOME="$jdk" PATH="$jdk/bin:$PATH"; fi
build_tools="${ARMORY_BUILD_TOOLS:-$sdk/build-tools/35.0.0}"
if [[ ! -x "$build_tools/aapt2" ]]; then build_tools="$sdk/build-tools/android-15"; fi
platform="$sdk/platforms/android-35/android.jar"
catalog="${1:-$root/outputs/shared-item-catalog-2026-11-12.152.zip}"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/assets/web" "$stage/classes" "$stage/dex" "$root/outputs"
cp "$app_dir"/web/* "$stage/assets/web/"

PYTHONPATH="$app_dir:$root/shared" python3 - "$catalog" "$stage/assets" <<'PY'
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from build_search import prepare
from item_pricing import price_catalog

archive_path, asset_path = sys.argv[1:]
assets = Path(asset_path)
with ZipFile(archive_path) as release:
    manifest = json.loads(release.read('manifest.json'))
    if manifest['catalog_id'] != 'shared-item-catalog' or manifest['format_version'] != 1:
        raise SystemExit('Unsupported catalog asset')
    db_path = manifest['database']
    def copy_verified(name, destination):
        digest = hashlib.sha256()
        with release.open(name) as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                destination.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != manifest['files'][name]['sha256']:
            raise SystemExit(f'Invalid catalog checksum: {name}')

    staged_db = assets.parent / 'items.sqlite3'
    with staged_db.open('wb') as output:
        copy_verified(db_path, output)
    pricing_path = 'catalog/supplements/item-prices.json'
    if pricing_path in manifest['files']:
        pricing_file = assets.parent / 'item-prices.json'
        with pricing_file.open('wb') as output:
            copy_verified(pricing_path, output)
        prices = json.loads(pricing_file.read_text())
    else:
        with sqlite3.connect(staged_db) as db:
            prices = price_catalog([json.loads(data) for (data,) in db.execute('SELECT data_json FROM items')])
    prepare(staged_db, prices)
    with staged_db.open('rb') as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    manifest['upstream_database_sha256'] = manifest['files'][db_path]['sha256']
    manifest['files'][db_path] = {'sha256': digest.hexdigest(), 'bytes': staged_db.stat().st_size}
    (assets / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with ZipFile(assets / 'database.zip', 'w', ZIP_DEFLATED, compresslevel=3) as database:
        database.write(staged_db, db_path)
    for name in manifest['files']:
        if name == pricing_path:
            continue
        if name.startswith('catalog/images/types/'):
            target = assets / 'web' / name.removeprefix('catalog/')
        elif name.startswith('catalog/supplements/'):
            target = assets / 'web' / Path(name).name
        elif name.startswith('catalog/licenses/') or name == 'catalog/images/manifest.json':
            target = assets / 'credits' / Path(name).name
        elif name in ('catalog/sources.json', 'catalog/taxonomy/entities.json'):
            target = assets / Path(name).name
        else:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('wb') as output:
            copy_verified(name, output)
PY

"$build_tools/aapt2" compile --dir "$app_dir/res" -o "$stage/resources.zip"
"$build_tools/aapt2" link -I "$platform" --manifest "$app_dir/AndroidManifest.xml" \
    -A "$stage/assets" --debug-mode -0 zip -o "$stage/unsigned.apk" "$stage/resources.zip"
javac --release 8 -cp "$platform" -d "$stage/classes" "$app_dir"/src/*.java
jar cf "$stage/classes.jar" -C "$stage/classes" .
"$build_tools/d8" --min-api 23 --lib "$platform" --output "$stage/dex" "$stage/classes.jar"
python3 - "$stage" <<'PY'
import sys
from pathlib import Path
from zipfile import ZipFile
stage = Path(sys.argv[1])
with ZipFile(stage / 'unsigned.apk', 'a') as package:
    package.write(stage / 'dex/classes.dex', 'classes.dex')
PY
"$build_tools/zipalign" -f 4 "$stage/unsigned.apk" "$stage/aligned.apk"
keystore="${ARMORY_DEBUG_KEYSTORE:-$local_tools/armory-debug.keystore}"
mkdir -p "$(dirname "$keystore")"
if [[ ! -f "$keystore" ]]; then
    keytool -genkeypair -keystore "$keystore" -storepass android -keypass android -alias androiddebugkey \
        -dname 'CN=Android Debug,O=Complete Guide,C=US' -keyalg RSA -keysize 2048 -validity 10000
fi
apk="$root/outputs/arms-and-equipment-guide-debug.apk"
"$build_tools/apksigner" sign --ks "$keystore" --ks-pass pass:android --key-pass pass:android \
    --out "$stage/signed.apk" "$stage/aligned.apk"
"$build_tools/apksigner" verify "$stage/signed.apk"
mv "$stage/signed.apk" "$apk"
printf '%s\n' "$apk"
