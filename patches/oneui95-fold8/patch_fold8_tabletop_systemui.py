#!/usr/bin/env python3
"""Build the Fold8 SystemUI APK with Samsung's native tabletop switch."""
import argparse
import hashlib
import io
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

from patch_fold8_systemui import leb, string_at, u32

DIR = Path("com/android/systemui/samsung/quicksetting/ui/details/rotation")
MODEL = f"L{DIR}/RotationLockDetailViewModel;"
INTERACTOR = "Lcom/android/systemui/util/SecQsUiDisplayModeInteractor;"
SETTINGS = "Lcom/android/systemui/util/SettingsHelper;"
FLOW = "Lkotlinx/coroutines/flow/StateFlowImpl;"
STUB = f"    invoke-static {{}}, {MODEL}->shouldShowTableTopPreference()V\n"
REFRESH = f"{MODEL}->refreshTabletopOption()V"
SHOW = f"{MODEL}->showTabletopOptionOnCover()Z"
HELPER = f"{MODEL}->settingsHelper:{SETTINGS}"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Unexpected tabletop patch section near {old.splitlines()[0]!r}")
    return text.replace(old, new, 1)


def patch_model(text):
    # The renderer already consumes the secondary options and each option's
    # native enabled, checked and visible fields. Initialize the existing row.
    constructor = (
        f"    new-instance v3, L{DIR}/RotationLockDetailOptions;\n\n"
        + STUB
    )
    text = replace_once(text, constructor,
        f"    new-instance v3, L{DIR}/RotationLockDetailOptions;\n\n"
        f"    invoke-direct {{v0}}, {SHOW}\n\n    move-result v9\n\n"
        f"    iget-object v8, v0, {HELPER}\n\n"
        f"    invoke-virtual {{v8}}, {SETTINGS}->isTableTopRotationAllowed()Z\n\n"
        "    move-result v8\n")
    text = replace_once(text,
        "    const v7, 0x7e1312c2\n\n    const/4 v10, 0x0\n",
        "    const v7, 0x7e1312c2\n\n    const/4 v10, 0x1\n")
    text = replace_once(text,
        STUB + "\n" + STUB + "\n    const/4 p1, 0x4\n\n"
        f"    invoke-virtual {{p0, p1, v0, v0}}, {MODEL}->updateVisibility(IZZ)V\n",
        f"    invoke-virtual {{p0}}, {REFRESH}\n\n    const/4 p1, 0x4\n")

    update_state = (
        ".method public final updateState(IZ)V\n    .locals 7\n\n"
        f"    :cond_0\n    iget-object v0, p0, {MODEL}->_primaryOptions:{FLOW}\n"
    )
    text = replace_once(text, update_state,
        ".method public final updateState(IZ)V\n    .locals 7\n\n"
        "    :cond_0\n    const/4 v0, 0x4\n\n    if-ne p1, v0, :oneos_primary_option\n\n"
        f"    iget-object v0, p0, {MODEL}->_secondaryOptions:{FLOW}\n\n"
        "    goto :oneos_read_option\n\n    :oneos_primary_option\n"
        f"    iget-object v0, p0, {MODEL}->_primaryOptions:{FLOW}\n\n"
        "    :oneos_read_option\n")

    start = ".method public static shouldShowTableTopPreference()V\n"
    i = text.index(start)
    j = text.index(".end method", i)
    # Keep the old descriptor for the donor Compose renderer, which calls the
    # log-only method before reading the real visibility from the StateFlow.
    text = text[:i] + start + "    .locals 0\n    return-void\n" + text[j:]
    return text + f"""
.method private final showTabletopOptionOnCover()Z
    .locals 2

    iget-object v0, p0, {MODEL}->secQsUiDisplayModeInteractor:{INTERACTOR}
    invoke-virtual {{v0}}, {INTERACTOR}->getFoldState()Lkotlinx/coroutines/flow/MutableStateFlow;
    move-result-object v0
    check-cast v0, {FLOW}
    invoke-virtual {{v0}}, {FLOW}->getValue()Ljava/lang/Object;
    move-result-object v0
    sget-object v1, {INTERACTOR[:-1]}$FoldState;->FOLDED:{INTERACTOR[:-1]}$FoldState;
    if-ne v0, v1, :oneos_not_on_cover
    const/4 v0, 0x1
    return v0

    :oneos_not_on_cover
    const/4 v0, 0x0
    return v0
.end method

.method public final refreshTabletopOption()V
    .locals 3

    const/4 v0, 0x4
    iget-object v1, p0, {HELPER}
    invoke-virtual {{v1}}, {SETTINGS}->isTableTopRotationAllowed()Z
    move-result v1
    invoke-virtual {{p0, v0, v1}}, {MODEL}->updateState(IZ)V

    invoke-direct {{p0}}, {SHOW}
    move-result v1
    const/4 v2, 0x0
    invoke-virtual {{p0, v0, v1, v2}}, {MODEL}->updateVisibility(IZZ)V
    return-void
.end method
"""


def patch_observer(text, register):
    start = f"    invoke-virtual {{{register}}}, Ljava/lang/Object;->getClass()Ljava/lang/Class;\n\n"
    return replace_once(text, start + STUB, f"    invoke-virtual {{{register}}}, {REFRESH}\n")


ITEM = SETTINGS[:-1] + "$Item;"
ITEM_MAP = SETTINGS[:-1] + "$ItemMap;"
ITEM_LIST = f"{SETTINGS}->mItemLists:{ITEM_MAP}"
ADD_ITEM = f"{ITEM_MAP}->add({ITEM})V"
TABLETOP_NAME = "tabletop_rotation"
SETTINGS_FILE = Path("com/android/systemui/util/SettingsHelper.smali")

# Use the stock WindowManager default on a fresh Settings provider so the
# switch reflects the effective value even before the user writes it.
REGISTER_TABLETOP = f"""

.method private registerTabletopRotation()V
    .locals 8

    new-instance v0, {ITEM}
    move-object v1, p0
    const-string v2, "System"
    const-string v3, "{TABLETOP_NAME}"
    const-string v4, "Int"
    const/4 v6, 0x1
    invoke-static {{v6}}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;
    move-result-object v5
    invoke-direct/range {{v0 .. v6}}, {ITEM}-><init>({SETTINGS}Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/Object;Z)V
    iget-object v7, p0, {ITEM_LIST}
    invoke-virtual {{v7, v0}}, {ADD_ITEM}
    return-void
.end method
"""

READ_TABLETOP = """.method public isTableTopRotationAllowed()Z
    .locals 1

    iget-object p0, p0, Lcom/android/systemui/util/SettingsHelper;->mItemLists:Lcom/android/systemui/util/SettingsHelper$ItemMap;

    const-string v0, "tabletop_rotation"

    invoke-virtual {p0, v0}, Lcom/android/systemui/util/SettingsHelper$ItemMap;->get(Ljava/lang/String;)Lcom/android/systemui/util/SettingsHelper$Item;

    move-result-object p0

    invoke-virtual {p0}, Lcom/android/systemui/util/SettingsHelper$Item;->getIntValue()I

    move-result p0

    const/4 v0, 0x1

    if-ne p0, v0, :cond_0

    return v0

    :cond_0
    const/4 p0, 0x0

    return p0
.end method"""

WRITE_TABLETOP = """.method public setTableTopRotationAllowed(Z)V
    .locals 3

    iget-object v0, p0, Lcom/android/systemui/util/SettingsHelper;->mContext:Landroid/content/Context;

    invoke-virtual {v0}, Landroid/content/Context;->getContentResolver()Landroid/content/ContentResolver;

    move-result-object v0

    const/4 v1, -0x2

    const-string v2, "tabletop_rotation"

    invoke-static {v0, v2, p1, v1}, Landroid/provider/Settings$System;->putIntForUser(Landroid/content/ContentResolver;Ljava/lang/String;II)Z

    iget-object p0, p0, Lcom/android/systemui/util/SettingsHelper;->mItemLists:Lcom/android/systemui/util/SettingsHelper$ItemMap;

    invoke-virtual {p0, v2}, Lcom/android/systemui/util/SettingsHelper$ItemMap;->get(Ljava/lang/String;)Lcom/android/systemui/util/SettingsHelper$Item;

    move-result-object p0

    invoke-virtual {p0, p1}, Lcom/android/systemui/util/SettingsHelper$Item;->setIntValue(I)V

    return-void
.end method"""


def patch_settings(text):
    register_after = (
        '    const-string/jumbo v3, "lock_screen_allow_rotation"\n\n'
        '    const-string v4, "Int"\n\n'
        f"    invoke-direct/range {{v0 .. v6}}, {ITEM}-><init>({SETTINGS}Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/Object;Z)V\n\n"
        f"    invoke-virtual {{v7, v0}}, {ADD_ITEM}\n"
    )
    text = replace_once(text, register_after, register_after +
        f"\n    invoke-direct/range {{p0 .. p0}}, {SETTINGS}->registerTabletopRotation()V\n")
    text = replace_once(text,
        ".method public isTableTopRotationAllowed()Z\n    .locals 0\n\n"
        "    const/4 p0, 0x0\n\n    return p0\n.end method",
        READ_TABLETOP)
    text = replace_once(text,
        ".method public setTableTopRotationAllowed(Z)V\n    .locals 0\n\n"
        "    return-void\n.end method",
        WRITE_TABLETOP)
    return text + REGISTER_TABLETOP


def patch_smali(source, target):
    original = source / "smali_classes3" / DIR
    output = target / "smali" / DIR
    output.mkdir(parents=True)
    files = (
        ("RotationLockDetailViewModel.smali", patch_model),
        ("RotationLockDetailViewModel$settingsListener$1.smali", lambda s: patch_observer(s, "p0")),
        ("RotationLockDetailViewModel$callback$1$1.smali", lambda s: patch_observer(s, "p1")),
    )
    for name, patch in files:
        (output / name).write_text(patch((original / name).read_text()))

    helper = target / "smali" / SETTINGS_FILE
    helper.parent.mkdir(parents=True)
    helper.write_text(patch_settings((source / "smali_classes4" / SETTINGS_FILE).read_text()))


PREFIX = b"Lcom/android/systemui/samsung/quicksetting/ui/details/rotation/RotationLockDetailViewModel"
MOVED_CLASSES = {
    0x100f418: {PREFIX + suffix + b";" for suffix in (b"", b"$settingsListener$1", b"$callback$1$1")},
    0x17c4f80: {SETTINGS.encode()},
}
EXPECTED_DONOR_APK = "fd1e6fb5daa5785d172d05c5c9ce8904e7fa2858661abd4664a0bddaef98b928"
EXPECTED_INPUT = "53dc34ad991c294c3bbe2c030092e1a35c02e096044c8a8780f2a94558036269"


def find_class_data_end(dex, offset):
    counts = []
    for _ in range(4):
        count, offset = leb(dex, offset)
        counts.append(count)
    for _ in range(sum(counts[:2]) * 2 + sum(counts[2:]) * 3):
        _, offset = leb(dex, offset)
    return offset


def remove_moved_classes(dex, header, expected_classes):
    end = header + u32(dex, header + 32)
    if dex[header:header+8] != b"dex\n041\0" or u32(dex, header + 116) != header:
        raise ValueError("Unexpected SystemUI DEX section")
    strings, types = u32(dex, header + 60), u32(dex, header + 68)
    count, classes = struct.unpack_from("<II", dex, header + 96)
    map_offset = u32(dex, header + 52)
    map_count = u32(dex, map_offset)
    sections = {
        kind: (map_row, length, offset)
        for map_row in range(map_offset+4, map_offset+4+12*map_count, 12)
        for kind, _, length, offset in (struct.unpack_from("<HHII", dex, map_row),)
    }
    class_map, map_class_count, map_class_offset = sections[0x0006]
    data_map, map_data_count, data_start = sections[0x2000]
    _, _, data_limit = sections[0x2005]
    if (map_class_count, map_class_offset) != (count, classes) or 0xf000 in sections:
        raise ValueError("Unexpected DEX class index")

    kept_rows = []
    kept_offsets = set()
    removed_offsets = set()
    removed = set()
    for row_start in range(classes, classes + 32 * count, 32):
        row = bytearray(dex[row_start:row_start+32])
        name = string_at(dex, strings, u32(dex, types + u32(row, 0) * 4))
        class_data_off = u32(row, 24)
        if name in expected_classes:
            removed.add(name)
            removed_offsets.add(class_data_off)
        else:
            kept_rows.append(row)
            kept_offsets.add(class_data_off)
    if removed != expected_classes or len(removed_offsets) != len(expected_classes) or 0 in removed_offsets:
        raise ValueError("The expected tabletop classes were not found")
    if removed_offsets & kept_offsets:
        raise ValueError("An unrelated class shares the tabletop class data")

    # A nonempty class_data item must have a declaring class in the same
    # logical DEX. Compact this section and remap every retained class-data
    # pointer while leaving code, method IDs and shared strings in place.
    data = bytearray()
    moved = {0: 0}
    offset = data_start
    for _ in range(map_data_count):
        stop = find_class_data_end(dex, offset)
        if stop > data_limit:
            raise ValueError("Unexpected class data section bounds")
        if offset not in removed_offsets:
            moved[offset] = data_start + len(data)
            data.extend(dex[offset:stop])
        offset = stop
    if kept_offsets - moved.keys() or any(dex[offset:data_limit]):
        raise ValueError("A class points outside its logical DEX class-data section")

    for row in kept_rows:
        struct.pack_into("<I", row, 24, moved[u32(row, 24)])
    new_class_table = b"".join(kept_rows).ljust(count * 32, b"\0")
    dex[classes:classes+len(new_class_table)] = new_class_table
    dex[data_start:data_limit] = data.ljust(data_limit-data_start, b"\0")
    struct.pack_into("<I", dex, header+96, len(kept_rows))
    struct.pack_into("<I", dex, class_map+4, len(kept_rows))
    struct.pack_into("<I", dex, data_map+4, map_data_count-len(removed_offsets))
    dex[header+12:header+32] = hashlib.sha1(dex[header+32:end]).digest()
    struct.pack_into("<I", dex, header+8, zlib.adler32(dex[header+12:end]))


def append_dex(base, added_dex, destination):
    data = base.read_bytes()
    new_code = added_dex.read_bytes()
    if not data[-22:].startswith(b"PK\x05\x06"):
        raise ValueError("Unexpected SystemUI ZIP layout")
    disk, cd_disk, count_disk, count, cd_size, cd_start, comment = struct.unpack_from("<HHHHIIH", data, len(data)-18)
    if disk or cd_disk or comment or count != count_disk or cd_start+cd_size != len(data)-22:
        raise ValueError("Unexpected SystemUI ZIP central directory")
    if data[cd_start-16:cd_start] != b"APK Sig Block 42":
        raise ValueError("SystemUI signing metadata is missing")
    block_length = struct.unpack_from("<Q", data, cd_start-24)[0] + 8
    sig_start = cd_start-block_length
    with zipfile.ZipFile(base) as apk:
        dex_entries = [name for name in apk.namelist() if name.startswith("classes") and name.endswith(".dex")]
    expected = ["classes.dex", *(f"classes{n}.dex" for n in range(2, len(dex_entries) + 1))]
    if not dex_entries or dex_entries != expected:
        raise ValueError("Expected consecutive SystemUI DEX entries")
    if len(new_code) % 4 or new_code[:4] != b"dex\n":
        raise ValueError("Expected an aligned rotation detail DEX")

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as extra:
        entry = zipfile.ZipInfo(f"classes{len(dex_entries) + 1}.dex", date_time=(2008, 1, 1, 0, 0, 0))
        block_align = 4096 if sig_start % 4096 == 0 else 4
        padding = (-(sig_start + 30 + len(entry.filename) + 4 + len(new_code))) % block_align
        entry.extra = struct.pack("<HH", 0xcafe, padding) + bytes(padding)
        extra.writestr(entry, new_code, compress_type=zipfile.ZIP_STORED)

    addition = payload.getvalue()
    extra_cd_at = struct.unpack_from("<I", addition, len(addition)-6)[0]
    extra_record = bytearray(addition[extra_cd_at:-22])
    if extra_record[:4] != b"PK\x01\x02":
        raise ValueError("Unexpected rotation DEX ZIP layout")
    struct.pack_into("<I", extra_record, 42, sig_start)
    with destination.open("wb") as output:
        output.write(data[:sig_start])
        output.write(addition[:extra_cd_at])
        output.write(data[sig_start:cd_start])
        output.write(data[cd_start:-22])
        output.write(extra_record)
        output.write(struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, count+1, count+1,
                                 cd_size+len(extra_record), cd_start+extra_cd_at, 0))

def build(donor, decoded, pre_tabletop, replace_script, output, apktool):
    if hashlib.sha256(donor.read_bytes()).hexdigest() != EXPECTED_DONOR_APK:
        raise ValueError("Unexpected One UI 9.5 SystemUI APK")
    with zipfile.ZipFile(pre_tabletop) as before:
        dex = bytearray(before.read("classes.dex"))
    if hashlib.sha256(dex).hexdigest() != EXPECTED_INPUT:
        raise ValueError("Expected the guarded Fold8 SystemUI DEX before the tabletop port")

    for section, names in MOVED_CLASSES.items():
        remove_moved_classes(dex, section, names)

    with tempfile.TemporaryDirectory(prefix="fold8-tabletop-") as tmp:
        work = Path(tmp)
        code = work / "code"
        patch_smali(decoded, code)
        (code / "apktool.yml").write_text(
            "version: 3.0.3\napkFileName: tabletop-code.jar\n"
            "sdkInfo:\n  minSdkVersion: 29\ndoNotCompress:\n- dex\n")
        code_jar = work / "code.jar"
        subprocess.run([apktool, "b", "-q", str(code), "-o", str(code_jar)], check=True)
        extra_dex = work / "tabletop.dex"
        with zipfile.ZipFile(code_jar) as jar:
            extra_dex.write_bytes(jar.read("classes.dex"))

        base_dex = work / "classes.dex"
        base_dex.write_bytes(dex)
        base_apk = work / "SystemUI.apk"
        subprocess.run([sys.executable, str(replace_script), str(donor), "classes.dex",
                        str(base_dex), str(base_apk)], check=True)
        append_dex(base_apk, extra_dex, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("donor", type=Path, help="original S948BXXU6ZZKN SystemUI.apk")
    parser.add_argument("decoded", type=Path, help="original donor decoded with apktool")
    parser.add_argument("pre_tabletop", type=Path, help="Fold8 SystemUI APK before the tabletop port")
    parser.add_argument("replace_script", type=Path, help="OneOS scripts/apk-replace-dex.py")
    parser.add_argument("output", type=Path)
    parser.add_argument("--apktool", default="apktool")
    build(**vars(parser.parse_args()))
