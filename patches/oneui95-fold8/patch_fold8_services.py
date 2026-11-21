#!/usr/bin/env python3
"""Restore SM-F971B panel types in the pinned S948BXXU6ZZKN guarded services JAR."""
from pathlib import Path
import sys

CLASS = "Lcom/android/server/wm/DisplayContent;"
METHOD = ".method public final onRequestedOverrideConfigurationChanged(Landroid/content/res/Configuration;)V"
ANCHOR = (
    f"{METHOD}\n"
    "    .locals 6\n\n"
    f"    iget-object v0, p0, {CLASS}->mUdcCutoutPolicy:Lcom/android/server/wm/UdcCutoutPolicy;"
)
PANEL_TYPE_METHOD = """\
.method private oneosApplyFold8PanelType(Landroid/view/DisplayInfo;Landroid/content/res/Configuration;)V
    .locals 2

    iget-boolean v0, p0, Lcom/android/server/wm/DisplayContent;->isDefaultDisplay:Z

    if-eqz v0, :oneos_fold8_panel_done

    if-eqz p1, :oneos_fold8_panel_done

    iget-object v0, p1, Landroid/view/DisplayInfo;->address:Landroid/view/DisplayAddress;

    if-eqz v0, :oneos_fold8_panel_done

    invoke-virtual {v0}, Landroid/view/DisplayAddress;->getPort()I

    move-result v0

    # F971BXXS3AZIJ: port 147 is the inner panel, port 148 the cover.
    const/16 v1, 0x93

    if-ne v0, v1, :oneos_fold8_cover

    const/4 v0, 0x0

    goto :oneos_fold8_set_type

    :oneos_fold8_cover
    const/16 v1, 0x94

    if-ne v0, v1, :oneos_fold8_panel_done

    const/4 v0, 0x5

    :oneos_fold8_set_type
    iput v0, p2, Landroid/content/res/Configuration;->semDisplayDeviceType:I

    :oneos_fold8_panel_done
    return-void
.end method

"""


PANEL_TYPE_CALL = (
    f"    invoke-direct {{p0, v0, p1}}, {CLASS}"
    "->oneosApplyFold8PanelType(Landroid/view/DisplayInfo;Landroid/content/res/Configuration;)V\n\n"
)
COMPUTE = (
    ".method public final computeScreenConfiguration(Landroid/content/res/Configuration;)V\n"
    "    .locals 14\n\n"
    f"    invoke-virtual {{p0, p1}}, {CLASS}"
    "->updateDisplayAndOrientation(Landroid/content/res/Configuration;)Landroid/view/DisplayInfo;\n\n"
    "    move-result-object v0\n\n"
)


INACTIVE_INTERNAL = """\
    iget-boolean v0, p0, Lcom/android/server/wm/DisplayContent;->isDefaultDisplay:Z

    if-nez v0, :oneos_fold8_keep_display_policy

    iget-object v0, p0, Lcom/android/server/wm/DisplayContent;->mDisplayInfo:Landroid/view/DisplayInfo;

    if-eqz v0, :oneos_fold8_keep_display_policy

    iget v0, v0, Landroid/view/DisplayInfo;->type:I

    const/4 v1, 0x1  # Display.TYPE_INTERNAL

    if-ne v0, v1, :oneos_fold8_keep_display_policy

    const/4 v0, 0x0

    return v0

    :oneos_fold8_keep_display_policy
"""

DISPLAY_POLICIES = (
    (".method public final isHomeSupported()Z\n    .locals 4\n\n"
     "    iget-object v0, p0, Lcom/android/server/wm/WindowContainer;->mWmService"),
    (".method public final isSystemDecorationsSupported()Z\n    .locals 2\n\n"
     "    iget v0, p0, Lcom/android/server/wm/DisplayContent;->mDisplayId:I"),
)


def patch(root):
    section = root / "smali_classes2"
    path = section / "com/android/server/wm/DisplayContent.smali"
    text = path.read_text()
    if text.count(ANCHOR) != 1 or ":oneos_fold8_" in text:
        raise ValueError("DisplayContent does not match the pinned guarded services JAR")
    before, first_instruction = ANCHOR.rsplit("\n", 1)
    text = text.replace(ANCHOR, before +
        f"    iget-object v0, p0, {CLASS}->mDisplayInfo:Landroid/view/DisplayInfo;\n\n" +
        PANEL_TYPE_CALL + first_instruction, 1)
    if text.count(COMPUTE) != 1:
        raise ValueError("Global display configuration does not match the pinned services JAR")
    text = text.replace(COMPUTE, COMPUTE + PANEL_TYPE_CALL, 1)
    text += "\n" + PANEL_TYPE_METHOD
    for policy in DISPLAY_POLICIES:
        if text.count(policy) != 1:
            raise ValueError("Display policy does not match the pinned guarded services JAR")
        before, first_instruction = policy.rsplit("\n", 1)
        text = text.replace(policy, before + INACTIVE_INTERNAL + first_instruction, 1)
    path.write_text(text)
    print(section.name)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
