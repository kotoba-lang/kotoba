#!/usr/bin/env python3
"""JUN-932 (JUN-920 follow-up): the native desktop kernel runs flex lines of up to sixteen items (cssom.flex-k, cssom.fxdiv-k,
cssom.flexplace-k: grow, scaled shrink, min/max clamp, freeze-and-redistribute, justify-content, auto margins, all as kernel-dialect
region code) over a deterministic grid.

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/flex (QEMU only, never a disk or the network): [case count:2 big
endian] then per case [length:2 big endian][wire stream], made by lib/kotoba.cssom/scripts/flex_k_cases.py (hand-derived cases, a
capacity grid with a case on each side of every bound, items on min/max bounds, cascades of freezes, exact ties, justify-content
and auto-margin placement, a seeded random grid). For each case it leaves ONE word at browser-context byte 4096 + 4 k (see
native/flex-entry.kotoba): status << 24 | a 24-bit digest of the final sizes (and offsets). This observer boots once, waits for the
first frame, reads the marker (effects word 51 = "FX01") and reads the records with the monitor command xp. It compares every
record with the digest of the EXACT model of the case table (Fractions, no f64), not with anything the kernel produced, and records
them in the receipt, where scripts/check-flex-k-native-macos.py (in lib/kotoba.cssom) compares the host-native f64 reference
with the same exact sizes. QEMU TCG only; no key is used.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, sys, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"FX01", "big")
HERE = Path(__file__).resolve().parent
CASES_PY = HERE.parents[2].parent / "kotoba.cssom" / "scripts" / "flex_k_cases.py"
sys.path.insert(0, str(CASES_PY.parent))
import flex_k_cases as K  # noqa: E402

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def fixture(cases):
    blobs = [K.encode(c) for c in cases]
    assert len(cases) <= 1000 and all(len(b) <= 65535 for b in blobs)
    return struct.pack(">H", len(cases)) + b"".join(struct.pack(">H", len(b)) + b for b in blobs), blobs

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    cases = K.all_cases()
    blob, blobs = fixture(cases)
    fwfile = out / "flex-cases.bin"; fwfile.write_bytes(blob)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    dump = out / "records.bin"
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/flex,file={fwfile}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=out, bufsize=1)
    def send(line, wait=0.3):
        proc.stdin.write(line + "\n"); proc.stdin.flush(); time.sleep(wait)
    def drain():
        t = ""
        while select.select([proc.stdout], [], [], 0.1)[0]:
            ch = os.read(proc.stdout.fileno(), 65536).decode(errors="replace")
            if not ch: break
            t += ch
        return t
    def words(first, count):
        drain(); send(f"xp /{count}wx {work + 4 * first:#x}", 0.6)
        f = re.findall(r"0x([0-9a-f]{8})", drain()); assert len(f) >= count, (first, count, len(f))
        return [int(x, 16) for x in f[-count:]]
    events, matches, records = [], [], []
    try:
        deadline = time.monotonic() + 3000
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        while time.monotonic() < deadline and words(2048 + 51, 1)[0] != MARKER: time.sleep(2)
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the flex self-test did not finish", hex(marker))
        assert words(319, 1)[0] == len(cases), "case count"
        raw = b""
        for first in range(0, len(cases), 64):
            n = min(64, len(cases) - first)
            raw += b"".join(struct.pack("<I", w) for w in words(1024 + first, n))
        assert len(raw) == 4 * len(cases), (len(raw), len(cases))
        dump.write_bytes(raw)
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    bad = []
    for k, c in enumerate(cases):
        (rec,) = struct.unpack_from("<I", raw, 4 * k)
        want = K.digest(c)
        records.append(dict(name=c["name"], status=rec >> 24, digest=rec & 0xFFFFFF, want=want))
        (matches if rec == want else bad).append(c["name"] if rec == want else (c["name"], hex(rec), hex(want)))
    events.append(dict(name="flex-cases", cases=len(cases), matches=len(matches), refusals=sum(1 for r in records if r["status"] != 0),
                       marker=hex(marker)))
    report = dict(status="PASS_NATIVE_FLEX_K_QEMU" if not bad else "FAIL_NATIVE_FLEX_K_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), cases=pin(CASES_PY), fixture=pin(fwfile),
                  records=records, mismatches=bad, events=events, signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-flex-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(matches), "of", len(cases))
    if bad:
        print("flex records differ from the exact model (name, record, expected):", bad[:10], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
