# Android development on Pop!_OS

## Evidence collected, 2026-11-07

The current host reports `XDG_CURRENT_DESKTOP=COSMIC` and `XDG_SESSION_TYPE=wayland`. `/dev/kvm` exists, but access and emulator acceleration have not yet been tested. `adb` and `emulator` were not found on PATH; the conventional `/home/admin/Android/Sdk` directory was absent. This does not prove no SDK exists elsewhere.

Prior chat reviewed: **Android Emulator Focus Issues**, 2026-10-31, chat ID `6ae55258-bff4-83e8-8003-5e9bf770287e`. The user reported that entering the Android emulator made the Pop!_OS laptop desktop unstable and prevented normal focus changes. The chat ended before a successful fix was confirmed. Do not treat the earlier proposed software rendering workaround as a demonstrated solution. The Jogging app source itself has not been located.

Upstream COSMIC issue #2965 remains open when checked. It documents an emulator transient utility window entering a map/unmap loop through XWayland and stalling the desktop. It is relevant evidence, not proof that the current host has exactly the same defect.

## Testing availability and inference

The user confirmed headless testing is preferred. As of November 7, 2026, the physical tablet is expected in about a week. Proceed with builds, rules tests, storage tests and headless Android checks now; physical-device acceptance remains pending arrival. Do not claim actual tablet performance, printing or Bluetooth validation before then.

The user authorizes cloud inference, local RTX 5080 / LM Studio inference, or a mix. Use local inference for bounded drafts, extraction and explanation rewrites when economical; review candidate output before integration. Keep architecture, rules correctness and final verification with the primary agent. The local helper status check on November 7 returned connection refused at 127.0.0.1:1234; no local inference was performed. An existing launcher is available at `/home/admin/Documents/ChatGPT/LearningAI/local-ai.sh`, but it unloads existing models and must not interrupt another workload.

## Workflow

1. Build and run pure rules/data tests without an emulator.
2. For Android automation, prefer a headless emulator (`-no-window`) to avoid its desktop windows. Check CPU virtualization separately with `emulator -accel-check`; Linux uses KVM. Verify the selected SDK emulator supports the intended GPU mode.
3. Use software graphics when hardware rendering has driver compatibility problems. Current Google documentation lists `-gpu software` and `-gpu swiftshader`; avoid deprecated `swiftshader_indirect`. Software graphics does not by itself fix a compositor window-management bug.
4. Example for an already-created compatible AVD:

   ```sh
   emulator -avd fighter_tablet -no-window -gpu software -no-snapshot -no-audio
   ```

   This is a proposed launch command, not a command tested on this host. Do not create a windowed emulator automatically as a fallback. Headless automation can use ADB screenshots and instrumentation.
5. Test touch, landscape/portrait layout, text scaling, responsiveness, PDF printing and Bluetooth on the actual SM-T290. Emulation is not evidence of physical-device performance or Bluetooth compatibility.
6. If a windowed emulator is necessary, keep the session brief, capture exact emulator/compositor/driver versions and retain a terminal recovery path. To stop one known emulator use `adb -s <emulator-serial> emu kill`; avoid ambiguous targeting when multiple devices are connected. Do not change global Qt or graphics environment settings based on an unverified workaround.

## Device and LineageOS

Target hardware is SM-T290, 8-inch 1280×800. The user may install LineageOS, but has not confirmed its version. Avoid a Google Play Services dependency. Confirm actual API level, supported ABIs, density and memory on-device before finalizing minimum SDK and any native libraries. Keep compatibility with the intended stock OS range where practical. Do not assume the newest available Android release is the installed target.

The supplied LineageOS installation page returned HTTP 403 to the research tool. No flashing instructions or claims about supported LineageOS releases were verified. OS installation is separate from app development.

## Sources

- Google emulator CLI: https://developer.android.com/studio/run/emulator-commandline
- Google acceleration/graphics modes: https://developer.android.com/studio/run/emulator-acceleration
- Google troubleshooting: https://developer.android.com/studio/run/emulator-troubleshooting
- COSMIC report: https://github.com/pop-os/cosmic-comp/issues/2965
- User-supplied device link: https://wiki.lineageos.org/devices/gtowifi/install/
