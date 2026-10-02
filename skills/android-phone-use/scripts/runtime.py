"""Host-specific dependencies and ADB discovery; no phone policy changes."""
from pathlib import Path
import os
import shutil
import sys

SCRIPTS = Path(__file__).resolve().parent


def vendor_dir():
    platform_name = 'windows' if os.name == 'nt' else 'native'
    return SCRIPTS / '.runtime' / platform_name / 'vendor'


def configure_adb():
    exe = 'adb.exe' if os.name == 'nt' else 'adb'
    explicit = os.environ.get('ANDROID_ADB_EXE') or os.environ.get('ADBUTILS_ADB_PATH')
    if explicit:
        selected = Path(explicit).expanduser()
        if not selected.is_file():
            raise RuntimeError(f'Configured ADB executable does not exist: {selected}')
    else:
        candidates = []
        if found := shutil.which(exe):
            candidates.append(Path(found))
        for name in ('ANDROID_SDK_ROOT', 'ANDROID_HOME'):
            if value := os.environ.get(name):
                candidates.append(Path(value) / 'platform-tools' / exe)
        if os.name == 'nt':
            candidates.append(Path.home() / '.codex' / 'tools' / 'android-platform-tools' / exe)
        candidates += [Path.home() / 'Android' / 'Sdk' / 'platform-tools' / exe,
                       vendor_dir() / 'adbutils' / 'binaries' / exe]
        selected = next((p for p in candidates if p.is_file()), None)
        if selected is None:
            raise RuntimeError('ADB was not found. Install Android platform-tools or set ANDROID_ADB_EXE.')
    selected = selected.resolve()
    if os.name != 'nt':
        with selected.open('rb') as stream:
            if stream.read(2) == b'MZ':
                raise RuntimeError('The native route requires Linux ADB; the configured executable is a Windows binary')
        if not os.access(selected, os.X_OK):
            raise RuntimeError(f'Linux ADB is not executable: {selected}')
    os.environ['ANDROID_ADB_EXE'] = str(selected)
    os.environ['ADBUTILS_ADB_PATH'] = str(selected)
    return selected


def add_vendor():
    vendor = str(vendor_dir())
    sys.path.insert(0, vendor)
    os.environ['PYTHONPATH'] = vendor + os.pathsep + os.environ.get('PYTHONPATH', '')
    return vendor
