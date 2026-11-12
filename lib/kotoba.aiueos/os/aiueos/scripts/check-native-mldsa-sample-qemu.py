#!/usr/bin/env python3
"""JUN-813 stage 3 (ADR-0286): the native desktop kernel runs the region-based ML-DSA-65 sampling and packing module (aiueos.mldsa-sample).

Before the desktop starts, the guest runs ExpandA for two matrix entries, SampleInBall, SimpleBitUnpack at 10, 20 and 4 bits
(and the BitUnpack offset), SimpleBitPack at 4 and 10 bits and hint unpacking, and leaves per step the first 8 values and a
40-bit checksum in the browser context (byte 1280 + 64 k). This gate boots once, waits for the first completed frame, reads the
preserved marker (effects word 51 = "SM01"), the records and the hint refusal results, and compares them with
scripts/mldsa_sample_oracle.py (hashlib SHAKE written from FIPS 204). One host value changed is the negative control. No key exists; QEMU TCG only.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"SM01", "big")
import mldsa_sample_oracle as oracle
CASES = oracle.records()

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
    events, matches = [], []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the sampling self-test did not finish", hex(marker))
        for k, (name, poly) in enumerate(CASES):
            raw = words(320 + 16 * k, 10)
            first8, check = raw[:8], raw[8] + (raw[9] << 32)
            assert first8 == poly[:8] and check == oracle.checksum(poly), (name, first8, poly[:8], check, oracle.checksum(poly))
            matches.append(name)
        refusals = words(480, 4)
        assert refusals == [1, 0, 0, 0], ("hint unpack results (valid, not-increasing, bad-padding, limit-decreases)", refusals)
        matches.append("hint-refusals")
        changed = list(CASES[0][1]); changed[100] ^= 1
        assert oracle.checksum(changed) != oracle.checksum(CASES[0][1]), "negative control"
        events.append(dict(name="sample-records", marker=hex(marker), matches=matches))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_MLDSA_SAMPLE_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), events=events,
                  signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-mldsa-sample-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], matches)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
