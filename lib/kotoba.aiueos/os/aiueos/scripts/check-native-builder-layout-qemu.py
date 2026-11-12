#!/usr/bin/env python3
"""JUN-942: a disk image made by the REAL release builder (make-release-image.py build --version N) is accepted by the guest's own update path.

Same machinery as check-native-provision-esp-qemu.py (desktop debug entry, the disk as an NVMe namespace, `-nic none`, fw_cfg opt/aiueos/update2
headers made by update2_oracle.py, AIUEIMG2 headers signed with the public TEST keys, install request "3" of the existing update2 hook) with ONE
difference: the disk is not the hdiutil fixture and is not provisioned by aiueos-provision-esp.py afterwards. It is what the builder wrote,
OSMETA.BIN included (the builder places it through aiueos-provision-esp.py's own code). The provisioning hook (install request "4") is never used,
and nothing here writes the journal except the builder.
  builder-esp            build N = 4; the independent layout check of check-builder-layout.py passes (reference journal, record-file rules);
                         the guest finds \\EFI\\ITONAMI\\BOOTX64.EFI (path 1, FAT32, 512-byte clusters) and hashes the loader the builder wrote.
  builder-cases-checked  every oracle case, no install request, no hook: every result equals the oracle's, the floor the guest loads is 4,
                         the disk is byte-identical afterwards.
  builder-equal          install a header whose version == N (4): result 9, nothing written, the floor stays 4.
  builder-above          install version 5 = N + 1: result 15, \\EFI\\ITONAMI\\BOOTX64.EFI is the admitted image, the floor advances to 5.
After every install boot \\EFI\\BOOT\\BOOTX64.EFI (the firmware's entry and universal fallback) is byte-identical to the loader the builder wrote.
Negative controls (the positive boots are not vacuous):
  neg-absent             the builder's image with OSMETA.BIN dropped: install refused 10, nothing written.
  neg-wrong-hash         the builder's image with one byte of the slot changed and its SHA-256 left alone: refused 10, nothing written.
  neg-floor-high         the builder run with --version 6: the version-6 header is refused 9 (N = 4 admits it).
  neg-floor-low          the builder run with --version 3: the version-4 header (== the right N) is installed 15 (the right N refuses it, 9).
The loader inside the disk is a synthetic MZ file (the guest only reads and hashes it); the booted kernel is the one passed as --kernel.
QEMU TCG only; test keys; the network pull (RTL8168) is not exercised; the FIRMWARE boot of the layout and real hardware are not exercised.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib.util


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


update2 = load("update2_gate", "check-native-update2-qemu.py")
layout = load("builder_layout_host", "check-builder-layout.py")
nvme, oracle, pin = update2.nvme, update2.oracle, update2.pin
N = oracle.FLOOR


def built(out, name, version, parts):
    """The real builder CLI; the independent layout check must pass before the guest ever sees the image."""
    disk, receipt = out / (name + ".img"), out / (name + ".json")
    r = layout.build(parts, disk, receipt, version)
    assert r.returncode == 0, r.stderr
    layout.check_layout(disk.read_bytes(), parts["efi"].read_bytes(), version)
    return disk


def boot_loader_bytes(raw):
    """EFI/BOOT/BOOTX64.EFI read with the independent walk."""
    (first, size, _), v = layout.entry_of(raw, "/EFI/BOOT/BOOTX64 EFI")
    return layout.file_bytes(raw, v, first, size)


def itonami_loader_bytes(raw):
    (first, size, _), v = layout.entry_of(raw, "/EFI/ITONAMI/BOOTX64 EFI")
    return layout.file_bytes(raw, v, first, size)


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"):
        setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    parts = layout.inputs(out / "in")
    loader = parts["efi"].read_bytes()
    blob, cases = oracle.fw_file()
    fw_all = out / "all.bin"
    fw_all.write_bytes(blob)
    img = oracle.image()
    by = {c["name"]: c for c in cases}
    assert by["floor-equal"]["code"] == 9 and by["floor-above"]["code"] == 15
    assert by["two-of-three-0-1"]["code"] == 15 and struct_version(by["two-of-three-0-1"]) == N + 1
    assert struct_version(by["floor-equal"]) == N and struct_version(by["floor-above"]) == N + 2
    kept = []

    def one(name, case):
        data, _ = oracle.fw_file([case])
        p = out / (name + ".bin")
        p.write_bytes(data)
        return p

    def install(name, disk, case, want_install, want_floor_seen, want_floor_after, installed):
        before = disk.read_bytes()
        original = itonami_loader_bytes(before)
        boot_before = boot_loader_bytes(before)
        assert boot_before == loader
        r = update2.boot(args, out, name, disk, "3", one(name, case), events)
        assert r["hook"] == 51, (name, r["hook"])
        assert r["install"] == want_install, (name, "install result", r["install"], "wanted", want_install)
        after = disk.read_bytes()
        v = nvme.fat32_volume(after)
        changed = [i for i in range(0, len(before), 512) if after[i:i + 512] != before[i:i + 512]]
        assert all(v["base"] <= i < v["end"] for i in changed), "a write outside the ESP"
        assert nvme.fat32_files(after)[1]["BOOTX64 EFI"][0] == (img if installed else original), (name, "BOOTX64.EFI")
        assert itonami_loader_bytes(after) == (img if installed else original), (name, "ITONAMI loader")
        assert boot_loader_bytes(after) == loader, (name, "EFI/BOOT/BOOTX64.EFI changed")
        kept.append(name)
        fl = r["floor"]
        if want_floor_seen is None:
            assert fl["loaded"] == 0 and fl["advance"] == 0, (name, fl)
        else:
            assert fl["loaded"] == 1 and fl["value"] == want_floor_seen, (name, fl)
        if want_floor_after is None:
            assert fl["advance"] == 0, (name, fl)
        else:
            assert fl["advance"] == 1 and fl["after"] == want_floor_after, (name, fl)
        if not installed:
            assert not changed, (name, "a refused header must write nothing", len(changed))
        events.append(dict(name=name, case=case, install=r["install"], floorSeen=fl["value"] if fl["loaded"] else None,
                           floorAfter=fl["after"] if fl["advance"] == 1 else None, changedSectors=len(changed)))
        return r

    # ---- positive: the builder's image, no provisioning hook, no other provisioning ----
    disk = built(out, "builder", N, parts)
    template = disk.read_bytes()
    meta = update2.osmeta(template)
    assert meta is not None and meta[1][:8] == b"OSUPMETA"
    facts = layout.check_layout(template, loader, N)
    r = update2.boot(args, out, "builder-cases", disk, None, fw_all, events)
    assert r["marker"] == update2.MARKER and r["count"] == len(cases), (hex(r["marker"]), r["count"])
    bad = [(c["name"], hex(r["results"][k]), c["code"], c["mask"]) for k, c in enumerate(cases)
           if r["results"][k] != c["code"] + 256 * c["mask"]]
    assert not bad, ("results differ from the oracle", bad)
    assert r["esp"] == dict(path=1, fat=32, size=len(loader), sha256=hashlib.sha256(loader).hexdigest()), r["esp"]
    assert r["floor"]["loaded"] == 1 and r["floor"]["value"] == N and r["floor"]["advance"] == 0, r["floor"]
    assert r["floor"]["provision"] == 0, "the provisioning hook must not have run"
    assert disk.read_bytes() == template, "a verify-only boot wrote the disk"
    events.append(dict(name="builder-esp", version=N, osmetaSha256=facts["osmetaSha256"], osmetaBytes=len(meta[1]),
                          clusterBytes=facts["clusterBytes"], diskOffset=facts["diskOffset"], loaderSha256=facts["loaderSha256"],
                          guestEsp=r["esp"]))
    events.append(dict(name="builder-cases-checked", cases=len(cases), floorSeen=N, diskUnchanged=True))
    install("builder-equal", disk, "floor-equal", 9, N, None, False)
    install("builder-above", disk, "two-of-three-0-1", 15, N, N + 1, True)

    # ---- negative controls ----
    p = out / "absent.img"
    p.write_bytes(layout.drop_osmeta(template))
    assert update2.osmeta(p.read_bytes()) is None
    install("neg-absent", p, "two-of-three-0-1", 10, None, None, False)
    p = out / "wronghash.img"
    at = update2.osmeta(template)[0]
    raw = bytearray(template)
    raw[at + 3 * 4096 + 100] ^= 1                    # published slot payload; its SHA-256 and the head's copy stay
    p.write_bytes(bytes(raw))
    install("neg-wrong-hash", p, "two-of-three-0-1", 10, None, None, False)
    p = built(out, "floorhigh", N + 2, parts)
    install("neg-floor-high", p, "floor-above", 9, N + 2, None, False)
    assert by["floor-above"]["code"] == 15, "with the right floor this header is admitted"
    p = built(out, "floorlow", N - 1, parts)
    install("neg-floor-low", p, "floor-equal", 15, N - 1, N, True)
    assert by["floor-equal"]["code"] == 9, "with the right floor this header is refused"
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_BUILDER_LAYOUT_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)), hostGate=pin(HERE / "check-builder-layout.py"),
                  builder=pin(HERE / "make-release-image.py"), provisioner=pin(HERE / "aiueos-provision-esp.py"),
                  oracle=pin(HERE / "update2_oracle.py"), events=events, network="none (-nic none)", testKeysOnly=True,
                  provisioningHookUsed=False, productionSignerSet=False, physicalHardware=False, firmwareBootOfLayout=False,
                  eachInstallKeptEfiBoot=len(kept) == 6, syntheticLoaderInDisk=True)
    (out / "native-builder-layout-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


def struct_version(case):
    return struct.unpack_from("<Q", case["hdr"], 8)[0]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"):
        p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
