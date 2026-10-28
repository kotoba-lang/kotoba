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
import native_regions
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
        assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
        self.surface, self.work = context + native_regions.SURFACE_OFFSET, context + native_regions.CONTEXT_OFFSET
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

    def read(self, addr):
        self.drain(); self.send(f"xp /1wx {addr:#x}", 0.5)
        found = re.findall(r"[0-9a-f]{16}: 0x([0-9a-f]{8})", self.drain())
        assert found, ("xp gave nothing", hex(addr))
        return int(found[-1], 16)

    def S(self, i): return self.read(self.surface + 4 * i)
    def W(self, i): return self.read(self.work + 4 * i)
    def words(self, first, count): return b"".join(struct.pack("<I", self.W(first + i)) for i in range(count))

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
        did_band = lambda shot: b.band(shot, 180, 330, 150, 168)
        for _ in range(8):   # a loaded host redraws late: look again before judging
            home_locked = b.screenshot("home-locked")
            if sum(1 for px in did_band(home_locked) if px != b"\xff\xff\xff") > 20: break
            time.sleep(3)
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
        attempts_on_disk = lambda: scratch.read_bytes()[4 * 512 + 12]
        assert attempts_on_disk() == 0 and b.W(100) == 0, "no failed attempt yet"
        b.type_text(WRONG); b.send("sendkey ret", 8.0)
        assert b.W(87) == 0 and b.W(94) == 8 and b.W(96) == 1 and b.S(2039) == 128 + 32768, (b.W(87), b.W(94), b.W(96), hex(b.S(2039)))
        assert b.W(100) == 1 and attempts_on_disk() == 1, ("the failed attempt must be counted in RAM and in the key record", b.W(100), attempts_on_disk())
        home_wrong = b.screenshot("home-wrong")
        assert key_row(home_wrong) != key_row(home_locked), "the key row must say the passphrase was wrong"
        assert b.words(928, 8) == bytes(32) and b.words(832, 8) == bytes(32), "a refused unlock must leave no seed and no passphrase"
        events.append(dict(name="unlock-wrong-passphrase", refused=True, stillLocked=True, seedBytes=b.words(928, 8).hex()))
        # the delay: keep guessing wrong until the guest refuses to try (no TSC frequency is assumed)
        assert (b.W(101), b.W(102)) == (0, 0), "no deadline before the 3rd failure"
        refused_at = None
        for n in range(2, 14):
            b.send("sendkey f8", 1.5); assert b.W(87) == 4 and b.W(98) == 1
            b.type_text(WRONG); b.send("sendkey ret", 8.0)
            if b.W(94) == 15: refused_at = n; break
            assert b.W(94) == 8 and b.W(100) == n and attempts_on_disk() == n, (n, b.W(94), b.W(100), attempts_on_disk())
        assert refused_at is not None and refused_at >= 4, ("the guest never refused", refused_at)
        assert b.W(87) == 0 and b.W(96) == 1 and (b.S(2039) >> 16) & 1 == 1, (b.W(87), b.W(96), hex(b.S(2039)))
        assert b.W(100) == refused_at - 1 and attempts_on_disk() == refused_at - 1, "a refused attempt must not be counted"
        assert b.words(928, 8) == bytes(32) and b.words(832, 8) == bytes(32), "a refused attempt must run no unlock and leave nothing"
        assert (b.W(101), b.W(102)) != (0, 0), "the deadline must be set"
        home_wait = b.screenshot("home-wait")
        assert key_row(home_wait) != key_row(home_wrong) and key_row(home_wait) != key_row(home_locked), "the key row must say to wait"
        events.append(dict(name="attempt-delay", refusedAtAttempt=refused_at, attemptsRecorded=refused_at - 1,
                           refusedAttemptNotCounted=True, deadlineSet=True, keyRowSaysWait=True))
        # a reboot does not skip the wait: the deadline is set from the boot when the record holds 3 or more attempts
        b.quit()
        b = Boot(args, out, "boot2c", scratch)
        assert b.W(96) == 1 and b.W(100) == refused_at - 1 and (b.W(101), b.W(102)) != (0, 0), (b.W(100), b.W(101), b.W(102))
        b.send("sendkey 2", 1.5); b.send("sendkey a", 1.5)
        events.append(dict(name="delay-after-reboot", attempts=refused_at - 1, deadlineSetFromBoot=True))
        # right passphrase: the boot-1 key is back (retried until the deadline has passed)
        for _ in range(80):
            b.send("sendkey f8", 1.5); assert b.W(87) == 4 and b.W(98) == 1
            b.type_text(PASS); b.send("sendkey ret", 8.0)
            if b.W(94) == 9: break
            assert b.W(94) == 15, ("only the delay may refuse the right passphrase", b.W(94))
            time.sleep(10)
        assert b.W(87) == 0 and b.W(94) == 9 and b.W(96) == 0, (b.W(87), b.W(94), b.W(96))
        seed2, pub2 = b.words(928, 8), b.words(320, 8)
        flags2 = b.S(2039)
        assert b.W(100) == 0 and attempts_on_disk() == 0, "a success must clear the attempt count in RAM and in the record"
        assert (flags2 >> 15) & 1 == 0 or (flags2 >> 7) & 0xffffff == int.from_bytes(pub1[:3], "big"), "wrong flag handling"
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
        # Forget (F10) is offered only while locked; it needs the passphrase, then erases sector 4
        b.send("sendkey f10", 1.5); assert b.W(87) == 0, "Forget must not be offered while the key is unlocked"
        b.send("sendkey f6", 4.0); assert b.W(94) == 11
        count = (b.S(2039) >> 2) & 15
        b.send("sendkey f10", 1.5)
        assert b.W(87) == 4 and b.W(98) == 2 and b.S(2039) == count * 4 + 128 + 3 + 2**31 + 16384, (b.W(87), b.W(98), hex(b.S(2039)))
        forget_panel = b.screenshot("forget-passphrase")
        assert title(forget_panel) != title(unlock_panel), "the forget panel must be titled differently from the unlock panel"
        assert b.band(forget_panel, px + 20, px + 460, py + 80, py + 104) != b.band(unlock_panel, px + 20, px + 460, py + 80, py + 104), "the action line must say erase"
        disk_before = scratch.read_bytes()
        b.type_text(WRONG); b.send("sendkey ret", 8.0)
        assert b.W(87) == 0 and b.W(94) == 13 and b.W(96) == 1 and b.S(2039) == count * 4 + 128 + 32768, (b.W(87), b.W(94), b.W(96), hex(b.S(2039)))
        after_wrong = scratch.read_bytes()
        changed = [i for i in range(len(after_wrong)) if after_wrong[i] != disk_before[i]]
        assert changed == [4 * 512 + 12] and after_wrong[4 * 512 + 12] == 1 and b.W(100) == 1, ("only the attempt count may change", changed)
        assert b.words(928, 8) == bytes(32), "a wrong passphrase must erase nothing and release nothing"
        disk_before = after_wrong
        events.append(dict(name="forget-wrong-passphrase", refused=True, onlyAttemptCountChanged=True, stillLocked=True))
        b.send("sendkey f10", 1.5); assert b.W(87) == 4 and b.W(98) == 2
        b.type_text(PASS); b.send("sendkey esc", 1.5)
        assert b.W(87) == 0 and b.W(94) == 6 and b.W(96) == 1 and scratch.read_bytes() == disk_before, "Esc must cancel without erasing or counting"
        # the attempt count survives a reboot (it is in the key record); the session's "wrong" flag does not
        b.quit()
        b = Boot(args, out, "boot2b", scratch)
        assert b.W(96) == 1 and b.W(100) == 1 and b.S(2039) == 128, (b.W(96), b.W(100), hex(b.S(2039)))
        assert (b.W(101), b.W(102)) == (0, 0), "under 3 attempts there is no deadline after a boot"
        count = 0   # the Approved count is per boot
        b.send("sendkey 2", 1.5); b.send("sendkey a", 1.5)
        events.append(dict(name="attempt-count-after-reboot", count=1, wrongFlagNotPersisted=True))
        b.send("sendkey f10", 1.5); assert b.W(87) == 4 and b.W(98) == 2
        b.type_text(PASS); b.send("sendkey ret", 8.0)
        assert b.W(87) == 0 and b.W(94) == 12 and b.W(96) == 0 and b.W(97) == 0, (b.W(87), b.W(94), b.W(96), b.W(97))
        assert b.S(2039) == count * 4, hex(b.S(2039))
        assert b.words(848, 16) == bytes(64) and b.words(928, 8) == bytes(32), "the blob and the seed must leave RAM"
        after = scratch.read_bytes()
        assert after[4 * 512:5 * 512] == bytes(512), "sector 4 must read back zero"
        assert after[:4 * 512] == disk_before[:4 * 512] and after[5 * 512:] == disk_before[5 * 512:], "only sector 4 may change"
        home_forgotten = b.screenshot("home-forgotten")
        assert key_row(home_forgotten) == key_row(home_none) and did_band(home_forgotten) == did_band(home_none), "the home must read as without a key"
        b.send("sendkey f7", 1.5); assert b.W(87) == 0, "nothing to sign after Forget"
        b.send("sendkey f8", 1.5); assert b.W(87) == 2, "F8 must offer to create a key, not to unlock"
        b.send("sendkey n", 1.5)
        events.append(dict(name="forget", erased=True, sectorZero=True, onlySector4Changed=True, homeWithoutKey=True))
    finally:
        b.quit()
    # ---- boot 4 (same disk): the forgotten key does not come back ----
    b = Boot(args, out, "boot4", scratch)
    try:
        assert b.W(96) == 0 and b.S(2039) == 0 and b.words(848, 16) == bytes(64), "a forgotten key must not be loaded at boot"
        b.send("sendkey 2", 1.5); b.send("sendkey a", 1.5)
        b.send("sendkey f8", 1.5); assert b.W(87) == 2
        b.send("sendkey n", 1.5)
        events.append(dict(name="forgotten-after-reboot", notLoaded=True, f8OffersCreate=True))
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
