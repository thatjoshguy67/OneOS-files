#!/usr/bin/env python3
"""Expose Fold8's native Continue apps on cover screen settings on S948BXXU6ZZKN."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile
import zlib

from patch_fold8_systemui import method_offsets, u32

ORIGINAL = "6043280d0a9c8dbca308c8be39ddac2a1fd2d921363ada55312efdcf0712b457"
CONTINUE = b"Lcom/samsung/android/settings/display/controller/FrontScreenAppsPreferenceController;"
AVAILABLE = b"Lcom/samsung/android/settings/accessibility/home/InstalledAppsPreferenceController;"
METHOD = b"getAvailabilityStatus"


def patch(source, output):
    if hashlib.sha256(source.read_bytes()).hexdigest() != ORIGINAL:
        raise ValueError("Settings APK does not match the pinned One UI 9.5 donor")
    with zipfile.ZipFile(source) as apk:
        dex = bytearray(apk.read("classes.dex"))
    header = 0
    matches = 0
    while header < len(dex):
        end = header + u32(dex, header + 32)
        if dex[header:header + 8] != b"dex\n041\0" or not header + 120 <= end <= len(dex):
            raise ValueError("Invalid Settings DEX container")
        entries = list(method_offsets(dex, header, CONTINUE, METHOD, b"I", include_reference=True))
        if entries:
            [(old, pointer, length)] = entries
            [new] = method_offsets(dex, header, AVAILABLE, METHOD, b"I")
            if (dex[old:old+8] != dex[new:new+8] or
                    dex[old+12:old+24] != bytes.fromhex("040000006200b24312300f00") or
                    dex[new+12:new+20] != bytes.fromhex("0200000012000f00") or length != 4 or
                    not 0x200000 <= new < 0x10000000):
                raise ValueError("Settings availability code items changed")
            encoded = bytes(0x80 | ((new >> shift) & 0x7f) for shift in (0, 7, 14))
            # Redirect only this Settings controller. Other methods may share the old code item.
            dex[pointer:pointer+4] = encoded + bytes((new >> 21,))
            dex[header+12:header+32] = hashlib.sha1(dex[header+32:end]).digest()
            struct.pack_into("<I", dex, header + 8, zlib.adler32(dex[header+12:end]))
            matches += 1
        header = end
    if matches != 1:
        raise ValueError("Expected one Continue apps on cover screen controller")
    output.write_bytes(dex)


if __name__ == "__main__":
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
