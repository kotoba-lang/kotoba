#!/usr/bin/env python3
"""ADR-0277 W3f slice: seal a seed under a passphrase and open it, in the native desktop kernel.

Before the desktop starts the guest seals the RFC 8032 section 7.1 test seed 1 under the public test passphrase
"correct horse" with aiueos.keyseal (iterated SHA-512 KDF, 1024 rounds; blob = salt16 || ct32 || tag16), then
opens the blob with the right passphrase, with a wrong one, and after one ciphertext byte was flipped. This gate
boots once, waits for the first completed frame, reads the preserved marker (effects word 51 = "KSEA") and the results over the
QEMU monitor and compares them with a Python reference of the same construction: the 64-byte blob must equal the
reference blob byte for byte, the good open returns the seed, and the wrong-passphrase and changed-blob opens
fail and leave their seed output zero. The seed, passphrase and salt are public test values: no device key is
sealed and nothing is written to a disk. QEMU TCG only.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"KSEA", "big")
ITERS = 1024
SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
SALT = bytes(17 + 13 * i for i in range(16))
PASS = b"correct horse"
WRONG = b"correct horsf"

def kdf(pw, salt, iters):
    h = hashlib.sha512(pw.ljust(32, b"\0") + salt).digest()
    for _ in range(iters - 1): h = hashlib.sha512(h + salt).digest()
    return h

def seal(pw, salt, seed, iters):
    k = kdf(pw, salt, iters)
    ct = bytes(a ^ b for a, b in zip(seed, k[:32]))
    return salt + ct + hashlib.sha512(k[32:] + salt + ct).digest()[:16]

def unseal(pw, blob, iters):
    salt, ct, tag = blob[:16], blob[16:48], blob[48:]
    k = kdf(pw, salt, iters)
    if hashlib.sha512(k[32:] + salt + ct).digest()[:16] != tag: return None
    return bytes(a ^ b for a, b in zip(ct, k[:32]))

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
    events = []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the key-seal self-test did not finish", hex(marker))
        status = words(440, 4)
        assert status == [1, 1, 0, 0], ("seal, good open, wrong-passphrase open, changed-blob open", status)
        blob = b"".join(struct.pack("<I", w) for w in words(320, 16))
        reference = seal(PASS, SALT, SEED, ITERS)
        assert blob == reference, ("the guest blob differs from the reference", blob.hex(), reference.hex())
        assert blob[:16] == SALT and blob[16:48] != SEED, "the salt must be in the clear and the seed must not"
        raw = lambda first: b"".join(struct.pack("<I", w) for w in words(first, 8))
        good, wrong, changed = raw(416), raw(424), raw(432)
        assert good == SEED, ("the right passphrase did not return the seed", good.hex())
        assert wrong == bytes(32), ("a wrong passphrase must release nothing", wrong.hex())
        assert changed == bytes(32), ("a changed blob must release nothing", changed.hex())
        # negative controls of the reference itself: the construction refuses what the guest refused
        assert unseal(PASS, blob, ITERS) == SEED and unseal(WRONG, blob, ITERS) is None
        flipped = bytearray(blob); flipped[20] ^= 1
        assert unseal(PASS, bytes(flipped), ITERS) is None
        events.append(dict(name="keyseal-seal-open", marker=hex(marker), iterations=ITERS, blob=blob.hex(),
                           matchesReference=True, goodOpenReturnsSeed=True, wrongPassphraseReleasesNothing=True,
                           changedBlobReleasesNothing=True))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_KEYSEAL_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), events=events,
                  sealed=True, deviceKey=False, physicalHardware=False, syntheticInput=False)
    (out / "native-keyseal-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events), "events")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
