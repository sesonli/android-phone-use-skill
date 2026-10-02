"""Bounded, general Android UI capture through ADB and UiAutomator2.

Requires an authorized, unlocked device. `scan` only scrolls; it never opens a
record, favorites, sends a message, or uses an app's private network API.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from runtime import configure_adb, add_vendor
add_vendor()
ADB = configure_adb()
BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def adb(serial: str, *args: str, timeout: int = 30) -> bytes:
    proc = subprocess.run([str(ADB), "-s", serial, *args], capture_output=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or f"adb exited {proc.returncode}")
    return proc.stdout


def checked_device(serial: str) -> None:
    if not ADB.is_file():
        raise RuntimeError(f"Windows ADB not found: {ADB}")
    devices = subprocess.run([str(ADB), "devices"], capture_output=True, check=True).stdout.decode()
    ready = {line.split()[0] for line in devices.splitlines()[1:] if len(line.split()) > 1 and line.split()[1] == "device"}
    if serial not in ready:
        raise RuntimeError(f"Device {serial} is not connected and authorized. Ready: {', '.join(sorted(ready)) or 'none'}")


def foreground_package(serial: str) -> str | None:
    output = adb(serial, "shell", "dumpsys", "window").decode("utf-8", "replace")
    matches = re.findall(r"mFocusedApp=.*? ([\w.]+)/", output)
    return matches[-1] if matches else None


def service(serial: str):
    try:
        import uiautomator2 as u2
    except ImportError as exc:
        raise RuntimeError("uiautomator2 is missing from project vendor directory") from exc
    return u2.connect(serial)


def parse_tree(xml: str) -> dict:
    root = ET.fromstring(xml)
    nodes: list[dict] = []
    children: dict[int, list[int]] = {}
    def visit(el: ET.Element, parent: int | None = None) -> int:
        idx = len(nodes)
        a = el.attrib
        match = BOUNDS.fullmatch(a.get("bounds", ""))
        bounds = [int(x) for x in match.groups()] if match else None
        nodes.append({"index": idx, "parent": parent, "text": a.get("text", ""),
                      "description": a.get("content-desc", ""), "resource_id": a.get("resource-id", ""),
                      "class": a.get("class", ""), "package": a.get("package", ""),
                      "bounds": bounds, "clickable": a.get("clickable") == "true",
                      "visible": a.get("visible-to-user", "true") == "true",
                      "scrollable": a.get("scrollable") == "true"})
        children[idx] = [visit(child, idx) for child in el if child.tag == "node"]
        return idx
    for child in root:
        if child.tag == "node":
            visit(child)
    labels = [{"text": n["text"] or n["description"], "bounds": n["bounds"],
               "resource_id": n["resource_id"], "node": n["index"]}
              for n in nodes if n["visible"] and (n["text"] or n["description"])]
    widths = [n["bounds"][2] for n in nodes if n["bounds"]]
    heights = [n["bounds"][3] for n in nodes if n["bounds"]]
    screen_w, screen_h = max(widths, default=0), max(heights, default=0)
    candidates = []
    for n in nodes:
        b = n["bounds"]
        if not b or not screen_w or not screen_h:
            continue
        area = (b[2] - b[0]) * (b[3] - b[1]) / (screen_w * screen_h)
        if not (0.025 <= area <= 0.65) or b[2] - b[0] < screen_w * 0.45:
            continue
        descendants = []
        stack = [n["index"]]
        while stack:
            current = stack.pop()
            if nodes[current]["text"] or nodes[current]["description"]:
                descendants.append(nodes[current]["text"] or nodes[current]["description"])
            stack.extend(children[current])
        descendants = list(dict.fromkeys(descendants))
        if len(descendants) >= 2 and (n["clickable"] or n["resource_id"]):
            candidates.append({"node": n["index"], "resource_id": n["resource_id"],
                               "bounds": b, "labels": descendants})
    # Prefer the smallest useful wrapper when a large clickable container nests cards.
    candidates.sort(key=lambda c: (c["bounds"][2]-c["bounds"][0]) * (c["bounds"][3]-c["bounds"][1]))
    cards = []
    for c in candidates:
        contained = any(c["bounds"][0] <= x["bounds"][0] and c["bounds"][1] <= x["bounds"][1]
                        and c["bounds"][2] >= x["bounds"][2] and c["bounds"][3] >= x["bounds"][3]
                        for x in cards)
        if not contained:
            cards.append(c)
    cards.sort(key=lambda c: (c["bounds"][1], c["bounds"][0]))
    if len(cards) < 3:
        # Flat lists often expose one label per repeated row and no enclosing
        # clickable wrapper. Keep these as single-field candidate records.
        counts = Counter(x["resource_id"] for x in labels if x["resource_id"])
        for item in labels:
            b = item["bounds"]
            if b and b[2] > b[0] and b[3] > b[1] and counts[item["resource_id"]] >= 3:
                cards.append({"node": item["node"], "resource_id": item["resource_id"],
                              "bounds": b, "labels": [item["text"]], "kind": "repeated_label"})
        cards.sort(key=lambda c: (c["bounds"][1], c["bounds"][0]))
    for c in cards:
        key = "\u241f".join(c["labels"])
        c["fingerprint"] = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return {"nodes": nodes, "labels": labels, "cards": cards,
            "screen": [screen_w, screen_h], "node_count": len(nodes), "label_count": len(labels)}


def old_dump(serial: str) -> str:
    # Baseline helper emits flattened JSON, so raw XML is read with its same 3-call path.
    remote = f"/sdcard/Download/phoneuse-{os.getpid()}.xml"
    try:
        adb(serial, "shell", "uiautomator", "dump", remote, timeout=30)
        return adb(serial, "exec-out", "cat", remote).decode("utf-8")
    finally:
        try:
            adb(serial, "shell", "rm", remote, timeout=5)
        except Exception:
            pass


def timed_dump(serial: str, backend: str, d=None, active_window=False) -> tuple[dict, float, float]:
    start = time.perf_counter()
    if backend == "u2":
        xml = d.dump_hierarchy(compressed=False, root_in_active=True) if active_window else d.dump_hierarchy(compressed=False)
    else:
        xml = old_dump(serial)
    dump_s = time.perf_counter() - start
    start = time.perf_counter()
    tree = parse_tree(xml)
    parse_s = time.perf_counter() - start
    return tree, dump_s, parse_s


def screenshot(serial: str, output: Path) -> dict:
    start = time.perf_counter()
    raw = adb(serial, "exec-out", "screencap", "-p")
    elapsed = time.perf_counter() - start
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Screen capture did not return PNG")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    return {"path": str(output), "seconds": elapsed, "bytes": len(raw)}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def contiguous_overlap(previous: list[str], current: list[str]) -> int:
    """Longest exact previous-page suffix matching the current-page prefix."""
    return max((n for n in range(1, min(len(previous), len(current)) + 1)
                if previous[-n:] == current[:n]), default=0)


def wait_stable(read, observe, previous, timeout: float, quiet: float, poll: float):
    """Adapt Android's quiet-interval policy to selected record fields and bounds.

    Unchanged observations wait through the timeout. Changed but unstable state
    is an error; it is never accepted just because the deadline expired.
    """
    start = time.perf_counter()
    last, since, pending = None, None, None
    samples = 0
    while time.perf_counter() - start < timeout:
        pending = read()
        state = observe(pending[0])
        samples += 1
        now = time.perf_counter()
        if state:
            if state != last:
                since = now
            elif state != previous and since is not None and now - since >= quiet:
                return pending, {"samples": samples, "changed": True, "stable": True}
        else:
            since = None
        last = state
        time.sleep(poll)
    if last and last == previous and since is not None and time.perf_counter() - since >= quiet:
        return pending, {"samples": samples, "changed": False, "stable": True}
    raise RuntimeError("Selected records did not become stable before timeout; stopped after scroll")


def bench(args) -> None:
    result = {"serial": args.serial, "repeats": args.repeats, "observations": []}
    for i in range(args.repeats):
        row = {"iteration": i + 1}
        tree, dump_s, parse_s = timed_dump(args.serial, "adb")
        row["adb"] = {"dump_seconds": dump_s, "parse_seconds": parse_s,
                      "nodes": tree["node_count"], "labels": tree["label_count"],
                      "cards": len(tree["cards"]),
                      "sample_label_ids": sorted({x["resource_id"] for x in tree["labels"] if x["resource_id"]})[:10]}
        if args.screenshot:
            row["screenshot"] = screenshot(args.serial, args.output.parent / f"bench-{i+1}.png")
        result["observations"].append(row)
    # The two UiAutomator services cannot own the accessibility connection at
    # the same time. Finish all shell dumps before starting the persistent jar.
    d = service(args.serial)
    for row in result["observations"]:
        tree, dump_s, parse_s = timed_dump(args.serial, "u2", d)
        row["u2"] = {"dump_seconds": dump_s, "parse_seconds": parse_s,
                     "nodes": tree["node_count"], "labels": tree["label_count"],
                     "cards": len(tree["cards"]),
                     "sample_label_ids": sorted({x["resource_id"] for x in tree["labels"] if x["resource_id"]})[:10]}
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def snapshot(args) -> None:
    d = service(args.serial) if args.backend == "u2" else None
    tree, dump_s, parse_s = timed_dump(args.serial, args.backend, d)
    result = {"serial": args.serial, "backend": args.backend, "dump_seconds": dump_s,
              "parse_seconds": parse_s, "tree": tree}
    if args.screenshot:
        result["screenshot"] = screenshot(args.serial, args.output.with_suffix(".png"))
    write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "dump_seconds": dump_s,
                      "nodes": tree["node_count"], "labels": tree["label_count"],
                      "cards": len(tree["cards"])}, ensure_ascii=False))


def scan(args) -> None:
    d = service(args.serial) if args.backend == "u2" else None
    stable_profile = args.profile == "stable"
    def read():
        return timed_dump(args.serial, args.backend, d, active_window=stable_profile)
    def current_package():
        if d:
            return d.info.get("currentPackageName") if stable_profile else d.app_current().get("package")
        return foreground_package(args.serial)
    if args.package:
        current = current_package()
        if current != args.package:
            raise RuntimeError(f"Foreground package is {current}, expected {args.package}")
    pages, unique = [], {}
    started = time.perf_counter()
    def records(tree: dict) -> list[dict]:
        if not args.record_id:
            return tree["cards"]
        out = []
        for node in tree["nodes"]:
            b = node["bounds"]
            inside = not args.region or (b and b[0] >= args.region[0] and b[1] >= args.region[1] and b[2] <= args.region[2] and b[3] <= args.region[3])
            if not inside or node["resource_id"] != args.record_id or not b or b[2] <= b[0] or b[3] <= b[1]:
                continue
            fields = []
            for item in tree["labels"]:
                ancestor = item["node"]
                while ancestor is not None and ancestor != node["index"]:
                    ancestor = tree["nodes"][ancestor]["parent"]
                if ancestor == node["index"] and item["text"].strip():
                    fields.append({"resource_id": item["resource_id"], "text": item["text"].strip()})
            values = [item["text"] for item in fields]
            if values:
                key = json.dumps(fields, ensure_ascii=False, sort_keys=True)
                out.append({"resource_id": args.record_id, "bounds": b, "labels": values, "fields": fields,
                            "fingerprint": hashlib.sha256(key.encode()).hexdigest()[:16],
                            "kind": "resource_id_subtree"})
        return out
    def signature_for(tree: dict) -> str:
        source = records(tree) if args.record_id else tree["labels"]
        strings = ["\u241f".join(x["labels"]) if "labels" in x else x["text"] for x in source]
        return hashlib.sha256("\u241f".join(strings).encode()).hexdigest()[:16]
    def record_state(tree: dict):
        return [(x["fingerprint"], tuple(x["bounds"])) for x in records(tree)]
    pending = None
    initial_stability = None
    if stable_profile:
        pending, initial_stability = wait_stable(read, record_state, None, args.wait_seconds,
                                                args.stable_seconds, args.poll_seconds)
    for page in range(args.pages):
        tree, dump_s, parse_s = pending or read()
        pending = None
        if args.record_id and not records(tree):
            ready_start = time.perf_counter()
            while not records(tree) and time.perf_counter() - ready_start < args.wait_seconds:
                time.sleep(args.settle_seconds)
                tree, dump_s, parse_s = read()
            if not records(tree):
                raise RuntimeError("Selected record ID is absent; stopped before scrolling")
        signature = signature_for(tree)
        row = {"page": page + 1, "signature": signature, "dump_seconds": dump_s,
               "parse_seconds": parse_s, "tree": tree}
        if page == 0 and initial_stability:
            row["initial_stability"] = initial_stability
        if args.screenshots == "all" or (args.screenshots == "sparse" and tree["label_count"] < args.sparse_threshold):
            row["screenshot"] = screenshot(args.serial, args.output.parent / f"page-{page+1}.png")
        pages.append(row)
        for card in records(tree):
            unique.setdefault(card["fingerprint"], {**card, "first_page": page + 1})
            if args.max_records and len(unique) >= args.max_records:
                break
        if args.max_records and len(unique) >= args.max_records:
            row["stop_reason"] = "Requested record limit reached"
            break
        if page + 1 == args.pages:
            break
        if args.package and current_package() != args.package:
            raise RuntimeError("Foreground app changed during scan; stopped before scrolling")
        w, h = tree["screen"]
        if not w or not h:
            raise RuntimeError("Unknown screen bounds; stopped before scrolling")
        action_start = time.perf_counter()
        if args.swipe:
            adb(args.serial, "shell", "input", "swipe", *(str(v) for v in args.swipe))
        elif d:
            d.swipe(w * 0.5, h * 0.82, w * 0.5, h * 0.28, duration=0.3)
        else:
            adb(args.serial, "shell", "input", "swipe", str(int(w * 0.5)), str(int(h * 0.82)),
                str(int(w * 0.5)), str(int(h * 0.28)), "300")
        row["swipe_seconds"] = time.perf_counter() - action_start
        load_start = time.perf_counter()
        changed = False
        if stable_profile:
            pending, observation = wait_stable(read, record_state, record_state(tree), args.wait_seconds,
                                               args.stable_seconds, args.poll_seconds)
            row["stability"] = observation
            changed = signature_for(pending[0]) != signature
            if changed:
                previous_ids = [x["fingerprint"] for x in records(tree)]
                current_ids = [x["fingerprint"] for x in records(pending[0])]
                overlap = contiguous_overlap(previous_ids, current_ids)
                row["overlap_records"] = overlap
                if overlap < args.min_overlap:
                    write_json(args.output.parent / "continuity-failure.json", {
                        "page": page + 1, "overlap": overlap, "previous_tree": tree,
                        "next_tree": pending[0], "accepted_pages": pages,
                        "reason": "Required contiguous record overlap is absent"})
                    raise RuntimeError(f"Record continuity lost (overlap {overlap} < {args.min_overlap}); stopped after scroll")
        else:
            while time.perf_counter() - load_start < args.wait_seconds:
                time.sleep(args.settle_seconds)
                pending = read()
                if signature_for(pending[0]) != signature:
                    changed = True
                    break
        row["load_seconds"] = time.perf_counter() - load_start
        if not changed:
            row["stop_reason"] = "No new accessible text after scroll"
            break
    elapsed = time.perf_counter() - started
    result = {"serial": args.serial, "backend": args.backend, "package": args.package, "record_id": args.record_id,
              "profile": args.profile, "max_records": args.max_records,
              "elapsed_seconds": elapsed, "pages_captured": len(pages), "unique_records": len(unique),
              "records_per_minute": len(unique) * 60 / elapsed if elapsed else 0,
              "note": ("Records are visible subtrees with the selected resource ID; validate their meaning in the app."
                       if args.record_id else "Records are heuristic groups of accessibility labels; validate before use."),
              "records": list(unique.values()), "pages": pages}
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("records", "pages")}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="ADB serial; always select explicitly")
    commands = parser.add_subparsers(dest="command", required=True)
    doc = commands.add_parser("doctor", help="Check device and project runtime")
    snap = commands.add_parser("snapshot", help="Capture one UI tree")
    snap.add_argument("--backend", choices=("adb", "u2"), default="u2")
    snap.add_argument("--output", type=Path, required=True)
    snap.add_argument("--screenshot", action="store_true")
    bm = commands.add_parser("bench", help="Compare old 3-call dump with persistent service")
    bm.add_argument("--repeats", type=int, default=3)
    bm.add_argument("--output", type=Path, required=True)
    bm.add_argument("--screenshot", action="store_true")
    sc = commands.add_parser("scan", help="Bounded scrolling capture of visible UI records")
    sc.add_argument("--backend", choices=("adb", "u2"), default="u2")
    sc.add_argument("--profile", choices=("conservative", "stable"), default="conservative",
                    help="stable: active-window reads, accessible-package checks, quiet interval and adjacent-page overlap")
    sc.add_argument("--pages", type=int, default=3)
    sc.add_argument("--max-records", type=int, help="Stop at this many unique records; captured page trees retain extra visible records")
    sc.add_argument("--package", help="Expected foreground package safety check")
    sc.add_argument("--region", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"), help="Require record bounds fully within this viewport")
    sc.add_argument("--record-id", help="Use each matching node and its labeled descendants as a structured record")
    sc.add_argument("--output", type=Path, required=True)
    sc.add_argument("--screenshots", choices=("none", "sparse", "all"), default="none")
    sc.add_argument("--sparse-threshold", type=int, default=8)
    sc.add_argument("--wait-seconds", type=float, default=5)
    sc.add_argument("--settle-seconds", type=float, default=0.5)
    sc.add_argument("--stable-seconds", type=float, default=0.25, help="Required quiet interval in stable profile")
    sc.add_argument("--poll-seconds", type=float, default=0.05, help="Poll interval in stable profile")
    sc.add_argument("--min-overlap", type=int, default=2, help="Required contiguous records shared by adjacent stable-profile list pages")
    sc.add_argument("--swipe", type=int, nargs=5, metavar=("X1", "Y1", "X2", "Y2", "MS"), help="Explicit shared ADB swipe for reproducible comparisons")
    args = parser.parse_args()
    checked_device(args.serial)
    if args.command == "doctor":
        from runtime import vendor_dir
        print(json.dumps({"serial": args.serial, "state": "device", "adb": str(ADB),
                          "vendor_uiautomator2": (vendor_dir() / "uiautomator2").is_dir()}))
    elif args.command == "snapshot":
        snapshot(args)
    elif args.command == "bench":
        if not 1 <= args.repeats <= 10:
            parser.error("--repeats must be 1..10")
        bench(args)
    elif args.command == "scan":
        if not 1 <= args.pages <= 20:
            parser.error("--pages must be 1..20")
        if args.max_records is not None and not 1 <= args.max_records <= 1000:
            parser.error("--max-records must be 1..1000")
        if not args.wait_seconds > 0 or not args.settle_seconds > 0:
            parser.error("--wait-seconds and --settle-seconds must be positive")
        if args.region and (args.region[0] >= args.region[2] or args.region[1] >= args.region[3]):
            parser.error("--region must have positive width and height")
        if args.profile == "stable":
            if args.backend != "u2" or not all((args.record_id, args.region, args.swipe, args.package)):
                parser.error("stable profile requires u2, --package, --record-id, --region and an explicit --swipe for an ordered list")
            if not 0 < args.stable_seconds < args.wait_seconds or not args.poll_seconds > 0 or args.min_overlap < 1:
                parser.error("stable profile requires 0 < --stable-seconds < --wait-seconds, positive --poll-seconds and --min-overlap")
        scan(args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
