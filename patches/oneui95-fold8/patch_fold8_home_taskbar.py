#!/usr/bin/env python3
"""Detach the 9.5 One UI Home taskbar when the Fold8 cover display takes over."""
from pathlib import Path
import sys


def replace_once(content, old, new):
    if content.count(old) != 1:
        raise ValueError(f"Expected one launcher anchor near {old.strip().splitlines()[0]}")
    return content.replace(old, new, 1)


def patch(dex_dir):
    controller = dex_dir / "cg/o0.smali"
    callback = dex_dir / "cg/f0.smali"
    collector = dex_dir / "cg/i0.smali"
    # Panel 5 is the cover on logical display 0. The inner display and external
    # displays keep the native fixed/floating taskbar paths.
    teardown = replace_once(controller.read_text(), ".method public final r()V\n", """\
.method public final removeTaskbarForCover(Landroid/content/res/Configuration;)Z
    .locals 2

    iget v0, p1, Landroid/content/res/Configuration;->semDisplayDeviceType:I
    const/4 v1, 0x5
    if-ne v0, v1, :other_display
    iget-object v0, p0, Lcg/o0;->a:Landroid/content/Context;
    invoke-virtual {v0}, Landroid/content/Context;->getDisplayId()I
    move-result v0
    if-nez v0, :other_display

    iget-object v0, p0, Lcg/o0;->A:Landroid/view/ViewGroup;
    if-eqz v0, :cover
    invoke-virtual {p0}, Lcg/o0;->r()V

    :cover
    const/4 v0, 0x1
    return v0

    :other_display
    const/4 v0, 0x0
    return v0
.end method

.method public final r()V
""")
    config_change = replace_once(
        callback.read_text(),
        "    check-cast p0, Lcg/o0;\n\n    iget-object v2, p0, Lcg/o0;->w:Ljava/lang/String;",
        """\
    check-cast p0, Lcg/o0;

    invoke-virtual {p0, p1}, Lcg/o0;->removeTaskbarForCover(Landroid/content/res/Configuration;)Z
    move-result v2
    if-eqz v2, :oneos_inner_config
    return-void

    :oneos_inner_config
    iget-object v2, p0, Lcg/o0;->w:Ljava/lang/String;""",
    )
    # The style collector can run after the last configuration callback. Check
    # its current resources before it can recreate the taskbar on the cover.
    style_change = replace_once(
        collector.read_text(),
        "    if-eqz v2, :cond_10\n\n    const/4 v2, 0x0\n",
        """\
    if-eqz v2, :cond_10

    iget-object v11, v8, Lcg/o0;->a:Landroid/content/Context;
    invoke-virtual {v11}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v11
    invoke-virtual {v11}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
    move-result-object v11
    invoke-virtual {v8, v11}, Lcg/o0;->removeTaskbarForCover(Landroid/content/res/Configuration;)Z
    move-result v11
    if-nez v11, :cond_c

    const/4 v2, 0x0
""",
    )
    controller.write_text(teardown)
    callback.write_text(config_change)
    collector.write_text(style_change)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
