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
    # The donor still needs v0 after this section. Use v2 for the result:
    # it holds ro.product.device, already saved in FW_PRODUCT_DEVICE, and
    # the next use below is a move-result-object that replaces its value.
    content, count = re.subn(
        r"^    sput-boolean v4, Lcom/samsung/android/rune/CoreRune;->FW_FOLD_WALLPAPER_POLICY:Z\n"
        r"(?=\s*\.line 689\n.*?\.line 708\n[^\n]+\n\s*move-result-object v2$)",
        """\
    invoke-static {v2}, Lcom/samsung/android/rune/CoreRune;->useFoldWallpaperPolicy(Ljava/lang/String;)Z
    move-result v2
    sput-boolean v2, Lcom/samsung/android/rune/CoreRune;->FW_FOLD_WALLPAPER_POLICY:Z
""",
        content,
        flags=re.M | re.S,
    )
    if count != 1:
        raise ValueError("Expected the 9.5 donor's disabled fold wallpaper policy")
    # Match the stock Fold8's enabled default and optional property override.
    rune.write_text(content + """
.method private static useFoldWallpaperPolicy(Ljava/lang/String;)Z
    .locals 2

    const-string/jumbo v0, "h8q"
    invoke-virtual {v0, p0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :done

    const-string/jumbo v0, "persist.wm.fold.wallpaper_policy"
    const/4 v1, 0x1
    invoke-static {v0, v1}, Landroid/os/SystemProperties;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0

    :done
    return v0
.end method
""")
    print(rune.relative_to(decoded).parts[0])


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
