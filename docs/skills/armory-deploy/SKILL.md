---
name: armory-deploy
description: Install a built Arms and Equipment Guide APK on the user's connected Android device and verify its version and launch. Use when the user asks to deploy, update, or release the app to their tablet.
---

Run `armory-deploy` from the workstation or `apps/arms-and-equipment/deploy.sh` from the repository. The default APK is the local Armory build in `outputs/`. Pass `--apk PATH` if deploying a specific artifact. Match the artifact to the requested tested release, using its published checksum when deploying from GitHub. Building, publishing, and installing are distinct actions.

With one USB device connected, the command selects it automatically even if emulators are running. Use `adb devices -l` and `--serial SERIAL` if there are multiple devices or the user named a particular target. The Galaxy Tab A 8.0 reports SM-T290 or SM_T290 and LineageOS can report product `lineage_gtowifi`. Device serials come from ADB. Never infer a target from model alone when multiple matching devices are connected.

The script checks package identity, installs in place, compares installed and expected versions, and launches the app. Report the device, version, and whether the foreground check passed. If ADB reports unauthorized, the tablet must accept USB debugging. A signature mismatch or downgrade requires the matching update artifact. Keep existing app data and ask before any uninstall or data reset.
