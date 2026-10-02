# Android Phone Use skill

A frozen Codex skill for persistent Android UI reads and bounded list capture. It packages the accepted v2 scanner, stable-state waits, adjacent-page overlap checks, lossless PNG capture, and upstream uiautomator2 controls. Invoke it as `$android-phone-use`.

The sharing value is a reusable workflow and its acceptance method: collect several pages in one local operation, preserve raw evidence, and reject lost continuity. The executor and device APIs come from maintained upstream projects.

## Hosts

| Host | Execution route |
|---|---|
| Windows Codex | Windows Python 3.13 and Windows ADB |
| WSL Codex CLI | Default: explicit Windows Python/ADB delegation; output paths translated |
| Native Linux | Explicit native route: Linux Python 3.10+, Linux dependencies, Linux ADB |

Routes have separate isolated dependency directories and never silently substitute one host for another. Windows phone acceptance is historical. Native Linux runtime validation is separate from a live phone workflow test.

## Install globally

Clone or extract this repository, then install the skill:

```bash
python3 install.py
```

The default destination is the current user's `.agents/skills/android-phone-use`, a [documented global Codex skill location](https://learn.chatgpt.com/docs/build-skills). Windows users can run `py -3.13 install.py`. `--destination` accepts a custom skill directory, including a desktop host's configured skills folder. Existing skills are preserved.

From the installed skill directory:

```bash
python3 scripts/run.py setup
python3 scripts/run.py doctor
```

Use `py -3.13` on Windows. On WSL, `auto` uses Windows execution. Set `PHONEUSE_WINDOWS_PYTHON` if Windows Python cannot be found. On pure Linux, `auto` uses native execution; `--runtime native` makes the selection explicit. Install Android platform-tools or configure `ANDROID_ADB_EXE` when ADB is unavailable.

Setup needs pip or uv on the selected runtime and reports which package manager it uses. The skill can also be installed from the repository's `skills/android-phone-use` directory with Codex's skill installer. Reopen the skill selector or start a new conversation if the installed entry does not appear.

## Capture

```bash
python3 scripts/run.py devices
python3 scripts/run.py toolkit --serial DEVICE_SERIAL snapshot --output evidence/current.json --screenshot
```

Choose the current connected, authorized phone serial. Do not reuse a historical wireless endpoint. For a list scan, first inspect the app's wrapper IDs, viewport, and swipe. Read [usage](skills/android-phone-use/references/usage.md) for the stable-profile example and upstream controls.

## Frozen behavior and evidence

Version 2.0.0 retains the v2 scanning functions. The general default remains conservative; stable mode is preferred for verified ordered lists with distinguishable records. The release manifest checks code and instructions before execution. Setup installs exact dependency versions and stops if an existing cache differs from the pins.

[Provenance](skills/android-phone-use/references/provenance.md) records the historical same-record Settings benchmark and its limits. The source package includes no private captures, device identifiers, pairing codes, or host credentials. Dependencies are installed at runtime instead of distributing platform-specific wheels.

## License

Package code and instructions use MIT. uiautomator2, adbutils, and other dependencies retain their upstream licenses. No language model is downloaded or invoked by this package.

## Release checks

```bash
python3 -m unittest discover -s tests -v
python3 skills/android-phone-use/scripts/run.py verify
```

These checks cover frozen-file tampering, preserving an existing installed skill, refusing to substitute native execution for a failed Windows route, and rejecting Windows ADB in native mode. They do not require an attached phone. Device-specific acceptance remains a separate test.
