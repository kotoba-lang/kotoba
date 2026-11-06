#!/usr/bin/env python3
"""JUN-813 (ADR-0286 amendment 6): host-side decoder and recorder for the CMOS RTC probe of native/update.kotoba (`rtc-probe`).

The probe runs once in the desktop debug entry and sends twelve KDBG records (UDP 7799, tags 0xc400..0xc40b). This file is written independently of the
kernel's decoder: it decodes the raw CMOS registers with `datetime`, recomputes every verdict flag it can from them, and compares with what the guest said.
It is used by the QEMU gate (check-native-rtc-qemu.py) and by the operator on the Mac:

  rtc_probe_decode.py listen  [--log kdbg.log] [--seconds N]    record UDP 7799 with the Mac's receive time (UTC) next to each datagram
  rtc_probe_decode.py decode  kdbg.log [--all] [--json]         decode the last (or every) complete probe report in a log
                                                                (reads the lines `listen` writes and the evidence-style lines without t=)

A log line is `HH:MM:SS source AIUEOS_KDBG tttt vvvvvvvvvvvvvvvv`, with ` t=<unix milliseconds>` appended by `listen`. When the records carry t=, the decoder
prints the offset between the RTC's face value and the Mac's UTC at the moment the report was sent, which is how a local-time RTC shows itself.

Record layout (all values 64 bit, shown as 16 hex digits on the wire):
  c400 "RTC1" << 32 | 1           c401/c403 registers 0x00..0x07 of snapshot A/B (register 0 in the low byte)
  c402/c404 registers 0x08 0x09 0x0A 0x0B 0x0C 0x0D 0x32 (bytes 0..6)     c405 guest conversion of A | B << 32 (face value read as UTC; 0 invalid)
  c406/c407 TSC at A/B            c408 spins to the update flag | spins to the seconds change << 24 | retries A << 48 | retries B << 56
  c409 `rtc-now` unix | status << 32        c40a flags | hypervisor << 32 | rtc-now status << 40 | flag self-check << 48 | verdict << 56
  c40b "RTC1" << 32 | 12 (record count)
"""
import argparse, calendar, datetime, json, re, socket, sys, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the decoder must not run with Python -O")
TAGS = list(range(0xC400, 0xC40C))
MAGIC = 0x52544331
BUILD_FLOOR = calendar.timegm((2026, 11, 6, 0, 0, 0))   # update.kotoba's floor, 1793923200
FAIL_NAMES = {1: "update-in-progress flag never cleared", 2: "no two equal snapshots", 4: "register D bit 7 clear: RTC lost power (battery dead)",
              8: "a field is invalid (BCD nibble over 9 or out of range)", 16: "earlier than the build floor 2026-11-06 (reset or dead RTC)",
              32: "seconds did not change", 64: "seconds changed by something other than 1..2 in the wait", 128: "register B SET bit: updates halted",
              256: "rtc-now (the freshness clock) disagrees with the probe", 512: "the probe's update-flag wait did not clear the flag"}
INFO_NAMES = {65536: "century register 0x32 plausible", 131072: "12-hour mode", 262144: "binary mode", 524288: "DST enable bit set",
              1048576: "update flag never seen (wait not exercised)", 2097152: "divider not 010 (not the 32.768 kHz setting)"}
LINE = re.compile(r"AIUEOS_KDBG\s+([0-9a-fA-F]{4})\s+([0-9a-fA-F]{16})(?:\s+t=(\d+))?")


def regs_from(lo, hi):
    """Registers of one snapshot: lo = c401/c403 (0x00..0x07), hi = c402/c404 (0x08 0x09 0x0A 0x0B 0x0C 0x0D 0x32)."""
    r = {i: (lo >> (8 * i)) & 255 for i in range(8)}
    r.update({8 + i: (hi >> (8 * i)) & 255 for i in range(6)})
    r[0x32] = (hi >> 48) & 255
    return r


def decode_registers(r):
    """Face value of one register snapshot, from the registers alone. Returns a dict; 'error' is set when a field is invalid, else 'unix' is the face
    value read as UTC. Rules (MC146818 / ACPI): register B bit 2 = binary (else BCD), bit 1 = 24 hour (else 12 hour with bit 7 of the hour byte = PM);
    the century register 0x32 counts when it decodes to 19..21, else 20 is assumed (as the kernel does)."""
    b = r[0x0B]
    binary, h24 = bool(b & 4), bool(b & 2)

    def field(v, what):
        if not binary and ((v & 15) > 9 or (v >> 4) > 9):
            raise ValueError(f"{what} register 0x{v:02x} is not BCD")
        return v if binary else (v >> 4) * 10 + (v & 15)
    try:
        sec, minute = field(r[0], "seconds"), field(r[2], "minutes")
        raw_h = r[4]
        pm = bool(raw_h & 0x80)
        hour = field(raw_h & 0x7F, "hours")
        if h24:
            if hour > 23: raise ValueError(f"hour {hour} in 24-hour mode")
        else:
            if not 1 <= hour <= 12: raise ValueError(f"hour {hour} in 12-hour mode")
            hour = hour % 12 + (12 if pm else 0)
        day, month, yy = field(r[7], "day"), field(r[8], "month"), field(r[9], "year")
        try:
            cc = field(r[0x32], "century")
        except ValueError:
            cc = 0
        century_ok = 19 <= cc <= 21
        year = (cc if century_ok else 20) * 100 + yy
        dt = datetime.datetime(year, month, day, hour, minute, sec, tzinfo=datetime.timezone.utc)   # raises on a bad day, month or second
    except ValueError as e:
        return dict(error=str(e), century_plausible=False)
    return dict(year=year, month=month, day=day, hour=hour, minute=minute, second=sec, unix=int(dt.timestamp()), iso=dt.strftime("%Y-%m-%dT%H:%M:%S"),
                century_plausible=century_ok, binary=binary, hour24=h24, dst=bool(b & 1), set_bit=bool(b & 0x80), vrt=bool(r[0x0D] & 0x80),
                divider=(r[0x0A] >> 4) & 7, uip=bool(r[0x0A] & 0x80))


def groups(records):
    """Complete reports (c400 .. c40b in order) of a stream of (tag, value[, t]) records; a boot that stops early is not complete."""
    out, cur = [], None
    for rec in records:
        tag, value = rec[0], rec[1]
        if tag == 0xC400:
            cur = []
        if cur is not None:
            cur.append(rec)
            if len(cur) == len(TAGS):
                if [x[0] for x in cur] == TAGS: out.append(cur)
                cur = None
    return out


def decode_report(rec):
    """Decode a complete report; independent of the guest's own conversion, then compared with it."""
    v = {x[0]: x[1] for x in rec}
    assert [x[0] for x in rec] == TAGS, "incomplete report"
    t = {x[0]: x[2] if len(x) > 2 else None for x in rec}
    magic_ok = v[0xC400] == (MAGIC << 32 | 1) and v[0xC40B] == (MAGIC << 32 | 12)
    A, B = regs_from(v[0xC401], v[0xC402]), regs_from(v[0xC403], v[0xC404])
    dA, dB = decode_registers(A), decode_registers(B)
    g = v[0xC40A]
    flags, hv, nst, chk, verdict = g & 0xFFFFFFFF, (g >> 32) & 1, (g >> 40) & 255, (g >> 48) & 255, g >> 56
    guest_unix = (v[0xC405] & 0xFFFFFFFF, v[0xC405] >> 32)
    tsc = (v[0xC406], v[0xC407])
    c8 = v[0xC408]
    rep = dict(magic_ok=magic_ok, regsA={f"0x{k:02x}": f"0x{x:02x}" for k, x in sorted(A.items())},
               regsB={f"0x{k:02x}": f"0x{x:02x}" for k, x in sorted(B.items())}, decodedA=dA, decodedB=dB, guestUnix=list(guest_unix),
               hypervisor=bool(hv), tsc=list(tsc), tscTicks=tsc[1] - tsc[0], spinsToUpdateFlag=c8 & 0xFFFFFF, spinsToSecondChange=(c8 >> 24) & 0xFFFFFF,
               retriesA=(c8 >> 48) & 255, retriesB=c8 >> 56, rtcNowUnix=v[0xC409] & 0xFFFFFFFF, rtcNowStatus=(v[0xC409] >> 32) & 255,
               guestFlags=flags, guestVerdict=verdict, flagSelfCheck=chk, rtcNowStatusInVerdict=nst)
    # what the registers alone say: the flags the host can recompute
    expect = 0
    if not (A[0x0D] & 0x80): expect |= 4
    if "error" in dA or "error" in dB: expect |= 8
    elif dA["unix"] < BUILD_FLOOR: expect |= 16
    if "error" not in dA and "error" not in dB:
        diff = dB["unix"] - dA["unix"]
        if diff == 0: expect |= 32
        if diff < 0 or diff > 2: expect |= 64
    if A[0x0B] & 0x80: expect |= 128
    rep["hostFlags"] = expect
    rep["hostComparableMask"] = 4 | 8 | 16 | 32 | 64 | 128
    rep["guestOnlyFlags"] = flags & (1 | 2 | 256 | 512)
    rep["flagsAgree"] = (flags & rep["hostComparableMask"]) == expect
    rep["conversionAgrees"] = guest_unix == tuple(d.get("unix", 0) for d in (dA, dB))
    rep["hostVerdict"] = 1 if (expect == 0 and not flags & (1 | 2 | 256 | 512)) else 0
    rep["verdictAgrees"] = verdict == rep["hostVerdict"] and verdict == (1 if flags & 1023 == 0 else 0)
    rep["failReasons"] = [name for bit, name in FAIL_NAMES.items() if flags & bit]
    rep["info"] = [name for bit, name in INFO_NAMES.items() if flags & bit]
    if "unix" in dA and "unix" in dB:
        rep["secondsAdvanced"] = dB["unix"] - dA["unix"]
        if rep["secondsAdvanced"] > 0:
            rep["tscPerSecond"] = rep["tscTicks"] / rep["secondsAdvanced"]
    # the Mac's UTC at the moment the conversion record was sent (listen writes t=): the offset of the RTC's face value from true UTC
    if t.get(0xC405) is not None and "unix" in dB:
        mac = t[0xC405] / 1000.0
        offset = dB["unix"] - mac
        rep["macUtcAtReport"] = datetime.datetime.fromtimestamp(mac, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        rep["faceMinusMacUtcSeconds"] = round(offset, 1)
        zone = round(offset / 900.0) * 900
        rep["nearestQuarterHourZone"] = zone
        rep["zoneResidualSeconds"] = round(offset - zone, 1)
        rep["reading"] = ("UTC" if zone == 0 and abs(offset) <= 30 else
                          f"NOT UTC: the face value is {zone / 3600:+.2f} h from UTC (local time, or a clock off by that much)" if abs(offset - zone) <= 30
                          else f"unclear: the face value is {offset:+.0f} s from the Mac's UTC and not near a quarter-hour zone (the clock is wrong or drifts)")
    return rep


def parse_log(text):
    out = []
    for line in text.splitlines():
        m = LINE.search(line)
        if m and 0xC400 <= int(m.group(1), 16) <= 0xC40B:
            out.append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3)) if m.group(3) else None))
    return out


def render(rep):
    L = []
    for name, d in (("A", rep["decodedA"]), ("B", rep["decodedB"])):
        L.append(f"snapshot {name}: " + (d["error"] if "error" in d else f"{d['iso']} (face value, read as UTC), unix {d['unix']}"))
    a = rep["decodedA"]
    if "error" not in a:
        L.append(f"mode: {'binary' if a['binary'] else 'BCD'}, {'24' if a['hour24'] else '12'}-hour, DST bit {int(a['dst'])}, SET bit {int(a['set_bit'])}, "
                 f"register D bit 7 (valid RTC power) {int(a['vrt'])}, divider {a['divider']:03b}, century register 0x32 "
                 f"{rep['regsA']['0x32']} ({'plausible' if a['century_plausible'] else 'NOT plausible: 20 assumed'})")
    L.append("registers A: " + " ".join(f"{k[2:]}={x[2:]}" for k, x in rep["regsA"].items()))
    L.append("registers B: " + " ".join(f"{k[2:]}={x[2:]}" for k, x in rep["regsB"].items()))
    if "secondsAdvanced" in rep:
        L.append(f"seconds advanced between the two reads: {rep['secondsAdvanced']} s; TSC ticks between them {rep['tscTicks']}"
                 + (f" = {rep['tscPerSecond'] / 1e9:.4f} GHz" if "tscPerSecond" in rep else ""))
    L.append(f"hypervisor bit: {int(rep['hypervisor'])} ({'a virtual machine' if rep['hypervisor'] else 'no hypervisor reported: physical hardware'})")
    L.append(f"rtc-now (the freshness clock): unix {rep['rtcNowUnix']} status {rep['rtcNowStatus']} (0 ok, 1 unstable, 2 invalid field, 3 below floor, 5 RTC lost power)")
    if "reading" in rep:
        L.append(f"Mac UTC when the report was sent: {rep['macUtcAtReport']}; face value minus Mac UTC = {rep['faceMinusMacUtcSeconds']} s -> {rep['reading']}")
    L.append("verdict (clock usable under Amendment 6): " + ("YES" if rep["guestVerdict"] else "NO") + (" (" + "; ".join(rep["failReasons"]) + ")" if rep["failReasons"] else ""))
    L.append("information: " + (", ".join(rep["info"]) or "none"))
    L.append(f"host checks: magic {rep['magic_ok']}, flags agree {rep['flagsAgree']}, conversion agrees {rep['conversionAgrees']}, verdict agrees {rep['verdictAgrees']}")
    return "\n".join(L)


def listen(log, seconds, port=7799):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError): pass
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
    s.bind(("", port)); s.settimeout(0.5)
    end = time.time() + seconds if seconds else None
    with open(log, "a") as f:
        print(f"listening on UDP {port}, appending to {log}; Ctrl-C to stop", file=sys.stderr)
        try:
            while end is None or time.time() < end:
                try: data, peer = s.recvfrom(4096)
                except socket.timeout: continue
                now = time.time()
                text = data.decode("ascii", "replace").rstrip("\r\n")
                f.write(time.strftime("%H:%M:%S", time.localtime(now)) + f" {peer[0]} {text} t={int(now * 1000)}\n"); f.flush()
        except KeyboardInterrupt:
            pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("listen"); l.add_argument("--log", default="kdbg.log"); l.add_argument("--seconds", type=float, default=0); l.add_argument("--port", type=int, default=7799)
    d = sub.add_parser("decode"); d.add_argument("log", type=Path); d.add_argument("--all", action="store_true"); d.add_argument("--json", action="store_true")
    a = p.parse_args()
    if a.cmd == "listen":
        listen(a.log, a.seconds, a.port); return 0
    reps = groups(parse_log(a.log.read_text()))
    if not reps:
        print("no complete RTC probe report (records c400..c40b) in the log", file=sys.stderr); return 1
    chosen = reps if a.all else reps[-1:]
    if a.json:
        print(json.dumps([decode_report(r) for r in chosen], indent=2, sort_keys=True))
    else:
        for i, r in enumerate(chosen):
            print(f"== report {len(reps) - len(chosen) + i + 1} of {len(reps)} ==\n" + render(decode_report(r)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
