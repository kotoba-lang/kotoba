"""Per-interface ARP/broadcast sweep. macOS + Linux compatible.

Uses subprocess (no scapy / no root). Each interface is swept independently
so that we can detect split L2 domains masquerading under the same /24.

OUI lookup is intentionally tiny — only the prefixes we expect to bump into
on a desk LAN (Apple, common router/AP vendors). Unknown OUI = best-effort
"unknown".
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any


# Minimal OUI map. Keep small; expand only when concrete evidence shows up.
OUI_HINTS: dict[str, str] = {
    "1c:f6:4c": "Apple",
    "f0:18:98": "Apple",
    "a8:8e:24": "Apple",
    "3c:a9:ab": "Apple",
    "64:d2:c4": "Apple",
    "2c:ca:16": "Intel",
    "0c:67:14": "router/AP",   # observed Wi-Fi gateway in dogfood env
    "2c:ff:65": "Murata/wireless-module",  # observed wired gateway
    "44:27:45": "unknown",
    "ee:d7:06": "random-MAC",  # privacy-randomized
    "62:3f:cd": "random-MAC",
}


@dataclass
class Host:
    ip: str
    mac: str
    iface: str
    oui_hint: str = ""

    @property
    def oui(self) -> str:
        return self.mac.lower().rsplit(":", 3)[0] if self.mac.count(":") >= 5 else ""


@dataclass
class Interface:
    name: str
    ip: str
    netmask: str
    mac: str
    is_active: bool
    medium: str  # "wired" | "wifi" | "other"


@dataclass
class ScanResult:
    iface: Interface
    hosts: list[Host] = field(default_factory=list)
    gateway_mac: str = ""


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return out.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _normalize_mac(raw: str) -> str:
    """`1:2:3:a:b:c` → `01:02:03:0a:0b:0c` (canonical lower)."""
    parts = raw.lower().split(":")
    if len(parts) != 6:
        return raw.lower()
    return ":".join(p.zfill(2) for p in parts)


def _oui_lookup(mac: str) -> str:
    prefix = mac.lower()[:8]  # "xx:xx:xx"
    if prefix in OUI_HINTS:
        return OUI_HINTS[prefix]
    # locally-administered (2nd nibble = 2/6/a/e) → likely randomized
    if len(mac) >= 2 and mac[1].lower() in {"2", "6", "a", "e"}:
        return "random-MAC"
    return "unknown"


def list_interfaces() -> list[Interface]:
    """Enumerate active IPv4 interfaces (macOS + Linux)."""
    out = _run(["ifconfig"])
    if not out:
        return []
    blocks = re.split(r"\n(?=[a-z0-9]+: flags=)", out)
    ifs: list[Interface] = []
    for blk in blocks:
        m_name = re.match(r"^([a-z0-9]+):", blk)
        if not m_name:
            continue
        name = m_name.group(1)
        if name in {"lo0", "lo", "gif0", "stf0"}:
            continue
        m_ip = re.search(r"inet (\d+\.\d+\.\d+\.\d+) netmask (\S+)", blk)
        m_mac = re.search(r"ether ([0-9a-f:]+)", blk)
        m_status = re.search(r"status: (\S+)", blk)
        if not m_ip:
            continue
        netmask_raw = m_ip.group(2)
        # macOS prints hex (0xffffff00); convert to dotted.
        if netmask_raw.startswith("0x"):
            n = int(netmask_raw, 16)
            netmask = ".".join(str((n >> s) & 0xFF) for s in (24, 16, 8, 0))
        else:
            netmask = netmask_raw
        ifs.append(
            Interface(
                name=name,
                ip=m_ip.group(1),
                netmask=netmask,
                mac=_normalize_mac(m_mac.group(1)) if m_mac else "",
                is_active=(m_status.group(1) if m_status else "active") == "active",
                medium=_infer_medium(name),
            )
        )
    return ifs


def _infer_medium(iface: str) -> str:
    """macOS heuristic: en0 historically wired, en1 Wi-Fi. Confirm via networksetup."""
    out = _run(["networksetup", "-listallhardwareports"])
    if not out:
        return "other"
    blocks = out.split("Hardware Port:")
    for b in blocks:
        if f"Device: {iface}" in b:
            label = b.split("\n", 1)[0].strip().lower()
            if "wi-fi" in label or "airport" in label:
                return "wifi"
            if "ethernet" in label or "thunderbolt" in label or "usb" in label:
                return "wired"
            return "other"
    return "other"


def scan_once(iface: Interface, sweep_timeout: float = 6.0) -> ScanResult:
    """ARP-sweep `iface`'s /24 and return ScanResult.

    Strategy: fire-and-forget broadcast ping to every host in the subnet, wait,
    then read the kernel ARP table filtered by `iface`. This is robust enough
    for a /24 on commodity hardware without raw sockets.
    """
    result = ScanResult(iface=iface)
    if not iface.is_active or not iface.ip:
        return result

    try:
        net = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
    except ValueError:
        return result
    if net.prefixlen < 22 or net.num_addresses > 1024:
        return result  # don't sweep larger than /22

    # Broadcast + per-host pings in parallel (background, short timeout each).
    procs: list[subprocess.Popen] = []
    for host in net.hosts():
        procs.append(
            subprocess.Popen(
                ["ping", "-c", "1", "-W", "200", "-n", str(host)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    # let pings settle
    deadline = sweep_timeout
    import time

    t0 = time.time()
    while time.time() - t0 < deadline:
        if all(p.poll() is not None for p in procs):
            break
        time.sleep(0.2)
    for p in procs:
        if p.poll() is None:
            p.kill()

    # ARP read
    arp_out = _run(["arp", "-a", "-n"])
    gw_ip = _default_gateway_for(iface.name)
    for line in arp_out.splitlines():
        # macOS: `? (192.168.1.1) at 2c:ff:65:f4:a5:36 on en0 ifscope [ethernet]`
        m = re.match(r"\?\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)\s+on\s+(\S+)", line)
        if not m:
            continue
        ip, mac_raw, seen_on = m.group(1), m.group(2), m.group(3)
        if seen_on != iface.name:
            continue
        if "incomplete" in mac_raw or mac_raw == "ff:ff:ff:ff:ff:ff":
            continue
        mac = _normalize_mac(mac_raw)
        host = Host(ip=ip, mac=mac, iface=iface.name, oui_hint=_oui_lookup(mac))
        result.hosts.append(host)
        if ip == gw_ip:
            result.gateway_mac = mac

    return result


def _default_gateway_for(iface: str) -> str:
    out = _run(["netstat", "-rn"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "default" and parts[-1] == iface:
            return parts[1]
    return ""


async def scan_all_async(ifaces: list[Interface]) -> list[ScanResult]:
    """Run `scan_once` for each iface concurrently in a thread pool."""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, scan_once, ifc) for ifc in ifaces]
    return list(await asyncio.gather(*tasks))


def scanresult_to_dict(r: ScanResult) -> dict[str, Any]:
    return {
        "iface": asdict(r.iface),
        "gateway_mac": r.gateway_mac,
        "hosts": [asdict(h) for h in r.hosts],
    }
