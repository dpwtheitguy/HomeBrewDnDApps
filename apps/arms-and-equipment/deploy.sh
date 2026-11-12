#!/usr/bin/env bash
# Install an already-built Armory APK on a connected Android device.
set -euo pipefail

script_dir="$(dirname "$(readlink -f "$0")")"
root="$(cd "$script_dir/../.." && pwd)"
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$root/.cache/android-tools/sdk}}"
package=org.completeguide.armory
activity="$package/.MainActivity"
apk="$root/outputs/arms-and-equipment-guide-debug.apk"
serial="${ANDROID_SERIAL:-}"

usage() {
    printf 'Usage: %s [--serial SERIAL] [--apk PATH]\n' "${0##*/}"
    printf 'Defaults to the sole USB device and the local Armory build.\n'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --serial|--apk)
            if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then usage >&2; exit 2; fi
            if [[ "$1" == --serial ]]; then serial="$2"; else apk="$2"; fi
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

adb="${ADB:-$(command -v adb || printf '%s/platform-tools/adb' "$sdk")}"
if [[ ! -f "$apk" ]]; then
    printf 'APK missing: %s\n' "$apk" >&2
    exit 1
fi

aapt2="${AAPT2:-${ARMORY_BUILD_TOOLS:-$sdk/build-tools/35.0.0}/aapt2}"
if [[ ! -x "$aapt2" ]]; then aapt2="$(command -v aapt2 || printf '%s/build-tools/android-15/aapt2' "$sdk")"; fi
badging="$("$aapt2" dump badging "$apk")"
apk_version="$(awk -F"'" -v package="$package" '/^package:/ && $2 == package {print $6; exit}' <<< "$badging")"
if [[ -z "$apk_version" ]]; then
    printf 'Expected an Armory APK with a version name: %s\n' "$apk" >&2
    exit 1
fi

if [[ -z "$serial" ]]; then
    if ! serial="$("$adb" -d get-serialno)"; then
        printf 'Connect one USB device or pass --serial.\n' >&2
        exit 1
    fi
fi
target=("$adb" -s "$serial")
[[ "$("${target[@]}" get-state)" == device ]]
model="$("${target[@]}" shell getprop ro.product.model)"
printf 'Deploying %s to %s (%s)\n' "$apk" "$model" "$serial"

# A failed update leaves the existing installation in place.
"${target[@]}" install -r "$apk"
installed="$("${target[@]}" shell dumpsys package "$package")"
version="$(awk -F= '/^[[:space:]]*versionName=/{print $2; exit}' <<< "$installed")"
if [[ "$version" != "$apk_version" ]]; then
    printf 'Expected Armory %s, found %s.\n' "$apk_version" "${version:-no installed version}" >&2
    exit 1
fi
printf 'Installed Armory %s\n' "$version"
"${target[@]}" shell am start -W -n "$activity"

for attempt in {1..10}; do
    activities="$("${target[@]}" shell dumpsys activity activities)"
    if awk -v package="$package" '/[rR]esumedActivity/ && index($0, package "/") {found=1} END {exit !found}' <<< "$activities"; then
        printf 'Armory is in the foreground.\n'
        exit 0
    fi
    sleep 1
done
printf 'Armory %s is installed. The foreground activity could not be verified.\n' "$version" >&2
exit 1
