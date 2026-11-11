#!/usr/bin/env bash
# Publish the already-tested APK from the current source commit.
set -euo pipefail

app_dir="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$app_dir/../.." && pwd)"
cd "$root"
apk="${1:-$root/outputs/arms-and-equipment-guide-debug.apk}"
branch=android-test-builds
name=arms-and-equipment-guide-latest-debug.apk

unzip -tq "$apk"
source_commit="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Commit the tested source changes before publishing the APK." >&2
    exit 1
fi

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
export GIT_INDEX_FILE="$stage/index"
git fetch --no-tags origin "refs/heads/$branch"
parent="$(git rev-parse FETCH_HEAD)"
git read-tree "$parent"

apk_blob="$(git hash-object -w "$apk")"
checksum="$(sha256sum "$apk" | cut -d' ' -f1)"
checksum_blob="$(printf '%s  %s\n' "$checksum" "$name" | git hash-object -w --stdin)"
git update-index --add --cacheinfo "100644,$apk_blob,$name"
git update-index --add --cacheinfo "100644,$checksum_blob,$name.sha256"
tree="$(git write-tree)"

if [[ "$tree" != "$(git rev-parse "$parent^{tree}")" ]]; then
    commit="$(git commit-tree "$tree" -p "$parent" -m "Publish Android test APK from $source_commit")"
    git push origin "$commit:refs/heads/$branch"
fi
printf 'Published SHA-256 %s\n' "$checksum"
