#!/usr/bin/env python3
"""Exercise guest startup density defaults without an Android device."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

INNER = '4630947004648141459'
COVER = '4630947123231501204'


class DensityTest(unittest.TestCase):
    def run_seed(self, existing=None, *, profile='f8', pda='S948BXXU6ZZKN',
                 native='420', vendor=''):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            state = work / 'data/system'
            state.mkdir(parents=True)
            build_prop = work / 'build.prop'
            build_prop.write_text(f'ro.build.PDA={pda}\n')
            vendor_xml = work / 'vendor.xml'
            vendor_xml.write_text(vendor)
            settings = state / 'display_settings.xml'
            if existing is not None:
                settings.write_text(existing)
            fixture = BLOCK.replace('/data/system', str(state))
            fixture = fixture.replace('/system/build.prop', str(build_prop))
            fixture = fixture.replace('/vendor/etc/display_settings.xml', str(vendor_xml))
            prelude = 'getprop() { printf "%s\\n" "$NATIVE"; }; bb() { :; }; chown() { :; }; BB=bb\n'
            subprocess.run(
                ['sh', '-c', prelude + fixture], check=True, capture_output=True,
                env={**os.environ, 'NATIVE': native, 'ONEOS_PROFILE': profile,
                     'ONEOS_GUEST_FORM': 'fold', 'INNER': INNER, 'COVER': COVER},
            )
            self.assertEqual([], list(state.glob('oneos-density.*')))
            return settings.read_text() if settings.exists() else None

    def displays(self, text):
        return {el.attrib['name']: el.attrib for el in ET.fromstring(text).findall('display')}

    def test_first_boot_creates_both_physical_display_defaults(self):
        for native, expected in (('420', '420'), ('440', '440'), ('213', '420'), ('', '420')):
            with self.subTest(native=native):
                entries = self.displays(self.run_seed(native=native))
                for panel in (INNER, COVER):
                    self.assertEqual('false', entries['local:' + panel]['isHomeSupported'])
                    self.assertEqual('false', entries['local:' + panel]['shouldShowSystemDecors'])
                self.assertEqual(expected, entries['local:' + INNER]['forcedDensity'])
                self.assertEqual(expected, entries['local:' + COVER]['forcedDensity'])

    def test_preserves_existing_density_and_unrelated_attributes(self):
        old = f'''<display-settings>
            <display name="local:{INNER}" forcedDensity="440" isHomeSupported="true" shouldShowSystemDecors="true" />
            <display name="local:{COVER}" someFlag="true" />
        </display-settings>'''
        entries = self.displays(self.run_seed(old))
        self.assertEqual('440', entries['local:' + INNER]['forcedDensity'])
        self.assertEqual('false', entries['local:' + INNER]['isHomeSupported'])
        self.assertEqual('false', entries['local:' + INNER]['shouldShowSystemDecors'])
        self.assertEqual('420', entries['local:' + COVER]['forcedDensity'])
        self.assertEqual('true', entries['local:' + COVER]['someFlag'])

    def test_uses_ports_for_port_indexed_settings(self):
        old = '''<display-settings>
            <config identifier="1" />
            <display name="port:148" forcedDensityRatio="1.1" />
        </display-settings>'''
        entries = self.displays(self.run_seed(old))
        self.assertEqual('420', entries['port:147']['forcedDensity'])
        self.assertEqual('1.1', entries['port:148']['forcedDensityRatio'])
        self.assertNotIn('forcedDensity', entries['port:148'])

    def test_wrong_target_or_malformed_settings_are_untouched(self):
        self.assertIsNone(self.run_seed(profile='f8u'))
        self.assertIsNone(self.run_seed(pda='S948BXXU6ZZKO'))
        invalid = '<display-settings>'
        self.assertEqual(invalid, self.run_seed(invalid))


if __name__ == '__main__':
    script = Path(sys.argv.pop(1)) / 'switcher/assets/guest_start.sh'
    BLOCK = script.read_text().split('        # Fold8 One UI 9.5 reports', 1)[1]
    BLOCK = BLOCK.split('        # vivo in fold mode 1', 1)[0]
    BLOCK = BLOCK.split('        if [', 1)[1]
    BLOCK = 'if [' + BLOCK
    unittest.main()
