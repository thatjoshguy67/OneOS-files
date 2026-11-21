#!/usr/bin/env python3
"""Enable the donor's existing multi-split stack for the Fold8."""
from pathlib import Path
import sys

RUNE = "Lcom/samsung/android/rune/CoreRune;"
FOLD_OPTIONS = (
    "MW_MULTI_SPLIT_FOR_COVER_DISPLAY",
    "MW_MULTI_SPLIT_DIVIDER_SIZE_FOLD",
    "MW_MULTI_SPLIT_FOLDING_POLICY",
    "MW_MULTI_SPLIT_APP_PAIR_FOLDING_POLICY",
    "MW_MULTI_SPLIT_FOLDING_DIVISION_POLICY",
    "MW_SPLIT_CONTINUITY_MODE",
)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Unexpected multi-split anchor near {old.strip()}")
    return text.replace(old, new, 1)


def patch(decoded):
    [rune] = decoded.glob("smali*/com/samsung/android/rune/CoreRune.smali")
    text = rune.read_text()
    start = text.index(".method static constructor blacklist <clinit>()V")
    end = text.index(".end method", start)
    body = text[start:end]
    body = replace_once(body, "    .locals 20\n", "    .locals 21\n")
    anchor = f"    sput-boolean v11, {RUNE}->MW_MULTI_SPLIT:Z\n"
    body = replace_once(body, anchor, f"""\
    invoke-static {{}}, {RUNE}->isFold8MultiSplit()Z
    move-result v20
    or-int v11, v11, v20

{anchor}""")
    # Follow the Fold8's cover snap, divider sizing, and panel-change policy.
    # Keep the guest's native tablet test outside this block.
    for option in FOLD_OPTIONS:
        body = replace_once(body, f"    sput-boolean v4, {RUNE}->{option}:Z\n",
                            f"    sput-boolean v20, {RUNE}->{option}:Z\n")
    last = f"    sput-boolean v20, {RUNE}->MW_MULTI_SPLIT_FOLDING_DIVISION_POLICY:Z\n"
    body = replace_once(body, last, last + f"\n    sget-boolean v11, {RUNE}->IS_TABLET_DEVICE:Z\n")
    rune.write_text(text[:start] + body + text[end:] + f"""
.method private static isFold8MultiSplit()Z
    .locals 2

    const-string/jumbo v0, "h8q"
    sget-object v1, {RUNE}->FW_PRODUCT_DEVICE:Ljava/lang/String;
    invoke-virtual {{v0, v1}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    return v0
.end method
""")
    print(rune.relative_to(decoded).parts[0])


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
