#!/usr/bin/env python3
"""Bind Samsung's Flex Panel to the Fold8 hinge and Shell in S948BXXU6ZZKN."""
import argparse
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from patch_fold8_tabletop_systemui import (
    EXPECTED_DONOR_APK, append_dex, remove_moved_classes, replace_once,
)

SHELL = "com/android/wm/shell"
SPLIT = f"{SHELL}/splitscreen/SplitScreenController"
SHORTCUT = f"{SHELL}/flexpanel/FlexPanelStartController"
PANEL = f"{SHELL}/controlpanel/activity/FlexPanelActivity"
CONTROLLER = f"{SHELL}/flexpanel/Fold8FlexPanel"
NAV = "com/android/systemui/navigationbar/remoteview/NavBarRemoteViewManager"
REMOTE = "Lcom/android/systemui/navigationbar/remoteview/NavBarRemoteView;"
PANEL_NAME = PANEL.replace("/", ".")
INPUT_APK = "35525b9457bc9d19e80b1667886640e15e6c40f030a8f1389d497a38be5160aa"

SPLIT_INIT = f"""
    iget-boolean v0, p0, L{SPLIT};->mIsSplitScreenSupported:Z
    if-eqz v0, :oneos_no_flex

    iget-object v0, p0, L{SPLIT};->mContext:Landroid/content/Context;
    iget-object v1, p0, L{SPLIT};->mMainExecutor:L{SHELL}/common/ShellExecutor;
    iget-object v2, p0, L{SPLIT};->mTaskOrganizer:L{SHELL}/ShellTaskOrganizer;
    iget-object v3, p0, L{SPLIT};->mDisplayImeController:L{SHELL}/common/DisplayImeController;
    iget-object v4, p0, L{SPLIT};->oneosFlexShortcut:L{SHORTCUT};
    move-object v5, p0
    invoke-static/range {{v0 .. v5}}, L{CONTROLLER};->start(Landroid/content/Context;Ljava/util/concurrent/Executor;L{SHELL}/ShellTaskOrganizer;L{SHELL}/common/DisplayImeController;L{SHORTCUT};L{SPLIT};)V

    :oneos_no_flex
"""

CLEAR_SHORTCUT = f"""
.method public final clearButton()V
    .locals 4

    iget-object v0, p0, L{SHORTCUT};->mSemStatusBarManager:Landroid/app/SemStatusBarManager;
    const-string v1, "{PANEL_NAME}"
    const/4 v2, 0x0
    const/16 v3, 0xb
    invoke-virtual {{v0, v1, v2, v2, v3}}, Landroid/app/SemStatusBarManager;->setNavigationBarShortcut(Ljava/lang/String;Landroid/widget/RemoteViews;II)V
    return-void
.end method
"""

FLEX_SHORTCUT_POSITION = f"""
.method private hasFlexPanelShortcut()Z
    .locals 3

    const/4 v0, 0x0
    const/4 v1, 0x1

    :check_position
    invoke-virtual {{p0, v0}}, L{NAV};->getRemoteView(I){REMOTE}
    move-result-object v2
    if-eqz v2, :next_position
    iget-object v2, v2, {REMOTE}->requestClass:Ljava/lang/String;
    const-string v1, "{PANEL_NAME}"
    invoke-virtual {{v1, v2}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v2
    const/4 v1, 0x1
    if-nez v2, :found

    :next_position
    if-eq v0, v1, :missing
    move v0, v1
    goto :check_position

    :found
    iput v0, p0, L{NAV};->adaptivePosition:I
    return v1

    :missing
    const/4 v0, 0x0
    return v0
.end method
"""


INPUT_CLEANUP = f"""
.method private disposeFlexInput()V
    .locals 2

    iget-object v0, p0, L{PANEL};->mEventReceiver:L{PANEL}$EventReceiver;
    const/4 v1, 0x0
    if-eqz v0, :oneos_dispose_monitor
    iput-object v1, p0, L{PANEL};->mEventReceiver:L{PANEL}$EventReceiver;
    invoke-virtual {{v0}}, Landroid/view/InputEventReceiver;->dispose()V

    :oneos_dispose_monitor
    iget-object v0, p0, L{PANEL};->mInputMonitor:Landroid/view/InputMonitor;
    if-eqz v0, :oneos_input_done
    iput-object v1, p0, L{PANEL};->mInputMonitor:Landroid/view/InputMonitor;
    invoke-virtual {{v0}}, Landroid/view/InputMonitor;->dispose()V

    :oneos_input_done
    return-void
.end method
"""


def edit_method(text, signature, edit):
    start = text.index(f" {signature}\n")
    end = text.index(".end method", start)
    return text[:start] + edit(text[start:end]) + text[end:]


def patch_split(text):
    field = f".field public final mTaskOrganizer:L{SHELL}/ShellTaskOrganizer;\n"
    text = replace_once(text, field, field + f"\n.field private final oneosFlexShortcut:L{SHORTCUT};\n")
    constructor_end = (
        "    :goto_1\n"
        f"    iput-object p1, p0, L{SPLIT};->mNsController:L{SHELL}/naturalswitching/NaturalSwitchingDropTargetController;\n"
    )
    text = replace_once(text, constructor_end, constructor_end +
        "\n    move-object/from16 p1, p31\n"
        f"    iput-object p1, p0, L{SPLIT};->oneosFlexShortcut:L{SHORTCUT};\n")
    return edit_method(text, "onInit()V", lambda body: replace_once(
        body, "    :cond_5\n    return-void\n", "    :cond_5\n" + SPLIT_INIT + "    return-void\n"))


def patch_panel(text):
    # Activity callbacks run on the same looper used by the input receiver.
    for method in ("onPause()V", "onDestroy()V"):
        text = edit_method(text, method, lambda body: re.sub(
            r"(    \.locals \d+\n)", rf"\g<1>\n    invoke-direct {{p0}}, L{PANEL};->disposeFlexInput()V\n", body, count=1))
    for method in ("onResume()V", "onDestroy()V"):
        text = edit_method(text, method, lambda body: replace_once(
            body, "    return-void\n",
            f"    invoke-static {{}}, L{CONTROLLER};->onPanelChanged()V\n\n    return-void\n"))
    return text + INPUT_CLEANUP


def patch_nav(text):
    # Preserve the existing keyboard shortcut priority, then check for Flex Panel.
    def edit(body):
        body = replace_once(body, "    .locals 4\n", "    .locals 5\n\n    move-object v4, p0\n")
        return replace_once(body, "    :cond_4\n    return v3\n",
            f"    :cond_4\n    invoke-direct {{v4}}, L{NAV};->hasFlexPanelShortcut()Z\n"
            "    move-result v3\n    return v3\n")
    return edit_method(text, "isSetMultimodalButton()Z", edit) + FLEX_SHORTCUT_POSITION


def patch_stage(text):
    coordinator = f"{SHELL}/splitscreen/StageCoordinator"
    listener = f"{SHELL}/splitscreen/StageTaskListener"
    # A visible companion can appear as an ActivityRecord in TransitionInfo.
    # Keep the exact task only if Shell has already received it in MAIN.
    text = replace_once(text,
        '    :cond_1d\n    new-instance v1, Ljava/lang/StringBuilder;\n\n    const-string v2, "  info:"',
        f'''    :cond_1d
    if-nez v12, :oneos_split_error
    invoke-direct {{v0, v11, v2}}, L{coordinator};->keepFlexCompanion(Landroid/window/TransitionInfo$Change;Ljava/util/HashSet;)Z
    move-result v35
    if-nez v35, :cond_18

    :oneos_split_error
    new-instance v1, Ljava/lang/StringBuilder;

    const-string v2, "  info:"''')
    return text + f"""
.method private keepFlexCompanion(Landroid/window/TransitionInfo$Change;Ljava/util/HashSet;)Z
    .locals 3

    if-eqz p1, :missing
    invoke-virtual {{p1}}, Landroid/window/TransitionInfo$Change;->getTaskInfo()Landroid/app/ActivityManager$RunningTaskInfo;
    move-result-object v0
    iget-object v1, p0, L{coordinator};->mMainStage:L{listener};
    invoke-virtual {{v1}}, L{listener};->getTopRunningTaskInfo()Landroid/app/ActivityManager$RunningTaskInfo;
    move-result-object v1
    invoke-static {{v0, v1}}, L{CONTROLLER};->isPendingCompanion(Landroid/app/TaskInfo;Landroid/app/TaskInfo;)Z
    move-result v2
    if-eqz v2, :missing

    iget v0, v1, Landroid/app/ActivityManager$RunningTaskInfo;->taskId:I
    invoke-static {{v0}}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;
    move-result-object v0
    invoke-virtual {{p2, v0}}, Ljava/util/HashSet;->add(Ljava/lang/Object;)Z
    const/4 v0, 0x1
    return v0

    :missing
    const/4 v0, 0x0
    return v0
.end method
"""


PATCHES = {
    NAV: ("smali_classes3", 0x100f418, patch_nav),
    SPLIT: ("smali_classes5", 0x1e912b4, patch_split),
    SHORTCUT: ("smali_classes5", 0x1e912b4, lambda text: text + CLEAR_SHORTCUT),
    PANEL: ("smali_classes5", 0x1e912b4, patch_panel),
    f"{SHELL}/splitscreen/StageCoordinator": ("smali_classes5", 0x1e912b4, patch_stage),
}


def compile_controller(work, smali, apktool):
    sdk = Path(os.environ["ANDROID_HOME"])
    api = sdk / "platforms/android-37.0/android.jar"
    compiler = sdk / "build-tools/37.0.0/d8"
    source = Path(__file__).resolve().with_name("fold8-flex-shell")
    classes = work / "classes"
    classes.mkdir()
    subprocess.run(["javac", "--release", "17", "-cp", str(api), "-d", str(classes),
                    *map(str, sorted(source.glob("*.java"))),
                    *map(str, sorted((source / "stubs").rglob("*.java")))], check=True)
    compiled = work / "controller.jar"
    subprocess.run([str(compiler), "--min-api", "36", "--lib", str(api),
                    "--classpath", str(classes), "--output", str(compiled),
                    *map(str, sorted((classes / CONTROLLER).parent.glob("Fold8FlexPanel*.class")))],
                    check=True)
    decoded = work / "controller"
    subprocess.run([apktool, "d", "-q", "-r", str(compiled), "-o", str(decoded)], check=True)
    controller_files = sorted((decoded / "smali" / CONTROLLER).parent.glob("Fold8FlexPanel*.smali"))
    if not controller_files or not any(path.name == "Fold8FlexPanel.smali" for path in controller_files):
        raise ValueError("Missing compiled Flex Panel controller")
    for src in controller_files:
        (smali / CONTROLLER).with_name(src.name).write_bytes(src.read_bytes())


def build(donor, decoded, r19, replace_script, output, apktool):
    if hashlib.sha256(donor.read_bytes()).hexdigest() != EXPECTED_DONOR_APK:
        raise ValueError("Unexpected original SystemUI APK")
    if hashlib.sha256(r19.read_bytes()).hexdigest() != INPUT_APK:
        raise ValueError("Expected r19's Fold8 SystemUI APK")
    with zipfile.ZipFile(r19) as source:
        dex = bytearray(source.read("classes.dex"))
        tabletop = source.read("classes2.dex")

    with tempfile.TemporaryDirectory(prefix="fold8-flex-systemui-") as tmp:
        work = Path(tmp)
        code = work / "code"
        smali = code / "smali"
        removed = {}
        for name, (section, header, patch) in PATCHES.items():
            destination = smali / (name + ".smali")
            destination.parent.mkdir(parents=True, exist_ok=True)
            original = decoded / section / (name + ".smali")
            destination.write_text(patch(original.read_text()))
            removed.setdefault(header, set()).add(f"L{name};".encode())
        for header, names in removed.items():
            remove_moved_classes(dex, header, names)

        compile_controller(work, smali, apktool)
        (code / "apktool.yml").write_text(
            "version: 3.0.3\napkFileName: flex-shell.jar\nsdkInfo:\n  minSdkVersion: 29\ndoNotCompress:\n- dex\n")
        combined = work / "flex.jar"
        subprocess.run([apktool, "b", "-q", str(code), "-o", str(combined)], check=True)
        flex_dex = work / "flex.dex"
        with zipfile.ZipFile(combined) as jar:
            flex_dex.write_bytes(jar.read("classes.dex"))

        base_dex = work / "base.dex"
        base_dex.write_bytes(dex)
        base_apk = work / "base.apk"
        subprocess.run([sys.executable, str(replace_script), str(donor), "classes.dex",
                        str(base_dex), str(base_apk)], check=True)
        tabletop_dex = work / "tabletop.dex"
        tabletop_dex.write_bytes(tabletop)
        tabletop_apk = work / "tabletop.apk"
        append_dex(base_apk, tabletop_dex, tabletop_apk)
        append_dex(tabletop_apk, flex_dex, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for value in ("donor", "decoded", "r19", "replace_script", "output"):
        parser.add_argument(value, type=Path)
    parser.add_argument("--apktool", default="apktool")
    build(**vars(parser.parse_args()))
