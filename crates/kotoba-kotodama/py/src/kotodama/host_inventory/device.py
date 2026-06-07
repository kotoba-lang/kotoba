"""Device-level collectors (sysctl / ioreg / df / pmset / system_profiler).

All collectors return plain dicts so the persist layer can write them
without further translation. Failures degrade to empty values, never
raise — a missing battery on a desktop is normal.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any


def _run(cmd: list[str], timeout: float = 10.0) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return out.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _sysctl(key: str) -> str:
    return _run(["sysctl", "-n", key]).strip()


def _to_int(s: str, default: int = 0) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return default


@dataclass
class DeviceIdentity:
    hardware_uuid: str = ""
    serial_number: str = ""
    hostname: str = ""
    device_kind: str = "mac"
    model_name: str = ""
    model_identifier: str = ""
    chip_arch: str = ""
    cpu_brand: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    memory_gb: int = 0
    storage_gb: int = 0
    os_name: str = "macOS"
    os_version: str = ""
    os_build: str = ""


@dataclass
class DeviceSnapshot:
    boot_time: str = ""
    uptime_seconds: int = 0
    cpu_usage_x100: int = 0
    memory_used_mb: int = 0
    memory_free_mb: int = 0
    swap_used_mb: int = 0
    load_1m_x100: int = 0
    load_5m_x100: int = 0
    load_15m_x100: int = 0
    process_count: int = 0
    thread_count: int = 0
    thermal_state: str = ""


def _ioreg_platform() -> dict[str, str]:
    out = _run(["ioreg", "-d2", "-c", "IOPlatformExpertDevice"])
    serial = re.search(r'"IOPlatformSerialNumber"\s*=\s*"([^"]+)"', out)
    uuid = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
    return {
        "serial": serial.group(1) if serial else "",
        "uuid": uuid.group(1) if uuid else "",
    }


def _model_name_from_identifier(ident: str) -> str:
    """Best-effort marketing name. Falls back to identifier itself."""
    out = _run(["system_profiler", "SPHardwareDataType"], timeout=8.0)
    m = re.search(r"Model Name:\s*(.+)", out)
    if m:
        return m.group(1).strip()
    return ident or ""


def _cpu_brand() -> str:
    brand = _sysctl("machdep.cpu.brand_string")
    if brand:
        return brand
    # Apple Silicon: brand_string is empty; use SPHardwareDataType
    out = _run(["system_profiler", "SPHardwareDataType"], timeout=8.0)
    m = re.search(r"Chip:\s*(.+)", out) or re.search(r"Processor Name:\s*(.+)", out)
    return m.group(1).strip() if m else ""


def collect_device() -> dict[str, Any]:
    """Return (identity, snapshot) merged dict for persistence."""
    ioreg = _ioreg_platform()
    model_id = _sysctl("hw.model")
    arch = _sysctl("hw.machine") or platform.machine()
    cpu_cores = _to_int(_sysctl("hw.physicalcpu"))
    cpu_threads = _to_int(_sysctl("hw.logicalcpu") or _sysctl("hw.ncpu"))
    mem_bytes = _to_int(_sysctl("hw.memsize"))
    storage_bytes = _storage_total_bytes()

    identity = DeviceIdentity(
        hardware_uuid=ioreg["uuid"],
        serial_number=ioreg["serial"],
        hostname=_sysctl("kern.hostname") or platform.node(),
        device_kind="mac",
        model_name=_model_name_from_identifier(model_id),
        model_identifier=model_id,
        chip_arch=arch,
        cpu_brand=_cpu_brand(),
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        memory_gb=round(mem_bytes / (1024**3)) if mem_bytes else 0,
        storage_gb=round(storage_bytes / (1024**3)) if storage_bytes else 0,
        os_name="macOS",
        os_version=_sysctl("kern.osproductversion"),
        os_build=_sysctl("kern.osversion"),
    )

    snapshot = _collect_snapshot()

    return {"identity": asdict(identity), "snapshot": asdict(snapshot)}


def _storage_total_bytes() -> int:
    """Root volume total bytes from `df -k /`."""
    out = _run(["df", "-k", "/"])
    lines = out.strip().splitlines()
    if len(lines) < 2:
        return 0
    parts = lines[1].split()
    if len(parts) < 2:
        return 0
    return _to_int(parts[1]) * 1024


def _parse_boottime() -> tuple[str, int]:
    """`sysctl -n kern.boottime` → ISO timestamp + uptime seconds."""
    raw = _sysctl("kern.boottime")
    m = re.search(r"sec\s*=\s*(\d+)", raw)
    if not m:
        return "", 0
    boot_epoch = int(m.group(1))
    now = int(time.time())
    iso = datetime.utcfromtimestamp(boot_epoch).isoformat(timespec="seconds") + "Z"
    return iso, max(0, now - boot_epoch)


_LOAD_RE = re.compile(r"load averages?:?\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")


def _collect_snapshot() -> DeviceSnapshot:
    snap = DeviceSnapshot()
    snap.boot_time, snap.uptime_seconds = _parse_boottime()

    upt = _run(["uptime"])
    m = _LOAD_RE.search(upt)
    if m:
        snap.load_1m_x100 = int(float(m.group(1)) * 100)
        snap.load_5m_x100 = int(float(m.group(2)) * 100)
        snap.load_15m_x100 = int(float(m.group(3)) * 100)

    # vm_stat → memory pages (4096B each)
    vm = _run(["vm_stat"])
    pages: dict[str, int] = {}
    for line in vm.splitlines():
        m = re.match(r'"?(Pages [^:]+?)"?:\s+(\d+)', line)
        if m:
            pages[m.group(1).strip()] = int(m.group(2))
    page_bytes = 4096
    active = pages.get("Pages active", 0)
    wired = pages.get("Pages wired down", 0)
    free = pages.get("Pages free", 0)
    spec = pages.get("Pages speculative", 0)
    snap.memory_used_mb = (active + wired) * page_bytes // (1024**2)
    snap.memory_free_mb = (free + spec) * page_bytes // (1024**2)

    sw = _run(["sysctl", "-n", "vm.swapusage"])
    m = re.search(r"used\s*=\s*([\d.]+)M", sw)
    if m:
        snap.swap_used_mb = int(float(m.group(1)))

    ps = _run(["ps", "-A", "-o", "pid,thcount"])
    lines = ps.splitlines()[1:]
    snap.process_count = len(lines)
    snap.thread_count = sum(_to_int(line.split()[-1]) for line in lines if line.strip())

    therm = _run(["pmset", "-g", "therm"])
    if therm:
        m = re.search(r"CPU_Scheduler_Limit\s*=\s*(\d+)", therm)
        if m and int(m.group(1)) < 100:
            snap.thermal_state = "throttled"
        else:
            snap.thermal_state = "nominal"

    return snap


# ── disks ────────────────────────────────────────────────────────────────


def collect_disks() -> list[dict[str, Any]]:
    """Parse `df -k` + `diskutil info -all` for richer metadata."""
    rows: list[dict[str, Any]] = []
    df_out = _run(["df", "-Pk"])
    seen: set[str] = set()
    for line in df_out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        source, size_k, used_k, avail_k, _pct, mount = parts[:6]
        if not source.startswith("/dev/"):
            continue
        if source in seen:
            continue
        seen.add(source)
        size_gb = _to_int(size_k) // (1024 * 1024)
        used_gb = _to_int(used_k) // (1024 * 1024)
        avail_gb = _to_int(avail_k) // (1024 * 1024)
        size = max(1, _to_int(size_k))
        use_pct_x100 = int(_to_int(used_k) / size * 10000)
        bsd = source.replace("/dev/", "")
        info = _diskutil_info(bsd)
        rows.append({
            "bsd_name": bsd,
            "mount_point": mount,
            "fs_type": info.get("file_system_personality", ""),
            "size_gb": size_gb,
            "used_gb": used_gb,
            "available_gb": avail_gb,
            "use_pct_x100": use_pct_x100,
            "is_internal": info.get("internal", False),
            "is_encrypted": info.get("encrypted", False),
            "is_removable": info.get("removable", False),
        })
    return rows


def _diskutil_info(bsd: str) -> dict[str, Any]:
    out = _run(["diskutil", "info", bsd], timeout=4.0)
    if not out:
        return {}
    def grab(label: str) -> str:
        m = re.search(rf"{re.escape(label)}:\s*(.+)", out)
        return m.group(1).strip() if m else ""
    return {
        "file_system_personality": grab("File System Personality") or grab("Type (Bundle)"),
        "internal": grab("Device Location").lower() == "internal" or grab("Internal").lower() == "yes",
        "encrypted": "yes" in grab("FileVault").lower() or grab("Encrypted").lower() == "yes",
        "removable": grab("Removable Media").lower() not in {"", "fixed"} and grab("Removable Media").lower() != "no",
    }


# ── battery ──────────────────────────────────────────────────────────────


def collect_battery() -> dict[str, Any] | None:
    """Return battery snapshot or None if no battery (desktop)."""
    out = _run(["pmset", "-g", "batt"], timeout=4.0)
    if "InternalBattery" not in out:
        return None
    pct_m = re.search(r"(\d+)%", out)
    charging = "charging" in out.lower() and "not charging" not in out.lower()
    plugged = "AC Power" in out
    health = _run(["system_profiler", "SPPowerDataType"], timeout=8.0)
    cycle = re.search(r"Cycle Count:\s*(\d+)", health)
    cond = re.search(r"Condition:\s*(\S+)", health)
    max_cap = re.search(r"Maximum Capacity:\s*(\d+)", health)
    design = re.search(r"Design Capacity\s*\(mAh\):\s*(\d+)", health)
    curr = re.search(r"Full Charge Capacity\s*\(mAh\):\s*(\d+)", health)
    volt = re.search(r"Voltage\s*\(mV\):\s*(\d+)", health)
    amp = re.search(r"Amperage\s*\(mA\):\s*(-?\d+)", health)
    return {
        "charge_pct": int(pct_m.group(1)) if pct_m else 0,
        "cycle_count": int(cycle.group(1)) if cycle else 0,
        "condition": cond.group(1) if cond else "",
        "is_charging": charging,
        "is_plugged": plugged,
        "max_capacity_pct": int(max_cap.group(1)) if max_cap else 0,
        "design_capacity_mah": int(design.group(1)) if design else 0,
        "current_capacity_mah": int(curr.group(1)) if curr else 0,
        "voltage_mv": int(volt.group(1)) if volt else 0,
        "amperage_ma": int(amp.group(1)) if amp else 0,
    }


# ── displays ─────────────────────────────────────────────────────────────


def collect_displays() -> list[dict[str, Any]]:
    raw = _run(["system_profiler", "-json", "SPDisplaysDataType"], timeout=10.0)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    displays: list[dict[str, Any]] = []
    for gpu in data.get("SPDisplaysDataType", []):
        for d in gpu.get("spdisplays_ndrvs", []) or []:
            res = d.get("_spdisplays_resolution", "") or d.get("spdisplays_resolution", "")
            w, h = _parse_resolution(res)
            hz = _parse_hz(d.get("spdisplays_pixels", "") or res)
            displays.append({
                "display_name": d.get("_name", ""),
                "vendor_id": d.get("_spdisplays_display-vendor-id", ""),
                "product_id": d.get("_spdisplays_display-product-id", ""),
                "resolution_w": w,
                "resolution_h": h,
                "refresh_hz": hz,
                "pixel_depth_bits": _to_int(d.get("spdisplays_depth", "").replace("CGSEightBitColor", "8")),
                "is_main": d.get("spdisplays_main", "").lower() == "spdisplays_yes",
                "is_builtin": d.get("spdisplays_builtin", "").lower() == "spdisplays_yes",
                "is_mirrored": d.get("spdisplays_mirror", "").lower() == "spdisplays_on",
            })
    return displays


def _parse_resolution(s: str) -> tuple[int, int]:
    m = re.search(r"(\d+)\s*x\s*(\d+)", s)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _parse_hz(s: str) -> int:
    m = re.search(r"@\s*(\d+)\s*Hz", s) or re.search(r"(\d+)\s*Hz", s)
    return int(m.group(1)) if m else 0
