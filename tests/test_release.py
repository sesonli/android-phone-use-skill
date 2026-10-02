"""Release invariants that do not need a phone, account, or model."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills'/'android-phone-use'
spec = importlib.util.spec_from_file_location('phone_use_release', SKILL/'scripts'/'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runtime_spec = importlib.util.spec_from_file_location('phone_use_runtime', SKILL/'scripts'/'runtime.py')
runtime = importlib.util.module_from_spec(runtime_spec)
runtime_spec.loader.exec_module(runtime)


class ReleaseTests(unittest.TestCase):
    def test_frozen_code_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp)/'skill'
            shutil.copytree(SKILL, copied, ignore=shutil.ignore_patterns('.runtime', '__pycache__'))
            previous = runner.SKILL
            try:
                runner.SKILL = copied
                self.assertEqual(runner.verify_release()['version'], '2.0.0')
                path = copied/'scripts'/'phoneuse.py'
                path.write_bytes(path.read_bytes()+b'\n# changed\n')
                with self.assertRaisesRegex(RuntimeError, 'integrity failed'):
                    runner.verify_release()
            finally:
                runner.SKILL = previous

    def test_install_preserves_existing_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'skills'/'android-phone-use'
            command = [sys.executable, str(ROOT/'install.py'), '--destination', str(target)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(first.stdout)['version'], '2.0.0')
            marker = target/'user-note.txt'
            marker.write_text('preserve my existing working state')
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn('Existing skill is preserved', second.stderr)
            self.assertEqual(marker.read_text(), 'preserve my existing working state')

    @unittest.skipUnless(os.name != 'nt', 'Host-selection check uses Linux')
    def test_failed_windows_route_does_not_switch_to_native(self):
        env = os.environ.copy()
        env['PHONEUSE_WINDOWS_PYTHON'] = '/nonexistent/phone-use/python.exe'
        command = [sys.executable, str(SKILL/'scripts'/'run.py'), '--runtime', 'windows', 'doctor']
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('"runtime_ready": true', result.stdout)
        self.assertTrue('Windows Python' in result.stderr or 'requires WSL' in result.stderr, result.stderr)

    @unittest.skipUnless(os.name != 'nt', 'Native host-boundary check uses Linux')
    def test_native_route_rejects_windows_adb(self):
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp)/'adb'
            executable.write_bytes(b'MZ' + b'\0'*32)
            executable.chmod(0o755)
            previous = os.environ.get('ANDROID_ADB_EXE')
            try:
                os.environ['ANDROID_ADB_EXE'] = str(executable)
                with self.assertRaisesRegex(RuntimeError, 'Windows binary'):
                    runtime.configure_adb()
            finally:
                if previous is None:
                    os.environ.pop('ANDROID_ADB_EXE', None)
                else:
                    os.environ['ANDROID_ADB_EXE'] = previous


if __name__ == '__main__':
    unittest.main()
