#!/usr/bin/env python3
"""ADR-0277 W3b slice: the native desktop kernel computes SHA-512 in the guest.

Before the desktop starts, the guest hashes three messages with aiueos.sha512 and leaves the digests in the
browser context: "abc" (words 320..335), the 112-byte FIPS 180-4 two-block message (336..351) and "abd"
(352..367). This gate boots once, waits for the first completed frame, reads the preserved marker (effects word 51 =
0x53483531) and the 48 digest words over the QEMU monitor, and compares them with hashlib.sha512 of the
same messages computed on the host. "abd" is the negative control: it must differ from "abc" and match
its own digest. No key exists and nothing is signed; QEMU TCG only.
"""
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"SH51", "big")
MSG2 = (b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrs"
        b"mnopqrstnopqrstu")
CASES = (("abc", b"abc", 320), ("fips-two-block", MSG2, 336), ("abd", b"abd", 352))

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def main(a):
    assert len(MSG2) == 112
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
    events, matches = [], []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the SHA-512 self-test did not finish", hex(marker))
        got = {}
        for name, msg, first in CASES:
            raw = b"".join(struct.pack("<I", w) for w in words(first, 16))
            expected = hashlib.sha512(msg).digest()
            assert raw == expected, (name, raw.hex(), expected.hex())
            got[name] = raw; matches.append(name)
        assert got["abc"] != got["abd"], "negative control: abd must differ from abc"
        events.append(dict(name="sha512-digests", marker=hex(marker), matches=matches,
                           digests={n: got[n].hex() for n in got}))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_SHA512_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), events=events,
                  signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-sha512-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], matches)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
