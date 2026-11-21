# Galaxy Z Fold8 on One UI 9.5

This patch targets OneOS 0.5.32, profile `f8`, and the S26 Ultra GSI
`oneui95-s948b` (S948BXXU6ZZKN). The raw image stays pinned at
`82ddc8561a2687f041c2820a0d910f266b3b71753582a65ebff0cec7e8d0bbe4`.

At the time of this rebase, the upstream 0.5.32 Git tag still pointed to
the 0.5.31 source commit (`5a0e8c3`). The 0.5.32 patch uses the three
session scripts shipped in the official 0.5.32 APK as its source base.

## Boot recovery

The retained Nov 19 takeover log records that zygote started at 07:53:03.
The recovery log records that zygote and system_server disappeared and the
watchdog returned to One UI. With full session logs disabled, the original
Java exception was unavailable. The stage still used OneOS 0.5.23 and the
early One UI 9.5 services JAR:

| Payload | SHA-256 |
| --- | --- |
| Services JAR in the failed stage | `53a6ec956bcbd980ac29eeb341a2830367f77f31b79a540c8fc8ad91b287d4c2` |
| Services JAR pinned by OneOS 0.5.32 | `6a23cb67c33f0d30e89f22e057666a91b7dcd18f68738b5b067a3f115dc135ca` |
| Guards pinned by OneOS 0.5.32 | `94edbc636284afedaecd020b56a0014981cfd6b769251b3226a338fd20eaa712` |

The Fold8's vendor SELinux policy contains a package-only signer stanza. The
old guest parser ignores the package entries and rejects the resulting empty
signer. The current pinned services JAR skips an empty signer and still rejects
a signer containing both a default label and package labels. That matches the
[0.5.27 Fold8 fix](https://github.com/fahadalijaved/OneOS/blob/v0.5.31/changelog.md)
and explains the retained symptoms, though the old session's missing logcat
prevents a definitive attribution. On the official app, use **Update** on the
One UI 9.5 system to refresh the stage before testing. Enable **Full session logs**
for a new trial.

## Foldable and AI changes

- One UI Home 18.5.00.113 checks the Fold and Landscape Fold flags at startup.
  It uses them to expose the native cover workspace, separate cover and inner
  layouts, and its wide inner layout. Turn off **Cover screen mirroring** in
  Home settings if the launcher initializes with it enabled. Its existing
  workspace and mirroring preferences are left to the launcher.
- The guest also takes the Fold8's half-fold support, taskbar flag, lid-aware
  lock-screen wallpaper styles and fold-specific keyboard version. It keeps
  the real Fold8 model and uses the existing OneOS paths for panel IDs, device
  states and touch. The Fold8 already supplies `ro.config.fold_disp=2448,1848,1248,1972`,
  `ro.product.first_api_level=37` and `ro.build.characteristics=phone`.
- For this guest session, `ro.build.version.sep` takes the donor value
  `180500`. The 9.5 framework reads this property for
  `Build.VERSION.SEM_PLATFORM_INT`, and One UI Home reads it directly. A
  version of `180000` would leave some 9.5 checks on the One UI 9.0 path,
  including the version check in Vex OCR. OneOS saves and restores the host
  value with its existing session override mechanism.
- The guest reports AI version 20271 or higher in both Samsung feature XMLs.
  The research found generation checks for Browser, AI Plan, SmartThings
  notification summaries and selected Phone/Call Assist paths. The system also
  adds the `DOC_TYPE_DETECTOR` solution for the Notes ProScan eligibility check
  when the GSI includes Vex Scanner. This leaves app installation, scanner
  models, service eligibility and CSC/account checks to the native apps.

## Fold8 display density

The first physical boot completed in the Samsung setup wizard with both
panels reporting 213 dpi. Host One UI recorded 420 dpi before the switch.
A live WindowManager override to 420 verified on both panels. The startup
patch now seeds per-panel density defaults before system_server starts and
preserves an existing guest override. The fixture tests cover unique IDs,
port-based IDs, missing native density and existing user choices. The
startup patch needs a physical boot test. Samsung's boot animation sizing
and routing are separate from WindowManager density.

## Build and verification

For 0.5.32, extract `guest_prepare.sh`, `guest_props.sh` and
`guest_start.sh` by hash from
the official APK's `assets/oneos/sets/scripts.sha256` and
`assets/oneos/files/`. Put them in `switcher/assets/`, then apply the patch:

```sh
git apply /path/to/OneOS-files/patches/oneui95-fold8/oneos-v0.5.32.patch
python3 /path/to/OneOS-files/patches/oneui95-fold8/test_features.py .
python3 /path/to/OneOS-files/patches/oneui95-fold8/test_density.py .
```

The 0.5.32 APK was rebuilt from the official APK with the three patched
scripts, updated content hashes and size index, and regenerated script
manifest pins in both BuildConfig and AppAssets. The other release assets
and the root script were retained. The official 9.5 set still carries the
same services JAR and adds its own A-series camera payload.

For the older 0.5.31 patch, with upstream tag `v0.5.31` checked out:

```sh
git apply /path/to/OneOS-files/patches/oneui95-fold8/oneos-v0.5.31.patch
python3 /path/to/OneOS-files/patches/oneui95-fold8/test_features.py .
scripts/build-guest-manager.sh --debug
cd app-android
./gradlew :app:assembleFullDebug
```

Android normally requires matching signing certificates for an in-place
update. The 0.5.31 contributor channel accepts only its listed package payload roles.
These changes go through the app's hashed session scripts. The patched APK
uses the official release's boot-fix payloads and app guards.

Validation covers the exact Home APK's feature checks, the pinned framework fix,
the feature XML merge with Fold8 and donor inputs, fixture tests for scope,
property restoration values and fallbacks, and the app's staging integrity audit. The base patched APK reached the guest's setup wizard on the Fold8.
Touch across fold transitions, the two Home layouts, AI feature behavior,
and density defaults on a subsequent boot still need a Fold8 trial.
