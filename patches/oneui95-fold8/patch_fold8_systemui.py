#!/usr/bin/env python3
"""Restore stock Fold8 navigation and posture-aware Quick Settings in S948BXXU6ZZKN."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile
import zlib

NAV = b"Lcom/android/systemui/navigationbar/plugin/BasicRuneFeatureChecker;"
NAV_METHOD = b"isFoldableTypeLandscapeFold"
TRUE_OWNER = b"Lcom/android/systemui/navigationbar/NavigationBarControllerImpl;"
TRUE_METHOD = b"supportsTaskbar"
QS = b"Lcom/android/systemui/util/SecQsUiDisplayModeInteractor;"
QS_METHOD = b"getDeviceFormFactor"
FORM = QS[:-1] + b"$DeviceFormFactor;"
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


def string_at(dex, table, index):
    _, at = leb(dex, u32(dex, table + index * 4))
    return bytes(dex[at:dex.index(0, at)])


def method_offsets(dex, header, owner_name, method_name, result_type, *, include_reference=False):
    strings, types = u32(dex, header + 60), u32(dex, header + 68)
    protos, methods = u32(dex, header + 76), u32(dex, header + 92)
    class_count, classes = struct.unpack_from("<II", dex, header + 96)

    def string(index):
        return string_at(dex, strings, index)

    for cls in range(classes, classes + class_count * 32, 32):
        type_index = u32(dex, cls)
        if string(u32(dex, types + type_index * 4)) != owner_name:
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
                reference = at
                code, at = leb(dex, at)
                owner, proto, name = struct.unpack_from("<HHI", dex, methods + method * 8)
                if owner == type_index and string(name) == method_name:
                    result, parameters = struct.unpack_from("<II", dex, protos + proto * 12 + 4)
                    if string(u32(dex, types + result * 4)) == result_type and parameters == 0:
                        yield (code, reference, at - reference) if include_reference else code


def field_indices(dex, header, owner_name, names):
    strings, types = u32(dex, header + 60), u32(dex, header + 68)
    count, fields = struct.unpack_from("<II", dex, header + 80)
    found = {}
    for index in range(count):
        owner, typ, name = struct.unpack_from("<HHI", dex, fields + index * 8)
        if owner != typ or string_at(dex, strings, u32(dex, types + owner * 4)) != owner_name:
            continue
        field = string_at(dex, strings, name)
        if field in names:
            if field in found:
                raise ValueError(f"Duplicate form factor {field!r}")
            found[field] = index
    if found.keys() != set(names):
        raise ValueError("Expected the donor's original PHONE, TABLET and LANDSCAPE_FOLD fields")
    return found


def patch_qs(dex, code, header, end):
    if not header < code + 36 <= end or u32(dex, code + 12) != 10:
        raise ValueError("Unexpected Quick Settings form-factor method size")
    insns = code + 16
    # sget-boolean; if-eqz; sget-object TABLET; return-object;
    # sget-object PHONE; return-object. Only the PHONE field reference changes.
    if [dex[insns + i * 2] for i in (0, 2, 4, 6, 7, 9)] != [0x63, 0x38, 0x62, 0x11, 0x62, 0x11]:
        raise ValueError("Unexpected Quick Settings form-factor instructions")
    fields = field_indices(dex, header, FORM, (b"PHONE", b"TABLET", b"LANDSCAPE_FOLD"))
    if struct.unpack_from("<H", dex, insns + 10)[0] != fields[b"TABLET"]:
        raise ValueError("Quick Settings tablet branch does not match")
    offset = insns + 16
    if struct.unpack_from("<H", dex, offset)[0] != fields[b"PHONE"]:
        raise ValueError("Quick Settings phone branch does not match")
    struct.pack_into("<H", dex, offset, fields[b"LANDSCAPE_FOLD"])


def redirect_navigation_gate(dex, header, end, entry):
    code, reference, length = entry
    alternatives = list(method_offsets(dex, header, TRUE_OWNER, TRUE_METHOD, b"Z"))
    if len(alternatives) != 1:
        raise ValueError("Expected a matching true code item in the navigation DEX")
    target = alternatives[0]
    if not all(header < offset + 20 <= end and u32(dex, offset + 12) == 2
               for offset in (code, target)):
        raise ValueError("Unexpected navigation code item sizes")
    if (dex[code+16:code+20] != OLD or dex[target+16:target+20] != NEW
            or dex[code:code+8] != dex[target:target+8]):
        raise ValueError("Navigation code items do not match the donor")
    encoded = bytearray()
    value = target
    while value >= 128:
        encoded.append((value & 127) | 128)
        value >>= 7
    encoded.append(value)
    if len(encoded) != length:
        raise ValueError("Navigation reference would change the encoded class data size")
    # R8 deduplicated the false code item with EmptyIterator.hasNext and
    # other methods. Redirect this method only, leaving both code items intact.
    dex[reference:reference + length] = encoded


def patch(apk, output):
    with zipfile.ZipFile(apk) as archive:
        dex = bytearray(archive.read("classes.dex"))
    header = 0
    nav = []
    qs = []
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
        nav.extend((code, header, end) for code in method_offsets(dex, header, NAV, NAV_METHOD, b"Z", include_reference=True))
        qs.extend((code, header, end) for code in method_offsets(dex, header, QS, QS_METHOD, FORM))
        header = end
    if len(nav) != 1 or len(qs) != 1:
        raise ValueError(f"Expected one navigation and one Quick Settings gate, found {len(nav)} and {len(qs)}")
    entry, header, end = nav[0]
    redirect_navigation_gate(dex, header, end, entry)
    patch_qs(dex, *qs[0])
    for _, header, end in (nav[0], qs[0]):
        dex[header+12:header+32] = hashlib.sha1(dex[header+32:end]).digest()
        struct.pack_into("<I", dex, header + 8, zlib.adler32(dex[header+12:end]))
    Path(output).write_bytes(dex)


if __name__ == "__main__":
    patch(*sys.argv[1:])
