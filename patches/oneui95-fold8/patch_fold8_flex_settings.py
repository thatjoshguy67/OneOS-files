#!/usr/bin/env python3
"""Restore the donor's searchable Flex Mode panel page for the Fold8 Flex port."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile
import zlib

from patch_fold8_systemui import method_offsets, u32

INPUT_DEX = "b6bff30b89be5b2aeb5f837b23004e840822d40ef8f106ad1f7b7860591dd95b"
NAMESPACE = b"Lcom/samsung/android/settings/"
PANEL = NAMESPACE + b"usefulfeature/labs/flexmodepanel/"
CONTEXT = b"Landroid/content/Context;"
SECTION = 0x12ca198

METHODS = (
    (PANEL + b"FlexModePanelPreferenceController;",
     NAMESPACE + b"wifi/WifiPreferenceController;",
     b"getAvailabilityStatus", b"I", (),
     bytes.fromhex("0400000062007e0412300f00"), bytes.fromhex("0200000012000f00")),
    (PANEL + b"FlexModePanelSettings$3;",
     NAMESPACE + b"nfc/NfcSettings$3;",
     b"isPageSearchEnabled", b"Z", (CONTEXT,),
     bytes.fromhex("0400000062007e0412000f00"), bytes.fromhex("0200000012100f00")),
)


def build(source, output):
    with zipfile.ZipFile(source) as apk:
        dex = bytearray(apk.read("classes.dex"))
    if hashlib.sha256(dex).hexdigest() != INPUT_DEX:
        raise ValueError("Expected the Fold8 Settings DEX after the cover-screen patch")
    if dex[SECTION:SECTION + 8] != b"dex\n041\0":
        raise ValueError("Unexpected Flex Mode Settings DEX section")

    for owner, replacement_owner, method, result, parameters, old_code, available_code in METHODS:
        [(old, pointer, length)] = method_offsets(
            dex, SECTION, owner, method, result,
            include_reference=True, parameter_types=parameters)
        [new] = method_offsets(
            dex, SECTION, replacement_owner, method, result, parameter_types=parameters)
        if (dex[old:old + 8] != dex[new:new + 8] or
                dex[old + 12:old + 12 + len(old_code)] != old_code or
                dex[new + 12:new + 12 + len(available_code)] != available_code or
                length != 4 or not 0x200000 <= new < 0x10000000):
            raise ValueError(f"Unexpected Flex Mode Settings code item for {method!r}")

        # Change only the target method's reference. The old code items
        # are shared with unrelated preference and search controllers.
        dex[pointer:pointer + 4] = bytes(
            0x80 | ((new >> shift) & 0x7f) for shift in (0, 7, 14)) + bytes((new >> 21,))

    end = SECTION + u32(dex, SECTION + 32)
    dex[SECTION + 12:SECTION + 32] = hashlib.sha1(dex[SECTION + 32:end]).digest()
    struct.pack_into("<I", dex, SECTION + 8, zlib.adler32(dex[SECTION + 12:end]))
    output.write_bytes(dex)


if __name__ == "__main__":
    build(*(Path(arg) for arg in sys.argv[1:]))
