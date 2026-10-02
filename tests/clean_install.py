"""Fresh installation smoke test; no Codex, SDK, phone, or cached vendor required."""
from pathlib import Path
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-automatic-bundled-adb', action='store_true')
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('PYTHON', 'PIP_', 'UV_', 'ANDROID_', 'ADB'))
           and k not in ('PHONEUSE_WINDOWS_PYTHON', 'CODEX_HOME')}
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_INDEX_URL='https://pypi.org/simple',
               PIP_NO_CACHE_DIR='1', PYTHONIOENCODING='utf-8')
    checks = []

    def run(label, command, expected=0):
        result = subprocess.run(command, env=env, cwd=directory,
                                capture_output=True, text=True, encoding='utf-8', timeout=180)
        if result.returncode != expected:
            raise RuntimeError(f'{label}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
        checks.append({'check': label, 'exit_code': result.returncode})
        print(label, 'PASS', flush=True)
        return result.stdout

    with tempfile.TemporaryDirectory(prefix='phone-use-clean-') as directory:
        work = Path(directory)
        environment = work/'venv'
        try:
            venv.EnvBuilder(with_pip=True).create(environment)
        except (subprocess.CalledProcessError, RuntimeError):
            uv = shutil.which('uv')
            if not uv:
                raise RuntimeError('Creating the test venv needs ensurepip or uv')
            if environment.exists():
                shutil.rmtree(environment)
            subprocess.run([uv, 'venv', '--seed', '--python', sys.executable,
                            str(environment)], check=True, env=env)
        bin_dir = environment/('Scripts' if os.name == 'nt' else 'bin')
        python = str(bin_dir/('python.exe' if os.name == 'nt' else 'python'))
        env['PATH'] = str(bin_dir)
        if os.name == 'nt':
            env['PATH'] += os.pathsep + str(Path(os.environ['SystemRoot'])/'System32')
        target = work/'installed'/'android-phone-use'
        run('install', [python, str(ROOT/'install.py'), '--destination', str(target)])
        assert not (target/'scripts/.runtime').exists(), 'Existing runtime cache was copied'
        runner = str(target/'scripts/run.py')
        route = 'windows' if os.name == 'nt' else 'native'
        command = [python, runner, '--runtime', route]
        run('frozen_files', command+['verify'])
        run('fresh_public_pypi_dependencies', command+['setup'])
        run('repeat_setup_preserves_pins', command+['setup'])
        vendor = target/'scripts/.runtime'/route/'vendor'
        if route == 'native':
            vendor = target/'scripts/.runtime/native/vendor'
        adb = vendor/'adbutils/binaries'/('adb.exe' if os.name == 'nt' else 'adb')
        assert adb.is_file(), 'The public dependency lacks bundled ADB for this platform'
        # Use a separate ADB server; do not reuse the operator's phone session.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env['ADB_SERVER_SOCKET'] = f'tcp:localhost:{port}'
        env['ANDROID_ADB_EXE'] = str(adb)
        try:
            output = json.loads(run('bundled_adb_doctor', command+['doctor']))
            assert output['runtime_ready'] is True
            assert output['live_phone_workflow_verified'] is False
            run('toolkit_help_utf8', command+['toolkit', '--help'])
            run('upstream_help_utf8', command+['u2', '--help'])
            absent = run('missing_device_rejected', command+['toolkit', '--serial',
                         'PHONE_USE_NONEXISTENT_TEST_DEVICE', 'snapshot', '--output',
                         str(work/'must-not-exist.json')], expected=1)
            assert not (work/'must-not-exist.json').exists(), absent
            env.pop('ANDROID_ADB_EXE')
            env.pop('ADBUTILS_ADB_PATH', None)
            automatic = json.loads(run('automatic_adb_discovery', command+['doctor']))
            if args.require_automatic_bundled_adb:
                assert Path(automatic['adb']).resolve() == adb.resolve(), automatic
        finally:
            subprocess.run([str(adb), 'kill-server'], env=env, capture_output=True, timeout=15)
        print(json.dumps({'runtime': route, 'python': sys.version.split()[0],
                          'fresh_dependencies_from_public_pypi': True,
                          'bundled_adb_verified': True,
                          'automatic_adb': automatic['adb'],
                          'phone_workflow_tested': False, 'checks': checks}, indent=2))


if __name__ == '__main__':
    main()
