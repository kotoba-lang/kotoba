#!/usr/bin/env python3
"""AWAI-120/121: actual USB HID ingress with PS/2 disabled, plus NVMe cold restore.

Python observes native guest decisions. QEMU inputs are synthetic and do not
prove human consent or a physical controller. Uses only private fixture media.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import time

if not __debug__:
    raise RuntimeError("this assertion gate must not run under Python -O")
HERE = Path(__file__).resolve().parent


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


keys = module("input_keys", "check-native-keystore-qemu.py")
nvme = module("input_nvme", "check-native-nvme-qemu.py")
# This integration gate tests state, not the existing large-file ESP hashing
# benchmark. A fixed-size fixture keeps the many cold boots bounded.
nvme.OWN_SIZE = 4096
pin = keys.pin


class StateBoot(keys.Boot):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except BaseException:
            if hasattr(self, "proc") and self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=10)
            raise

    def W(self, i):
        if 600 <= i <= 702:
            # storage_state.kotoba: profile 6's controller state is disjoint
            # from the Ed25519/signing scratch in browser-context2048..3071.
            if not hasattr(self, "storage"):
                rw = self.work - keys.native_regions.CONTEXT_OFFSET
                # KM-SEALED-SCRATCH in the pinned Amu kernel-v3 image ABI.
                scratch = struct.unpack("<Q", self.dump(rw + 272, 8))[0]
                self.storage = scratch + 9 * 4096 + 3584
            return self.read(self.storage + (i - 600) * 4)
        return super().W(i)


def main(args):
    for name in ("media", "efi", "kernel", "font", "qemu", "firmware"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    disk = out / "state-nvme.raw"
    expected_boot = nvme.fat32_disk(out, disk)
    # Copy writable firmware variables so OVMF never writes NvVars to the ESP.
    variables = out / "vars.fd"
    shutil.copyfile(args.firmware.with_name("edk2-i386-vars.fd"), variables)
    original = disk.read_bytes()
    observer = pin(Path(__file__))
    events = []
    active = None
    status = "FAILED"

    def boot(name, target=disk, usb=True):
        extra = ["-machine", "q35,accel=tcg,i8042=off", "-cpu", "max,phys-bits=37",
                 "-drive", f"if=pflash,format=raw,file={variables}",
                 "-drive", f"file={target},format=raw,if=none,id=nv0,cache=directsync",
                 "-device", "nvme,serial=AWAI120STATE,drive=nv0"]
        if usb == "second":
            extra += ["-device", "qemu-xhci,id=empty"]
        if usb == "hub":
            extra += ["-device", "qemu-xhci,id=usb", "-device", "usb-kbd,bus=usb.0,port=1",
                      "-device", "usb-hub,id=hub,bus=usb.0,port=2",
                      "-device", "usb-mouse,bus=usb.0,port=2.1"]
        elif usb:
            extra += ["-device", "qemu-xhci,id=usb", "-device", "usb-kbd,bus=usb.0,port=1",
                      "-device", "usb-mouse,bus=usb.0,port=2"]
        b = StateBoot(args, out, name, None, extra, first_frame_seconds=600)
        assert b.W(138) == (15 if usb else 1), ("xHCI result", b.W(138))
        assert b.W(139) == 16383, "native HID rejection/control vectors failed"
        return b

    try:
        active = boot("save")
        b = active
        assert b.W(700) == 0, "boot must not create a state file"
        assert pin(disk)["sha256"] == hashlib.sha256(original).hexdigest()
        b.send("sendkey 2", 1)
        b.type_text("aba")
        assert b.S(2) == 2 and b.S(2038) == 15 and b.W(73) == 4
        events.append(dict(name="usb-keyboard-no-ps2", goal="aba"))
        # Both keys are in one HID report. Enter opens a panel, Y must not
        # approve that new panel from the remainder of that report.
        b.send("sendkey ret-y", 2)
        assert b.W(87) == 1 and b.W(961) == 0, (b.W(87), b.W(961))
        b.send("sendkey n", 1)
        assert b.W(87) == 0 and b.W(961) == 0
        events.append(dict(name="same-report-consent-refused"))
        x, y = b.W(50), b.W(51)
        b.send("mouse_move 25 17", 1)
        assert (b.W(50), b.W(51)) == (x + 25, y + 17), (x, y, b.W(50), b.W(51))
        b.send("mouse_button 1", 1)
        assert b.W(67) == 1
        b.send("mouse_button 0", 1)
        assert b.W(67) == 0
        events.append(dict(name="usb-mouse-no-ps2", dx=25, dy=17))
        b.send("sendkey 2", 1)
        b.send("sendkey ret", 1)
        b.send("sendkey y", 2)
        assert b.W(961) == 1 and b.W(85) == 0
        token = b.W(962)
        b.send("sendkey 3", 1)
        b.send("sendkey ret", 2)
        assert b.W(963) == 1 and b.W(992) == 0
        cid = b.dump(b.work + 3856, 36)
        b.send("sendkey 2", 1)
        b.send("sendkey f5", 1)
        deadline = time.monotonic() + 120
        while b.W(82) == 0 and time.monotonic() < deadline:
            time.sleep(0.5)
        assert b.W(700) == 1 and b.W(80) == 1 and b.W(82) == 1, (b.W(700), b.W(80), b.W(82))
        state_at = b.W(701) + (b.W(702) << 32)
        # Creating a passphrase-sealed key exercises crypto after NVMe is
        # mounted, then writes through the same live controller queues.
        b.send("sendkey f8", 1)
        b.send("sendkey y", 1)
        b.type_text("correct horse")
        b.send("sendkey ret", 1)
        deadline = time.monotonic() + 120
        while b.W(94) == 0 and time.monotonic() < deadline:
            time.sleep(0.5)
        assert b.W(94) == 1 and b.W(97) == 1, (b.W(94), b.W(97))
        seed, blob = b.words(928, 8), b.words(848, 16)
        b.send("sendkey 4", 1)
        b.send("sendkey ret", 1)
        assert b.W(87) == 3
        b.send("sendkey y", 2)
        deadline = time.monotonic() + 120
        while b.W(973) != 1 and time.monotonic() < deadline:
            time.sleep(0.5)
        while b.W(87) != 0 and time.monotonic() < deadline:
            time.sleep(0.5)
        post, public, signature = b.words(936, 16), b.words(952, 8), b.words(976, 16)
        assert keys.ed_verify(public, post, signature)
        b.send("sendkey 2", 1)
        b.send("sendkey f5", 1)
        deadline = time.monotonic() + 120
        while b.W(80) != 2 and time.monotonic() < deadline:
            time.sleep(0.5)
        assert b.W(80) == 2 and b.W(82) == 2, (b.W(80), b.W(82), b.W(77), b.W(87), b.S(2))
        b.screenshot("saved")
        events.append(dict(name="nvme-state-created-and-saved", generation=2, offset=state_at,
                           sealedKey=True, signedOutbox=True))
        b.quit()
        active = None
        saved = disk.read_bytes()
        assert saved[state_at + 4 * 4096 + 16:state_at + 4 * 4096 + 80] == blob
        assert seed not in saved and b"correct horse" not in saved
        volume, files = nvme.fat32_files(saved)
        assert hashlib.sha256(files["BOOTX64 EFI"][0]).hexdigest() == expected_boot["sha256"]
        assert original[:volume["base"]] == saved[:volume["base"]]
        assert original[volume["end"]:] == saved[volume["end"]:]
        assert saved[state_at:state_at + 16] == struct.pack("<4I", 0x49415741, 0x54465244, 1, 128)
        assert saved[state_at + 2 * 4096:state_at + 2 * 4096 + 4] == b"WDT1"
        active = boot("cold-restore")
        b = active
        assert b.W(80) == 2 and b.W(81) == 2, (b.W(80), b.W(81))
        assert [b.S(236 + i) for i in range(3)] == list(b"aba")
        assert b.W(961) == 1 and b.W(962) == token and b.W(963) == 1
        assert b.dump(b.work + 3856, 36) == cid
        assert b.W(87) == 0 and b.W(88) == 0 and b.W(94) == 0, "approval/key authority must not restore"
        assert b.W(96) == 1 and b.W(97) == 1 and b.words(928, 8) == bytes(32)
        assert b.words(848, 16) == blob, "the sealed key must restore locked"
        assert b.W(973) == 1 and b.words(936, 16) == post and b.words(952, 8) == public
        assert b.words(976, 16) == signature and keys.ed_verify(public, post, signature)
        b.send("sendkey 2", 1)
        b.screenshot("restored")
        events.append(dict(name="cold-restore", goal="aba", runs=1, blocks=1, approval=0))
        b.type_text("c")
        assert b.S(2038) == 16
        b.proc.kill()
        b.proc.wait(timeout=10)
        active = None
        assert disk.read_bytes() == saved, "uncommitted editing changed NVMe"
        active = boot("crash-restore")
        assert active.W(80) == 2 and active.S(2038) == 15
        assert [active.S(236 + i) for i in range(3)] == list(b"aba")
        active.quit()
        active = None
        events.append(dict(name="uncommitted-crash-restores-last-commit"))
        damaged = bytearray(saved)
        damaged[state_at + 2 * 4096 + 32] ^= 1
        corrupt = out / "corrupt.raw"
        corrupt.write_bytes(damaged)
        active = boot("corrupt-refused", corrupt)
        assert active.W(81) >= 2**31 and active.W(80) == 0, (active.W(81), active.W(80))
        active.quit()
        active = None
        assert corrupt.read_bytes() == damaged
        events.append(dict(name="corrupt-published-slot-refused-disk-unchanged"))
        # A complete but unpublished next slot must never become current.
        unpublished = bytearray(saved)
        record = bytearray(saved[state_at + 2 * 4096:state_at + 2 * 4096 + 512])
        struct.pack_into("<I", record, 8, 3)
        record[480:] = hashlib.sha256(record[:480]).digest()
        unpublished[state_at + 3 * 4096:state_at + 3 * 4096 + 512] = record
        pending = out / "unpublished.raw"
        pending.write_bytes(unpublished)
        active = boot("unpublished-ignored", pending)
        assert active.W(80) == 2 and active.S(2038) == 15
        active.quit()
        active = None
        assert pending.read_bytes() == unpublished
        events.append(dict(name="unpublished-slot-ignored"))
        bad_gpt = bytearray(saved)
        bad_gpt[512 + 16] ^= 1
        # Invalidate both headers: OVMF otherwise repairs the primary from
        # the valid backup before our kernel sees the deliberately bad CRC.
        bad_gpt[len(bad_gpt) - 512 + 16] ^= 1
        invalid = out / "bad-gpt.raw"
        invalid.write_bytes(bad_gpt)
        active = boot("gpt-refused", invalid)
        assert active.W(700) == 0
        active.send("sendkey 2", 1)
        active.send("sendkey f5", 3)
        assert active.W(80) == 0 and active.W(82) >= 2**31
        active.quit()
        active = None
        assert invalid.read_bytes() == bad_gpt
        events.append(dict(name="bad-gpt-crc-refused-disk-unchanged"))
        # A completely absent xHCI controller must not look like USB input.
        active = boot("usb-absent", usb=False)
        assert active.W(73) == 0 and active.W(75) == 0
        active.quit()
        active = None
        events.append(dict(name="usb-absent-no-input"))
        # A first controller with no HID must halt before the shared DMA
        # pages are assigned to a second controller carrying both devices.
        active = boot("second-controller", usb="second")
        active.send("sendkey 2", 1)
        before = active.W(73)
        active.send("sendkey c", 1)
        assert active.S(2) == 2 and active.W(73) == before + 1
        x, y = active.W(50), active.W(51)
        active.send("mouse_move 7 5", 1)
        assert (active.W(50), active.W(51)) == (x + 7, y + 5)
        active.quit()
        active = None
        events.append(dict(name="empty-first-controller-halted-second-hid-active"))
        active = boot("hub-child", usb="hub")
        active.send("sendkey 2", 1)
        before = active.W(73)
        active.send("sendkey v", 1)
        assert active.S(2) == 2 and active.W(73) == before + 1
        x, y = active.W(50), active.W(51)
        active.send("mouse_move 9 6", 1)
        assert (active.W(50), active.W(51)) == (x + 9, y + 6)
        active.quit()
        active = None
        events.append(dict(name="root-keyboard-and-usb2-hub-child-mouse"))
        assert pin(Path(__file__)) == observer, "observer source changed during the run"
        status = "PASS_NATIVE_USB_HID_NVME_STATE_QEMU"
    except BaseException:
        if active is not None:
            (out / "failure-state.json").write_text(json.dumps({
                "context": {str(i): active.W(i) for i in (73, 77, 79, 80, 81, 82, 85, 86, 87, 94, 97, 700, 961, 973)},
                "focus": active.S(2)}, indent=2) + "\n")
            active.screenshot("failure")
            active.send("info registers", .2)
            (out / "failure-registers.txt").write_text(active.drain())
        raise
    finally:
        if active is not None:
            active.quit()
        (out / "native-input-state-qemu.json").write_text(json.dumps({
            "status": status, "events": events, "observer": observer,
            "kernel": pin(args.kernel), "efi": pin(args.efi), "media": pin(args.media),
            "font": pin(args.font),
            "helperSources": {name: pin(HERE / name) for name in (
                "check-native-keystore-qemu.py", "check-native-nvme-qemu.py",
                "check-native-consent-qemu.py", "native_regions.py")},
            "firmware": pin(args.firmware), "qemu": pin(args.qemu),
            "fixtureBootFile": expected_boot, "physicalHardware": False,
            "syntheticInputProvesHumanConsent": False, "D2WorkspaceCodec": False,
            "BluetoothQualified": False, "USBHubQualified": False,
        }, indent=2) + "\n")
    print(status, len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"):
        p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
