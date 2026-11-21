#!/usr/bin/env python3
"""Restore Samsung's Flex Panel per-app settings API in the guarded Fold8 services JAR."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

WM = "Lcom/android/server/wm/WindowManagerService;"
ATM = "Lcom/android/server/wm/ActivityTaskManagerService;"
POLICY = "Lcom/android/server/wm/Fold8FlexAppPolicy;"
CONTEXT = "Landroid/content/Context;"
BINDER = "Landroid/os/Binder;"
USER = "Landroid/os/UserHandle;"
GET = "getSupportsFlexPanel(ILjava/lang/String;)I"
SET = "setSupportsFlexPanel(ILjava/lang/String;Z)V"

CHECK_USER = f"""
.method private checkFlexPanelUser(I)V
    .locals 2

    if-gez p1, :real_user
    new-instance v0, Ljava/lang/IllegalArgumentException;
    const-string v1, "Flex Panel requires a concrete user ID"
    invoke-direct {{v0, v1}}, Ljava/lang/IllegalArgumentException;-><init>(Ljava/lang/String;)V
    throw v0

    :real_user
    invoke-static {{}}, {USER}->getCallingUserId()I
    move-result v0
    if-eq p1, v0, :same_user
    iget-object v0, p0, {WM}->mContext:{CONTEXT}
    const-string v1, "android.permission.INTERACT_ACROSS_USERS_FULL"
    const-string p1, "Access another user's Flex Panel choices"
    invoke-virtual {{v0, v1, p1}}, {CONTEXT}->enforceCallingOrSelfPermission(Ljava/lang/String;Ljava/lang/String;)V

    :same_user
    return-void
.end method
"""

GET_BODY = f"""
    .locals 5

    iget-object v0, p0, {WM}->mContext:{CONTEXT}
    const-string v1, "android.permission.MANAGE_ACTIVITY_TASKS"
    const-string v2, "Read Flex Panel app support"
    invoke-virtual {{v0, v1, v2}}, {CONTEXT}->enforceCallingOrSelfPermission(Ljava/lang/String;Ljava/lang/String;)V
    invoke-direct {{p0, p1}}, {WM}->checkFlexPanelUser(I)V

    invoke-static {{}}, {BINDER}->clearCallingIdentity()J
    move-result-wide v1
    :try_start
    invoke-static {{p1}}, {USER}->of(I){USER}
    move-result-object v3
    const/4 v4, 0x0
    invoke-virtual {{v0, v3, v4}}, {CONTEXT}->createContextAsUser({USER}I){CONTEXT}
    move-result-object v0
    iget-object v3, p0, {WM}->mAtmService:{ATM}
    iget-boolean v3, v3, {ATM}->mForceResizableActivities:Z
    invoke-static {{v0, p1, p2, v3}}, {POLICY}->getFlags({CONTEXT}ILjava/lang/String;Z)I
    move-result v0
    :try_end
    .catchall {{:try_start .. :try_end}} :restore_and_throw

    invoke-static {{v1, v2}}, {BINDER}->restoreCallingIdentity(J)V
    return v0

    :restore_and_throw
    move-exception v0
    invoke-static {{v1, v2}}, {BINDER}->restoreCallingIdentity(J)V
    throw v0
"""

SET_BODY = f"""
    .locals 5

    iget-object v0, p0, {WM}->mContext:{CONTEXT}
    const-string v1, "android.permission.WRITE_SECURE_SETTINGS"
    const-string v2, "Change Flex Panel app choices"
    invoke-virtual {{v0, v1, v2}}, {CONTEXT}->enforceCallingOrSelfPermission(Ljava/lang/String;Ljava/lang/String;)V
    invoke-direct {{p0, p1}}, {WM}->checkFlexPanelUser(I)V

    invoke-static {{}}, {BINDER}->clearCallingIdentity()J
    move-result-wide v1
    :try_start
    invoke-static {{p1}}, {USER}->of(I){USER}
    move-result-object v3
    const/4 v4, 0x0
    invoke-virtual {{v0, v3, v4}}, {CONTEXT}->createContextAsUser({USER}I){CONTEXT}
    move-result-object v0
    iget-object v3, p0, {WM}->mAtmService:{ATM}
    iget-boolean v3, v3, {ATM}->mForceResizableActivities:Z
    invoke-static {{v0, p1, p2, p3, v3}}, {POLICY}->setSelected({CONTEXT}ILjava/lang/String;ZZ)V
    :try_end
    .catchall {{:try_start .. :try_end}} :restore_and_throw

    invoke-static {{v1, v2}}, {BINDER}->restoreCallingIdentity(J)V
    return-void

    :restore_and_throw
    move-exception v0
    invoke-static {{v1, v2}}, {BINDER}->restoreCallingIdentity(J)V
    throw v0
"""


def replace_stub(text, signature, previous, body):
    declaration = f".method public final {signature}\n"
    stub = declaration + previous + ".end method"
    if text.count(stub) != 1:
        raise ValueError(f"Unexpected donor code for {signature}")
    return text.replace(stub, declaration + body.lstrip("\n") + ".end method", 1)


def compile_policy(destination):
    sdk = Path(os.environ["ANDROID_HOME"])
    platform = sdk / "platforms/android-37.0/android.jar"
    d8 = sdk / "build-tools/37.0.0/d8"
    apktool_jar = os.environ.get("APKTOOL")
    apktool = ["java", "-jar", apktool_jar] if apktool_jar else ["apktool"]
    sources = Path(__file__).resolve().with_name("fold8-flex-policy")
    with tempfile.TemporaryDirectory(prefix="fold8-flex-policy-") as tmp:
        work = Path(tmp)
        java_output = work / "classfiles"
        java_output.mkdir()
        subprocess.run(["javac", "--release", "17", "-cp", str(platform), "-d", str(java_output),
                        str(sources / "ActivityInfo.java"), str(sources / "Fold8FlexAppPolicy.java")],
                       check=True, stdout=sys.stderr)
        jar = work / "FlexAppPolicy.jar"
        subprocess.run([str(d8), "--min-api", "36", "--lib", str(platform), "--output", str(jar),
                        str(java_output / "com/android/server/wm/Fold8FlexAppPolicy.class")],
                       check=True, stdout=sys.stderr)
        with zipfile.ZipFile(jar) as code:
            if code.namelist() != ["classes.dex"]:
                raise ValueError("Expected one DEX for the compiled app policy")
        decoded = work / "decoded"
        subprocess.run([*apktool, "d", "-q", "-r", str(jar), "-o", str(decoded)],
                       check=True, stdout=sys.stderr)
        smali = decoded / "smali/com/android/server/wm/Fold8FlexAppPolicy.smali"
        shutil.copyfile(smali, destination)


def patch(root):
    section = root / "smali_classes2"
    wms = section / "com/android/server/wm/WindowManagerService.smali"
    text = replace_stub(wms.read_text(), GET, "    .locals 0\n\n    const/4 p0, 0x2\n\n    return p0\n",
                        GET_BODY)
    text = replace_stub(text, SET, "    .locals 0\n\n    return-void\n", SET_BODY)
    destination = wms.with_name("Fold8FlexAppPolicy.smali")
    if destination.exists() or "checkFlexPanelUser(I)V" in wms.read_text():
        raise ValueError("The Fold8 Flex Panel app policy was already applied")
    compile_policy(destination)
    wms.write_text(text + "\n" + CHECK_USER)
    print(section.name)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
