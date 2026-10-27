#!/usr/bin/env python3
"""ADR-0277 W3d slice: Ed25519 public keys from seeds in the native desktop kernel.

Before the desktop starts the guest derives the Ed25519 public key (RFC 8032 section 5.1.5: SHA-512 of the seed,
clamp, scalar multiplication of the base point, encoding) for the three RFC 8032 section 7.1 test seeds and leaves
128 bytes per case from word 320 of the browser context; the first 32 bytes are the encoded key. This gate boots
once, waits for the first completed frame, reads the marker (word 99 = "ED25") and the 96 result words over the
QEMU monitor and compares the keys with the published RFC 8032 public keys. The seeds are public test vectors: no
device key exists and nothing is signed. QEMU TCG only.
"""
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"ED25", "big")
CASES = (
    ("rfc8032-test1", "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"),
    ("rfc8032-test2", "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"),
    ("rfc8032-test3", "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025"),
)

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

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
    events = []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(99, 1)[0]
        assert marker == MARKER, ("the Ed25519 self-test did not finish", hex(marker))
        keys = []
        for k, (name, expected) in enumerate(CASES):
            raw = b"".join(struct.pack("<I", w) for w in words(320 + 32 * k, 32))
            got = raw[:32]
            assert got.hex() == expected, (name, got.hex(), expected)
            keys.append(dict(case=name, publicKey=got.hex()))
        assert len({k["publicKey"] for k in keys}) == 3, "the three keys must differ"
        events.append(dict(name="ed25519-pubkey", marker=hex(marker), keys=keys))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_ED25519_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), events=events,
                  signing=False, deviceKey=False, physicalHardware=False, syntheticInput=False)
    (out / "native-ed25519-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(keys), "keys")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
