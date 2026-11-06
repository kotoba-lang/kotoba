#!/usr/bin/env python3
"""JUN-813 stage 6 (ADR-0286 amendment 5): native/update.kotoba admits an AIUECAT1 signed catalog through its real update path.

One boot of the desktop debug entry (the one that probes NVMe/ESP and runs update.kotoba's self-tests) on a fresh FAT32 fixture ESP
attached as an NVMe disk with QEMU `-nic none`, with the fw_cfg file opt/aiueos/cat1 made by cat_oracle.py (a hypervisor-only hook; a
physical board has no fw_cfg). Every case is a 16384-byte signature-block header and a catalog body slot of 8192 bytes. The header
reaches the verifier through the same chunk path as the AIUEIMG2 headers (aiueos.imgsig, the Ed25519 and ML-DSA-65 verifiers, context
"AIUECAT1"); the body is then streamed through the image path (chunk-done: SHA-256 against the manifest) and each 128-byte entry is
checked as it lands. Case k is the word 300 + k of the guest context and must equal the oracle's result | counted-mask << 8 | flags << 16.
The oracle's verdicts are derived independently (RFC 8032 integer Ed25519, the ACVP-checked ML-DSA-65 reference, hashlib, its own parser
of the layout). Cases: 2-of-3 and 3 signers, a full 64-entry catalog, one signer, a duplicated signer, signatures made under the AIUEIMG2
context, an image-magic header, production mode (no signer set), manifest and header structure, entry count 0 and 65, version 0, body hash
tampering, and the entry rules (duplicate dock id, dock ids 18 / 0 / 83 / 2^32-1, non-ASCII / unterminated / empty / control / junk titles,
nonzero reserved bytes, a CID that is a string / has a bad codec, hash code or version, bundle sizes 0 and 2^25+1, several defects at once).
Afterwards the ESP walk must still read the fixture's own BOOTX64.EFI (the ML-DSA arena shares owned window 4 with the NVMe queues, and
update.kotoba re-probes the driver), the disk must be byte-identical (a verify-only boot writes nothing), the AIUEIMG1 self-test must still
read 7 / [15, 1, 7], and the desktop must still draw. QEMU TCG only; the keys are public TEST keys; hdiutil makes the FAT32 fixture,
so this gate is macOS only.
"""
import argparse, hashlib, importlib.util, json, shutil
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nvme_gate", HERE / "check-native-nvme-qemu.py")
nvme = importlib.util.module_from_spec(spec); spec.loader.exec_module(nvme)
keystore = nvme.keystore
import cat_oracle as oracle
MARKER = int.from_bytes(b"CAT1", "big")
RESULT_WORD = 300
pin = keystore.pin


def boot(args, out, name, disk, fwfile):
    vars_copy = out / f"{name}-vars.fd"
    shutil.copyfile(args.firmware.parent / "edk2-i386-vars.fd", vars_copy)
    extra = ["-drive", f"if=pflash,format=raw,file={vars_copy}", "-cpu", "max,phys-bits=37",
             "-drive", f"file={disk},format=raw,if=none,id=nv0", "-device", "nvme,serial=AWAI122NVME512,drive=nv0",
             "-fw_cfg", f"name=opt/aiueos/cat1,file={fwfile}"]
    b = keystore.Boot(args, out, name, None, extra, first_frame_seconds=6000)
    try:
        r = dict(hook=b.W(211), install=b.W(208), stream=b.W(180), marker=b.W(234), count=b.W(235), walk=b.W(233),
                 nvme=b.W(600), v1=[b.W(188), b.W(189) & 255, (b.W(189) >> 8) & 255, (b.W(189) >> 16) & 255])
        raw = b.words(RESULT_WORD, 64)
        r["results"] = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, 256, 4)]
        digest = b.words(680, 8)
        r["esp"] = dict(path=b.W(677), fat=b.W(662), size=b.W(675),
                        sha256=b"".join(digest[i:i + 4][::-1] for i in range(0, 32, 4)).hex())
        frames = b.W(79)
        b.send("sendkey 1", 2.0)
        r["drew"] = b.W(79) > frames
    finally:
        b.quit()
    vars_copy.unlink()
    return r


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    blob, cases = oracle.fw_file()
    fw_all = out / "cat1-all.bin"; fw_all.write_bytes(blob)
    disk = out / "cases.img"
    want = nvme.fat32_disk(out, disk)
    before = disk.read_bytes()
    r = boot(args, out, "catalog-cases", disk, fw_all)
    assert r["marker"] == MARKER and r["count"] == len(cases), ("the cases did not finish", hex(r["marker"]), r["count"])
    matches, bad = [], []
    for k, c in enumerate(cases):
        wanted = c["code"] + 256 * c["mask"] + 65536 * c["flags"]
        if r["results"][k] == wanted: matches.append(c["name"])
        else: bad.append((c["name"], hex(r["results"][k]), hex(wanted)))
    assert not bad, ("catalog cases differ from the oracle (name, got result|mask<<8|flags<<16, want)", bad)
    assert r["v1"] == [7, 15, 1, 7], ("the AIUEIMG1 self-test changed", r["v1"])
    assert r["walk"] == 15 and r["nvme"] == 15, ("the storage walk after the ML-DSA arena failed", r["walk"], r["nvme"])
    assert r["esp"] == dict(path=want["path"], fat=want["fat"], size=want["size"], sha256=want["sha256"]), (r["esp"], want)
    assert disk.read_bytes() == before, "a verify-only boot must not write the disk"
    assert r["drew"], "the desktop must still draw after the catalog path ran"
    admitted = [c["name"] for c in cases if c["code"] == 15]
    refused = {c["name"]: [c["code"], c["mask"], c["flags"]] for c in cases if c["code"] != 15}
    events = [dict(name="catalog-cases", marker=hex(r["marker"]), cases=len(cases), matches=matches, admitted=admitted, refused=refused),
              dict(name="catalog-storage-restored", espWalkAfter=r["walk"], nvmeProbe=r["nvme"], diskUnchanged=True, espBootSha256=r["esp"]["sha256"]),
              dict(name="catalog-regression", imageSelfTest=r["v1"], desktopStillDraws=True)]
    disk.unlink()
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_CATALOG_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)),
                  oracle=pin(HERE / "cat_oracle.py"), signingOracle=pin(HERE / "imgsig_oracle.py"), reference=pin(oracle.o.REF / "reference.py"),
                  events=events, network="none (-nic none)", testKeysOnly=True, productionSignerSet=False, notWiredToDesktop=True,
                  physicalHardware=False)
    (out / "native-catalog-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(cases), "cases", len(admitted), "admitted")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
