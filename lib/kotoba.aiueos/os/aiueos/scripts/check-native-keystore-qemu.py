#!/usr/bin/env python3
"""ADR-0277 W3f: the sealed device key survives a reboot, and a wrong passphrase is refused.

Three boots of the same consent-profile kernel (two over one provisioned 64 KiB scratch disk, the third with no disk) (a test fixture; the guest
never formats a disk). Boot 1: F8, Allow, a passphrase, Enter: the key is created and its sealed blob is written
to sector 4 and read back (word 97 = 1). QEMU is then quit. Boot 2, same disk: the guest finds the sealed key at
boot (word 96 = 1, the home says "DID: locked", no seed in RAM, the blob in RAM equals the disk's); F8 opens the
unlock request; a wrong passphrase is refused (word 94 = 8, still locked, seed zero, passphrase buffer wiped);
the right one unlocks (word 94 = 9): the seed and the public key are the boot-1 ones, the fingerprint is shown
again, and a consent-bound signature (F7) verifies under the boot-1 public key. The passphrase is a public test
value; only the sealed blob is on the disk (the gate also checks that the seed is not in the disk image).
QEMU TCG, synthetic input: it proves no human consent and no physical-disk behaviour.
"""
import argparse, hashlib, importlib.util, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("consent_gate", HERE / "check-native-consent-qemu.py")
consent = importlib.util.module_from_spec(spec); spec.loader.exec_module(consent)
pin, ed_verify, unseal = consent.pin, consent.ed_verify, consent.unseal
PASS, WRONG = "correct horse", "correct horsf"


class Boot:
    def __init__(self, args, out, name, scratch):
        image = args.kernel.read_bytes()
        rw = struct.unpack_from("<IIQQQQQQ", image, 120)
        context = rw[3]
        assert rw[5] == 0x240000 and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
        self.surface, self.work = context + 0x238000, context + 0x23a000
        self.out, self.name = out, name
        cmd = [str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
               "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware}",
               "-drive", f"file={args.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
               "-nic", "none", "-display", "none", "-no-reboot", "-monitor", "stdio"]
        if scratch is not None:
            cmd += ["-device", "isa-ide,id=draft-controller",
                    "-drive", f"file={scratch},format=raw,if=none,id=draft,cache=directsync",
                    "-device", "ide-hd,drive=draft,bus=draft-controller.0,unit=1,serial=AWAI90DRAFT000001"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, cwd=out, bufsize=1)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if self.W(79) >= 1: break
            time.sleep(2)
        assert self.W(79) >= 1, (name, "no first frame")

    def send(self, line, wait=0.4):
        self.proc.stdin.write(line + "\n"); self.proc.stdin.flush(); time.sleep(wait)

    def drain(self):
        text = ""
        while select.select([self.proc.stdout], [], [], 0.2)[0]:
            chunk = os.read(self.proc.stdout.fileno(), 65536).decode(errors="replace")
            if not chunk: break
            text += chunk
        return text

    def dump(self, addr, length):
        # Observe one native range in a single monitor command. The previous
        # per-word sleep took minutes for the4096-byte wipe assertion and did
        # not add any guest/device coverage. Keep the exact full-range checks.
        path = self.out / "keystore-observation.bin"
        if path.exists(): path.unlink()
        self.drain()
        self.send(f"pmemsave {addr:#x} {length} {path.name}", .05)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if path.exists() and path.stat().st_size == length:
                raw = path.read_bytes(); path.unlink(); return raw
            if self.proc.poll() is not None: break
            time.sleep(.02)
        raise AssertionError(("native memory observation missing", hex(addr), length))

    def read(self, addr): return struct.unpack("<I", self.dump(addr, 4))[0]
    def S(self, i): return self.read(self.surface + 4 * i)
    def W(self, i): return self.read(self.work + 4 * i)
    def words(self, first, count): return self.dump(self.work + 4 * first, 4 * count)

    def type_text(self, text):
        for ch in text: self.send("sendkey " + ("spc" if ch == " " else ch), 0.6)

    def screenshot(self, name):
        self.send(f"screendump {name}.ppm", 2.0)
        raw = (self.out / f"{name}.ppm").read_bytes()
        _, dims, _, pixels = raw.split(b"\n", 3)
        width, height = map(int, dims.split())
        return width, height, pixels

    def band(self, shot, x0, x1, y0, y1):
        w = shot[0]
        return [shot[2][3 * (y * w + x):3 * (y * w + x) + 3] for y in range(y0, y1) for x in range(x0, x1)]

    def quit(self):
        try: self.send("quit", 0.5)
        except Exception: pass
        try: self.proc.wait(timeout=15)
        except Exception: self.proc.kill()


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    scratch = out / "scratch.raw"
    raw = bytearray(128 * 512)
    struct.pack_into("<4I", raw, 0, 0x49415741, 0x54465244, 1, 128)
    scratch.write_bytes(raw)
    events = []
    # ---- boot 1: create the key under a passphrase; it is sealed and written to sector 4 ----
    b = Boot(args, out, "boot1", scratch)
    try:
        assert b.W(96) == 0 and b.S(2039) == 0, "a blank disk must not look like a stored key"
        b.send("sendkey 2", 1.5); b.send("sendkey a", 1.5)
        home_none = b.screenshot("home-none")
        key_row = lambda shot: b.band(shot, 180, 330, 170, 188)
        assert sum(1 for px in key_row(home_none) if px != b"\xff\xff\xff") > 20, "the key row must be drawn"
        b.send("sendkey f8", 1.5); assert b.W(87) == 2
        key_panel = b.screenshot("key-request")
        b.send("sendkey y", 1.5); assert b.W(87) == 4
        create_panel = b.screenshot("create-passphrase")
        b.type_text(PASS); b.send("sendkey ret", 8.0)
        assert b.W(87) == 0 and b.W(94) == 1 and b.W(97) == 1, (b.W(87), b.W(94), b.W(97))
        seed1, pub1, blob1 = b.words(928, 8), b.words(320, 8), b.words(848, 16)
        flags1 = b.S(2039)
        assert seed1 != bytes(32) and (flags1 >> 6) & 1 == 1 and (flags1 >> 7) & 0xffffff == int.from_bytes(pub1[:3], "big")
        assert unseal(PASS.encode(), blob1) == seed1
        events.append(dict(name="boot1-create", fingerprint=pub1[:3].hex(), publicKey=pub1.hex(), blob=blob1.hex(), persisted=True))
    finally:
        b.quit()
    disk = scratch.read_bytes()
    assert disk[4 * 512:4 * 512 + 4] == b"KSL1" and disk[4 * 512 + 16:4 * 512 + 80] == blob1, "sector 4 does not hold the sealed blob"
    assert seed1 not in disk and PASS.encode() not in disk, "the seed or the passphrase is on the disk in the clear"
    assert disk[0:16] == bytes(raw[0:16]) and set(disk[4 * 512 + 80:5 * 512]) == {0}, "the record must be only the blob"
    # ---- boot 2: the same disk; the key is locked until the right passphrase ----
    b = Boot(args, out, "boot2", scratch)
    try:
        assert b.W(96) == 1 and b.S(2039) == 128, (b.W(96), hex(b.S(2039)))
        assert b.words(848, 16) == blob1, "the blob read at boot differs from the one written"
        assert b.words(928, 8) == bytes(32) and b.words(320, 8) == bytes(32), "no seed or public key may exist before unlock"
        b.send("sendkey 2", 1.5); b.send("sendkey a", 1.5)
        home_locked = b.screenshot("home-locked")
        did_band = lambda shot: b.band(shot, 180, 330, 150, 168)
        assert key_row(home_none) != key_row(home_locked), "the key row must say locked, not none"
        assert did_band(home_none) != did_band(home_locked), "the DID line must read differently when a sealed key is stored"
        assert sum(1 for px in did_band(home_locked) if px != b"\xff\xff\xff") > 20, "the locked DID line must be drawn"
        b.send("sendkey f7", 1.5); assert b.W(87) == 0, "signing must be impossible while the key is locked"
        events.append(dict(name="boot2-locked", locked=True, blobEqualsDisk=True, seedInRam=False, signingRefused=True))
        # wrong passphrase: refused, still locked
        b.send("sendkey f8", 1.5)
        assert b.W(87) == 4 and b.W(98) == 1 and b.S(2039) == 128 + 3 + 2**31 + 8192, (b.W(87), b.W(98), hex(b.S(2039)))
        unlock_panel = b.screenshot("unlock-passphrase")
        px, py = (unlock_panel[0] - 480) // 2, (unlock_panel[1] - 224) // 2
        title = lambda shot: b.band(shot, px + 20, px + 460, py + 14, py + 40)
        assert title(unlock_panel) != title(create_panel), "the unlock panel must be titled differently from the create panel"
        assert b.band(unlock_panel, px + 20, px + 460, py + 56, py + 80) == b.band(create_panel, px + 20, px + 460, py + 56, py + 80), "the service line is the same"
        b.type_text(WRONG); b.send("sendkey ret", 8.0)
        assert b.W(87) == 0 and b.W(94) == 8 and b.W(96) == 1 and b.S(2039) == 128, (b.W(87), b.W(94), b.W(96), hex(b.S(2039)))
        assert b.words(928, 8) == bytes(32) and b.words(832, 8) == bytes(32), "a refused unlock must leave no seed and no passphrase"
        events.append(dict(name="unlock-wrong-passphrase", refused=True, stillLocked=True, seedBytes=b.words(928, 8).hex()))
        # right passphrase: the boot-1 key is back
        b.send("sendkey f8", 1.5); assert b.W(87) == 4 and b.W(98) == 1
        b.type_text(PASS); b.send("sendkey ret", 8.0)
        assert b.W(87) == 0 and b.W(94) == 9 and b.W(96) == 0, (b.W(87), b.W(94), b.W(96))
        seed2, pub2 = b.words(928, 8), b.words(320, 8)
        flags2 = b.S(2039)
        assert seed2 == seed1 and pub2 == pub1, "the unlocked key is not the stored one"
        assert (flags2 >> 6) & 1 == 1 and (flags2 >> 7) & 0xffffff == int.from_bytes(pub1[:3], "big") and flags2 & 3 == 0, hex(flags2)
        assert b.words(832, 8) == bytes(32), "the passphrase buffer must be wiped after unlock"
        home_ready = b.screenshot("home-ready")
        assert key_row(home_ready) != key_row(home_locked) and key_row(home_ready) != key_row(home_none), "the key row must say ready"
        events.append(dict(name="unlock-right-passphrase", unlocked=True, fingerprint=pub2[:3].hex(), samePublicKey=True, sameSeed=True))
        # a consent-bound signature under the restored key verifies under the boot-1 public key
        b.send("sendkey f7", 1.5); assert b.W(87) == 3
        b.send("sendkey y", 3.0)
        sig = b.words(800, 16)
        challenge = b"itonami-w3-sign-test"
        assert ed_verify(pub1, challenge, sig), "the signature after unlock does not verify under the boot-1 public key"
        foreign = consent.ed_public(bytes(range(32)))
        assert not ed_verify(foreign, challenge, sig), "a foreign key must not verify"
        events.append(dict(name="sign-after-unlock", verifies=True, foreignKeyRefused=True, signature=sig.hex()))
        # Lock (F6): everything secret leaves RAM, the key goes back to the locked state, the disk is untouched
        count = (b.S(2039) >> 2) & 15
        disk_before = scratch.read_bytes()
        b.send("sendkey f6", 4.0)
        assert b.W(87) == 0 and b.W(94) == 11 and b.W(96) == 1, (b.W(87), b.W(94), b.W(96))
        assert b.S(2039) == count * 4 + 128, (hex(b.S(2039)), count)
        zero = bytes(32)
        assert b.words(928, 8) == zero and b.words(320, 8) == zero and b.words(800, 16) == bytes(64), "seed, public key and signature must be gone"
        assert b.words(768, 16) == bytes(64) and b.words(512, 8) == zero and b.words(1024, 8) == zero, "signing buffer and workspace must be wiped"
        assert scratch.read_bytes() == disk_before, "Lock must not write to the disk"
        b.send("sendkey f7", 1.5); assert b.W(87) == 0, "signing must be impossible while locked"
        home_relocked = b.screenshot("home-relocked")
        assert key_row(home_relocked) == key_row(home_locked) and key_row(home_relocked) != key_row(home_ready), "the key row must say locked again"
        events.append(dict(name="lock", wiped=True, lockedAgain=True, diskUntouched=True, signingRefused=True))
        # and the right passphrase brings the same key back
        b.send("sendkey f8", 1.5); assert b.W(87) == 4 and b.W(98) == 1
        b.type_text(PASS); b.send("sendkey ret", 8.0)
        assert b.W(94) == 9 and b.W(96) == 0 and b.words(928, 8) == seed1 and b.words(320, 8) == pub1, "unlock after lock must restore the same key"
        events.append(dict(name="unlock-after-lock", sameKey=True))
    finally:
        b.quit()
    # ---- boot 3: no disk. A key that is not stored cannot be locked (it would be lost): Lock refuses and changes nothing ----
    b = Boot(args, out, "boot3", None)
    try:
        b.send("sendkey 2", 1.5); b.send("sendkey a", 1.5)
        b.send("sendkey f8", 1.5); assert b.W(87) == 2
        b.send("sendkey y", 1.5); assert b.W(87) == 4
        b.type_text(PASS); b.send("sendkey ret", 8.0)
        assert b.W(94) == 1 and b.W(97) == 0, ("no disk: the key must exist and be RAM-only", b.W(94), b.W(97))
        flags3, seed3 = b.S(2039), b.words(928, 8)
        b.send("sendkey f6", 2.0)
        assert b.W(94) == 10 and b.S(2039) == flags3 and b.words(928, 8) == seed3 and b.W(96) == 0, "Lock must refuse an unstored key and change nothing"
        b.send("sendkey f7", 1.5); assert b.W(87) == 3, "the unstored key must still sign"
        b.send("sendkey n", 1.5)
        events.append(dict(name="lock-refused-unstored", refused=True, keyKept=True))
    finally:
        b.quit()
    assert pin(args.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_KEYSTORE_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  font=pin(args.font), firmware=pin(args.firmware), observer=pin(Path(__file__)), events=events,
                  persistedAcrossReboot=True, wrongPassphraseRefused=True, physicalHardware=False,
                  syntheticInputProvesHumanConsent=False)
    (out / "native-keystore-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
