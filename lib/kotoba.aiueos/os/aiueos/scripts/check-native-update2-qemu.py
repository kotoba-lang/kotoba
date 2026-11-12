#!/usr/bin/env python3
"""JUN-813 stage 5b (ADR-0286 amendment 2): native/update.kotoba admits an AIUEIMG2 image through its real update path.

Four boots of the desktop debug entry (the one that probes NVMe/ESP and runs update.kotoba's self-tests), each on a fresh FAT32
fixture ESP attached as an NVMe disk with QEMU `-nic none`, with the fw_cfg file opt/aiueos/update2 made by update2_oracle.py (a
hypervisor-only hook; a physical board has no fw_cfg). Every header is 16384 bytes and reaches the verifier through the same chunk
path as the network pull: the first 128 bytes, then 1 KiB pieces, each entry's Ed25519 and ML-DSA-65 signatures verified as the
entry's last byte lands, then (only for an admitted header) the 5000-byte image hashed against the manifest.
  update2-cases       30 cases, no install request: three signers, two of three (0+1, 2+0), one signer, an ML-DSA half bad, an Ed25519 half
                      bad, a tampered image byte (digest), a tampered manifest, a duplicate id, an unknown id, the same valid header
                      under the production signer set (JUN-813 amendment 7: signed by TEST keys, so no slot counts: result 1), bad magic, count 0, nonzero reserved, version 0, an
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
JUN-813 stage 5c (ADR-0286 amendment 4): the guest also keeps a hash-checked per-channel version floor in its update journal (OSMETA.BIN).
The fixture ESP has none, so a provisioning boot (hook request "4", QEMU only) first makes it with floor 4; that disk is the template of every
later boot, and the independent oracle (update2_oracle.py, FLOOR = 4) says which header is above it. Boots, in order:
  update2-provision   request "4": OSMETA.BIN is created (floor 4) and initialised by the journal's own code.
  update2-cases       the oracle's cases, now with the boundary (version above / equal / below the floor) for AIUEIMG2 and AIUEIMG1. Nothing is
                      written, journal included.
  update2-install     install 2-of-3 version 5: installed, the floor advances 4 -> 5 (read back from the guest and from the disk).
  update2-replay      the same install again: result 9, nothing is written.
  update2-newer       version 6: installed, the floor advances 5 -> 6 (an unconfirmed earlier prepare is abandoned first).
  update2-crash-before-advance / -repeat / -refused   request "5" installs but stops before the advance (the hook's stand-in for a
                      crash between the committed install and the journal write): the image is installed and the floor is still 4; the
                      same version is admitted once more (floor -> 5) and then refused. This is a simulated interruption: the guest is not
                      killed between the two writes (that timing is not exercised); the journal's own crash ordering is the existing gate's.
  update2-journal-corrupt  one byte of the published OSMETA.BIN slot flipped: result 10, nothing written (fail closed, not floor 0).
  update2-journal-absent   no OSMETA.BIN at all: result 10, nothing written.
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
        r["floor"] = dict(loaded=b.W(258), value=b.W(256) + (b.W(257) << 32), advance=b.W(259),
                          after=b.W(260) + (b.W(261) << 32), provision=b.W(262))
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


def osmeta(raw):
    """(offset, bytes) of OSMETA.BIN in a FAT32 fixture, or None."""
    v = nvme.fat32_volume(raw)
    efi = nvme.fat32_dir(raw, v, v["root"])["EFI        "][0]
    own = nvme.fat32_dir(raw, v, efi)["ITONAMI    "][0]
    e = nvme.fat32_dir(raw, v, own).get("OSMETA  BIN")
    if e is None: return None
    at = v["data"] + (e[0] - 2) * v["cluster"]
    return at, raw[at:at + 20480]


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    blob, cases = oracle.fw_file()
    fw_all = out / "update2-all.bin"; fw_all.write_bytes(blob)
    img = oracle.image()
    floor0 = oracle.FLOOR

    # --- provisioning boot: the fixture ESP has no OSMETA.BIN; the guest's own journal code makes it (floor 4) ---
    template = out / "template.img"
    want = nvme.fat32_disk(out, template)
    assert osmeta(template.read_bytes()) is None, "the plain fixture must have no OSMETA.BIN"
    one0, _ = oracle.fw_file(["two-of-three-0-1"])
    fw_one = out / "one.bin"; fw_one.write_bytes(one0)
    r = boot(args, out, "update2-provision", template, "4", fw_one, events)
    assert r["hook"] == 52 and r["floor"]["provision"] == 1, ("provisioning failed", r["hook"], r["floor"])
    prov = osmeta(template.read_bytes())
    assert prov is not None and prov[1][:8] == b"OSUPMETA", "OSMETA.BIN was not created"
    events.append(dict(name="update2-provision", hook=r["hook"], osmetaBytes=len(prov[1]), install=0))
    tmpl_bytes = template.read_bytes()

    disk = out / "disk.img"

    def fresh(): disk.write_bytes(tmpl_bytes); return tmpl_bytes

    # --- verify-only: every oracle case, including the floor boundary ---
    before = fresh()
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
    assert r["floor"]["loaded"] == 1 and r["floor"]["value"] == floor0 and r["floor"]["advance"] == 0, r["floor"]
    assert disk.read_bytes() == before, "a verify-only boot must not write the disk (the journal included)"
    events.append(dict(name="update2-cases", marker=hex(r["marker"]), matches=matches, espWalkAfter=r["walk"], diskUnchanged=True,
                       floorSeen=r["floor"]["value"]))

    def install(name, case, request, want_install, want_boot, want_floor_seen, want_floor_after, journal_changes):
        """One install boot on the current disk. want_floor_after None: not advanced. want_boot: BOOTX64.EFI content or None (unchanged)."""
        one, _ = oracle.fw_file([case])
        fw = out / f"{name}.bin"; fw.write_bytes(one)
        before = disk.read_bytes()
        original = nvme.fat32_files(before)[1]["BOOTX64 EFI"][0]
        meta_before = (osmeta(before) or (0, b""))[1]
        r = boot(args, out, name, disk, request, fw, events)
        assert r["hook"] == (51 if request == "3" else int(request) + 48), (name, r["hook"])
        assert r["install"] == want_install and r["stream"] == (want_install if want_install in (9, 10, 7, 1) else 15), \
            (name, r["install"], r["stream"])
        after = disk.read_bytes()
        v, files = nvme.fat32_files(after)
        changed = [i for i in range(0, len(before), 512) if after[i:i + 512] != before[i:i + 512]]
        assert all(v["base"] <= i < v["end"] for i in changed), ("a write outside the ESP", changed[:4])
        if want_boot is not None: assert files["BOOTX64 EFI"][0] == want_boot, (name, "BOOTX64.EFI is not the admitted image")
        else: assert files["BOOTX64 EFI"][0] == original, (name, "a refused image must not replace BOOTX64.EFI")
        meta_after = osmeta(after)
        if meta_after is not None:
            assert (meta_after[1] != meta_before) == journal_changes, (name, "journal bytes changed", meta_after[1] != meta_before)
        fl = r["floor"]
        if want_floor_seen is not None: assert fl["loaded"] == 1 and fl["value"] == want_floor_seen, (name, fl)
        else: assert fl["loaded"] == 0, (name, "the journal must not have loaded", fl)
        if want_floor_after is None: assert fl["advance"] == 0, (name, "the floor must not advance", fl)
        else: assert fl["advance"] == 1 and fl["after"] == want_floor_after, (name, fl)
        if want_install in (1, 9, 10): assert not changed, (name, "a refused header must write nothing", len(changed))
        events.append(dict(name=name, case=case, request=request, hook=r["hook"], install=r["install"], stream=r["stream"],
                           changedSectors=len(changed), bootSize=len(files["BOOTX64 EFI"][0]), floorSeen=fl["value"] if fl["loaded"] else None,
                           floorAfter=fl["after"] if fl["advance"] == 1 else None, journalChanged=journal_changes))
        return r

    # --- install advances the floor; the replay and an older image are refused; a newer one advances again ---
    fresh()
    install("update2-install", "two-of-three-0-1", "3", 15, img, floor0, 5, True)
    install("update2-replay", "two-of-three-0-1", "3", 9, img, 5, None, False)
    # the replay boot does not touch anything, so BOOTX64.EFI is still the image just installed
    install("update2-newer", "floor-above", "3", 15, img, 5, 6, True)
    # --- crash order: the install commits, the advance does not happen ---
    fresh()
    install("update2-crash-before-advance", "two-of-three-0-1", "5", 15, img, floor0, None, False)
    install("update2-crash-repeat", "two-of-three-0-1", "3", 15, img, floor0, 5, True)
    install("update2-crash-refused", "two-of-three-0-1", "3", 9, img, 5, None, False)
    # --- a failed install never advances the floor ---
    fresh()
    install("update2-tampered", "tampered-image", "3", 7, None, floor0, None, False)
    fresh()
    install("update2-one-signer", "one-signer", "3", 1, None, floor0, None, False)
    # --- fail closed: a corrupt or missing journal refuses the update, it is never floor 0 ---
    bad = bytearray(tmpl_bytes); at = prov[0]
    bad[at + 3 * 4096 + 100] ^= 1   # the published slot (generation 1 -> sector 3) payload
    disk.write_bytes(bytes(bad))
    install("update2-journal-corrupt", "two-of-three-0-1", "3", 10, None, None, None, False)
    nvme.fat32_disk(out, disk)
    assert osmeta(disk.read_bytes()) is None
    install("update2-journal-absent", "two-of-three-0-1", "3", 10, None, None, None, False)
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_UPDATE2_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)),
                  oracle=pin(HERE / "update2_oracle.py"), reference=pin(oracle.o.REF / "reference.py"), events=events,
                  network="none (-nic none)", testKeysOnly=True, productionSignerSet=False, physicalHardware=False,
                  versionFloorHashCheckedNotSigned=True, journalCrashInterruptionSimulatedByHook=True)
    (out / "native-update2-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
