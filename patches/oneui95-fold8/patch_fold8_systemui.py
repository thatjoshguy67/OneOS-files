#!/usr/bin/env python3
"""Restore Fold8 navigation, taskbar, and posture-aware Quick Settings in S948BXXU6ZZKN."""
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
TASKBAR = b"Lcom/android/systemui/navigationbar/store/NavBarStateManagerImpl;"
TASKBAR_METHOD = b"getTaskBarState"
NAV_SIZE = b"Lcom/android/systemui/navigationbar/util/NavigationBarLargeScreenUtil;"
CONTEXT = b"Landroid/content/Context;"
POLICY = b"Lcom/android/systemui/BasicRune;"
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


def method_offsets(dex, header, owner_name, method_name, result_type, *,
                   include_reference=False, parameter_types=()):
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
                    parameter_count = u32(dex, parameters) if parameters else 0
                    args = struct.unpack_from(f"<{parameter_count}H", dex, parameters + 4) if parameters else ()
                    if (string(u32(dex, types + result * 4)) == result_type
                            and tuple(string(u32(dex, types + arg * 4)) for arg in args) == parameter_types):
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


def patch_taskbar(dex, code, header, end):
    if not header < code + 16 + 38 * 2 <= end or u32(dex, code + 12) != 522:
        raise ValueError("Unexpected taskbar method size")
    at = code + 16 + 6 * 2
    expected = (
        0x0254, 0x0e3d, 0x106e, 0x02dc, 0x0002, 0x020c, 0x106e, 0x03e8,
        0x0002, 0x020c, 0x2252, 0x005d, 0x1312, 0x0239, 0x0003, 0x1028,
        0x0071, 0xc716, 0x0000, 0x020a, 0x0239, 0x000b, 0x0071, 0xc70a,
        0x0000, 0x020a, 0x0238, 0x0003, 0x0328, 0x0212, 0x0228, 0x3201,
    )
    if struct.unpack_from("<32H", dex, at) != expected:
        raise ValueError("Unexpected taskbar eligibility instructions")
    # Use the same panel classifier as onConfigChanged, so opening and
    # closing the device triggers the native taskbar handoff.
    updated = (
        0x0254, 0x0e3d,                 # load Context
        0x1071, 0x23bb, 0x0002, 0x020a, # NavigationBarLargeScreenUtil.isLargeScreen()
        0x1312, 0x1928,                 # const/4 v3, 1; goto existing eligibility
    ) + (0,) * 24
    struct.pack_into("<32H", dex, at, *updated)


def patch_nav_size(dex, code, header, end):
    at = code + 16 + 16 * 2
    if (not header < at + 12 <= end or u32(dex, code + 12) != 27
            or struct.unpack_from("<6H", dex, at) !=
            (0x1071, 0xc701, 0x0001, 0x010a, 0x0139, 0x0003)):
        raise ValueError("Unexpected navigation panel classifier instructions")
    # The Fold8 changes display 0 between physical panels. The donor's
    # display context can retain its old Samsung panel ID. Use the platform
    # large-window check (600 dp) in the Fold branch. The cover is 475 dp
    # and the inner display is 704 dp at stock density.
    struct.pack_into("<6H", dex, at, 0x1071, 0xc2d4, 0x0001, 0x010a, 0x0138, 0x0003)


def patch_nav_visibility(dex, code, header, end):
    # The donor's framework lacks Fold-specific visibility arbitration. Use
    # SystemUI's native remove/restore handoff when it delegates to Launcher.
    at = code + 16 + 741 * 2
    if (not header < at + 12 <= end or u32(dex, code + 12) < 747
            or struct.unpack_from("<6H", dex, at) !=
            (0x0202, 0x0010, 0x0228, 0x3201, 0x026a, 0x0570)):
        raise ValueError("Unexpected navigation visibility policy instructions")
    struct.pack_into("<2H", dex, at, 0x0212, 0x0000)  # const/4 v2, 0; nop


def patch(apk, output):
    with zipfile.ZipFile(apk) as archive:
        dex = bytearray(archive.read("classes.dex"))
    header = 0
    nav = []
    qs = []
    taskbar = []
    visibility = []
    nav_size = []
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
        taskbar.extend((code, header, end) for code in method_offsets(
            dex, header, TASKBAR, TASKBAR_METHOD, b"I", parameter_types=(b"Z",)))
        nav_size.extend((code, header, end) for code in method_offsets(
            dex, header, NAV_SIZE, b"isLargeScreen", b"Z", parameter_types=(CONTEXT,)))
        visibility.extend((code, header, end) for code in method_offsets(dex, header, POLICY, b"<clinit>", b"V"))
        header = end
    if any(len(entries) != 1 for entries in (nav, qs, taskbar, nav_size, visibility)):
        raise ValueError("Expected one of each navigation, Quick Settings, and taskbar gate")
    entry, header, end = nav[0]
    redirect_navigation_gate(dex, header, end, entry)
    patch_qs(dex, *qs[0])
    patch_taskbar(dex, *taskbar[0])
    patch_nav_size(dex, *nav_size[0])
    patch_nav_visibility(dex, *visibility[0])
    for header, end in {entry[1:] for entry in (nav[0], qs[0], taskbar[0], nav_size[0], visibility[0])}:
        dex[header+12:header+32] = hashlib.sha1(dex[header+32:end]).digest()
        struct.pack_into("<I", dex, header + 8, zlib.adler32(dex[header+12:end]))
    Path(output).write_bytes(dex)


if __name__ == "__main__":
    patch(*sys.argv[1:])
