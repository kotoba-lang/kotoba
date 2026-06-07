"""App-level collectors — installed apps, running processes, launch items.

`system_profiler SPApplicationsDataType` is slow (30-90s for a busy Mac);
we use a faster path: scan /Applications + read each Info.plist via
`plutil -convert json -o -`. Returns the same shape (bundle_id, version,
path, last_modified).
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _run(cmd: list[str], timeout: float = 10.0) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return out.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


APP_ROOTS = [
    "/Applications",
    "/Applications/Utilities",
    "/System/Applications",
    "/System/Applications/Utilities",
    str(Path.home() / "Applications"),
]


def collect_installed_apps(max_apps: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for root in APP_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for name in entries:
            if not name.endswith(".app"):
                continue
            app_path = os.path.join(root, name)
            if app_path in seen_paths:
                continue
            seen_paths.add(app_path)
            row = _read_app_bundle(app_path)
            if row:
                rows.append(row)
            if len(rows) >= max_apps:
                return rows
    return rows


def _read_app_bundle(app_path: str) -> dict[str, Any] | None:
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if not os.path.isfile(plist_path):
        return None
    try:
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None
    bundle_id = str(data.get("CFBundleIdentifier", "")).strip()
    if not bundle_id:
        return None
    try:
        st = os.stat(app_path)
        last_mod = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    except OSError:
        last_mod = ""
    size_mb = _app_size_mb(app_path)
    return {
        "bundle_id": bundle_id,
        "app_name": str(data.get("CFBundleName") or data.get("CFBundleDisplayName") or os.path.basename(app_path).removesuffix(".app")),
        "version": str(data.get("CFBundleVersion", "")),
        "short_version": str(data.get("CFBundleShortVersionString", "")),
        "app_path": app_path,
        "size_mb": size_mb,
        "install_date": "",
        "last_modified": last_mod,
        "category": str(data.get("LSApplicationCategoryType", "")),
        "vendor": str(data.get("CFBundleGetInfoString", "")) or _vendor_from_bundle_id(bundle_id),
        "install_kind": _classify_install_kind(app_path, bundle_id),
        "signature_authority": "",
        "obtained_from": "",
    }


def _vendor_from_bundle_id(bid: str) -> str:
    parts = bid.split(".")
    if len(parts) >= 2 and parts[0] in {"com", "net", "org", "io", "ai"}:
        return parts[1]
    return parts[0] if parts else ""


def _classify_install_kind(path: str, bundle_id: str) -> str:
    if path.startswith("/System/"):
        return "system"
    if bundle_id.startswith("com.apple."):
        return "apple"
    if "Mas/" in path or bundle_id.startswith("com.apple.appstore."):
        return "mas"
    return "direct"


def _app_size_mb(path: str) -> int:
    """Cheap approximation: stat the bundle directory."""
    try:
        out = subprocess.run(
            ["du", "-sk", path], capture_output=True, text=True, timeout=4.0
        )
        first = out.stdout.split("\t", 1)[0]
        return int(first) // 1024 if first.isdigit() else 0
    except (subprocess.TimeoutExpired, ValueError):
        return 0


# ── processes ────────────────────────────────────────────────────────────


def collect_processes(max_rows: int = 2000) -> list[dict[str, Any]]:
    """`ps -A -o ...` parsed into typed rows. CPU/MEM scaled ×100.

    No `lstart` (5-token date is hard to parse robustly across locales) —
    `etime` plus the current wall clock gives `started_at` exactly enough
    precision for inventory snapshots.
    """
    out = _run([
        "ps", "-A", "-o",
        "pid=,ppid=,user=,pcpu=,pmem=,rss=,vsz=,etime=,comm=,command=",
    ], timeout=15.0)
    rows: list[dict[str, Any]] = []
    now = time.time()
    for line in out.splitlines():
        parsed = _parse_ps_line(line, now=now)
        if parsed is None:
            continue
        rows.append(parsed)
        if len(rows) >= max_rows:
            break
    return rows


# pid ppid user pcpu pmem rss vsz etime comm command...
_PS_LINE_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\S+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s*(.*)$"
)


def _parse_ps_line(line: str, *, now: float) -> dict[str, Any] | None:
    m = _PS_LINE_RE.match(line)
    if not m:
        return None
    pid, ppid, user, pcpu, pmem, rss, vsz, etime, comm, command = m.groups()
    elapsed = _parse_etime_seconds(etime)
    try:
        started = datetime.fromtimestamp(now - elapsed, tz=timezone.utc)
        started_iso = started.isoformat(timespec="seconds")
    except (OSError, ValueError):
        started_iso = ""
    return {
        "pid": int(pid),
        "ppid": int(ppid),
        "user_name": user,
        "process_name": os.path.basename(comm),
        "command": (command or comm)[:2000],
        "cpu_pct_x100": int(float(pcpu) * 100),
        "memory_pct_x100": int(float(pmem) * 100),
        "rss_kb": int(rss),
        "vsz_kb": int(vsz),
        "elapsed_seconds": elapsed,
        "started_at": started_iso,
        "bundle_id": _bundle_id_from_command(comm, command or ""),
    }


def _parse_etime_seconds(etime: str) -> int:
    """Parse `[DD-]HH:MM:SS` / `MM:SS` / `SS` to seconds."""
    days = 0
    if "-" in etime:
        d, etime = etime.split("-", 1)
        days = int(d)
    parts = etime.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h, m, s = 0, nums[0], nums[1]
    else:
        h, m, s = 0, 0, nums[0]
    return days * 86400 + h * 3600 + m * 60 + s


_BUNDLE_RE = re.compile(r"/([A-Za-z0-9_+\-.]+)\.app/")


def _bundle_id_from_command(comm: str, command: str) -> str:
    """Heuristic — extract `Foo.app` from path and return inferred bundle_id."""
    m = _BUNDLE_RE.search(command) or _BUNDLE_RE.search(comm)
    if not m:
        return ""
    return ""  # actual bundle_id requires Info.plist; left blank for join later


# ── launch items ─────────────────────────────────────────────────────────


LAUNCH_ROOTS = [
    ("/Library/LaunchDaemons", False, False),
    ("/Library/LaunchAgents", False, True),
    ("/System/Library/LaunchDaemons", False, False),
    ("/System/Library/LaunchAgents", False, True),
    (str(Path.home() / "Library" / "LaunchAgents"), True, True),
]


def collect_launchitems(max_items: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    loaded = _loaded_labels()
    for root, is_user, _is_agent in LAUNCH_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for name in entries:
            if not name.endswith(".plist"):
                continue
            plist_path = os.path.join(root, name)
            row = _read_launch_plist(plist_path, is_user=is_user, loaded=loaded)
            if row:
                rows.append(row)
            if len(rows) >= max_items:
                return rows
    return rows


def _loaded_labels() -> set[str]:
    out = _run(["launchctl", "list"], timeout=4.0)
    labels: set[str] = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            labels.add(parts[-1])
    return labels


def _read_launch_plist(path: str, *, is_user: bool, loaded: set[str]) -> dict[str, Any] | None:
    try:
        with open(path, "rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None
    label = str(data.get("Label", "") or os.path.basename(path).removesuffix(".plist"))
    program = str(data.get("Program", "") or " ".join(data.get("ProgramArguments", []) or []))
    return {
        "label": label,
        "plist_path": path,
        "program": program[:2000],
        "is_loaded": label in loaded,
        "is_user": is_user,
        "run_at_load": bool(data.get("RunAtLoad", False)),
        "keep_alive": bool(data.get("KeepAlive", False)),
    }
