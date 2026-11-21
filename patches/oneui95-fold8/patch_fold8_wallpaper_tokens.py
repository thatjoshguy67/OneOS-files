#!/usr/bin/env python3
"""Restore physical-display wallpaper token registration on the Fold8 guest."""
from pathlib import Path
import sys


def replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError(f"Wallpaper method has an unexpected anchor: {anchor.strip().splitlines()[0]}")
    return text.replace(anchor, replacement, 1)


def patch(decoded):
    section = decoded / "smali_classes2"
    wm = section / "com/android/server/wm"
    local_service = wm / "WindowManagerService$LocalService.smali"
    window_token = wm / "WallpaperWindowToken.smali"
    service = local_service.read_text()
    method = ".method public final setWallpaperPhysicalDisplayId(Landroid/os/IBinder;J)V"
    if service.count(method) != 1:
        raise ValueError("Expected the One UI 9.5 donor wallpaper binder method")
    start = service.index(method)
    end = service.index(".end method", start)
    body = service[start:end]
    # The phone build leaves this enabled branch as a throw-null stub.
    # v2 is the wallpaper token that the native lookup has already checked.
    body = replace_once(body, """\
    :cond_1
    invoke-virtual {p0}, Lcom/android/server/wm/WindowContainer;->asWallpaperToken()Lcom/android/server/wm/WallpaperWindowToken;

    move-result-object p0

    iput-wide p2, p0, Lcom/android/server/wm/WallpaperWindowToken;->mPhysicalDisplayId:J

    iget-object p0, p0, Lcom/android/server/wm/WindowContainer;->mWmService:Lcom/android/server/wm/WindowManagerService;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    const/4 p0, 0x0

    throw p0
""", """\
    :cond_1
    invoke-virtual {v2, p2, p3}, Lcom/android/server/wm/WallpaperWindowToken;->setPhysicalDisplayId(J)V

    goto :unlock_wallpaper_token
""")
    body = replace_once(body, """\
    invoke-static {p0, p1}, Landroid/util/Slog;->w(Ljava/lang/String;Ljava/lang/String;)I

    monitor-exit v1
""", """\
    invoke-static {p0, p1}, Landroid/util/Slog;->w(Ljava/lang/String;Ljava/lang/String;)I

    :unlock_wallpaper_token
    monitor-exit v1
""")

    token = window_token.read_text()
    if " setPhysicalDisplayId(J)V" in token:
        raise ValueError("Unexpected existing Fold8 wallpaper token setter")
    # Stable physical display addresses use their low byte for the port.
    # Fold8 port 147 is the inner panel and 148 is the cover. Keeping this
    # local avoids a display-manager call while the WM lock is held.
    token += """
.method public final setPhysicalDisplayId(J)V
    .locals 2

    iput-wide p1, p0, Lcom/android/server/wm/WallpaperWindowToken;->mPhysicalDisplayId:J

    long-to-int v0, p1
    and-int/lit16 v0, v0, 0xff
    const/16 v1, 0x93
    if-ne v0, v1, :secondary

    const/4 v0, 0x1
    goto :store

    :secondary
    const/4 v0, 0x0

    :store
    iput-boolean v0, p0, Lcom/android/server/wm/WallpaperWindowToken;->mIsForPrimaryDevice:Z
    const/4 v0, 0x0
    iput-object v0, p0, Lcom/android/server/wm/WallpaperWindowToken;->stringInfo:Ljava/lang/String;
    return-void
.end method
"""
    local_service.write_text(service[:start] + body + service[end:])
    window_token.write_text(token)
    print(section.name)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
