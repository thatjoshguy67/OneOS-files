# Galaxy Z Fold8 on One UI 9.5

This patch targets OneOS 0.5.32, profile `f8`, and the S26 Ultra GSI
`oneui95-s948b` (S948BXXU6ZZKN). The raw image stays pinned at
`82ddc8561a2687f041c2820a0d910f266b3b71753582a65ebff0cec7e8d0bbe4`.

At the time of this rebase, the upstream 0.5.32 Git tag still pointed to
the 0.5.31 source commit (`5a0e8c3`). The 0.5.32 patch uses the three
session scripts shipped in the official 0.5.32 APK as its source base.

## r24 on OneOS 0.5.33

Apply `oneos-v0.5.33-fold8-r24.patch` to
`e5683cc3da23c8856609875c826119635cc49381`. That is the 0.5.33 source
revision corresponding to the supplied APK. The upstream `v0.5.33` tag
currently points to the previous commit. This patch carries the r24
Fold8 stack onto the release with its new guest storage payloads.

The [r24 payload release](https://github.com/thatjoshguy67/OneOS-files/releases/tag/fold8-oneui95-r24)
contains all eight added or modified files and the complete `oneui95.sha256`
manifest. The patch records their exact download locations and sizes.
Unmodified files use the existing upstream download sources.

Use the release APK's `assets/oneos/sets/oneui95.sha256` to obtain and
verify `services_patched.jar`, `vold_patched` and
`service.incremental_patched.so`. Reuse r24's four Fold8 APKs and its
per-set `OneOSGuest.apk`. Apply the 0.5.33
`switcher/patches/guest_own_vold.py` to r24's
`Fold8OneUI95Services.jar` with `scripts/patch-built-jar.sh`. Apply it
to r24's `framework_patched.jar` through a Python wrapper that passes
`--framework` before the decoded-tree argument. The matching manifests
and guard list pin both rebuilt JARs. Put the files in the
`out/overlays_oneui95_r10` input set and run
`scripts/check-staging-apk.py` on the resulting APK.

Both the default and Fold8 services builds use `gvld`, so selecting
the Fold8 path keeps the release's separate guest storage service.
The new diagnostic gate and the rest of the stock return scripts are
carried forward. The 0.5.33 r24 build booted to Home on the Fold8.
SystemUI and Home stayed up and the stock `vold` and guest `gvld`
registered under separate processes. Returning to stock without
restarting the phone still needs a physical test.

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
12. `oneui95-fold8-panel-parity-v0.5.32.patch`
13. `oneui95-fold8-taskbar-v0.5.32.patch`
14. `oneui95-fold8-tabletop-v0.5.32.patch`
15. `oneui95-fold8-pdi-boot-v0.5.32.patch`
16. `oneui95-fold8-rotation-v0.5.32.patch`
17. `oneui95-fold8-tabletop-control-v0.5.32.patch`
18. `oneui95-fold8-flex-panel-v0.5.32.patch`
19. `oneui95-fold8-cover-and-flex-v0.5.32.patch`
20. `oneui95-fold8-cover-nav-wallpaper-v0.5.32.patch`
21. `oneui95-fold8-wallpaper-registration-v0.5.32.patch`
22. `oneui95-fold8-multitasking-v0.5.32.patch`

The layout patch restores the host's 420 dpi panel records and migrates the
existing guest Home's layout preferences from the stock launcher once.
The stock values observed were 6×8 on the inner workspace and 4×6 on
the cover. Workspace databases, pages and unrelated preferences are preserved. Use OneOS's **Update** on the
existing One UI 9.5 stage to deploy the new set before a test boot. The
staging patch adds the guarded services payload to the root file list so
the updater can receive and verify it.

Build and embed these four assets in the `oneui95` set:

- `Fold8OneUI95Framework.apk`. Build `fold8-framework-rro` with AAPT2, then
  align and sign it. The resource mappings use the values from the stock
  Fold8 framework and its product and vendor overlays. They cover the
  two-panel cutouts, status-bar insets, fold state IDs, close-to-sleep,
  reopen wake states, fold-lock support, unfold transitions and the
  SystemUI posture map for states 0 through 3.
  During guest preparation the resource APK is placed on a private tmpfs
  so overlayfs can use it on the Fold8's casefold-capable storage. The
  stock navigation settings use a 568dp breakpoint, between the
  475dp cover and the 704dp inner display.
- `Fold8OneUI95SystemUI.apk`. Run `patch_fold8_systemui.py` with the original
  S948BXXU6ZZKN SystemUI APK and an output DEX path. Feed the output to
  OneOS's `scripts/apk-replace-dex.py` as `classes.dex`. It restores
  Samsung's wide-fold navigation gate by redirecting only its encoded
  method reference. The old code item is shared with Kotlin's empty-list
  `size()` and iterator methods. The patch selects `LANDSCAPE_FOLD` on the
  phone branch. The existing 9.5 interactor chooses `WALLET` when closed
  and `WIDE_WALLET` when open. In the Fold navigation branch, the existing
  large-window check distinguishes the stock 475 dp cover from the 704 dp
  inner screen, including during configuration changes. Taskbar eligibility
  uses the same check. SystemUI hands the navigation window to Launcher
  using its native remove and restore path because the phone donor lacks
  the Fold window manager's visibility arbitration.
  With Apktool 3.0.3, decode the original donor and run
  `patch_fold8_tabletop_systemui.py <donor.apk> <decoded_donor> <patched.apk> <OneOS/scripts/apk-replace-dex.py> <output.apk>`
  on the Fold8 SystemUI built above. Use the output as the packaged
  Fold8 SystemUI. The patch takes four affected classes out of the
  original DEX container and adds their rebuilt definitions in a
  secondary DEX. It restores stock Quick Settings visibility for
  **Auto rotate when partially folded** on the cover display. The switch
  uses the per-user `tabletop_rotation` system setting, with the stock
  WindowManager default when the setting is absent. The Fold8 runtime
  loaded the rebuilt classes and verified preference registration and
  the view model's display and checked states with an injected fold
  state. Persistence in the guest and real hinge transitions need a
  guest boot check.
- `Fold8OneUI95Services.jar`. Run OneOS's `scripts/patch-built-jar.sh` with the
  guarded `services_patched.jar` pinned at
  `6a23cb67c33f0d30e89f22e057666a91b7dcd18f68738b5b067a3f115dc135ca`,
  `patch_fold8_services.py` and the output JAR path. The patch adds the
  Fold8 panel type in `DisplayContent.onRequestedOverrideConfigurationChanged`.
  It also applies the same panel type while computing the global display
  configuration, where SystemUI reads it. It sets `semDisplayDeviceType=0` on the inner panel (physical port 147)
  and `5` on the cover (port 148) when either panel is the active default
  display. Unknown ports and other logical displays follow the guest's
  existing behavior. It uses `DisplayAddress.getPort()`, which is present
  in the 9.5 boot framework. The patched JAR retains the OneOS guards. Startup
  selects it only for the Fold8 and the pinned donor and validates the
  bound file before starting the guest. Internal display 1 cannot
  host Home or system decorations. External displays retain their
  regular DeX path.
  Apply `patch_fold8_rotation.py` to that rebuilt JAR before packing it.
  It restores the `tabletop_rotation` observer and uses the existing
  half-fold rotation and restoration paths on display 0. The guest
  reads the stock preference default and keeps the cover and flat
  inner screen under their normal rotation policy.
- `Fold8OneUI95Settings.apk`. Run `patch_fold8_settings.py` with the
  original S948BXXU6ZZKN SecSettings APK and an output DEX path. Replace
  `classes.dex` using `scripts/apk-replace-dex.py`. The patch exposes
  the guest's native Continue apps on cover screen page, which reads
  and writes the same fold-lock setting as the stock Fold8 page.

Add the four names and hashes to the live One UI set manifest and supply
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

The 0.5.33 r24 patch shows **Feature flags** on the One UI 9.5 card and
details page for every device that supports this guest. **Dynamic Island
player** is on by default. The choice is saved per system and takes effect
on the next guest boot. When the player is off, the boot script derives and
verifies the temporary APK from the pinned stock or Fold8 SystemUI. The Fold8
variant keeps its Quick Settings and navigation patches.

### Stock firmware audit

The reference is SM-F971B F971BXXS3AZIJ (One UI 9.0). The guest is
S948BXXU6ZZKN (One UI 9.5). Both ship `ro.build.characteristics=phone`.
The Fold8 hardware supplies `ro.config.fold_disp=2448,1848,1248,1972`.
Samsung's panel distinction lives in Android configurations, SystemUI
and Samsung's floating features.

| Area | Finding |
| --- | --- |
| Quick Settings, Home and navigation | The patch supplies the native Fold Home grids (6 × 8 inside and 4 × 6 on the cover), reports panel IDs 0 and 5, and makes taskbar eligibility and navigation handoff use the same active display size. The running guest verified one navigation window on the cover and one taskbar window after opening, with distinct fixed and floating window geometry. The Home panel-ID change and inner widget sizing need a boot of the packaged update. |
| Lock screen, AOD and wallpaper | The feature merge takes `LOCKSCREEN,ROTATIONAL,AOD`, the stock lid/rotatable wallpaper policy and the Fold8 camera-indicator geometry. The overlay restores the stock per-panel cutout and status-bar resources. |
| Samsung Keyboard and half-fold | Both guest feature XMLs get the stock half-fold flag and keyboard fold UX version `81`. The framework overlay declares folded states 0 and 1, half-folded state 2 and open state 3. The guest's physical posture transitions need a device check. |
| Rotation, continuity and window management | The donor compiles out Samsung's separate per-panel rotation, app continuity and freeform-window folding policies. These require ports of the affected call sites. The hardware state and basic fold-lock path are included. |
| Flex Panel and tabletop | The stock framework disables the dedicated panel. The user's Flex Restore module recovers it with framework, Settings and SystemUI hooks. The 9.5 donor uses Android's `DeviceStateProviderImpl` in place of the Samsung posture provider those hooks target. The tabletop patch uses the Fold8 angle sensor for state 2 at the module's 50–135° entry threshold. The services patch restores tabletop rotation behind Samsung's existing setting. The cover Quick Settings switch writes that same setting. The r20 Flex Panel port pairs Samsung’s native panel with an eligible app in the half-open state. |
| Rear-screen and dual-screen modes | The stock framework's concurrent rear-display state is absent from the guest's device-state topology. Its configuration remains a separate port. |
| Boot animation | The guest's Samsung renderer already supports main and sub QMGs. The boot preparation validates the stock inner (2448 × 1848) and cover (1248 × 1972) QMG pairs and mounts them over the guest's media directory. The renderer and the animations still need a physical boot check. |

The set also carries the separate One UI 9.5 experiments for Samsung's
`VOICE` Audio Eraser capability, the stock audio separator value when missing
from the donor, and the existing Now Bar notification test setting in the
guest. Real audio processing and notification behavior require on-device
verification.

PDI 7.4.01.9 uses its own app-private storage fallback when the guest
framework reports Samsung Keep unavailable to the Fold8's Moneta process.
The process, version and model checks leave other callers on the original
framework path. To reproduce the framework payload, apply
`switcher/patches/oneui95_fold8_pdi_framework.py` to the original guarded
`framework_patched.jar` and replace its `classes7.dex`. Package the resulting
JAR with the updated guard manifest. Boot preparation keeps the donor's
Samsung Suggestions APK visible only when its digest and the mounted
framework digest both match. The packaged fallback needs a guest boot check.


### Flex Mode panel

Stock F971BXXS3AZIJ and donor S948BXXU6ZZKN both return unsupported
from WindowManager's Flex Panel app query and discard app-choice writes.
The Fold8's installed Flex Restore module implements these on stock.
The guest port uses the same per-user choice keys and its own settings
provider. The host and donor framework resources have the same Flex app
policy entries. The port reads that resource for native app layouts and
checks each app's launcher activities, resize support and opt-out metadata.
The getter requires Android's task-management permission. The setter requires
permission to write secure settings. Cross-user calls require Android's
cross-user permission.

- Apply `patch_fold8_flex_policy.py` to r19's `Fold8OneUI95Services.jar`
  with `scripts/patch-built-jar.sh`. Set `ANDROID_HOME` to a SDK containing
  the Android 37.0 platform and 37.0.0 build tools. The compile-time declaration
  for Android's hidden ActivityInfo methods stays outside the assembled DEX.
- Run `patch_fold8_flex_settings.py <r19-Fold8OneUI95Settings.apk> <output.dex>`.
  Use `scripts/apk-replace-dex.py` with the original S948BXXU6ZZKN Settings APK
  to package the new `classes.dex`. It enables the native Advanced features
  row and search entry and retains Continue apps on cover screen.
- Run `patch_fold8_flex_systemui.py <donor.apk> <decoded_donor> <r19-Fold8OneUI95SystemUI.apk> <OneOS/scripts/apk-replace-dex.py> <output.apk>`.
  It uses the guest Shell’s existing split pairing and stages the native
  panel as the bottom app. The guest registers for the Fold8 half-open
  posture and listens to app focus, the selected-app policy, IME and shade
  visibility. It schedules automatic opening for apps selected in
  Settings and exposes Samsung’s panel shortcut for other eligible apps.
  The native remote-view path routes the shortcut through navigation and
  taskbar. Closing the phone or unfolding clears the shortcut and
  dismisses the panel.

Fixture tests used the actual donor policy resource and covered app
eligibility, independent user choices and failed writes. On the stock
Fold8, isolated Android runtime probes loaded the rebuilt policy and checked
Settings availability and search. The compiled SystemUI retained all donor
classes, including the previous tabletop patch, and Android loaded the
Flex Panel, split-screen and navigation classes. Hinge-triggered launch,
native panel controls and the visible taskbar shortcut still need a
physical guest run.


### Cover-screen configuration and Flex Panel cleanup

The first r20 boot reproduced a Launcher taskbar alongside SystemUI
navigation in cover mode. The guest WindowManager already records the
physical panel IDs. Its `Configuration` dropped the ID when copying,
merging or parceling it to clients. Apply
`patch_fold8_panel_configuration.py` to the PDI-patched
`framework_patched.jar` with `scripts/patch-built-jar.sh`. The patch
restores Samsung's `CONFIG_DISPLAY_DEVICE_TYPE` bit, the stock
undefined value, and the stock parcel field order. This lets Launcher
and SystemUI receive panel 5 on the cover and panel 0 inside. It uses
their existing separate workspaces and preserves launcher data.

The revised `patch_fold8_flex_systemui.py` builds the r21 SystemUI from
the original donor and the r19 tabletop payload. To reproduce the
intermediate r20 SystemUI, use its source at commit `9e02efa`.
The Flex Activity now disposes the touch receiver and monitor on the
activity looper. The shortcut floats over the bottom half of the inner
display and can be dragged. Samsung's navigation shortcut is available
if the floating window fails to attach. The context refreshes the
position after display changes and hides the shortcut outside Flex posture.

The r21 Configuration copy, delta and parcel paths passed isolated ART
probes on the Fold8. Its Flex cleanup disposed a real temporary input
receiver on the owning looper. Visual cover Home, navigation ownership,
the floating hint, and a full open and close of Flex Panel still require
the user-started r21 guest session.

### Cover navigation and wallpaper

The r21 guest used the dedicated 4×6 cover Home layout. When folded, One UI
Home reported its taskbar hidden but retained its window beside SystemUI's
cover navigation bar. `patch_fold8_home_taskbar.py` removes the launcher
window on the cover configuration callback and guards its style collector
against reattaching it. The inner display retains the native fixed and
floating taskbar paths.

Build `Fold8OneUI95Home.apk` from the original `TouchWizHome_2017.apk`
(One UI Home 18.5.00.113, SHA-256
`97d54eff5d79c5cca53d7c01a7bee20c99b3c74554df1466b91268ee5d9e58da`).
Decode it with `apktool d -r`. Copy the decoded `apktool.yml` and only
`smali_classes3` into a temporary project, naming that directory `smali`.
Pass it to `patch_fold8_home_taskbar.py`, rebuild the project and extract
its `classes.dex`. Use `scripts/apk-replace-dex.py` to place it in the
original APK as `classes3.dex`. The Fold8 guest binds the staged APK over
the exact donor during preparation.

The stock Fold8 uses physical display IDs to pick the Home and lock
wallpaper tokens. The 9.5 guest wrote and drew a replacement cover
wallpaper, but WindowManager selected the inner token on the cover.
Apply `patch_fold8_wallpaper_policy.py` to the r21 `framework_patched.jar`
using `scripts/patch-built-jar.sh`. This enables that existing WindowManager
policy for the Fold8 and keeps Samsung's `persist.wm.fold.wallpaper_policy`
override. It does not need to migrate wallpaper files or change the stock
host's properties. Package the new framework and Home payload and update the
existing One UI 9.5 stage before retesting both displays.

Use the r23 or later framework. The original r22 patch reused a live string register
in `CoreRune.<clinit>`, so ART rejected the class and the guest Zygote
stopped. The r23 helper leaves that register intact. On the Fold8 and an
Android 17 emulator, an isolated ART verifier run reproduced the r22 type
error and cleared it with the r23 initializer. The guest boot and wallpaper
selection still require on-device testing.

For r24, run `scripts/patch-built-jar.sh` with the r23
`Fold8OneUI95Services.jar` and `patch_fold8_wallpaper_tokens.py`. Enabling
fold wallpaper routing exposed an incomplete setter in the phone donor
that threw a null exception during wallpaper service attachment. The
replacement registers the full physical display ID and marks the inner
panel from its Fold8 port while holding the existing WindowManager lock.
An isolated runtime probe on the Fold8 reproduced the r23 null exception
and exercised the r24 setter with the inner and cover IDs and with missing
and non-wallpaper tokens. Rebuild the OneOS package with the updated
services pin before updating the 9.5 stage.

### Three-app split screen and Flex entry

Apply `patch_fold8_multi_split.py` to the r24 `framework_patched.jar` with
`scripts/patch-built-jar.sh`. One UI 9.5 keeps the third-stage organizer,
split divider, rotate, app pair and Natural Switching code but normally
enables its multi-split group only for tablets. The patch includes the
Fold8 in that group without changing the general tablet flag. The native
panel-sensitive split paths use the guest's restored panel configuration.

Build the updated SystemUI with `patch_fold8_flex_systemui.py` and the
original donor and r19 tabletop payload. In r24, the existing primary app
was already in the main split stage when the Flex panel drew. The
transition contained the app's ActivityRecord rather than a top-level
Task change, so Shell aborted the split and the Flex panel closed. The
updated Shell accepts this entry only when the launched Flex activity
and its exact companion match the pending Fold8 request. All other
incomplete split transitions go through Samsung's existing handling.

The rebuilt framework initializer, StageCoordinator and Flex controller
passed isolated ART checks on the Fold8. The three-app layout, drag
rearranging and panel entry still need an interactive guest run.
