#!/usr/bin/env python3
"""JUN-813 (ADR-0286 amendment 7): native/update.kotoba in PRODUCTION mode (test = 0) admits objects signed by the production signer set.

The signer set is VERIFICATION-ONLY: three slots kept on one Mac (scripts/aiueos-signer.py), whose PUBLIC keys are compiled in
(aiueos.imgsig-prodkeys, from fixtures/signers/prod-pubkeys.json). The private seeds are not in the repository, so this gate cannot sign:
it replays three golden fixtures that were signed ONCE with the real slots (fixtures/signers/golden/, public data) and cases derived from them
on the host from public bytes (an entry dropped, a byte flipped, one kind presented as another) or signed by the public TEST keys
(scripts/prodsig_oracle.py). Every expected verdict is computed by the independent references under the production PUBLIC keys.

One verification boot of the desktop debug entry (the one that probes NVMe/ESP and runs update.kotoba's hooks) on a fresh FAT32 fixture ESP
attached as an NVMe disk, QEMU `-nic none`, with the RTC fixed at 2026-11-06T12:00:00 (inside the golden freshness record's validity) and the
fw_cfg files opt/aiueos/update2, cat1 and fresh. A provisioning boot first makes OSMETA.BIN with version floor 4 (the image path reads it and
fails closed without it, exactly as in the update2 gate).
  prodsig-provision    request "4": OSMETA.BIN (floor 4).
  prodsig-image        AIUEIMG2 in production mode: the golden header ADMITS (result 15, slots 0+1) and is REFUSED in test mode; REFUSED are a
                       one-signer header (1), a header signed by TEST keys (1), a flipped byte in an ML-DSA signature, an Ed25519 signature or
                       the manifest (1), a flipped image byte (digest, 7), and the golden catalog and freshness headers presented as images (1: their byte 7 is "1", so `admit` judges them by its AIUEIMG1
                       branch, whose signature check comes first).
  prodsig-catalog      AIUECAT1: the golden catalog ADMITS (15, slots 1+2) and the same refusals; an image and a freshness record presented
                       as a catalog are refused (2).
  prodsig-fresh        AIUEFRS1: the golden record ADMITS (15, slots 0+2, verdict fresh) and the same refusals.
Case k of each file is compared with the oracle's result | counted mask << 8 (| flags << 16, | freshness verdict << 16). Afterwards the ESP walk
must still read the fixture's own BOOTX64.EFI, the disk must be byte-identical to the provisioned template (verify-only), the AIUEIMG1 self-test
must still read 7 / [15, 1, 7] and the desktop must still draw. The gate is useless without its negative controls, which are rebuilt kernels run
through this same gate: production mode that accepts the TEST keys, and production mode that ignores the signer count.
QEMU TCG only; hdiutil makes the FAT32 fixture, so this gate is macOS only. Not measured: a physical board, the network pull (RTL8168).
"""
import argparse, calendar, hashlib, importlib.util, json, shutil, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


nvme = load("nvme_gate", "check-native-nvme-qemu.py")
u2 = load("update2_gate", "check-native-update2-qemu.py")
keystore = nvme.keystore
import prodsig_oracle as oracle
MARKER = int.from_bytes(b"FRS1", "big")       # the last hook to run (update2, then cat1, then fresh) leaves its marker
pin = keystore.pin


def rtc_arg(unix):
    t = time.gmtime(unix)
    return ["-rtc", f"base={t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d},clock=vm"]


def words(b, first, n):
    raw = b.words(first, n)
    return [int.from_bytes(raw[i:i + 4], "little") for i in range(0, 4 * n, 4)]


def boot(args, out, name, disk, files):
    vars_copy = out / f"{name}-vars.fd"
    shutil.copyfile(args.firmware.parent / "edk2-i386-vars.fd", vars_copy)
    extra = ["-drive", f"if=pflash,format=raw,file={vars_copy}", "-cpu", "max,phys-bits=37",
             "-drive", f"file={disk},format=raw,if=none,id=nv0", "-device", "nvme,serial=AWAI122NVME512,drive=nv0"]
    for fwname, path in files.items():
        extra += ["-fw_cfg", f"name=opt/aiueos/{fwname},file={path}"]
    extra += rtc_arg(oracle.CLOCK_BASE)
    b = keystore.Boot(args, out, name, None, extra, first_frame_seconds=6000)
    try:
        deadline = time.monotonic() + 900
        while b.W(234) != MARKER and time.monotonic() < deadline: time.sleep(2)
        r = dict(hook=b.W(211), marker=b.W(234), count=b.W(235), walk=b.W(233), nvme=b.W(600),
                 v1=[b.W(188), b.W(189) & 255, (b.W(189) >> 8) & 255, (b.W(189) >> 16) & 255])
        halves = words(b, 236, 20)
        r["image"] = [(halves[k // 2] >> (16 * (k & 1))) & 0xffff for k in range(40)]
        r["catalog"] = words(b, 300, 64)
        r["fresh"] = words(b, 400, 64)
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


def compare(kind, cases, got, want_of):
    matches, bad = [], []
    for k, c in enumerate(cases):
        want = want_of(c)
        (matches if got[k] == want else bad).append(c["name"] if got[k] == want else (c["name"], hex(got[k]), hex(want)))
    assert not bad, (f"production-mode {kind} cases differ from the oracle (name, got, want)", bad)
    return matches


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    img_cases, cat_cases, frs_cases = oracle.image_cases(), oracle.catalog_cases(), oracle.fresh_cases()
    fw = {}
    for name, blob in (("update2", oracle.fw_image(img_cases)), ("cat1", oracle.fw_catalog(cat_cases)), ("fresh", oracle.fw_fresh(frs_cases))):
        fw[name] = out / f"{name}.bin"; fw[name].write_bytes(blob)

    # --- provisioning boot: the guest's own journal code makes OSMETA.BIN (floor 4); that disk is the template ---
    template = out / "template.img"
    want = nvme.fat32_disk(out, template)
    assert u2.osmeta(template.read_bytes()) is None, "the plain fixture must have no OSMETA.BIN"
    one = out / "one.bin"; one.write_bytes(oracle.fw_image(img_cases[:1]))
    r = u2.boot(args, out, "prodsig-provision", template, "4", one, events)
    assert r["hook"] == 52 and r["floor"]["provision"] == 1, ("provisioning failed", r["hook"], r["floor"])
    assert u2.osmeta(template.read_bytes()) is not None, "OSMETA.BIN was not created"
    events.append(dict(name="prodsig-provision", hook=r["hook"], floor=oracle.upd.FLOOR))
    tmpl_bytes = template.read_bytes()
    disk = out / "disk.img"; disk.write_bytes(tmpl_bytes)

    # --- the verification boot: three files, one boot ---
    r = boot(args, out, "prodsig-cases", disk, fw)
    assert r["marker"] == MARKER and r["hook"] == 0, ("the hooks did not finish", hex(r["marker"]), r["hook"])
    assert r["count"] == len(frs_cases), ("the last hook did not run its cases", r["count"])
    m_img = compare("image", img_cases, r["image"], lambda c: c["code"] + 256 * c["mask"])
    m_cat = compare("catalog", cat_cases, r["catalog"], lambda c: c["code"] + 256 * c["mask"] + 65536 * c["flags"])
    m_frs = compare("freshness", frs_cases, r["fresh"], lambda c: c["code"] + 256 * c["mask"] + 65536 * c["state"])
    # the headline: the production mode ADMITS the golden fixtures and nothing else it was given
    adm = lambda cs: [c["name"] for c in cs if c["mode"] == 1 and c["code"] == 15]
    assert adm(img_cases) == ["golden-image-production"] and adm(cat_cases) == ["golden-catalog-production"] \
        and adm(frs_cases) == ["golden-freshness-production"], "the oracle's own admitted set is not exactly the golden fixtures"
    assert r["v1"] == [7, 15, 1, 7], ("the AIUEIMG1 self-test changed", r["v1"])
    assert r["walk"] == 15 and r["nvme"] == 15, ("the storage walk after the ML-DSA arena failed", r["walk"], r["nvme"])
    assert r["esp"] == dict(path=want["path"], fat=want["fat"], size=want["size"], sha256=want["sha256"]), (r["esp"], want)
    assert disk.read_bytes() == tmpl_bytes, "a verify-only boot must not write the disk"
    assert r["drew"], "the desktop must still draw after the production-mode paths ran"
    refused = lambda cs: {c["name"] + ("" if c["mode"] == 1 else " (test mode)"): [c["code"], c["mask"]] for c in cs if c["code"] != 15}
    events.append(dict(name="prodsig-image", cases=len(img_cases), matches=m_img, admitted=adm(img_cases), refused=refused(img_cases),
                       testModeAdmits=[c["name"] for c in img_cases if c["mode"] == 0 and c["code"] == 15]))
    events.append(dict(name="prodsig-catalog", cases=len(cat_cases), matches=m_cat, admitted=adm(cat_cases), refused=refused(cat_cases),
                       testModeAdmits=[c["name"] for c in cat_cases if c["mode"] == 0 and c["code"] == 15]))
    events.append(dict(name="prodsig-fresh", cases=len(frs_cases), matches=m_frs, admitted=adm(frs_cases), refused=refused(frs_cases),
                       testModeAdmits=[c["name"] for c in frs_cases if c["mode"] == 0 and c["code"] == 15], rtcBase=oracle.CLOCK_BASE))
    events.append(dict(name="prodsig-regression", espWalkAfter=r["walk"], diskUnchanged=True, imageSelfTest=r["v1"], desktopStillDraws=True))
    disk.unlink(); template.unlink()
    assert pin(args.media) == media_before
    golden = {k: pin(oracle.GOLDEN / v) for k, v in oracle.FILES.items()}
    report = dict(status="PASS_NATIVE_PRODSIG_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)),
                  oracle=pin(HERE / "prodsig_oracle.py"), signingOracle=pin(HERE / "imgsig_oracle.py"), reference=pin(oracle.o.REF / "reference.py"),
                  pinnedPublicKeys=pin(oracle.o.PROD_PUBKEYS), goldenFixtures=golden, events=events, network="none (-nic none)",
                  productionSignerSet=True, verificationOnlySignerSet=True, allThreeSlotsOnOneMac=True, privateKeysInRepository=False,
                  goldenSignedOnceWithRealSlots=True, notWiredToDesktop=True, physicalHardware=False)
    (out / "native-prodsig-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(img_cases), len(cat_cases), len(frs_cases), "cases")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
