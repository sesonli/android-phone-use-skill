# Testing and evidence boundaries / 测试方法与证据范围

## What a clean installation tests

Run `python tests/clean_install.py` from the repository. Windows uses Python 3.13. Linux uses Python 3.10 or newer; WSL runs this test through Linux explicitly. Creating the temporary virtual environment requires ensurepip or an existing uv installation.

The test creates a new installation and virtual environment, copies no existing vendor cache, clears Python/Android SDK configuration, restricts PATH, ignores local pip configuration, and obtains the exact dependencies from public PyPI without pip's cache. It uses the dependency's bundled ADB and a separate localhost ADB server, which it stops afterward. Existing skill installations and phone-control sessions are preserved.

Checks: installation; frozen-file hashes; fresh dependency installation; repeat setup; imports and bundled ADB; toolkit and upstream CLI help decoded as UTF-8; rejection of an absent device before writing a capture; automatic ADB discovery. CI additionally requires automatic discovery to select the bundled ADB.

Local tests still share the operator's OS and Python installation. They are not a fresh Windows VM or a security sandbox. The GitHub workflow checks out the public repository on new hosted runners: Ubuntu with Python 3.10 and 3.13, and Windows with Python 3.13. These runners have preinstalled software; restricting PATH and selecting bundled ADB reduces accidental SDK dependencies, but does not prove compatibility with a minimal OS or every CPU architecture.

A clean-install pass proves only these checks. It does not start Android UiAutomator on a real phone, read an app, transcribe audio, send a message, measure model latency, or establish record completeness.

## Prerequisites that remain the user's responsibility

Install an appropriate Python interpreter and provide network access to public PyPI for initial setup. Windows requires Python 3.13; Linux requires Python 3.10 or newer. The initial setup requires pip or uv. The ADB binary must be executable and compatible with the host architecture. USB needs OS access to the device; wireless ADB needs an authorized, reachable connection. WSL's default Windows route additionally needs Windows Python and working WSL interop; native WSL USB access needs the device exposed to WSL.

No preinstalled Codex, Android SDK, personal ADB key, local vendor cache, or particular user's filesystem path is required by the clean-install test. Actual skill discovery needs a compatible Codex installation. Controlling a phone requires that phone's debugging authorization and a working UiAutomator service. Other Android devices, OS builds, and app workflows remain untested unless separate evidence is recorded.

## Current phone evidence

Independent clean-install evidence: [run 37054394789](https://github.com/sesonli/android-phone-use-skill/actions/runs/37054394789), commit `ad3c8cf778b4b803d14ec4d5942c98522337e70c`, completed successfully on 2026-10-02. All nine installation checks passed in each of the three hosted jobs: Ubuntu/Python 3.10, Ubuntu/Python 3.13, and Windows/Python 3.13. The full logs were inspected, including automatic selection of bundled ADB. These are installation results only.

The historical acceptance is the OnePlus 8T / Android 13 / Windows / wireless ADB Settings-list workload described in [provenance](skills/android-phone-use/references/provenance.md). Runtime checks and this historical phone test are separate evidence. Follow the [CI run history](https://github.com/sesonli/android-phone-use-skill/actions/workflows/clean-install.yml) for each independent installation result and its exact commit. An unrun, failed, or cancelled job is not a pass.

## Deferred WeChat scenario / 微信测试计划，暂不执行

This scenario has not been tested and must not be advertised as supported. It is deferred until the user resumes phone testing. The designated target is **WeChat File Transfer Assistant (文件传输助手)**, not a personal contact or group.

1. Observe the foreground app and verify the chat is File Transfer Assistant.
2. Read a controlled test text and retain only the minimum evidence needed to check its content.
3. Use a controlled test voice message and WeChat's own Convert to Text action if present. Verify the resulting text against the known spoken content; an unavailable action or inaccessible result is a failed or untested step.
4. Prepare a reply based on the controlled conversation, verify the target again, send the test reply when this deferred test is authorized to resume, and verify that the exact text appears in the chat.
5. Record each step's success or failure separately. Seeing a send button or clicking it is not verified delivery. Chat display does not prove a human recipient read a message.

微信测试目前没有执行。后续只以“文件传输助手”为对象，使用受控的测试文字与语音，分别验证读消息、微信内置转文字、理解上下文、发送测试回复和界面结果。当前不操作微信，也不向真实联系人或群聊发送测试消息。仅当恢复手机测试后才执行这一计划。
