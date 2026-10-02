"""Explicit Windows/WSL/native Linux entrypoint for the frozen v2 toolkit."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent


def is_wsl():
    try:
        return 'microsoft' in Path('/proc/sys/kernel/osrelease').read_text().lower()
    except OSError:
        return False


def verify_release():
    manifest = json.loads((SKILL / 'frozen-manifest.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['files'].items():
        path = SKILL / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Frozen release integrity failed: {relative}')
    return manifest


def windows_path(path):
    return subprocess.check_output(['wslpath', '-w', str(Path(path).resolve())], text=True).strip()


def windows_python():
    explicit = os.environ.get('PHONEUSE_WINDOWS_PYTHON')
    if explicit:
        path = explicit
        if ':' in path and not path.startswith('/'):
            path = subprocess.check_output(['wslpath', '-u', path], text=True).strip()
        if not Path(path).is_file():
            raise RuntimeError(f'Configured Windows Python was not found: {explicit}')
        return [path]
    for name in ('py.exe', 'python3.13.exe', 'python.exe'):
        if found := shutil.which(name):
            return [found, '-3.13'] if name == 'py.exe' else [found]
    candidate = subprocess.check_output(['wslpath', '-u', r'C:\Python313\python.exe'], text=True).strip()
    if Path(candidate).is_file():
        return [candidate]
    raise RuntimeError('Windows Python 3.13 was not found. Set PHONEUSE_WINDOWS_PYTHON; no native fallback is used.')


def translated_arguments(command, arguments):
    out = list(arguments)
    for index, value in enumerate(out):
        if index and out[index-1] == '--output' and not (':' in value or value.startswith('\\')):
            out[index] = windows_path(value)
    if command == 'u2' and 'screenshot' in out:
        index = out.index('screenshot') + 1
        if index < len(out) and not out[index].startswith('-') and ':' not in out[index]:
            out[index] = windows_path(out[index])
    return out


def required_versions():
    lines = (SCRIPTS / 'requirements-lock.txt').read_text().splitlines()
    return dict(line.split('==', 1) for line in lines if line and not line.startswith('#'))


def dependency_status(vendor):
    normalize = lambda value: value.lower().replace('_', '-')
    installed = {normalize(d.metadata['Name']): d.version
                 for d in importlib.metadata.distributions(path=[str(vendor)])}
    return {name: {'expected': version, 'installed': installed.get(normalize(name))}
            for name, version in required_versions().items()
            if installed.get(normalize(name)) != version}


def main():
    if os.name == 'nt':
        for stream in (sys.stdout, sys.stderr):
            stream.reconfigure(encoding='utf-8')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', choices=('auto', 'windows', 'native'), default='auto')
    parser.add_argument('command', choices=('verify', 'setup', 'doctor', 'devices', 'adb', 'toolkit', 'u2'))
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    manifest = verify_release()
    if args.command == 'verify':
        print(json.dumps({'version': manifest['version'], 'files_verified': len(manifest['files']), 'passed': True}))
        return 0
    selected = args.runtime
    if selected == 'auto':
        selected = 'windows' if os.name == 'nt' or is_wsl() else 'native'
    if selected == 'windows' and os.name != 'nt':
        if not is_wsl():
            raise RuntimeError('Windows execution from Linux requires WSL interop')
        forwarded = translated_arguments(args.command, args.arguments)
        return subprocess.run(windows_python() + [windows_path(__file__), '--runtime', 'windows',
                                                  args.command, *forwarded]).returncode
    if selected == 'native' and (os.name == 'nt' or platform.system() != 'Linux'):
        raise RuntimeError('The native route requires Linux; choose windows explicitly on Windows')
    if os.name == 'nt' and sys.version_info[:2] != (3, 13):
        raise RuntimeError('This frozen Windows runtime requires Python 3.13')
    if sys.version_info < (3, 10):
        raise RuntimeError('The native runtime requires Python 3.10 or newer')
    from runtime import add_vendor, configure_adb, vendor_dir
    vendor = vendor_dir()
    mismatches = dependency_status(vendor)
    if args.command == 'setup':
        if not mismatches:
            print(json.dumps({'runtime': selected, 'dependencies_already_pinned': True}))
            return 0
        if vendor.exists() and any(vendor.iterdir()):
            raise RuntimeError('Existing dependencies differ from the frozen pins. Preserve them and use a fresh skill installation.')
        vendor.mkdir(parents=True, exist_ok=True)
        if importlib.util.find_spec('pip'):
            installer = [sys.executable, '-m', 'pip', 'install']
            manager = 'pip'
        elif uv := shutil.which('uv'):
            installer = [uv, 'pip', 'install', '--python', sys.executable]
            manager = 'uv'
        else:
            raise RuntimeError('Setup requires pip or uv; install one in the selected host runtime')
        print(json.dumps({'dependency_installer': manager, 'runtime': selected}), flush=True)
        result = subprocess.run(installer + ['--only-binary=:all:', '--target', str(vendor),
                                             '-r', str(SCRIPTS / 'requirements-lock.txt')])
        if result.returncode:
            return result.returncode
        mismatches = dependency_status(vendor)
    if mismatches:
        raise RuntimeError('Pinned dependencies are missing or differ. Run setup. ' + json.dumps(mismatches))
    if args.command == 'setup':
        print(json.dumps({'runtime': selected, 'dependencies_pinned': True}))
        return 0
    add_vendor()
    adb_exe = configure_adb()
    if args.command in ('setup', 'doctor'):
        import uiautomator2, adbutils
        from PIL import Image
        raw = subprocess.run([str(adb_exe), 'devices'], capture_output=True, check=True, timeout=10).stdout.decode()
        ready = [line.split()[0] for line in raw.splitlines()[1:]
                 if len(line.split()) > 1 and line.split()[1] == 'device']
        print(json.dumps({'version': manifest['version'], 'runtime': selected, 'python': sys.executable,
                          'adb': str(adb_exe), 'runtime_ready': True, 'ready_devices': ready,
                          'live_phone_workflow_verified': False}, indent=2))
        return 0
    if args.command in ('devices', 'adb'):
        command = ['devices', '-l'] if args.command == 'devices' else args.arguments
        return subprocess.run([str(adb_exe), *command]).returncode
    executable = 'phoneuse.py' if args.command == 'toolkit' else 'u2cli.py'
    return subprocess.run([sys.executable, str(SCRIPTS / executable), *args.arguments]).returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
