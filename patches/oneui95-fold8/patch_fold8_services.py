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
PANEL_TYPE = """\
    iget-boolean v0, p0, Lcom/android/server/wm/DisplayContent;->isDefaultDisplay:Z

    if-eqz v0, :oneos_fold8_panel_done

    iget-object v0, p0, Lcom/android/server/wm/DisplayContent;->mDisplayInfo:Landroid/view/DisplayInfo;

    iget-object v0, v0, Landroid/view/DisplayInfo;->address:Landroid/view/DisplayAddress;

    instance-of v1, v0, Landroid/view/DisplayAddress$Physical;

    if-eqz v1, :oneos_fold8_panel_done

    check-cast v0, Landroid/view/DisplayAddress$Physical;

    invoke-virtual {v0}, Landroid/view/DisplayAddress$Physical;->getPort()I

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
    iput v0, p1, Landroid/content/res/Configuration;->semDisplayDeviceType:I

    :oneos_fold8_panel_done
"""


def patch(root):
    section = root / "smali_classes2"
    path = section / "com/android/server/wm/DisplayContent.smali"
    text = path.read_text()
    if text.count(ANCHOR) != 1 or ":oneos_fold8_" in text:
        raise ValueError("DisplayContent does not match the pinned guarded services JAR")
    before, first_instruction = ANCHOR.rsplit("\n", 1)
    path.write_text(text.replace(ANCHOR, before + PANEL_TYPE + first_instruction, 1))
    print(section.name)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
