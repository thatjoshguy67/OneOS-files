#!/usr/bin/env python3
"""Restore the stock Fold8 navigation feature in S948BXXU6ZZKN's SystemUI DEX."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile
import zlib

TYPE = b"Lcom/android/systemui/navigationbar/plugin/BasicRuneFeatureChecker;"
METHOD = b"isFoldableTypeLandscapeFold"
OLD = b"\x12\x00\x0f\x00"  # const/4 v0, 0; return v0
NEW = b"\x12\x10\x0f\x00"  # const/4 v0, 1; return v0 (F971BXXS3AZIJ)


def u32(dex, at):
    return struct.unpack_from("<I", dex, at)[0]


def leb(dex, at):
    value = 0
    for shift in range(0, 35, 7):
        part = dex[at]
        at += 1
        value |= (part & 127) << shift
        if part < 128:
            return value, at
    raise ValueError("Invalid ULEB128")


def method_offsets(dex, header):
    strings, types = u32(dex, header + 60), u32(dex, header + 68)
    protos, methods = u32(dex, header + 76), u32(dex, header + 92)
    class_count, classes = struct.unpack_from("<II", dex, header + 96)

    def string(index):
        _, at = leb(dex, u32(dex, strings + index * 4))
        return dex[at:dex.index(0, at)]

    for cls in range(classes, classes + class_count * 32, 32):
        type_index = u32(dex, cls)
        if string(u32(dex, types + type_index * 4)) != TYPE:
            continue
        at = u32(dex, cls + 24)
        counts = []
        for _ in range(4):
            count, at = leb(dex, at)
            counts.append(count)
        for _ in range(2 * (counts[0] + counts[1])):
            _, at = leb(dex, at)
        for count in counts[2:]:
            method = 0
            for _ in range(count):
                diff, at = leb(dex, at)
                method += diff
                _, at = leb(dex, at)
                code, at = leb(dex, at)
                owner, proto, name = struct.unpack_from("<HHI", dex, methods + method * 8)
                if owner == type_index and string(name) == METHOD:
                    result, parameters = struct.unpack_from("<II", dex, protos + proto * 12 + 4)
                    if string(u32(dex, types + result * 4)) == b"Z" and parameters == 0:
                        yield code


def patch(apk, output):
    with zipfile.ZipFile(apk) as archive:
        dex = bytearray(archive.read("classes.dex"))
    header = 0
    matches = []
    while header < len(dex):
        if dex[header:header+8] != b"dex\n041\0":
            raise ValueError("Expected a DEX 041 container")
        size = u32(dex, header + 32)
        end = header + size
        if (size < 120 or end > len(dex) or u32(dex, header + 112) != len(dex)
                or u32(dex, header + 116) != header):
            raise ValueError("Invalid DEX container bounds")
        if (hashlib.sha1(dex[header+32:end]).digest() != dex[header+12:header+32]
                or zlib.adler32(dex[header+12:end]) != u32(dex, header + 8)):
            raise ValueError("Invalid original DEX digests")
        matches.extend((code, header, end) for code in method_offsets(dex, header))
        header = end
    if len(matches) != 1:
        raise ValueError(f"Expected one Fold8 navigation gate, found {len(matches)}")
    code, header, end = matches[0]
    if not header < code + 20 <= end or u32(dex, code + 12) != 2 or dex[code+16:code+20] != OLD:
        raise ValueError("Navigation gate does not match the S948B donor")
    dex[code+16:code+20] = NEW
    dex[header+12:header+32] = hashlib.sha1(dex[header+32:end]).digest()
    struct.pack_into("<I", dex, header + 8, zlib.adler32(dex[header+12:end]))
    Path(output).write_bytes(dex)


if __name__ == "__main__":
    patch(*sys.argv[1:])
