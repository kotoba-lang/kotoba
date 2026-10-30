#!/usr/bin/env python3
"""AWAI-122 stage 1: the debug entry's read-only NVMe driver finds a controller, identifies it and reads LBA 1.

Three boots of the desktop debug entry (native/desktop-debug-entry.kotoba, which probes NVMe once at boot), each
with QEMU `-nic none`:
  512    an NVMe disk with 512-byte blocks: result 15, namespace size and block size as attached, the model is
         QEMU's, and the 64 bytes the guest read from LBA 1 equal the disk's bytes 512..575;
  4096   the same with 4096-byte blocks: LBA 1 is bytes 4096..4159;
  absent no NVMe function: result 1, and the desktop still draws.
After every boot the disk image is byte-identical to before (the driver has no write command). Each boot also
checks that the desktop keeps drawing after the probe. The NVMe boots use a 37-bit guest physical address width:
with QEMU's default, OVMF places the 64-bit NVMe BAR at 768 GiB and the loader's PCI collector, which admits host
addresses below 512 GiB, refuses the boot (as it should). QEMU TCG: it qualifies no physical controller.
"""
import argparse, hashlib, importlib.util, json, os
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("keystore_gate", HERE / "check-native-keystore-qemu.py")
keystore = importlib.util.module_from_spec(spec); spec.loader.exec_module(keystore)
pin = keystore.pin
MODEL = "QEMU NVMe Ctrl"


def disk(path, block):
    # A recognisable LBA 1 for either block size: "EFI PART" then a counter pattern.
    raw = bytearray(os.urandom(1 << 20))
    for at in (512, 4096):
        raw[at:at + 64] = b"EFI PART" + bytes((at // 256 + i) & 255 for i in range(56))
    path.write_bytes(bytes(raw))
    return bytes(raw[block:block + 64])


def boot(args, out, name, block, events):
    path = out / f"{name}.img"
    extra = []
    expected = None
    if block:
        expected = disk(path, block)
        extra = ["-cpu", "max,phys-bits=37", "-drive", f"file={path},format=raw,if=none,id=nv0",
                 "-device", f"nvme,serial=AWAI122NVME{block},drive=nv0,logical_block_size={block},physical_block_size={block}"]
        before = hashlib.sha256(path.read_bytes()).hexdigest()
    b = keystore.Boot(args, out, name, None, extra)
    try:
        result = b.W(600)
        if not block:
            assert result == 1, ("no NVMe function must give result 1", result)
            row = dict(name=name, result=result)
        else:
            assert result == 15, ("NVMe probe failed at step", result, hex(b.W(617)))
            model = b.words(620, 10).decode("ascii", "replace").rstrip(" \0")
            blocks = b.W(607) + (b.W(608) << 32)
            assert model == MODEL, model
            assert b.W(609) == block.bit_length() - 1, (b.W(609), block)
            assert blocks == (1 << 20) // block, (blocks, block)
            assert b.W(606) >= 0x10000, hex(b.W(606))
            got = b.words(630, 16)
            assert got == expected, ("LBA 1 differs", got.hex(), expected.hex())
            row = dict(name=name, result=result, model=model, blocks=blocks, blockBytes=block,
                       version=hex(b.W(606)), lba1=got[:8].decode())
        frames = b.W(79)
        b.send("sendkey 1", 2.0)
        assert b.W(79) > frames, "the desktop must still draw after the probe"
        row["desktopKeptRunning"] = True
    finally:
        b.quit()
    if block:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before, "the NVMe disk changed"
        row["diskUnchanged"] = True
        path.unlink()
    events.append(row)


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    boot(args, out, "nvme-512", 512, events)
    boot(args, out, "nvme-4096", 4096, events)
    boot(args, out, "nvme-absent", 0, events)
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_NVME_READ_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)), events=events,
                  network="none (-nic none)", writeCommands=False, physicalHardware=False)
    (out / "native-nvme-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
