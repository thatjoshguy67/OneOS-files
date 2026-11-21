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

## Fold8 SystemUI, Home and Settings identity

- The running guest already exposes `SM-F971B` and `h8q` in its model, device
  and boot properties. Settings also uses a marketing-name feature value.
  Copy the host's **Galaxy Z Fold8** label into both guest feature files.
- Use the Fold8's status-bar placement, lock-screen subdisplay policy and
  camera-indicator geometry. The Fold8's stock build characteristics remain
  `phone`. Its large-screen configuration comes from the display and fold
  features.
- Route One UI's CLOSE and TENT states to the cover, as the host's
  OUTER_PRIMARY device-state configuration specifies. Whichever panel is
  active remains logical display 0. The inactive built-in panel cannot
  request secondary Home or system decorations. This targets the logged
  loop where Samsung's DeX SecondaryLauncher repeatedly exits on an
  internal display. Other displays keep their own settings.
- Samsung's Home build defaults cover mirroring on for Fold devices with a
  first API level of at least 36. Turn off **Cover screen mirroring** in
  Home settings for separate workspaces. The patch leaves the user’s
  launcher data and choice intact.

## Fold8 display density

The first physical boot completed in the Samsung setup wizard with both
panels reporting 213 dpi. Host One UI recorded 420 dpi before the switch.
A live WindowManager override to 420 verified on both panels. The startup
patch now seeds per-panel density defaults before system_server starts and
preserves an existing guest override. The fixture tests cover unique IDs,
port-based IDs, missing native density and existing user choices. The
startup patch needs a physical boot test. Samsung's boot animation sizing
and routing are separate from WindowManager density.

## OneOS guest manager

Both official manager variants declared `com.sec.knox.provider2` for
OxygenOS, and Android rejected the APK because One UI 9.5 already provides
that authority through its `android` package. The One UI variant removes the
conflicting provider declaration and preserves the remaining manager
components. Version 0.13 was installed and resolved to its normal Home entry
in the running Fold8 guest.

To build this variant, run `remove_guest_knox_stub.py` on the official 0.13
`guest_manager.apk`; align and sign the result. Pack it as `OneOSGuest.apk`
in the `oneui95` set and regenerate that set's SHA-256 pin and file index.
The startup patch prefers that set-specific file for S948BXXU6ZZKN.
Other system sets keep the common manager, including the OxygenOS stub.

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

## Bring Apps search and filters

Apply `oneos-v0.5.32.patch` and then `bring-apps-v0.5.32.patch` to upstream
source commit `813cc976475c65dc271f1adfcd6dae566143535c`. The host picker
and guest manager 0.14 search app labels and package names and offer User,
System, and All app filters. The host keeps selections when the view is
filtered. User apps still use the existing APK and data copy.

System entries copy base and split APKs and use the guest's regular package
installer. The guest keeps packages it already has. The live picker uses a
host-owned snapshot of package paths made before handoff. Updated system APKs
under `/data/app` use OneOS's read-only host view during a session.

For the Fold8 test build, build guest manager 0.14, use
`remove_guest_knox_stub.py` on the One UI variant, align and sign it, and
bundle it as `OneOSGuest.apk` in the 9.5 set by its SHA-256. Rebuild the
host with the revised set pin and updated scripts, and verify the result
with `scripts/check-staging-apk.py`.

## Fold8 display, Quick Settings and taskbar

Apply the patches in this order to OneOS source `813cc976475c65dc271f1adfcd6dae566143535c`:

1. `oneos-v0.5.32.patch`
2. `bring-apps-v0.5.32.patch`
3. `oneui95-headline-v0.5.32.patch`
4. `oneui95-fold8-layout-v0.5.32.patch`
5. `oneui95-fold8-ui-modes-v0.5.32.patch`
6. `oneui95-fold8-staging-v0.5.32.patch`
7. `oneui95-feature-flags-v0.5.32.patch`
8. `oneui95-feature-entry-v0.5.32.patch`
9. `oneui95-fold8-boot-fix-v0.5.32.patch`
10. `oneui95-fold8-boot-animation-v0.5.32.patch`
11. `oneui95-systemui-shared-code-v0.5.32.patch`

The layout patch restores the host's 420 dpi panel records and migrates the
existing guest Home's mirroring setting from the host once. Other Home
preferences and workspace data are preserved. Use OneOS's **Update** on the
existing One UI 9.5 stage to deploy the new set before a test boot. The
staging patch adds the guarded services payload to the root file list so
the updater can receive and verify it.

Build and embed these three assets in the `oneui95` set:

- `Fold8OneUI95Framework.apk`. Build `fold8-framework-rro` with AAPT2, then
  align and sign it. The 17 resource mappings use the values from the stock
  Fold8 framework and its product and vendor overlays. They cover the
  two-panel cutouts, status-bar insets, fold state IDs, close-to-sleep,
  reopen wake states, fold-lock support and unfold transitions.
  During guest preparation the resource APK is placed on a private tmpfs
  so overlayfs can use it on the Fold8's casefold-capable storage.
- `Fold8OneUI95SystemUI.apk`. Run `patch_fold8_systemui.py` with the original
  S948BXXU6ZZKN SystemUI APK and an output DEX path. Feed the output to
  OneOS's `scripts/apk-replace-dex.py` as `classes.dex`. It restores
  Samsung's wide-fold navigation gate by redirecting only its encoded
  method reference. The old code item is shared with Kotlin's empty-list
  `size()` and iterator methods. The patch selects `LANDSCAPE_FOLD` on the
  phone branch. The existing 9.5 interactor chooses `WALLET` when closed
  and `WIDE_WALLET` when open.
- `Fold8OneUI95Services.jar`. Run OneOS's `scripts/patch-built-jar.sh` with the
  guarded `services_patched.jar` pinned at
  `6a23cb67c33f0d30e89f22e057666a91b7dcd18f68738b5b067a3f115dc135ca`,
  `patch_fold8_services.py` and the output JAR path. The patch adds the
  Fold8 panel type in `DisplayContent.onRequestedOverrideConfigurationChanged`.
  It sets `semDisplayDeviceType=0` on the inner panel (physical port 147)
  and `5` on the cover (port 148) when either panel is the active default
  display. Unknown ports and other logical displays follow the guest's
  existing behavior. It uses `DisplayAddress.getPort()`, which is present
  in the 9.5 boot framework. The patched JAR retains the OneOS guards. Startup
  selects it only for the Fold8 and the pinned donor and validates the
  bound file before starting the guest.

Add the three names and hashes to the live One UI set manifest and supply
their bytes when building the APK. The test manifest stores the reference
build's hashes. Regenerate the set pin and asset index and run
`scripts/check-staging-apk.py` on the result.

The taskbar preference is seeded once through the guest Settings provider
as `global/task_bar=1`, which matches the stock phone. The native donor code
checks the active panel type, the Home role, unlock and provisioning to
determine availability. The patch keeps all three supported fold-lock
preferences intact on later starts, including Samsung's swipe-to-continue
setting.

### Feature flags

**Feature flags** appears on the Fold8 One UI 9.5 card and near the top
of its system detail page. **Dynamic Island player** is on by default. The choice is saved per
system and takes effect when you next start the guest. When the player is
off, the boot script derives the media-chip variant from the pinned Fold8
SystemUI APK and verifies the result before mounting it. The SystemUI
payload itself and the Fold8 Quick Settings and navigation edits stay the
same in the staged set.

### Stock firmware audit

The reference is SM-F971B F971BXXS3AZIJ (One UI 9.0). The guest is
S948BXXU6ZZKN (One UI 9.5). Both ship `ro.build.characteristics=phone`.
The Fold8 hardware supplies `ro.config.fold_disp=2448,1848,1248,1972`.
Samsung's panel distinction lives in Android configurations, SystemUI
and Samsung's floating features.

| Area | Finding |
| --- | --- |
| Quick Settings, Home and navigation | The fold-aware SystemUI path, configuration panel types, native launcher workspace split and taskbar enablement are included. |
| Lock screen, AOD and wallpaper | The feature merge takes `LOCKSCREEN,ROTATIONAL,AOD`, the stock lid/rotatable wallpaper policy and the Fold8 camera-indicator geometry. The overlay restores the stock per-panel cutout and status-bar resources. |
| Samsung Keyboard and half-fold | Both guest feature XMLs get the stock half-fold flag and keyboard fold UX version `81`. The framework overlay declares folded states 0 and 1, half-folded state 2 and open state 3. The guest's physical posture transitions need a device check. |
| Rotation, continuity and window management | The donor compiles out Samsung's separate per-panel rotation, app continuity and freeform-window folding policies. These require ports of the affected call sites. The hardware state and basic fold-lock path are included. |
| Flex Panel | The stock Fold8 and donor both compile the dedicated Flex Panel gates off. The patch carries the stock half-fold support. |
| Rear-screen and dual-screen modes | The stock framework's concurrent rear-display state is absent from the guest's device-state topology. Its configuration remains a separate port. |
| Boot animation | The guest's Samsung renderer already supports main and sub QMGs. The boot preparation validates the stock inner (2448 × 1848) and cover (1248 × 1972) QMG pairs and mounts them over the guest's media directory. The renderer and the animations still need a physical boot check. |

The set also carries the separate One UI 9.5 experiments for Samsung's
`VOICE` Audio Eraser capability, the stock audio separator value when missing
from the donor, and the existing Now Bar notification test setting in the
guest. Real audio processing and notification behavior require on-device
verification.

PDI's imported APK needs privileged permissions and Samsung Pass storage.
The guest lacks a separate Samsung Pass storage backend, so PDI remains
disabled in the existing stage.
