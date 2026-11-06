#!/usr/bin/env python3
"""JUN-813 (ADR-0286 amendment 6): the RTC clock reader and the AIUEFRS1 freshness record of native/update.kotoba, through the real update path.

Boots of the desktop debug entry (the one that probes NVMe/ESP and runs update.kotoba's hooks) on a fresh FAT32 fixture ESP attached as an
NVMe disk, QEMU `-nic none`, TCG. Every file reaches the guest through fw_cfg (a hypervisor-only hook; a physical board has no fw_cfg).
  fresh-clock-probes   opt/aiueos/clock, five boots with a different RTC: QEMU's default (follows the host clock) and `-rtc clock=vm` with a
                       base of 2026-11-06T12:34:56, a leap day just before midnight (2028-02-29T23:59:50), 2100-03-01 and a date before the
                       kernel's build floor (2025-01-01). The guest reads the CMOS (ports 0x70/0x71), converts to unix time and waits for three
                       changes of the seconds register, taking the TSC at each. Asserted: the clock reading equals the base plus the virtual time since
                       reset (0 .. 900 s; for the default RTC it lies between the host's time before launch and after the read), the status is 0
                       (or 3 for the 2025 date, the reading refused, the raw conversion still correct), the seconds register advances by one at each
                       change and the TSC distance between two changes is within a factor of two of the PIT-calibrated TSC rate (word 110 ticks per ms).
  fresh-clock-decoder  the same boots decode the synthetic CMOS rows of fresh_oracle.clock_rows (BCD / binary, 24 / 12 hour, centuries, leap days,
                       invalid fields): every row equals the oracle's datetime-based conversion.
  fresh-cases          opt/aiueos/fresh: every case of fresh_oracle (header = the AIUEIMG2 signature block, magic AIUEFRS1, ML-DSA context AIUEFRS1) with the
                       RTC at 2026-11-06T12:00:00; case k is word 400 + k and must equal the oracle's result | counted mask << 8 | verdict << 16.
  fresh-cases-clock-ahead / -no-clock  the admitted cases again with the RTC 40 days ahead (the records expire) and with a date before the build
                       floor (no usable clock: verdict 4, the record is still admitted).
Afterwards the ESP walk must still read the fixture's own BOOTX64.EFI (the ML-DSA arena shares owned window 4 with the NVMe queues), the disk must be
byte-identical (nothing here writes), the AIUEIMG1 self-test must still read 7 / [15, 1, 7], and the desktop must still draw. QEMU TCG only; the keys
are public TEST keys; hdiutil makes the FAT32 fixture, so this gate is macOS only. Not measured here: a physical board, a binary-mode or 12-hour RTC
(only the synthetic rows reach those paths), a clock that was set by someone else while the guest ran.
"""
import argparse, calendar, hashlib, importlib.util, json, shutil, struct, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nvme_gate", HERE / "check-native-nvme-qemu.py")
nvme = importlib.util.module_from_spec(spec); spec.loader.exec_module(nvme)
keystore = nvme.keystore
import fresh_oracle as oracle
CASE_WORD, CLOCK_MARKER, CASE_MARKER = 400, int.from_bytes(b"CLK1", "big"), int.from_bytes(b"FRS1", "big")
pin = keystore.pin
B0 = calendar.timegm((2026, 11, 6, 12, 0, 0))
GAP = 900   # a guest reaches the update hook within this many seconds of virtual time after reset


def rtc_arg(unix, how="vm"):
    t = time.gmtime(unix)
    return ["-rtc", f"base={t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d},clock={how}"]


def boot(args, out, name, disk, fwname, fwfile, rtc, want_marker, first_word):
    vars_copy = out / f"{name}-vars.fd"
    shutil.copyfile(args.firmware.parent / "edk2-i386-vars.fd", vars_copy)
    extra = ["-drive", f"if=pflash,format=raw,file={vars_copy}", "-cpu", "max,phys-bits=37",
             "-drive", f"file={disk},format=raw,if=none,id=nv0", "-device", "nvme,serial=AWAI122NVME512,drive=nv0",
             "-fw_cfg", f"name={fwname},file={fwfile}"] + rtc
    launched = time.time()
    b = keystore.Boot(args, out, name, None, extra, first_frame_seconds=6000)
    try:
        marker_word = 364 if fwname.endswith("clock") else 234
        deadline = time.monotonic() + 600
        while b.W(marker_word) != want_marker and time.monotonic() < deadline: time.sleep(2)
        r = dict(launched=launched, marker=b.W(marker_word), hook=b.W(211), walk=b.W(233), nvme=b.W(600), count=b.W(235),
                 v1=[b.W(188), b.W(189) & 255, (b.W(189) >> 8) & 255, (b.W(189) >> 16) & 255], tick_per_ms=b.W(110))
        r["read_at"] = time.time()
        raw = b.words(first_word[0], first_word[1])
        r["words"] = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]
        if fwname.endswith("clock"):
            cw, rw = b.words(364, 40), b.words(460, 44)
            r["clock"] = [int.from_bytes(cw[i:i + 4], "little") for i in range(0, 160, 4)]
            r["rows"] = [int.from_bytes(rw[i:i + 4], "little") for i in range(0, 176, 4)]
        digest = b.words(680, 8)
        r["esp"] = dict(path=b.W(677), fat=b.W(662), size=b.W(675),
                        sha256=b"".join(digest[i:i + 4][::-1] for i in range(0, 32, 4)).hex())
        frames = b.W(79)
        b.send("sendkey 1", 2.0)
        r["drew"] = b.W(79) > frames
    finally:
        b.quit()
    vars_copy.unlink()
    return r


def w64(words, i): return words[i] + (words[i + 1] << 32)


def bcd_or_bin(v, regb): return v if regb & 4 else (v >> 4) * 10 + (v & 15)


def probe_checks(name, r, base, how):
    """Asserts the clock boot against what QEMU was told; returns the measurements."""
    c = r["clock"]       # c[i] = word 364 + i
    W = lambda k: c[k - 364]
    assert r["marker"] == CLOCK_MARKER and r["hook"] == 0, (name, "the clock hook did not finish", hex(r["marker"]))
    status, status0, raw_unix = W(365), W(397), w64(c, 398 - 364)
    u0, u3 = w64(c, 382 - 364), w64(c, 392 - 364)
    regb = W(381)
    assert regb & 2 and not regb & 4, (name, "unexpected register B", hex(regb))   # 24 hour, BCD
    regs = tuple(W(374 + i) for i in range(8))   # the last snapshot the guest decoded
    century_ok = bool(regs[6] in (0x19, 0x20, 0x21))
    if how == "default":
        lo, hi = int(r["launched"]) - 2, int(r["read_at"]) + 2
        assert lo <= raw_unix <= hi, (name, "the default RTC does not follow the host clock", raw_unix, lo, hi)
        delta = raw_unix - int(r["launched"])
    elif century_ok and regs[6] == bcd_or_bin(0, 0) + 0x20 + (1 if base >= 4102444800 else 0):
        delta = raw_unix - base
        assert 0 <= delta <= GAP, (name, "RTC is not base + virtual time since reset", delta)
    else:
        delta = None   # QEMU did not expose the century of this base in register 0x32: recorded, and the guest is checked against the oracle only
    # the last snapshot (words 374..381) is the one behind u3: the guest's conversion of it must equal the oracle's (u3 is 0 when refused)
    assert u3 in (0, oracle.rtc_unix(regs)), (name, "guest conversion differs from the oracle's on the registers it read", u3, regs)
    floor_refused = raw_unix < oracle.BUILD_FLOOR
    if floor_refused:
        assert status0 == 3 and u0 == 0, (name, "a clock before the build floor must be refused", status0, u0)
    else:
        assert status0 == 0 and u0 == raw_unix, (name, status0, u0, raw_unix)
    secs = [(W(394) >> (8 * i)) & 255 for i in range(4)]
    secs = [bcd_or_bin(s, regb) for s in secs]
    assert all(secs[i + 1] == (secs[i] + 1) % 60 for i in range(3)), (name, "seconds register does not advance by one", secs)
    assert W(395) == 7, (name, "a wait for a seconds change timed out", W(395))
    t = [w64(c, 384 - 364 + 2 * i) for i in range(4)]
    d1, d2 = t[2] - t[1], t[3] - t[2]
    cal = r["tick_per_ms"] * 1000   # PIT-calibrated TSC ticks per second
    assert cal > 0 and 0.5 * cal <= d1 <= 2 * cal and 0.5 * cal <= d2 <= 2 * cal, (name, "TSC per RTC second vs PIT-calibrated rate", d1, d2, cal)
    assert (u3 == 0) if floor_refused else (3 <= u3 - u0 <= 5), (name, "clock reading after three seconds", u0, u3)
    return dict(name=name, rtc=how, base=base, startDeltaSeconds=delta, status=status0, rawUnix=raw_unix, rtcRegisterB=hex(regb),
                century=hex(W(380)), secondsSeen=secs, tscPerRtcSecond=[d1, d2], pitCalibratedTscPerSecond=cal,
                ratio=[round(d1 / cal, 4), round(d2 / cal, 4)])


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    disk = out / "fixture.img"
    want = nvme.fat32_disk(out, disk)
    before = disk.read_bytes()
    events = []

    # --- the clock: five RTC settings, each boot also decodes the synthetic rows ---
    blob, rows = oracle.clock_fw_file()
    fw_clock = out / "clock.bin"; fw_clock.write_bytes(blob)
    plans = [("clock-default-host", None, [], "default"),
             ("clock-vm-2026-11-06", calendar.timegm((2026, 11, 6, 12, 34, 56)), None, "vm"),
             ("clock-vm-leap-day-2028", calendar.timegm((2028, 2, 29, 23, 59, 50)), None, "vm"),
             ("clock-vm-2100-03-01", calendar.timegm((2100, 3, 1, 0, 0, 0)), None, "vm"),
             ("clock-vm-before-build-floor", calendar.timegm((2025, 1, 1, 0, 0, 0)), None, "vm")]
    probes, decoded = [], 0
    for name, base, rtc, how in ([] if args.cases_only else plans):
        disk.write_bytes(before)
        r = boot(args, out, name, disk, "opt/aiueos/clock", fw_clock, rtc if rtc is not None else rtc_arg(base), CLOCK_MARKER, (364, 40))
        probes.append(probe_checks(name, r, base, how))
        got = r["rows"]
        assert got[0] == len(rows), (name, "the decoder rows did not run", got[0])
        bad = [(n, got[4 + k], u) for k, (n, _row, u) in enumerate(rows) if got[4 + k] != u]
        assert not bad, (name, "the guest's RTC decoder differs from the oracle's (row, got, want)", bad)
        decoded += len(rows)
        assert r["nvme"] == 15 and r["drew"] and r["esp"] == dict(path=want["path"], fat=want["fat"], size=want["size"], sha256=want["sha256"]), \
            (name, r["nvme"], r["drew"], r["esp"])
    if args.cases_only:   # negative controls (rebuilt mutants) run the cases alone; the real gate never does
        print("CASES-ONLY run: the clock boots are skipped")
    events.append(dict(name="fresh-clock-probes", probes=probes))
    events.append(dict(name="fresh-clock-decoder", rows=[dict(name=n, row=list(row), unix=u) for n, row, u in rows], bootsChecked=len(plans)))

    # --- the freshness records ---
    def cases_boot(label, chosen, clock_base, expect_clock):
        blob, cs = oracle.fw_file(B0, chosen, expect_clock)
        fw = out / f"fresh-{label}.bin"; fw.write_bytes(blob)
        disk.write_bytes(before)
        r = boot(args, out, f"fresh-{label}", disk, "opt/aiueos/fresh", fw, rtc_arg(clock_base), CASE_MARKER, (CASE_WORD, 64))
        assert r["marker"] == CASE_MARKER and r["count"] == len(cs), ("the cases did not finish", label, hex(r["marker"]), r["count"])
        matches, bad = [], []
        for k, c in enumerate(cs):
            wanted = c["code"] + 256 * c["mask"] + 65536 * c["state"]
            (matches if r["words"][k] == wanted else bad).append(c["name"] if r["words"][k] == wanted else (c["name"], hex(r["words"][k]), hex(wanted)))
        assert not bad, ("freshness cases differ from the oracle (name, got result|mask<<8|verdict<<16, want)", label, bad)
        assert r["v1"] == [7, 15, 1, 7], ("the AIUEIMG1 self-test changed", r["v1"])
        assert r["walk"] == 15 and r["nvme"] == 15, ("the storage walk after the ML-DSA arena failed", r["walk"], r["nvme"])
        assert r["esp"] == dict(path=want["path"], fat=want["fat"], size=want["size"], sha256=want["sha256"]), (r["esp"], want)
        assert disk.read_bytes() == before, "a verify-only boot must not write the disk"
        assert r["drew"], "the desktop must still draw after the freshness path ran"
        return r, cs, matches

    r, cs, matches = cases_boot("cases", None, B0, None)
    admitted = {c["name"]: c["state"] for c in cs if c["code"] == 15}
    refused = {c["name"]: [c["code"], c["mask"]] for c in cs if c["code"] != 15}
    events.append(dict(name="fresh-cases", rtcBase=B0, cases=len(cs), matches=matches, admittedStates=admitted, refused=refused))
    keep = sorted(admitted) + ["one-signer", "header-signed-under-image-context"]
    r2, cs2, m2 = cases_boot("clock-ahead", keep, B0 + 40 * 86400, B0 + 40 * 86400)
    events.append(dict(name="fresh-cases-clock-ahead", rtcBase=B0 + 40 * 86400, cases=len(cs2), matches=m2,
                       states={c["name"]: c["state"] for c in cs2 if c["code"] == 15}))
    r3, cs3, m3 = cases_boot("no-clock", keep, calendar.timegm((2025, 1, 1, 0, 0, 0)), "none")
    events.append(dict(name="fresh-cases-no-clock", rtcBase=calendar.timegm((2025, 1, 1, 0, 0, 0)), cases=len(cs3), matches=m3,
                       states={c["name"]: c["state"] for c in cs3 if c["code"] == 15}))
    events.append(dict(name="fresh-storage-restored", espWalkAfter=r["walk"], nvmeProbe=r["nvme"], diskUnchanged=True, espBootSha256=r["esp"]["sha256"]))
    events.append(dict(name="fresh-regression", imageSelfTest=r["v1"], desktopStillDraws=True))
    disk.unlink()
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_FRESH_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)),
                  oracle=pin(HERE / "fresh_oracle.py"), signingOracle=pin(HERE / "imgsig_oracle.py"), reference=pin(oracle.o.REF / "reference.py"),
                  events=events, network="none (-nic none)", testKeysOnly=True, productionSignerSet=False, notWiredToDesktop=True,
                  physicalHardware=False, clockIsQemuNotABoard=True)
    (out / "native-fresh-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(cs), "cases", len(admitted), "admitted", decoded, "rows decoded")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    p.add_argument("--cases-only", action="store_true")
    main(p.parse_args())
