#!/usr/bin/env python3
"""JUN-932/920 (ADR-0287): the native desktop kernel runs the CSSOM grid track sizing and table column width slice (cssom.grid-k,
cssom.table-k: layout.cljk track-sizes, distribute-fr, distribute-equally-with-caps, grid-track-intrinsics, span-width,
table-column-widths, table-fixed-column-widths, distribute-excess, all as kernel-dialect region code) over a deterministic grid.

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/grid (QEMU only, never a disk or the network): [case count:2 big
endian] then per case [kind:1][word count:2 big endian][u32 big endian words], made by lib/kotoba.cssom/scripts/grid_k_cases.py (hand
derived cases, a track-mix grid, seeded random cases, exact-tie cases, and one case on each side of every bound). For each case it
leaves four u32 words at browser-context byte 4096 + 16 k (see native/grid-entry.kotoba): status, output count, hash, sum. This observer
boots once, waits for the first frame, reads the marker (effects word 51 = "GR01") and the records with the monitor command xp, and
checks, from the case table and the exact model (not from the kernel), the status, count, hash and sum of every case. The records go
into the receipt, where scripts/check-grid-k-native-macos.py (in lib/kotoba.cssom) compares them with the native f64 references.
QEMU TCG only; no key is used.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, sys, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"GR01", "big")
HERE = Path(__file__).resolve().parent
CASES_PY = HERE.parents[2].parent / "kotoba.cssom" / "scripts" / "grid_k_cases.py"
sys.path.insert(0, str(CASES_PY.parent))
import grid_k_cases as K  # noqa: E402

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def fixture(cases):
    blobs = [bytes([0 if c["kind"] == "grid" else 1]) + c["blob"] for c in cases]
    assert len(cases) <= 240 and all(len(b) <= 65535 for b in blobs)
    return struct.pack(">H", len(cases)) + b"".join(blobs), blobs

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    cases = K.all_cases()
    blob, blobs = fixture(cases)
    fwfile = out / "grid-cases.bin"; fwfile.write_bytes(blob)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    dump = out / "records.bin"
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/grid,file={fwfile}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
        assert marker == MARKER, ("the grid self-test did not finish", hex(marker))
        assert words(319, 1)[0] == len(cases), "case count"
        raw = b""
        for first in range(0, 4 * len(cases), 64):
            n = min(64, 4 * len(cases) - first)
            raw += b"".join(struct.pack("<I", w) for w in words(1024 + first, n))
        assert len(raw) == 16 * len(cases), (len(raw), len(cases))
        dump.write_bytes(raw)
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    bad = []
    for k, c in enumerate(cases):
        status, count, h, total = struct.unpack_from("<IIII", raw, 16 * k)
        rec = dict(name=c["name"], kind=c["kind"], status=status, count=count if status == 0 else None,
                   hash=h if status == 0 else None, sum=total if status == 0 else None)
        records.append(rec)
        e = K.expected(c)
        ok = status == -e[0] if e[0] < 0 else (status == 0 and (count, h, total) == (e[3], e[1], e[2]))
        ok = ok and status == (c["status"] and -c["status"])
        (matches if ok else bad).append(c["name"] if ok else (c["name"], rec, e))
    events.append(dict(name="grid-cases", cases=len(cases), matches=len(matches), handDerived=sum(1 for c in cases if c["expect"] is not None),
                       refusals=sum(1 for c in cases if c["status"] != 0), marker=hex(marker)))
    report = dict(status="PASS_NATIVE_GRID_K_QEMU" if not bad else "FAIL_NATIVE_GRID_K_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), cases=pin(CASES_PY), fixture=pin(fwfile),
                  records=records, mismatches=bad, events=events, signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-grid-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(matches), "of", len(cases))
    if bad:
        print("grid records differ from the exact model (name, record, expected):", bad[:10], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
