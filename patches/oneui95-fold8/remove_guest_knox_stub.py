#!/usr/bin/env python3
"""Make the One UI variant of the OneOS guest manager APK, ready for signing."""
from pathlib import Path
import struct
import sys
import zipfile
import re

ANDROID_NS = "http://schemas.android.com/apk/res/android"
STUB_CLASS = "com.fahadali.oneos.guest.KnoxProviderStub"
STUB_AUTHORITY = "com.sec.knox.provider2"


def string_pool(data, at, header_size):
    count, _, flags, start = struct.unpack_from("<4I", data, at + 8)

    def length(pos, wide):
        if wide:
            first, = struct.unpack_from("<H", data, pos)
            if first & 0x8000:
                low, = struct.unpack_from("<H", data, pos + 2)
                return ((first & 0x7fff) << 16) | low, pos + 4
            return first, pos + 2
        first = data[pos]
        if first & 0x80:
            return ((first & 0x7f) << 8) | data[pos + 1], pos + 2
        return first, pos + 1

    utf8 = bool(flags & 0x100)
    strings = []
    for index in range(count):
        relative, = struct.unpack_from("<I", data, at + header_size + index * 4)
        count_units, pos = length(at + start + relative, not utf8)
        if utf8:
            count_bytes, pos = length(pos, False)
            strings.append(data[pos:pos + count_bytes].decode("utf-8"))
        else:
            strings.append(data[pos:pos + count_units * 2].decode("utf-16-le"))
    return strings


def remove_stub(data):
    kind, header_size, size = struct.unpack_from("<HHI", data)
    if kind != 3 or header_size != 8 or size != len(data):
        raise ValueError("invalid binary Android manifest")
    strings = []
    stack = []
    matches = []
    pos = header_size
    while pos < size:
        kind, head, length = struct.unpack_from("<HHI", data, pos)
        if head < 8 or length < head or pos + length > size:
            raise ValueError("invalid binary XML chunk")
        if kind == 1:
            strings = string_pool(data, pos, head)
        elif kind == 0x0102:
            node = pos + head
            name, = struct.unpack_from("<I", data, node + 4)
            offset, width, count = struct.unpack_from("<HHH", data, node + 8)
            attrs = {}
            for index in range(count):
                attr = node + offset + width * index
                namespace, key, raw = struct.unpack_from("<3I", data, attr)
                if namespace == 0xffffffff or strings[namespace] != ANDROID_NS:
                    continue
                value_type = data[attr + 15]
                value, = struct.unpack_from("<I", data, attr + 16)
                if raw != 0xffffffff:
                    attrs[strings[key]] = strings[raw]
                elif value_type == 3:
                    attrs[strings[key]] = strings[value]
            target = (strings[name] == "provider" and len(stack) == 2
                      and strings[stack[-1][0]] == "application"
                      and attrs.get("name") in (STUB_CLASS, ".KnoxProviderStub")
                      and attrs.get("authorities") == STUB_AUTHORITY)
            stack.append((name, pos, target))
        elif kind == 0x0103:
            end_name, = struct.unpack_from("<I", data, pos + head + 4)
            name, start, target = stack.pop()
            if name != end_name:
                raise ValueError("unbalanced binary XML")
            if target:
                matches.append((start, pos + length))
        pos += length
    if stack or len(matches) != 1:
        raise ValueError(f"expected exactly one Knox stub provider, found {len(matches)}")
    start, end = matches[0]
    patched = bytearray(data[:start] + data[end:])
    struct.pack_into("<I", patched, 4, len(patched))
    return patched


def main():
    src, dst = map(Path, sys.argv[1:3])
    signature = re.compile(r"META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))$", re.I)
    with zipfile.ZipFile(src) as apk:
        manifest = remove_stub(apk.read("AndroidManifest.xml"))
        with zipfile.ZipFile(dst, "w") as out:
            for info in apk.infolist():
                if signature.fullmatch(info.filename):
                    continue
                contents = manifest if info.filename == "AndroidManifest.xml" else apk.read(info.filename)
                out.writestr(info, contents)


if __name__ == "__main__":
    main()
