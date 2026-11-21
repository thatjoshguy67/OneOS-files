#!/usr/bin/env python3
"""Connect Samsung's tabletop rotation setting to the donor's half-fold policy."""
from pathlib import Path
import sys

DISPLAY = "Lcom/android/server/wm/DisplayRotation;"
FOLD = DISPLAY[:-1] + "$FoldController;"
STATE = "Lcom/android/server/wm/DeviceStateController$DeviceStateEnum;"
DEFAULT_DISPLAY = f"{DISPLAY}->isDefaultDisplay:Z"
CONTROLLER = f"{DISPLAY}->mFoldController:{FOLD}"
MODE = f"{DISPLAY}->mTabletopRotationMode:I"
ALLOWED = f"{DISPLAY}->oneosTabletopRotationAllowed()Z"
ACTIVE = f"{DISPLAY}->oneosTabletopRotationActive()Z"
REFRESH = f"{DISPLAY}->updateOrientationListenerLw()V"

TABLETOP_SETTING = """\
    const-string/jumbo v9, "tabletop_rotation"

    invoke-static {v9}, Landroid/provider/Settings$System;->getUriFor(Ljava/lang/String;)Landroid/net/Uri;

    move-result-object v9

    invoke-virtual {v2, v9, v8, v1, v7}, Landroid/content/ContentResolver;->registerContentObserver(Landroid/net/Uri;ZLandroid/database/ContentObserver;I)V

"""

READ_MODE = f"""\
    const-string/jumbo v7, "tabletop_rotation"

    invoke-static {{v0, v7, v4, v3}}, Landroid/provider/Settings$System;->getIntForUser(Landroid/content/ContentResolver;Ljava/lang/String;II)I

    move-result v7

    if-eqz v7, :oneos_tabletop_locked

    move v7, v5

    goto :oneos_tabletop_apply

    :oneos_tabletop_locked
    move v7, v4

    :oneos_tabletop_apply
    iget v8, p0, {MODE}

    if-eq v8, v7, :oneos_tabletop_mode_read

    iput v7, p0, {MODE}

    move v2, v4

    move v6, v4

    :oneos_tabletop_mode_read
"""

HELPERS = f"""\
.method public final oneosTabletopRotationAllowed()Z
    .locals 1

    # Keep the native FoldController and its resource override. For this
    # guest's built-in display also honor Samsung's setting (0 means free).
    iget-object v0, p0, {CONTROLLER}
    if-eqz v0, :oneos_no_tabletop
    iget-boolean v0, v0, {FOLD}->mAllowHalfFoldAutoRotationOverride:Z
    if-nez v0, :oneos_allow_tabletop
    iget-boolean v0, p0, {DEFAULT_DISPLAY}
    if-eqz v0, :oneos_no_tabletop
    iget v0, p0, {MODE}
    if-nez v0, :oneos_no_tabletop

    :oneos_allow_tabletop
    const/4 v0, 0x1
    return v0

    :oneos_no_tabletop
    const/4 v0, 0x0
    return v0
.end method

.method private oneosTabletopRotationActive()Z
    .locals 2

    invoke-virtual {{p0}}, {ALLOWED}
    move-result v0
    if-eqz v0, :oneos_tabletop_not_active

    iget-object v0, p0, {CONTROLLER}
    iget-object v0, v0, {FOLD}->mDeviceStateEnum:{STATE}
    sget-object v1, {STATE}->HALF_FOLDED:{STATE}
    if-ne v0, v1, :oneos_tabletop_not_active
    const/4 v0, 0x1
    return v0

    :oneos_tabletop_not_active
    const/4 v0, 0x0
    return v0
.end method
"""


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError(f"Unexpected donor rotation code near {old.splitlines()[0]!r}")
    return text.replace(old, new)


def patch_display(text):
    before_camera_observer = '    const-string/jumbo v9, "camera_autorotate"\n'
    text = replace(text, before_camera_observer, TABLETOP_SETTING + before_camera_observer)

    update_listener = f"    :cond_4\n    if-eqz v2, :cond_5\n\n    invoke-virtual {{p0}}, {REFRESH}"
    text = replace(text, update_listener, "    :cond_4\n" + READ_MODE + update_listener.removeprefix("    :cond_4\n"))

    native_choice = (
        f"    :cond_2\n    :goto_1\n    iget-object p1, p0, {CONTROLLER}\n\n"
        + "    if-eqz p1, :cond_5\n"
    )
    text = replace(text, native_choice,
        f"    :cond_2\n    :goto_1\n    invoke-direct {{p0}}, {ACTIVE}\n\n"
        "    move-result v0\n\n    if-nez v0, :cond_4\n\n"
        + native_choice.split("    :goto_1\n", 1)[1])

    native_orientation = f"    if-eqz v4, :cond_1b\n\n    iget-object v10, v0, {CONTROLLER}\n"
    text = replace(text, native_orientation,
        f"    if-eqz v4, :cond_1b\n\n    invoke-direct {{v0}}, {ACTIVE}\n\n"
        f"    move-result v10\n\n    if-nez v10, :cond_1b\n\n    iget-object v10, v0, {CONTROLLER}\n")

    sensor_support = (
        f"    :cond_d\n    iget v1, v0, {DISPLAY}->mUserRotationMode:I\n\n"
        f"    iget-boolean v2, v0, {DISPLAY}->mSupportAutoRotation:Z"
    )
    text = replace(text, sensor_support, sensor_support +
        f"\n\n    invoke-direct {{v0}}, {ACTIVE}\n\n    move-result v5\n\n    if-nez v5, :cond_e")

    # Revert an override that really occurred even if the user switched
    # tabletop rotation off before unfolding.
    revert = f"    iget-boolean v9, v8, {FOLD}->mAllowHalfFoldAutoRotationOverride:Z\n\n    if-eqz v9, :cond_8"
    text = replace(text, revert,
        f"    iget v9, v8, {FOLD}->mHalfFoldSavedRotation:I\n\n    if-ltz v9, :cond_8")
    return text + "\n" + HELPERS


def patch_controller(text):
    save_rotation = (
        "    if-eq v4, v6, :cond_2\n\n"
        f"    iget-object v4, v3, {DISPLAY}->mDisplayContent:Lcom/android/server/wm/DisplayContent;"
    )
    text = replace(text, save_rotation,
        f"    if-eq v4, v6, :cond_2\n\n    invoke-virtual {{v3}}, {ALLOWED}\n\n"
        "    move-result v4\n\n    if-eqz v4, :cond_2\n\n"
        + save_rotation.split("\n\n", 1)[1])
    rotation = (
        f"    iget-object v0, v3, {DISPLAY}->mService:Lcom/android/server/wm/WindowManagerService;\n\n"
        "    invoke-virtual {v0, v5, v5}, Lcom/android/server/wm/WindowManagerService;->updateRotationUnchecked(ZZ)V"
    )
    return replace(text, rotation, f"    invoke-virtual {{v3}}, {REFRESH}\n\n" + rotation, count=2)


def patch(root):
    section = root / "smali_classes2"
    display = section / "com/android/server/wm/DisplayRotation.smali"
    controller = display.with_name("DisplayRotation$FoldController.smali")
    display_text = patch_display(display.read_text())
    controller_text = patch_controller(controller.read_text())
    display.write_text(display_text)
    controller.write_text(controller_text)
    print(section.name)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
