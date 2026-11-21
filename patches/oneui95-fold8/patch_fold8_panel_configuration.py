#!/usr/bin/env python3
"""Restore the stock Fold8 Configuration panel field throughout the 9.5 guest."""
from pathlib import Path
import re
import sys

CONFIG = "Landroid/content/res/Configuration;"
PANEL = f"{CONFIG}->semDisplayDeviceType:I"
NIGHT = f"{CONFIG}->nightDim:I"
CHANGE = "0x4000000"


def insert_after(text, anchor, added):
    if text.count(anchor) != 1:
        raise ValueError(f"Unexpected Configuration anchor near {anchor.strip().splitlines()[0]}")
    return text.replace(anchor, anchor + "\n" + added.strip("\n") + "\n\n", 1)


def edit_method(text, signature, edit):
    pattern = re.compile(r"(^\.method [^\n]* " + re.escape(signature) +
                         r"\n)(.*?)(^\.end method)", re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Expected one Configuration.{signature}")
    match = matches[0]
    return text[:match.start(2)] + edit(match[2]) + text[match.end(2):]


def patch_configuration(text):
    def on(signature, anchor, addition):
        nonlocal text
        text = edit_method(text, signature, lambda body: insert_after(body, anchor, addition))

    # Configuration diff/update use Samsung's native CONFIG_DISPLAY_DEVICE_TYPE
    # bit. Undefined deltas carry -1, while 0 is a genuine inner-panel change.
    on("diff(Landroid/content/res/Configuration;ZZ)I", "    :cond_33\n", f"""
    iget p2, p1, {PANEL}
    if-eq p2, p3, :oneos_panel_diff_done
    iget v0, p0, {PANEL}
    if-eq v0, p2, :oneos_panel_diff_done
    const/high16 p2, {CHANGE}
    or-int/2addr v1, p2

    :oneos_panel_diff_done
""")
    on("updateFrom(Landroid/content/res/Configuration;Z)I", "    :cond_28\n", f"""
    iget p2, p1, {PANEL}
    if-eq p2, v2, :oneos_panel_update_done
    iget v1, p0, {PANEL}
    if-eq v1, p2, :oneos_panel_update_done
    const/high16 v1, {CHANGE}
    or-int/2addr v0, v1
    iput p2, p0, {PANEL}

    :oneos_panel_update_done
""")
    on("generateDelta(Landroid/content/res/Configuration;Landroid/content/res/Configuration;)Landroid/content/res/Configuration;",
       "    :cond_1e\n", f"""
    iget v1, p0, {PANEL}
    iget v2, p1, {PANEL}
    if-eq v1, v2, :oneos_panel_delta_done
    iput v2, v0, {PANEL}

    :oneos_panel_delta_done
""")
    on("compareTo(Landroid/content/res/Configuration;)I", "    :cond_26\n", f"""
    iget v2, p0, {PANEL}
    iget v4, p1, {PANEL}
    sub-int/2addr v2, v4
    if-eqz v2, :oneos_panel_compare_done
    return v2

    :oneos_panel_compare_done
""")
    on("hashCode()I",
       f"    iget v0, p0, {NIGHT}\n\n    add-int/2addr v1, v0\n\n    mul-int/lit8 v1, v1, 0x1f\n", f"""
    iget v0, p0, {PANEL}
    add-int/2addr v1, v0
    mul-int/lit8 v1, v1, 0x1f
""")
    on("setTo(Landroid/content/res/Configuration;)V",
       f"    iput v0, p0, {NIGHT}\n", f"""
    iget v0, p1, {PANEL}
    iput v0, p0, {PANEL}
""")
    on("setTo(Landroid/content/res/Configuration;II)V", "    :cond_18\n", f"""
    const/high16 p3, {CHANGE}
    and-int/2addr p3, p2
    if-eqz p3, :oneos_panel_mask_done
    iget p3, p1, {PANEL}
    iput p3, p0, {PANEL}

    :oneos_panel_mask_done
""")
    on("setToDefaults()V", f"    iput v1, p0, {NIGHT}\n",
       f"    iput v1, p0, {PANEL}")
    # Preserve the stock Fold8 position between nightDim and themeSeq.
    on("readFromParcel(Landroid/os/Parcel;)V", f"    iput v0, p0, {NIGHT}\n", f"""
    invoke-virtual {{p1}}, Landroid/os/Parcel;->readInt()I
    move-result v0
    iput v0, p0, {PANEL}
""")
    on("writeToParcel(Landroid/os/Parcel;I)V",
       f"    iget p2, p0, {NIGHT}\n\n    invoke-virtual {{p1, p2}}, Landroid/os/Parcel;->writeInt(I)V\n", f"""
    iget p2, p0, {PANEL}
    invoke-virtual {{p1, p2}}, Landroid/os/Parcel;->writeInt(I)V
""")
    on("toString()Ljava/lang/String;",
       f"    iget v1, p0, {NIGHT}\n\n    invoke-virtual {{v0, v1}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;\n", f"""
    const-string v1, " dt/"
    invoke-virtual {{v0, v1}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    iget v1, p0, {PANEL}
    invoke-virtual {{v0, v1}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
""")
    return text


def patch(root):
    path = root / "smali/android/content/res/Configuration.smali"
    current = path.read_text()
    # The field has precisely three default constructor writes in the pinned donor.
    if current.count(PANEL) != 3:
        raise ValueError("Expected the unported S948BXXU6ZZKN Configuration")
    path.write_text(patch_configuration(current))
    print("smali")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
