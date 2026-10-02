# Usage

The skill includes `scripts/run.py`, the v2 `phoneuse.py` scanner, and an upstream CLI launcher. Commands below are run from the installed skill directory. Replace `DEVICE_SERIAL`, output paths, package, IDs, and bounds with observed values.

## Setup and verification

Windows PowerShell:

```powershell
py -3.13 scripts/run.py setup
py -3.13 scripts/run.py doctor
py -3.13 scripts/run.py devices
```

WSL, using Windows execution explicitly:

```bash
python3 scripts/run.py --runtime windows setup
python3 scripts/run.py --runtime windows doctor
python3 scripts/run.py --runtime windows devices
```

The default on WSL is the Windows route. `PHONEUSE_WINDOWS_PYTHON` accepts a Windows executable path or its WSL path. Windows Python must be 3.13. The launcher locates `py.exe`, `python.exe`, or the standard `C:\Python313\python.exe` installation. Configure the environment variable when those are unavailable. Skill paths on the WSL filesystem are translated to UNC paths with `wslpath`; imports still run on Windows.

Native Linux:

```bash
python3 scripts/run.py --runtime native setup
python3 scripts/run.py --runtime native doctor
python3 scripts/run.py --runtime native devices
```

Linux requires Python 3.10 or newer and an executable Linux ADB. Setup uses an available pip or uv and reports which it selected. It installs the exact Python requirements in `scripts/.runtime/native/vendor`; Windows uses `scripts/.runtime/windows/vendor`. Neither route changes global Python packages. ADB can come from PATH, Android SDK environment variables, or the dependency's bundled platform binary. `ANDROID_ADB_EXE` selects an explicit ADB executable. No Windows executable is selected in native mode.

`run.py verify` validates the frozen file hashes without importing device dependencies. `doctor` reports runtime readiness and connected device serials; it does not certify an app workflow. If an existing runtime's dependencies differ from the pins, setup stops rather than overwriting them.

## Snapshot and upstream controls

```bash
python3 scripts/run.py toolkit --serial DEVICE_SERIAL snapshot --output evidence/current.json --screenshot
python3 scripts/run.py u2 -s DEVICE_SERIAL device-info
python3 scripts/run.py u2 -s DEVICE_SERIAL dump-hierarchy
python3 scripts/run.py u2 -s DEVICE_SERIAL click --text Settings
```

Use `py -3.13` instead of `python3` on Windows. Upstream input commands require a fresh observed selector and current task authorization. Use `run.py u2 --help` for the installed CLI's exact options.

On the WSL Windows route, toolkit `--output` paths and the upstream `screenshot` filename are converted from WSL to Windows paths. For other upstream commands that accept file paths, provide an explicit Windows or UNC path. Native mode keeps Linux output paths unchanged.

## Stable list scan

Illustration for the historical 1080 by 2400 Android Settings fixture:

```bash
python3 scripts/run.py toolkit --serial DEVICE_SERIAL scan --profile stable --pages 20 --max-records 34 --package com.android.settings --record-id android:id/title --region 0 285 1080 2249 --swipe 540 1900 540 1000 900 --screenshots all --output evidence/scan/scan.json
```

These coordinates and resource IDs are fixture examples, not general app defaults. First observe the current screen and choose the record wrapper ID, content region, and controlled swipe. Stable mode requires all of them and an expected foreground package. Its timeout is 5 seconds, quiet interval 0.25 seconds, poll interval 0.05 seconds, and minimum overlap 2 records. Explicit parameters can adapt these to an app after coverage checks.

Each record contains labeled subtree fields, resource IDs, bounds, a content fingerprint, and first-page provenance. Raw page trees retain extra visible records on the final page even when `--max-records` stops collection. A failed overlap writes `continuity-failure.json` and raises an error after that scroll.

For layouts incompatible with ordered overlap, use `--profile conservative` with an appropriate `--settle-seconds`. It does not establish exact list continuity. Validate completeness independently for each app.

## Service lifecycle

uiautomator2 uses its temporary phone-side UiAutomator service. The upstream CLI can persist host connections across calls. Shell `uiautomator dump` and the persistent service cannot own the UiAutomation connection simultaneously. Before an old ADB baseline, stop the host service only if this task owns it, allow its phone connection to close, and confirm no other controller is running. Ordinary capture does not need the slow baseline.

Use `run.py u2 kill-server` only for a server this task started. Wireless disconnect does not disable debugging on the phone. Do not put credentials, pairing codes, private app captures, or test-specific device information into the shared package.
