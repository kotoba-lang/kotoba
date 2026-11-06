#!/usr/bin/env python3
"""JUN-813 (ADR-0286 amendment 6): the CMOS RTC probe of native/update.kotoba (`rtc-probe`, KDBG 0xc400..0xc40b) under QEMU, decoded independently on the host.

The probe is what the operator runs on the real 6600H; this gate shows what it reports on QEMU for the five RTC settings kotoba#1275's `fresh` gate used and
that an independent decoder (rtc_probe_decode.py: raw registers through `datetime`, not the kernel's code) reproduces every field the guest reported.
The probe uses ports 0x70/0x71 only: no fw_cfg, no NVMe, no disk (these boots attach no NVMe device and no fw_cfg file), nothing is written.
The guest keeps each KDBG record as three context words (tag, value low, value high; words 1500 + 3k, count at 1499, marker "RTC1" at 1498); the gate reads
exactly those, over the QEMU monitor. QEMU has no RTL8168, so the UDP transmission of the same records is NOT observed here (the 6600H netlog is).
  rtc-default-host / rtc-vm-2026-11-06 / rtc-vm-leap-day-2028 / rtc-vm-2100-03-01 / rtc-vm-before-build-floor   one boot each. Asserted from the registers:
      register B reads 24 hour BCD (QEMU's setting; the decoder is also checked on synthetic binary / 12-hour registers below); the two snapshots decode to
      the base plus the virtual time since reset (0..900 s; the default RTC to the host clock around the launch); the second read is 1..2 s after the first;
      the TSC between them is 0.5e9..2e9 ticks per RTC second (QEMU TCG runs the TSC at about 1 GHz); the guest's conversion of both snapshots equals the
      decoder's; the verdict flags the decoder can recompute (register D, invalid field, build floor, no seconds advance, wrong advance, SET bit) equal the
      guest's; the guest-only flags (flag stuck, no equal snapshots, rtc-now disagrees, wait broken) are 0; the update-flag self-check cleared the flag (1);
      rtc-now (the freshness clock) is usable exactly when the probe says so; the hypervisor bit is set (this is a VM, not a board).
      Verdicts: 2026-11-06, the 2028 leap day: yes; 2100-03-01 (QEMU leaves register 0x32 at 0x20, so the face value is the year 2000) and 2025-01-01: no, below the floor.
  rtc-decoder-negative-controls   the decoder on synthetic registers (binary, 12-hour, century cases, invalid fields) against `datetime`; then tampered copies of a
      real report that must be flagged: a BCD nibble changed, the guest's conversion shifted, the verdict inverted, register D bit 7 cleared, a record dropped.
  rtc-regression   the desktop still draws after the probe, and the verifier self-test still reads 7 / [15, 1, 7].
Rebuilt-kernel mutants (a probe that skips the update-flag wait; a BCD decode that is wrong) are run by building the `rtc` profile from a mutated update.kotoba and
running this gate on it: it must fail (90-docs/evidence/rtc-probe-qemu-20261106 records the runs). QEMU TCG only: it measures no board.
"""
import argparse, calendar, datetime, importlib.util, json, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("keystore_gate", HERE / "check-native-keystore-qemu.py")
keystore = importlib.util.module_from_spec(spec); spec.loader.exec_module(keystore)
spec = importlib.util.spec_from_file_location("rtc_probe_decode", HERE / "rtc_probe_decode.py")
dec = importlib.util.module_from_spec(spec); spec.loader.exec_module(dec)
pin = keystore.pin
MARKER = int.from_bytes(b"RTC1", "big")
GAP = 900   # a guest reaches the probe within this many seconds of virtual time after reset


def rtc_arg(unix):
    t = time.gmtime(unix)
    return ["-rtc", f"base={t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d},clock=vm"]


def boot(args, out, name, rtc):
    launched = time.time()
    b = keystore.Boot(args, out, name, None, rtc, first_frame_seconds=900)   # the probe runs before the first frame
    try:
        deadline = time.monotonic() + 300
        while b.W(1498) != MARKER and time.monotonic() < deadline: time.sleep(1)
        assert b.W(1498) == MARKER and b.W(1499) == 12, (name, "the probe did not finish", hex(b.W(1498)), b.W(1499))
        raw = b.words(1500, 36)
        w = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, 144, 4)]
        recs = [(w[3 * k], w[3 * k + 1] + (w[3 * k + 2] << 32)) for k in range(12)]
        detail = b.W(189)
        r = dict(launched=launched, read_at=time.time(), records=recs, v1=[b.W(188), detail & 255, (detail >> 8) & 255, (detail >> 16) & 255],
                 nvme=b.W(600), hook=b.W(211))
        frames = b.W(79)
        b.send("sendkey 1", 2.0)
        r["drew"] = b.W(79) > frames
    finally:
        b.quit()
    return r


def bcd(v): return (v // 10) * 16 + v % 10


def check_boot(name, r, base, how):
    rep = dec.decode_report(r["records"])
    assert rep["magic_ok"], (name, "the report's first or last record is not RTC1")
    assert rep["hypervisor"], (name, "QEMU must report the hypervisor bit")
    dA, dB = rep["decodedA"], rep["decodedB"]
    assert "error" not in dA and "error" not in dB, (name, dA, dB)
    assert dA["hour24"] and not dA["binary"], (name, "unexpected register B mode", rep["regsA"]["0x0b"])
    assert rep["flagsAgree"] and rep["conversionAgrees"] and rep["verdictAgrees"], (name, "the guest and the host decoder disagree", rep)
    assert rep["guestOnlyFlags"] == 0, (name, "guest-only failure flags set", hex(rep["guestOnlyFlags"]))
    assert rep["flagSelfCheck"] == 1, (name, "the update-in-progress flag was not seen cleared by the probe's wait", rep["flagSelfCheck"])
    assert 1 <= rep["secondsAdvanced"] <= 2, (name, "seconds between the two reads", rep["secondsAdvanced"])
    assert 0.5e9 <= rep["tscPerSecond"] <= 2e9, (name, "TSC per RTC second", rep["tscPerSecond"])
    assert rep["spinsToUpdateFlag"] > 0 and rep["spinsToSecondChange"] > 0, (name, "spin counters", rep["spinsToUpdateFlag"], rep["spinsToSecondChange"])
    ua = dA["unix"]
    if how == "default":
        lo, hi = int(r["launched"]) - 2, int(r["read_at"]) + 2
        assert lo <= ua <= hi, (name, "the default RTC does not follow the host clock", ua, lo, hi)
        delta = ua - int(r["launched"])
    else:
        # the registers carry base + virtual time since reset; the century register is checked separately (QEMU leaves it at 0x20 for 2100)
        want = datetime.datetime.fromtimestamp(base, datetime.timezone.utc)
        got = datetime.datetime(dA["year"] % 100 + (want.year // 100) * 100, dA["month"], dA["day"], dA["hour"], dA["minute"], dA["second"],
                                tzinfo=datetime.timezone.utc)
        delta = int(got.timestamp()) - base
        assert 0 <= delta <= GAP, (name, "the registers are not the base plus the virtual time since reset", delta, dA["iso"])
    floor_refused = ua < dec.BUILD_FLOOR
    assert rep["guestVerdict"] == (0 if floor_refused else 1), (name, "verdict", rep["guestVerdict"], dA["iso"])
    assert (rep["rtcNowUnix"] == 0) if floor_refused else (rep["rtcNowStatus"] == 0 and abs(rep["rtcNowUnix"] - dB["unix"]) <= 4), \
        (name, "rtc-now (the freshness clock) and the probe disagree", rep["rtcNowStatus"], rep["rtcNowUnix"], dB["unix"])
    assert floor_refused == bool(rep["guestFlags"] & 16) and not (rep["guestFlags"] & 0x3EF), (name, "unexpected flags", hex(rep["guestFlags"]))
    return dict(name=name, rtc=how, base=base, startDeltaSeconds=delta, verdict=rep["guestVerdict"], flags=hex(rep["guestFlags"]), failReasons=rep["failReasons"],
                info=rep["info"], faceValueA=dA["iso"], faceValueB=dB["iso"], registersA=rep["regsA"], registersB=rep["regsB"], secondsAdvanced=rep["secondsAdvanced"],
                tscTicks=rep["tscTicks"], tscPerSecond=round(rep["tscPerSecond"]), spinsToUpdateFlag=rep["spinsToUpdateFlag"],
                spinsToSecondChange=rep["spinsToSecondChange"], retries=[rep["retriesA"], rep["retriesB"]], rtcNowUnix=rep["rtcNowUnix"],
                rtcNowStatus=rep["rtcNowStatus"], flagSelfCheck=rep["flagSelfCheck"], hypervisorBit=rep["hypervisor"]), rep


def synthetic_decoder_checks():
    """The host decoder against `datetime` on registers QEMU never produces (binary, 12 hour, century cases) and on invalid fields."""
    def regs(sec, minute, hour, day, month, yy, cc, b, d=0x80, a=0x26, h12pm=False):
        def enc(v): return v if b & 4 else bcd(v)
        h = enc(hour) if b & 2 else enc(hour % 12 or 12) | (0x80 if hour >= 12 else 0)
        return {0: enc(sec), 1: 0, 2: enc(minute), 3: 0, 4: h, 5: 0, 6: 3, 7: enc(day), 8: enc(month), 9: enc(yy), 10: a, 11: b, 12: 0, 13: d, 0x32: enc(cc)}
    good = [("bcd-24", (56, 34, 12, 6, 11, 26, 20, 0x02), (2026, 11, 6, 12, 34, 56)),
            ("binary-24", (56, 34, 12, 6, 11, 26, 20, 0x06), (2026, 11, 6, 12, 34, 56)),
            ("bcd-12-pm", (5, 7, 23, 29, 2, 28, 20, 0x00), (2028, 2, 29, 23, 7, 5)),
            ("binary-12-am", (0, 0, 0, 1, 1, 27, 20, 0x04), (2027, 1, 1, 0, 0, 0)),
            ("binary-12-noon", (59, 59, 12, 31, 12, 99, 20, 0x04), (2099, 12, 31, 12, 59, 59)),
            ("bcd-24-year-2100", (0, 0, 0, 1, 3, 0, 21, 0x02), (2100, 3, 1, 0, 0, 0)),
            ("bcd-24-century-ff-assumes-20", (1, 2, 3, 4, 5, 26, 0xFF, 0x02), (2026, 5, 4, 3, 2, 1))]
    rows = []
    for name, a, want in good:
        r = regs(*a[:7], a[7]);
        if name == "bcd-24-century-ff-assumes-20": r[0x32] = 0xFF
        d = dec.decode_registers(r)
        w = datetime.datetime(*want, tzinfo=datetime.timezone.utc)
        assert "error" not in d and d["unix"] == int(w.timestamp()), (name, d, w)
        rows.append(dict(name=name, unix=d["unix"]))
    r = regs(56, 34, 12, 6, 11, 26, 20, 0x02)
    bad = [("bcd-nibble-a", {**r, 0: 0x3A}), ("bcd-minute-9a", {**r, 2: 0x9A}), ("seconds-60", {**r, 0: 0x60}), ("hour-24", {**r, 4: 0x24}),
           ("month-13", {**r, 8: 0x13}), ("day-0", {**r, 7: 0x00}), ("31-november", {**r, 7: 0x31, 8: 0x11}),
           ("12h-hour-0", {**r, 11: 0x00, 4: 0x00}), ("12h-hour-13", {**r, 11: 0x00, 4: 0x13}), ("dead-rtc-ff", {i: 0xFF for i in r})]
    for name, x in bad:
        assert "error" in dec.decode_registers(x), ("an invalid register set was accepted", name)
    return rows, [n for n, _ in bad]


def negative_controls(rep_records):
    """Tampered copies of a real report: each must be seen as wrong by the decoder's checks (guest and host disagree), or as incomplete."""
    def tamper(tag, fn):
        return [(t, fn(v) if t == tag else v) for t, v in rep_records]
    base = dec.decode_report(rep_records)
    assert base["flagsAgree"] and base["conversionAgrees"] and base["verdictAgrees"]
    out = {}
    # a BCD nibble of the seconds register changed to 0xA (invalid BCD): the registers say invalid, the guest said fine
    t = dec.decode_report(tamper(0xC401, lambda v: (v & ~0xFF) | 0x3A))
    assert not t["flagsAgree"] and not t["conversionAgrees"], t; out["bcd-nibble-changed"] = "flags and conversion disagree"
    # the guest mis-decoded BCD (took 0x34 minutes as hex 52): its conversion differs from the decoder's
    t = dec.decode_report(tamper(0xC405, lambda v: v + 18 * 60)); assert not t["conversionAgrees"], t; out["guest-conversion-shifted"] = "conversion disagrees"
    t = dec.decode_report(tamper(0xC40A, lambda v: v ^ (1 << 56))); assert not t["verdictAgrees"], t; out["verdict-inverted"] = "verdict disagrees"
    t = dec.decode_report(tamper(0xC402, lambda v: v & ~(0x80 << 40)))   # register D bit 7 cleared
    assert not t["flagsAgree"], t; out["register-d-vrt-cleared"] = "flags disagree"
    t = dec.decode_report(tamper(0xC404, lambda v: (v & ~(0xFF << 24)) | (0x80 << 24)))   # register B of snapshot B: SET bit
    assert not t["flagsAgree"] or not t["conversionAgrees"] or t["decodedB"].get("set_bit") != base["decodedB"].get("set_bit"), t
    out["register-b-set-bit-on-b"] = "seen in snapshot B"
    assert not dec.groups(rep_records[:5] + rep_records[6:]), "a report with a dropped record must not be complete"; out["record-dropped"] = "no complete report"
    return out


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    plans = [("rtc-default-host", None, [], "default"),
             ("rtc-vm-2026-11-06", calendar.timegm((2026, 11, 6, 12, 34, 56)), None, "vm"),
             ("rtc-vm-leap-day-2028", calendar.timegm((2028, 2, 29, 23, 59, 50)), None, "vm"),
             ("rtc-vm-2100-03-01", calendar.timegm((2100, 3, 1, 0, 0, 0)), None, "vm"),
             ("rtc-vm-before-build-floor", calendar.timegm((2025, 1, 1, 0, 0, 0)), None, "vm")]
    events, first, last = [], None, None
    for name, base, rtc, how in plans:
        r = boot(args, out, name, rtc if rtc is not None else rtc_arg(base))
        row, rep = check_boot(name, r, base, how)
        assert r["drew"] and r["v1"] == [7, 15, 1, 7] and r["nvme"] == 1 and r["hook"] == 0, (name, r["drew"], r["v1"], r["nvme"], r["hook"])
        row["records"] = [[hex(t), f"{v:016x}"] for t, v in r["records"]]
        events.append(row)
        first = first or r["records"]; last = r
    want_verdict = {"rtc-default-host": 1, "rtc-vm-2026-11-06": 1, "rtc-vm-leap-day-2028": 1, "rtc-vm-2100-03-01": 0, "rtc-vm-before-build-floor": 0}
    assert {e["name"]: e["verdict"] for e in events} == want_verdict, [(e["name"], e["verdict"]) for e in events]
    # the QEMU boots are split into the five named events plus the decoder / regression events below
    rows, invalid = synthetic_decoder_checks()
    controls = negative_controls(first)
    events.append(dict(name="rtc-decoder-negative-controls", syntheticDecoded=rows, invalidRefused=invalid, tamperedReports=controls))
    events.append(dict(name="rtc-regression", updateSelfTest=last["v1"][1:], desktopStillDraws=True, noNvmeDeviceNoFwCfg=True))
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_RTC_PROBE_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before, firmware=pin(args.firmware),
                  font=pin(args.font), observer=pin(Path(__file__)), decoder=pin(HERE / "rtc_probe_decode.py"), events=events,
                  network="none (-nic none): the KDBG datagrams are not observed, the stored records are", physicalHardware=False,
                  clockIsQemuNotABoard=True, readOnly=True)
    (out / "native-rtc-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(plans), "boots", len(rows), "synthetic rows", len(controls), "tamper controls")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
