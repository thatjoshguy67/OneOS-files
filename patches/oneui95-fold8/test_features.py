#!/usr/bin/env python3
"""Run the Fold8 merge in isolation with fixture XML. No Android device needed."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

PREFIX = "SEC_FLOATING_FEATURE_"
FOLD = "FRAMEWORK_SUPPORT_FOLDABLE_TYPE_FOLD"
WIDE = "FRAMEWORK_SUPPORT_FOLDABLE_TYPE_LANDSCAPE_FOLD"
HALF = "FRAMEWORK_SUPPORT_HALF_FOLDED_MODE"
SIP = "SIP_CONFIG_FOLD_UX_VERSION"
WALLPAPER = "LOCKSCREEN_CONFIG_WALLPAPER_STYLE"
TASKBAR = "LAUNCHER_SUPPORT_TASKBAR"
AI = "COMMON_CONFIG_AI_VERSION"
SCANNER = "CAMERA_DOCUMENTSCAN_SOLUTIONS"


def write_features(path, features):
    root = ET.Element("SecFloatingFeatureSet")
    for key, value in features.items():
        ET.SubElement(root, PREFIX + key).text = value
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="unicode")


def read_features(path):
    root = ET.parse(path).getroot()
    return {el.tag.removeprefix(PREFIX): el.text for el in root}


class Fold8FeaturesTest(unittest.TestCase):
    def run_merge(self, *, profile="f8", form="fold", donor="S948BXXU6ZZKN",
                  enabled="1", scanner=True, scan="SCANNER_FILTER,MAGNET",
                  wide=True, broken_system=False):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            stage = directory / "stage"
            rootfs = directory / "rootfs"
            (stage / "data").mkdir(parents=True)
            (rootfs / "system").mkdir(parents=True)
            (rootfs / "system/build.prop").write_text(f"ro.build.PDA={donor}\n")

            host_vendor = directory / "vendor.xml"
            host_system = directory / "system.xml"
            write_features(host_vendor, {FOLD: "TRUE", HALF: "TRUE", SIP: "0"})
            host = {FOLD: "TRUE", TASKBAR: "TRUE", SIP: "81",
                    WALLPAPER: "LID,VIDEO,ROTATABLE,GENWEATHER"}
            if wide:
                host[WIDE] = "TRUE"
            write_features(host_system, host)
            vendor = stage / "data/oneos_floating_feature.xml"
            system = stage / "data/oneos_system_floating_feature.xml"
            write_features(vendor, {SCANNER: scan, "CAMERA_CONFIG_CAMID_WIDE": "0"})
            write_features(system, {SCANNER: scan, AI: "20300", SIP: "0",
                                    WALLPAPER: "VIDEO,FLIPSUIT_LOCK",
                                    "CAMERA_CONFIG_CAMID_WIDE": "0"})
            if scanner:
                scanner_dir = rootfs / "system/priv-app/VexScanner"
                scanner_dir.mkdir(parents=True)
                (scanner_dir / "VexScanner.apk").touch()
            if broken_system:
                system.write_text("<SecFloatingFeatureSet>")
            block = MERGE.replace("/vendor/etc/floating_feature.xml", str(host_vendor))
            block = block.replace("/system/etc/floating_feature.xml", str(host_system))
            result = subprocess.run(
                ["sh", "-c", 'chown() { :; }\n' + block], check=True,
                env={**os.environ, "ONEOS_PROFILE": profile, "FORM": form,
                     "ROOTFS": str(rootfs), "STAGE": str(stage), "ONEOS_ONEUI_FLOATING": enabled},
                capture_output=True, text=True,
            )
            self.assertEqual([], list((stage / "data").glob("*.f8")))
            return read_features(vendor), None if broken_system else read_features(system), result.stdout

    def test_native_layout_and_keyboard_flags_reach_both_files(self):
        vendor, system, log = self.run_merge()
        for merged in (vendor, system):
            for key in (FOLD, WIDE, HALF, TASKBAR):
                self.assertEqual("TRUE", merged[key])
            self.assertEqual("81", merged[SIP])
            self.assertEqual("LID,VIDEO,ROTATABLE,GENWEATHER", merged[WALLPAPER])
            self.assertEqual("0", merged["CAMERA_CONFIG_CAMID_WIDE"])
            self.assertEqual("SCANNER_FILTER,MAGNET,DOC_TYPE_DETECTOR", merged[SCANNER])
        self.assertEqual("20271", vendor[AI])
        self.assertEqual("20300", system[AI])
        self.assertIn("Fold8 cover", log)

    def test_scanner_path_keeps_existing_capabilities(self):
        for scanner, scan in ((True, "SCANNER_FILTER,DOC_TYPE_DETECTOR"),
                              (False, "SCANNER_FILTER")):
            with self.subTest(scanner=scanner):
                vendor, system, _ = self.run_merge(scanner=scanner, scan=scan)
                self.assertEqual(scan, vendor[SCANNER])
                self.assertEqual(scan, system[SCANNER])

    def test_exact_donor_profile_and_form_with_opt_out(self):
        for options in ({"profile": "f8u"}, {"donor": "S948BXXU6ZZKO"},
                        {"form": "phone"}, {"enabled": "0"}):
            with self.subTest(options=options):
                vendor, system, log = self.run_merge(**options)
                self.assertNotIn(FOLD, vendor)
                self.assertNotIn(FOLD, system)
                self.assertFalse(log)

    def test_missing_fold_config_or_invalid_system_file_leaves_baseline(self):
        for options in ({"wide": False}, {"broken_system": True}):
            with self.subTest(options=options):
                vendor, _, log = self.run_merge(**options)
                self.assertNotIn(FOLD, vendor)
                self.assertIn("could not apply", log)


if __name__ == "__main__":
    source = Path(sys.argv.pop(1)) / "switcher/assets/guest_prepare.sh"
    MERGE = source.read_text().split("# The S26 Ultra donor does not describe", 1)[1]
    MERGE = MERGE.split("# The phone's eSIM chip", 1)[0].split("\n", 1)[1]
    unittest.main()
