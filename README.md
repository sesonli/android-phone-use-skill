# Android Phone Use skill

[English](README.md) | [简体中文](README.zh-CN.md)

A Codex skill for operating Android phones through USB or wireless ADB. It reads accessible UI labels and positions, exposes upstream uiautomator2 controls, and collects scrollable lists as structured records with PNG evidence. Invoke it as `$android-phone-use`.

## What it does

- Capture the current screen's UI tree and a lossless screenshot.
- Use observed selectors or coordinates to operate the phone through uiautomator2.
- Collect several list pages in one bounded local operation.
- Wait for selected records and positions to settle, then check overlap between adjacent pages.
- Save structured records and page evidence for inspection and comparison.

The package freezes the accepted v2 scanner. It combines maintained [uiautomator2](https://github.com/openatx/uiautomator2) and [adbutils](https://github.com/openatx/adbutils) with a reusable capture workflow. Its sharing value is the integrated workflow and acceptance method. The toolkit itself does not call a language model.

Example request after installation:

> Use $android-phone-use to inspect the connected Android phone, capture its current screen, and collect the first 30 records from the visible list with screenshots.

## Phone compatibility

This is an **Android phone skill**. Computer operating-system support and phone operating-system support are separate.

| Phone software | Scope of this release |
|---|---|
| Android, including Android-based manufacturer systems | Target platform. The phone must authorize ADB and allow the Android UiAutomator service to run. Each device and app still needs validation. |
| Huawei software that retains Android compatibility | Conditional and untested. Use only if ADB and Android UiAutomator actually work on that build; the ability to install APKs alone is insufficient. |
| HarmonyOS NEXT / native HarmonyOS | Unsupported. This package has no HarmonyOS HDC or native UI automation backend. |
| iPhone / iOS | Unsupported. This package has no iOS automation backend. |

The historical phone acceptance used **one OnePlus 8T running Android 13**, over wireless ADB, on a Settings application list. It does not establish coverage of every Android version, phone brand, or app. The release does not claim a tested minimum Android version.

Enable debugging, authorize the selected host, and confirm the phone appears as `device` in `adb devices`. See [Android's ADB documentation](https://developer.android.com/tools/adb). UI capture depends on content exposed to Android UiAutomator; custom views and image-only content may need screenshot inspection. HarmonyOS uses a separate toolchain documented in [Huawei's HDC guide](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/hdc); this release does not implement it.

## Hosts

| Host | Execution route | Validation |
|---|---|---|
| Windows Codex | Windows Python 3.13 and Windows ADB | Historical phone acceptance plus current runtime checks |
| WSL Codex CLI, default | Explicit Windows Python/ADB delegation; output paths translated | Runtime checks, including execution from the WSL filesystem |
| WSL Codex CLI, `--runtime native` | Linux Python 3.10+, Linux dependencies and Linux ADB | Runtime checks in WSL; no Linux phone workflow acceptance |
| Standalone Linux | Native Linux execution; no Windows required | Native route checked in WSL; standalone Linux phone workflow untested |

Routes have separate isolated dependency directories and never silently substitute one host for another. Windows phone acceptance is historical. Native Linux runtime validation is separate from a live phone workflow test.

**WSL and Linux can use this skill; it is not Windows-only.** The WSL default reuses the Windows execution route. Explicit native mode uses Linux tools instead. For native mode, Linux ADB must reach the phone through USB or an authorized wireless connection; WSL USB access requires the device to be made available to WSL. A successful `doctor` check without a connected device verifies the runtime only.

## Install globally

Clone this repository, then install the skill:

```bash
git clone https://github.com/sesonli/android-phone-use-skill.git
cd android-phone-use-skill
python3 install.py
```

You can also download and extract the source, then run `install.py` from that directory.

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
