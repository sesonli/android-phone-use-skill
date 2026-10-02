---
name: android-phone-use
description: "Operate an authorized Android phone and capture UI records with the frozen v2 toolkit. Use for persistent UI reads, bounded list scans, stable-state waits, adjacent-page continuity checks, and lossless screenshots from Windows, WSL, or native Linux."
---

# Android Phone Use

Use the packaged v2 scanner and pinned uiautomator2 3.7.0. Keep task outputs in the task workspace. The installed skill is a frozen release; develop later experiments separately.

## Runtime and entrypoint

Read [references/usage.md](references/usage.md) for commands, installation, and path handling. Run `scripts/run.py doctor` before device work. It verifies the release files, dependency versions, imports, and ADB availability; an empty `ready_devices` list means no phone is connected.

- Windows: use Windows Python 3.13.
- WSL: the default entrypoint explicitly delegates to Windows Python and Windows ADB. It translates output paths and uses the Windows host's existing ADB authorization. It does not silently switch hosts when that route fails.
- Native Linux: use `--runtime native` with Linux Python, Linux dependencies, and Linux ADB. This route has separate runtime validation; historical phone timings belong to the Windows route. Native Linux phone workflow performance must be measured on an attached device.

Use `scripts/run.py verify` to check the frozen files. Missing dependencies can be installed with `scripts/run.py setup`; each runtime has its own isolated dependency directory. Set `PHONEUSE_WINDOWS_PYTHON` or `ANDROID_ADB_EXE` when automatic discovery does not find the intended executable.

## Observe and operate

1. Discover devices through `run.py devices`; select an authorized, unlocked phone by its current serial. Wireless IPs and ports change. If discovery fails, use the endpoint currently shown on the phone or restore USB. An open TCP port alone does not identify a phone.
2. Capture a current tree and PNG through `run.py toolkit ... snapshot`. Use the tree for labels and selectors; inspect the PNG for images, clipped records, or custom views. The upstream CLI is available through `run.py u2 ...` for selectors and input.
3. Configure the repeated record wrapper ID, viewport, expected package, and swipe from the current app. Use one foreground controller per phone. Verify actions in the resulting UI.

For an ordered list with distinguishable records, prefer `scan --profile stable`. It uses active-window reads, accessible foreground-package checks, a 250 ms quiet interval for selected fields and bounds, and at least two contiguous overlapping records between adjacent pages. A continuity failure stops the scan and writes evidence. Preserve that evidence and adjust the viewport or gesture before retrying.

The scanner's default remains `conservative`, retaining fixed waits and all-window reads. Use it when the app does not meet the ordered-list assumptions. It provides fewer continuity guarantees. Bound work with `--pages` (maximum 20) and optionally `--max-records`. Keep PNG on every page when comparing performance under the original acceptance workload.

Visible text and positions becoming stable does not establish that photos or late network responses finished loading. Content-based deduplication can merge distinct records with identical fields. Heuristic grouping without a configured record ID needs visual validation. Accessibility captures only rendered, exposed content.

## Provenance and maintenance

Read [references/provenance.md](references/provenance.md) when citing measurements or extending the package. The packaged observation and scanning functions retain the accepted v2 algorithms. Portability changes are confined to runtime selection and dependency/ADB paths. No model is invoked by the toolkit.

Use current task authorization for consequential app actions. The historical test phone's permissions do not grant authority over another phone, account, purchase, or outbound message.
