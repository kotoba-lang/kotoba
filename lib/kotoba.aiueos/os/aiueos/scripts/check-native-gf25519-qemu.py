#!/usr/bin/env python3
"""ADR-0277 W3c slice: GF(2^255-19) arithmetic in the native desktop kernel.

Before the desktop starts the guest runs aiueos.gf25519 on three (a, b) pairs and leaves a*b, inv(a), a+b and a-b
(32 bytes each, canonical little-endian) in the browser context, 128 bytes per case from word 320. This gate boots
once, waits for the first completed frame, reads the preserved marker (effects word 51 = "GF25") and the 96 result words over the
QEMU monitor and compares them with Python's big-integer arithmetic mod p. The pairs are a generic pair, (p-1, p-1)
and (1, 2^254). Results must also be canonical (< p). No key, point arithmetic or signature; QEMU TCG only.
"""
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
P = 2**255 - 19
MARKER = int.from_bytes(b"GF25", "big")
CASES = ((0x1f2e3d4c5b6a79880123456789abcdef0fedcba98765432100112233445566ff % P,
          0x7edcba98765432100fedcba987654321aabbccddeeff00112233445566778899 % P), (P - 1, P - 1), (1, 2**254))

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def le(x): return (x % P).to_bytes(32, "little")

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == 0x240000 and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + 0x23a000
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
    events, checked = [], []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the GF(2^255-19) self-test did not finish", hex(marker))
        for k, (x, y) in enumerate(CASES):
            raw = b"".join(struct.pack("<I", w) for w in words(320 + 32 * k, 32))
            got = [raw[i * 32:(i + 1) * 32] for i in range(4)]
            want = [le(x * y), le(pow(x, P - 2, P)), le(x + y), le(x - y)]
            names = ("mul", "inv", "add", "sub")
            for n, g, w in zip(names, got, want):
                assert int.from_bytes(g, "little") < P, (k, n, "not canonical")
                assert g == w, (k, n, g.hex(), w.hex())
            checked.append(dict(case=k, ok=list(names)))
        events.append(dict(name="gf25519", marker=hex(marker), cases=checked))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_GF25519_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), events=events,
                  signing=False, pointArithmetic=False, physicalHardware=False, syntheticInput=False)
    (out / "native-gf25519-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(checked), "cases")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
