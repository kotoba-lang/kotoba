#!/usr/bin/env python3
"""AWAI-122 stages 1-2: the debug entry's read-only NVMe driver identifies a controller and reads LBA 1, then
finds the ESP, walks FAT16/FAT32 to the installed loader and takes its SHA-256.

Four boots of the desktop debug entry (native/desktop-debug-entry.kotoba, which probes NVMe and the ESP once at
boot), each with QEMU `-nic none`:
  fat32  a 40 MiB GPT disk with 512-byte blocks whose one partition is a FAT32 ESP (made with hdiutil, then
         retyped to the ESP GUID with fresh GPT CRCs) holding \\EFI\\itonami\\BOOTX64.EFI (300,001 random bytes)
         and a different \\EFI\\BOOT\\BOOTX64.EFI: NVMe result 15, model/size/LBA 1 as attached, ESP result 15,
         path ITONAMI, FAT32, and the size and SHA-256 of the itonami file;
  fat16  this build's own GPT/FAT16 media attached as the NVMe disk: path BOOT, FAT16, and the size and SHA-256
         of this build's BOOTX64.EFI;
  4096   1 MiB with 4096-byte blocks, a GPT header with no partition entries: LBA 1 is bytes 4096..4159 and the
         ESP result is 3 (no ESP);
  absent no NVMe function: NVMe result 1, ESP result 1.
After every boot the disk image is byte-identical to before (the driver has no write command), and the desktop
keeps drawing after the probe. The NVMe boots use a 37-bit guest physical address width: with QEMU's default,
OVMF places the 64-bit NVMe BAR at 768 GiB and the loader's PCI collector, which admits host addresses below
512 GiB, refuses the boot (as it should). They also get a writable copy of OVMF's variable store, since without
one OVMF writes \\NvVars to the first FAT volume, the fixture ESP. hdiutil makes the FAT32 fixture, so the gate is macOS only (as is the
build that calls it). QEMU TCG: it qualifies no physical controller or firmware-written ESP.
"""
import argparse, hashlib, importlib.util, json, os, shutil, struct, subprocess, zlib
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("keystore_gate", HERE / "check-native-keystore-qemu.py")
keystore = importlib.util.module_from_spec(spec); spec.loader.exec_module(keystore)
pin = keystore.pin
MODEL = "QEMU NVMe Ctrl"
ESP_GUID = bytes.fromhex("28732AC11FF8D211BA4B00A0C93EC93B")
OWN_SIZE = 300001


def retype_esp(raw):
    # Primary and backup GPT: partition 0 becomes an ESP; entry-array and header CRC32s are recomputed.
    for header_at in (512, len(raw) - 512):
        lba, count, size = struct.unpack_from("<QII", raw, header_at + 72)
        table = lba * 512
        raw[table:table + 16] = ESP_GUID
        struct.pack_into("<I", raw, header_at + 88, zlib.crc32(bytes(raw[table:table + count * size])))
        header_size = struct.unpack_from("<I", raw, header_at + 12)[0]
        struct.pack_into("<I", raw, header_at + 16, 0)
        struct.pack_into("<I", raw, header_at + 16, zlib.crc32(bytes(raw[header_at:header_at + header_size])))


def fat32_disk(out, path):
    src = out / "fat32-src"
    (src / "EFI" / "itonami").mkdir(parents=True)
    (src / "EFI" / "BOOT").mkdir(parents=True)
    own = os.urandom(OWN_SIZE)
    (src / "EFI" / "itonami" / "BOOTX64.EFI").write_bytes(own)
    (src / "EFI" / "BOOT" / "BOOTX64.EFI").write_bytes(os.urandom(5000))
    stem = out / "fat32"
    subprocess.run(["hdiutil", "create", "-quiet", "-srcfolder", str(src), "-fs", "MS-DOS FAT32",
                    "-layout", "GPTSPUD", "-format", "UDTO", "-size", "40m", "-volname", "ESP", str(stem)],
                   check=True, env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})
    shutil.rmtree(src)
    raw = bytearray((out / "fat32.cdr").read_bytes())
    (out / "fat32.cdr").unlink()
    first = struct.unpack_from("<Q", raw, struct.unpack_from("<Q", raw, 512 + 72)[0] * 512 + 32)[0] * 512
    assert raw[first + 82:first + 90] == b"FAT32   ", raw[first + 82:first + 90]
    retype_esp(raw)
    path.write_bytes(bytes(raw))
    return dict(path=1, fat=32, size=OWN_SIZE, sha256=hashlib.sha256(own).hexdigest())


def header_only_disk(path):
    # 4096-byte blocks: "EFI PART" at LBA 1 and nothing after it, so the GPT names no partition.
    raw = bytearray(os.urandom(1 << 20))
    raw[4096:8192] = b"EFI PART" + bytes(4088)
    path.write_bytes(bytes(raw))


def boot(args, out, name, kind, events):
    path = out / f"{name}.img"
    extra, block, want = [], 0, None
    if kind == "fat32":
        block, want = 512, fat32_disk(out, path)
    elif kind == "fat16":
        block = 512
        shutil.copyfile(args.media, path)
        efi = args.efi.read_bytes()
        want = dict(path=2, fat=16, size=len(efi), sha256=hashlib.sha256(efi).hexdigest())
    elif kind == "4096":
        block = 4096
        header_only_disk(path)
    if block:
        # A writable copy of OVMF's variable store: without one OVMF saves its variables as \NvVars on the
        # first FAT volume it finds, which here is the fixture ESP (observed: a 10,427-byte NVVARS file).
        vars_copy = out / f"{name}-vars.fd"
        shutil.copyfile(args.firmware.parent / "edk2-i386-vars.fd", vars_copy)
        extra = ["-drive", f"if=pflash,format=raw,file={vars_copy}",
                 "-cpu", "max,phys-bits=37", "-drive", f"file={path},format=raw,if=none,id=nv0",
                 "-device", f"nvme,serial=AWAI122NVME{block},drive=nv0,logical_block_size={block},physical_block_size={block}"]
        image = path.read_bytes()
        before = hashlib.sha256(image).hexdigest()
    # The probe, including the SHA-256 of a 6 MB loader under TCG, runs before the first frame.
    b = keystore.Boot(args, out, name, None, extra, first_frame_seconds=600)
    try:
        result, esp = b.W(600), b.W(676)
        if not block:
            assert result == 1 and esp == 1, ("no NVMe function must give results 1/1", result, esp)
            row = dict(name=name, result=result, esp=esp)
        else:
            assert result == 15, ("NVMe probe failed at step", result, hex(b.W(617)))
            model = b.words(620, 10).decode("ascii", "replace").rstrip(" \0")
            blocks = b.W(607) + (b.W(608) << 32)
            assert model == MODEL, model
            assert b.W(609) == block.bit_length() - 1, (b.W(609), block)
            assert blocks == len(image) // block, (blocks, block)
            assert b.W(606) >= 0x10000, hex(b.W(606))
            got = b.words(630, 16)
            assert got == image[block:block + 64], ("LBA 1 differs", got.hex())
            row = dict(name=name, result=result, model=model, blocks=blocks, blockBytes=block,
                       version=hex(b.W(606)), lba1=got[:8].decode(), esp=esp)
            if want is None:
                assert esp == 3, ("a GPT with no entries must give ESP result 3", esp)
            else:
                digest = b.words(680, 8)
                digest = b"".join(digest[i:i + 4][::-1] for i in range(0, 32, 4)).hex()
                seen = dict(path=b.W(677), fat=b.W(662), size=b.W(675), sha256=digest)
                assert esp == 15, ("ESP read failed", esp, seen, b.W(652))
                assert seen == want, (seen, want)
                row.update(path="ITONAMI" if seen["path"] == 1 else "BOOT", fat=seen["fat"],
                           size=seen["size"], sha256=digest)
        frames = b.W(79)
        b.send("sendkey 1", 2.0)
        assert b.W(79) > frames, "the desktop must still draw after the probe"
        row["desktopKeptRunning"] = True
    finally:
        b.quit()
    if block:
        after = path.read_bytes()
        changed = [i for i in range(0, len(image), 512) if after[i:i + 512] != image[i:i + 512]]
        assert not changed, ("the NVMe disk changed", len(changed), "sectors, first", changed[:8])
        row["diskUnchanged"] = True
        path.unlink()
        vars_copy.unlink()
    events.append(row)


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    boot(args, out, "nvme-fat32", "fat32", events)
    boot(args, out, "nvme-fat16-media", "fat16", events)
    boot(args, out, "nvme-4096", "4096", events)
    boot(args, out, "nvme-absent", "absent", events)
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
