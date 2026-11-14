#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ $# -lt 3 || ! "$1" =~ ^[A-Za-z]$ || ! "$2" =~ ^[0-9]+([.-][0-9]+)+$ ]]; then
    echo "Usage: $0 LETTER RELEASE SERIAL [SERIAL ...]" >&2
    exit 2
fi

letter="${1,,}"
release="$2"
shift 2
inventory="catalog/research/bg3-batch-$letter.json"
archive="outputs/shared-item-catalog-$release.zip"
apk="outputs/arms-and-equipment-guide-${release##*.}-debug.apk"
report="outputs/check-$letter-${release##*.}"
qa_pythonpath=".cache/armory-qa/usr/lib/python3/dist-packages"
if [[ -n "${PYTHONPATH:-}" ]]; then
    qa_pythonpath="$qa_pythonpath:$PYTHONPATH"
fi

python3 scripts/onboard_bg3_item.py catalog/research/bg3-onboarding/*.json \
    --version "$release" --batch-inventory "$inventory"
apps/arms-and-equipment/build.sh "$archive"
cp outputs/arms-and-equipment-guide-debug.apk "$apk"
python3 scripts/check_bg3_batch_sources.py "$archive" "$inventory" \
    --output "$report/source-check.jsonl"

check_device() {
    local serial="$1"
    adb -s "$serial" install -r "$apk"
    adb -s "$serial" shell am force-stop org.completeguide.armory
    adb -s "$serial" shell am start -W -n org.completeguide.armory/.MainActivity
    PYTHONPATH="$qa_pythonpath" python3 scripts/check_all_records.py "$archive" "$apk" \
        --output "$report" --serial "$serial" --batch-inventory "$inventory" --screenshots 3
}

pids=()
for serial in "$@"; do
    check_device "$serial" >"$report/$serial.log" 2>&1 &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
for serial in "$@"; do
    cat "$report/$serial.log"
done
exit "$status"
