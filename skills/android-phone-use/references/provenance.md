# Frozen release provenance

Release: 2.0.1. Frozen on 2026-10-02 from the accepted v2 scanner. Version 2.0.0 remains available as the original frozen tag.

The 2.0.1 patch corrects `toolkit doctor` to inspect the current runtime dependency directory. The scanning and observation functions are unchanged. Offline tests replay synthetic XML frames through the real extraction, waiting, scrolling, and continuity logic, while replacing device transport and the clock. These tests are separate from live-phone evidence.

The original scanner SHA-256 was `53c3d2f04f0a1eb5a1ddf6b7ab1f13581dde82e00bed1d27ebdc520c0eed9b0e`. The release adds portable ADB/dependency discovery and explicit Windows, WSL, and Linux entrypoints. Core observation, record extraction, quiet-interval waiting, foreground checks, scrolling, PNG capture, and deduplication functions are retained. No round-3 gesture or screenshot experiment is promoted into this release.

The maintained [uiautomator2](https://github.com/openatx/uiautomator2) executor is pinned at 3.7.0. [adbutils](https://github.com/openatx/adbutils) is pinned at 2.12.0. Both use MIT licensing. Full Python dependency versions are in `scripts/requirements-lock.txt`; upstream distributions retain their own licenses. The runtime dependencies are installed separately and are not included in the source archive.

The readiness policy adapts Android's [UiObject2 stable-state guidance](https://developer.android.com/reference/androidx/test/uiautomator/UiObject2) to host observations of selected records and bounds. The server does not expose that AndroidX extension directly. List continuity is checked by an exact suffix/prefix overlap. The release supplies a bounded batch operation that can reduce repeated agent calls; no model latency or token saving was measured.

## Historical phone acceptance

Windows Python 3.13 controlled a OnePlus 8T running Android 13 over wireless ADB. Three alternating paired runs captured the exact same ordered first 34 Settings application records; one expanded pair captured 80. Both policies kept a lossless PNG on every page, with identical record ordering and no duplicates in the accepted comparisons.

| Workload | Conservative policy | Stable policy |
|---|---:|---:|
| 34 records, mean of 3 pairs | 15.689 s | 13.253 s |
| 80 records, 1 pair | 42.699 s | 34.460 s |

Timings include UI reads, waits, gestures, foreground checks, PNG capture/transfer, parsing, and deduplication. They exclude fixture launch/normalization, Python/service startup, and model inference. These historical results concern one Settings list; they do not prove another app's coverage or speed. The native Linux route has not inherited a phone-level speed claim.

Whole-container UiScrollable and alternate swipe injection were rejected because they skipped records or were slower on the fixture. Lossy JPEG was not substituted for PNG. Later segmented-gesture and transport candidates remained untested when the phone connection was lost. The source archive omits private UI trees, screenshots, device serials, IP addresses, and authentication material.
