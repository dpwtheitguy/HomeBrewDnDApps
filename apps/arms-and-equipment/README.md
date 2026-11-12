# Arms and Equipment Guide

First Android app in the Complete Guide collection. Browse and inspect the shared catalog offline. The guide uses original armory art and field-guide typography, with BG3-inspired equipment cards, category tabs, and a pinned inspection panel on wide screens.

## Build and install

Use JDK 17, Python 3.9+, Android SDK Platform 35, and Build Tools 35.0.0. Set `JAVA_HOME` and `ANDROID_HOME` to the installed tools. The build script also recognizes the workspace-local tools under `.cache/android-tools`.

```sh
apps/arms-and-equipment/build.sh
apps/arms-and-equipment/deploy.sh
```

Pass a different shared catalog ZIP as the first argument to pin a newer release. The build validates the input database checksum and derives an FTS4 search index for older Android SQLite versions. The app extracts its pinned database to private storage on first launch and opens it read-only. Field notes are saved separately by stable item ID. Changing the bundled catalog version currently requires building and installing a new APK. The shared catalog itself releases independently.

The APK targets API 34 and declares API 23 as its minimum. Android System WebView is required. There are no Google Play Services dependencies or network permissions. Build 0.4.153 was installed and launched on a physical SM-T290 running LineageOS. API 23 still needs a device check. Allow roughly 400 MiB of private storage for the extracted catalog.

The deploy script selects the sole USB device by default. Pass `--serial SERIAL` for a specific target or `--apk PATH` for a specific built APK. It installs in place and verifies the installed version and foreground activity. For a shorter workstation command, link the script into a directory on your PATH.

```sh
mkdir -p ~/.local/bin
ln -s "$(pwd)/apps/arms-and-equipment/deploy.sh" ~/.local/bin/armory-deploy
armory-deploy
```

Codex can run the same workflow with the [armory-deploy skill](../../docs/skills/armory-deploy/SKILL.md).

## Publish a tester build

Bump the Android version in `AndroidManifest.xml` when preparing a new tester build. Build the APK, run the Android checks on that APK, and commit the tested source. Run `apps/arms-and-equipment/publish-test-build.sh` with the tested APK in `outputs/`. The script updates the public download and SHA-256 checksum on the `android-test-builds` branch. The README download link stays the same.

## Headless testing

Use a tablet AVD and software rendering on Pop!_OS.

```sh
emulator -avd armory_api29 -no-window -gpu swiftshader -no-snapshot -no-audio
adb shell am start -n org.completeguide.armory/.MainActivity
adb exec-out screencap -p > armory-preview.png
```

The Android share sheet accepts either entry text or a generated PDF with field notes. Delivery depends on the share targets installed on the device.

## Visual references

- [AD&D 2e Arms and Equipment Guide, TSR 2123](https://files.spawningpool.net/docs/Vault2.0.-.TTRPG-Gamebooks/Dungeons%20%26%20Dragons%20%5Bmulti%5D/AD%26D%202nd%20Edition/Accessories/DMGR3%20-%20Arms%20and%20Equipment%20Guide.pdf)
- [Baldur’s Gate 3 inventory and equipment reference](https://bg3.wiki/wiki/Options)
- [Shared catalog provenance and license notes](../../catalog/README.md)

The banner was generated with the built-in image tool for this project. Equipment icons and attribution come from the shared catalog.

Banner prompt (built-in image generation)

> Wide landscape banner illustration for an original fantasy arms and equipment field guide. Old tabletop RPG sourcebook interior art, hand-etched sepia ink and drypoint engraving on very dark charcoal stained paper. On the right half a meticulously rendered medieval sallet helmet, crossed swords and a fluted gauntlet on a wooden armorer's workbench, small motes of dust and muted golden raking light. Left half fades into near-black negative space for UI overlay. Fine hatch marks, authentic material textures, dark warm palette, restrained and elegant. No people, text, letters, logos, frames, labels or existing franchise imagery.

## Search defaults and class training

Use **Filters → Save as default** to keep your facets, category, sort order, and grid or list view for later launches. For example, combine **Mystara** with **Rogue · 2024**. Search text stays session-specific. Active filters can be removed individually above the results.

Rogue and Fighter use [2024 base-class training](https://www.dndbeyond.com/sources/dnd/br-2024/character-classes). The filter matches 2024 items with catalog evidence, including documented base equipment for a conversion. It does not evaluate feats, multiclassing, attunement, or character-specific grants.

### Live mirror on Pop!_OS

Keep the Android emulator headless. With scrcpy installed, open a direct video mirror in a separate Wayland window.

```sh
SDL_VIDEODRIVER=wayland scrcpy -s emulator-5580 --no-audio --max-fps=30 --render-driver=software
```

Use the actual ADB serial if the emulator uses a different port. The APK's screens are served from its own assets to Android System WebView. SQLite search runs on a background worker, cancels superseded queries, and retrieves catalog cards from a compact index. The emulator uses a software WebView layer to work around a rendering glitch. Physical devices use the default Android hardware rendering path.

On an item, use **Copy entry** to copy its summary and field notes to the Android clipboard, or long-press the description to select a passage.

## Weapon rules

Weapon inspection displays D&D 2024 source rules and expandable weapon properties and mastery. BG3 weapon records include game damage, range, variant stats, passives, actions and recharge details from the revision-linked supplement. Copy and PDF export include the displayed rules. Source links open through the device's browser.

The BG3 supplement can be refreshed with `python3 scripts/fetch_bg3_weapon_rules.py`. Package the refreshed supplement under a new catalog version. It contains structured game facts and original summaries with revision links. Legacy catalog entries and public-index leads still require source verification or an explicit tabletop conversion.

## Item detail coverage

The shared catalog supplement adds structured rules, acquisition and crafting leads for BG3 equipment and consumables. A separate pinned 2024 SRD spell reference supplies casting time, damage, area and other spell fields for identified scrolls and named spells explicitly cast from 2024 items. 2024 crafting guidelines and original adaptation drafts have their own labels.

Run `python3 scripts/audit_item_details.py` from the workspace root to refresh the [field-by-field audit](../../catalog/reports/ITEM-DETAIL-AUDIT.md). It covers every catalog record and tracks gaps without treating a source link or a keyword match as verified rules.

## Base cost, buy and sell

The Value panel displays all three fields for every catalog item. Expand its pricing basis to see the economy, source or estimate method, unit scope, and quote policy. The APK indexes the versioned pricing supplement in SQLite for offline inspection. Copy entry and PDF export include all three prices.

## Filter testing and shopping

**Filters → Shop by price** accepts a minimum or maximum base buy price in gp. It combines with the source, category, and other facets. **About this app → Visit Blinsky’s Toys** opens the six priced toys from the adventure's Vallaki shop. The basket tracks quantities and a total for the current session.

Use `python3 apps/arms-and-equipment/tests/filter_matrix.py` with `websocket-client` installed and a debug build running on the headless emulator. The runner compares the rendered Android search results against the shared catalog and exercises the hidden shop.

The weapon-profile supplement covers every record classified as a weapon. It keeps native BG3 and D&D 2024 rules, identifies usable 2024 base weapon comparisons for legacy records, and labels unresolved weapon families with a provisional improvised profile for DM review. A draft profile does not verify a legacy weapon's bonuses or special powers. Generate it with `python3 scripts/build_weapon_profiles.py` before packaging a new catalog release.
