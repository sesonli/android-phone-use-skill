"""Install the frozen skill in a user scope, without replacing existing skills."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'skills'/'android-phone-use'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', type=Path, help='Exact destination skill directory')
    p.add_argument('--windows-vendor-from', type=Path, help='Optional existing pinned Windows dependency cache')
    args = p.parse_args()
    target = args.destination or Path.home()/'.agents'/'skills'/'android-phone-use'
    target = target.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise RuntimeError(f'Existing skill is preserved: {target}')
    manifest = json.loads((SOURCE/'frozen-manifest.json').read_text())
    for relative, expected in manifest['files'].items():
        if hashlib.sha256((SOURCE/relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Frozen release integrity failed: {relative}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.phone-use-install-', dir=target.parent) as staging_parent:
        staging = Path(staging_parent)/'android-phone-use'
        shutil.copytree(SOURCE, staging, ignore=shutil.ignore_patterns('.runtime', '__pycache__', '*.pyc'))
        if args.windows_vendor_from:
            cache = args.windows_vendor_from.resolve()
            if not (cache/'uiautomator2-3.7.0.dist-info').is_dir():
                raise RuntimeError('Cache does not contain uiautomator2 3.7.0')
            shutil.copytree(cache, staging/'scripts'/'.runtime'/'windows'/'vendor',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for relative, expected in manifest['files'].items():
            if hashlib.sha256((staging/relative).read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Frozen release integrity failed: {relative}')
        os.rename(staging, target)
    print(json.dumps({'installed': str(target), 'version': manifest['version'],
                      'windows_cache_copied': bool(args.windows_vendor_from)}, indent=2))


if __name__ == '__main__':
    main()
