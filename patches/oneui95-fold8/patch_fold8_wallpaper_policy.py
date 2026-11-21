#!/usr/bin/env python3
"""Restore stock physical-display wallpaper routing in the 9.5 Fold8 guest."""
from pathlib import Path
import re
import sys


def patch(decoded):
    [rune] = decoded.glob("smali*/com/samsung/android/rune/CoreRune.smali")
    content = rune.read_text()
    if content.count("    move-result-object v2\n\n    sput-object v2, "
                     "Lcom/samsung/android/rune/CoreRune;->FW_PRODUCT_DEVICE:Ljava/lang/String;") != 1:
        raise ValueError("Unexpected donor CoreRune product-device register")
    # v2 still contains ro.product.device at this point. The stock Fold8
    # enables its policy by default and honors this property as an override.
    content, count = re.subn(
        r"^    sput-boolean v4, Lcom/samsung/android/rune/CoreRune;->FW_FOLD_WALLPAPER_POLICY:Z$",
        """\
    const-string/jumbo v0, "h8q"
    invoke-virtual {v0, v2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :oneos_wallpaper_policy_set
    const-string/jumbo v0, "persist.wm.fold.wallpaper_policy"
    invoke-static {v0, v3}, Landroid/os/SystemProperties;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0

    :oneos_wallpaper_policy_set
    sput-boolean v0, Lcom/samsung/android/rune/CoreRune;->FW_FOLD_WALLPAPER_POLICY:Z""",
        content,
        flags=re.M,
    )
    if count != 1:
        raise ValueError("Expected the 9.5 donor's disabled fold wallpaper policy")
    rune.write_text(content)
    print(rune.relative_to(decoded).parts[0])


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
