#!/usr/bin/env python3
"""JUN-813 stage 5b (ADR-0286 amendment 2): native/update.kotoba admits an AIUEIMG2 image through its real update path.

Four boots of the desktop debug entry (the one that probes NVMe/ESP and runs update.kotoba's self-tests), each on a fresh FAT32
fixture ESP attached as an NVMe disk with QEMU `-nic none`, with the fw_cfg file opt/aiueos/update2 made by update2_oracle.py (a
hypervisor-only hook; a physical board has no fw_cfg). Every header is 16384 bytes and reaches the verifier through the same chunk
path as the network pull: the first 128 bytes, then 1 KiB pieces, each entry's Ed25519 and ML-DSA-65 signatures verified as the
entry's last byte lands, then (only for an admitted header) the 5000-byte image hashed against the manifest.
  update2-cases       30 cases, no install request: three signers, two of three (0+1, 2+0), one signer, an ML-DSA half bad, an Ed25519 half
                      bad, a tampered image byte (digest), a tampered manifest, a duplicate id, an unknown id, the same valid header
                      under the production signer set (no keys pinned: refused), bad magic, count 0, nonzero reserved, version 0, an
                      oversize image; review hardening: nonzero entry reserved/padding bytes (first and last), nonzero layout bytes 68
                      and 127, count 5, count 4 (a duplicate fourth entry, and a fourth entry that is the second counted signer), key ids
                      256, 65536 and 2^24, a signature made under context AIUEIMG1; last, a case whose header stream breaks (mode 2)
                      after entries 0 and 1 were verified: result 21 with mask 3. Case k is the low (even k) or high (odd k) 16 bits
                      of word 236 + k / 2 and must equal the oracle's result | counted-mask << 8. Afterwards the
                      ESP walk (word 233) must still read the fixture's own BOOTX64.EFI (with the broken-stream case last, this also shows that a
                      failed header stream restores the NVMe/ESP driver state, finding B): the ML-DSA arena shares owned window 4
                      with the NVMe queues and the walk's data page, and update.kotoba re-probes the driver after it.
  update2-install     install request "3" with a 2-of-3 image: the staging file and BOOTX64.EFI hold the 5000-byte image; only ESP sectors
                      change.
  update2-tampered    install with one image byte changed: result 7 (digest), BOOTX64.EFI is as it was.
  update2-one-signer  install with a header one signer short: result 1, nothing is written to the disk.
The AIUEIMG1 self-test (words 188/189) must still read 7 / [15, 1, 7] in every boot. QEMU TCG only; the keys are public TEST keys; the
network pull itself (RTL8168) is not exercised. hdiutil makes the FAT32 fixture, so this gate is macOS only.
"""
import argparse, hashlib, importlib.util, json, shutil
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nvme_gate", HERE / "check-native-nvme-qemu.py")
nvme = importlib.util.module_from_spec(spec); spec.loader.exec_module(nvme)
keystore = nvme.keystore
import update2_oracle as oracle
MARKER = int.from_bytes(b"UP02", "big")
pin = keystore.pin


def boot(args, out, name, disk, request, fwfile, events):
    vars_copy = out / f"{name}-vars.fd"
    shutil.copyfile(args.firmware.parent / "edk2-i386-vars.fd", vars_copy)
    extra = ["-drive", f"if=pflash,format=raw,file={vars_copy}", "-cpu", "max,phys-bits=37",
             "-drive", f"file={disk},format=raw,if=none,id=nv0", "-device", "nvme,serial=AWAI122NVME512,drive=nv0",
             "-fw_cfg", f"name=opt/aiueos/update2,file={fwfile}"]
    if request: extra += ["-fw_cfg", f"name=opt/aiueos/install,string={request}"]
    b = keystore.Boot(args, out, name, None, extra, first_frame_seconds=6000)
    try:
        r = dict(hook=b.W(211), install=b.W(208), stream=b.W(180), marker=b.W(234), count=b.W(235), walk=b.W(233),
                 nvme=b.W(600), v1=[b.W(188), b.W(189) & 255, (b.W(189) >> 8) & 255, (b.W(189) >> 16) & 255])
        r["results"] = b.words(236, 20)
        # two cases per word: case k is the low (even k) or high (odd k) 16 bits of word 236 + k / 2
        halves = [int.from_bytes(r["results"][i:i + 4], "little") for i in range(0, 80, 4)]
        r["results"] = [(halves[k // 2] >> (16 * (k & 1))) & 0xffff for k in range(40)]
        digest = b.words(680, 8)
        r["esp"] = dict(path=b.W(677), fat=b.W(662), size=b.W(675),
                        sha256=b"".join(digest[i:i + 4][::-1] for i in range(0, 32, 4)).hex())
        frames = b.W(79)
        b.send("sendkey 1", 2.0)
        assert b.W(79) > frames, "the desktop must still draw after the update path ran"
    finally:
        b.quit()
    vars_copy.unlink()
    assert r["v1"] == [7, 15, 1, 7], ("the AIUEIMG1 self-test changed", r["v1"])
    return r


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    blob, cases = oracle.fw_file()
    fw_all = out / "update2-all.bin"; fw_all.write_bytes(blob)
    disk = out / "cases.img"
    want = nvme.fat32_disk(out, disk)
    before = disk.read_bytes()
    r = boot(args, out, "update2-cases", disk, None, fw_all, events)
    assert r["marker"] == MARKER and r["count"] == len(cases), ("the cases did not finish", hex(r["marker"]), r["count"])
    matches = []
    bad = []
    for k, c in enumerate(cases):
        if r["results"][k] == c["code"] + 256 * c["mask"]: matches.append(c["name"])
        else: bad.append((c["name"], hex(r["results"][k]), c["code"], c["mask"]))
    assert not bad, ("update2 cases differ from the oracle (name, got result|mask<<8, want result, want mask)", bad)
    assert r["walk"] == 15 and r["nvme"] == 15, ("the storage walk after the ML-DSA arena failed", r["walk"], r["nvme"])
    assert r["esp"] == dict(path=want["path"], fat=want["fat"], size=want["size"], sha256=want["sha256"]), (r["esp"], want)
    assert disk.read_bytes() == before, "a verify-only boot must not write the disk"
    events.append(dict(name="update2-cases", marker=hex(r["marker"]), matches=matches, espWalkAfter=r["walk"], diskUnchanged=True))
    disk.unlink()

    img = oracle.image()
    for name, case, want_install, want_stream, expect_boot in (
            ("update2-install", "two-of-three-0-1", 15, 15, img),
            ("update2-tampered", "tampered-image", 7, 7, None),
            ("update2-one-signer", "one-signer", 1, 1, None)):
        one, sel = oracle.fw_file([case])
        fw = out / f"{name}.bin"; fw.write_bytes(one)
        own = nvme.fat32_disk(out, disk)
        original = nvme.fat32_files(disk.read_bytes())[1]["BOOTX64 EFI"][0]
        before = disk.read_bytes()
        r = boot(args, out, name, disk, "3", fw, events)
        assert r["hook"] == 51 and r["install"] == want_install and r["stream"] == want_stream, (name, r["hook"], r["install"], r["stream"])
        after = disk.read_bytes()
        v, files = nvme.fat32_files(after)
        changed = [i for i in range(0, len(before), 512) if after[i:i + 512] != before[i:i + 512]]
        assert all(v["base"] <= i < v["end"] for i in changed), ("a write outside the ESP", changed[:4])
        if expect_boot is not None:
            assert files["BOOTX64 EFI"][0] == expect_boot, "BOOTX64.EFI is not the admitted image"
        else:
            assert files["BOOTX64 EFI"][0] == original, "a refused image must not replace BOOTX64.EFI"
        if name == "update2-one-signer":
            assert not changed, ("a refused header must write nothing", len(changed))
        events.append(dict(name=name, case=case, hook=r["hook"], install=r["install"], stream=r["stream"],
                           changedSectors=len(changed), bootSize=len(files["BOOTX64 EFI"][0])))
        disk.unlink()
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_UPDATE2_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)),
                  oracle=pin(HERE / "update2_oracle.py"), reference=pin(oracle.o.REF / "reference.py"), events=events,
                  network="none (-nic none)", testKeysOnly=True, productionSignerSet=False, physicalHardware=False)
    (out / "native-update2-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
