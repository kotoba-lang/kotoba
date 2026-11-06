#!/usr/bin/env python3
"""JUN-813 stage 5c follow-up (ADR-0286 amendment 4): a board provisioned by aiueos-provision-esp.py accepts exactly versions above N.

Same machinery as check-native-update2-qemu.py (desktop debug entry, NVMe fixture ESP, `-nic none`, fw_cfg opt/aiueos/update2 headers
made by update2_oracle.py, AIUEIMG2 headers signed with the public TEST keys), with ONE difference: the fixture ESP is provisioned by the
REAL command (`aiueos-provision-esp.py DISK --version 4`), never by the hypervisor-only provisioning hook (install request "4" is not used
anywhere in this gate). fw_cfg still carries the test fixtures (the headers and the install request "3"/"" of the existing update2 hook).
  provision-cases        the oracle's 38 cases, no install request: every result equals the oracle's, the floor read by the guest is 4,
                         the disk is byte-identical afterwards (a verify-only boot never writes).
  provision-equal        install a header whose version == N (4): result 9, nothing written, the floor stays 4.
  provision-above        install a header with version 6 (> N): result 15, BOOTX64.EFI is the admitted image, the floor advances to 6.
Negative controls (each must fail the way the real behaviour demands; they show the positive boots are not vacuous):
  neg-absent             no OSMETA.BIN at all (the ESP as the builders leave it): install refused 10, nothing written.
  neg-wrong-hash         provisioned, then one byte of the slot changed with its SHA-256 left alone: refused 10, nothing written.
  neg-floor-high         provisioned with --version 6 instead of 4: the version-6 header is refused 9 (the correct floor admits it, 15).
  neg-floor-low          provisioned with --version 3 instead of 4: the version-4 (== N) header is installed 15 (the correct floor refuses it, 9).
QEMU TCG only; test keys; the network pull (RTL8168) is not exercised; hdiutil makes the fixture, so this gate is macOS only.
"""
import argparse
import hashlib
import json
from pathlib import Path
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
tool = load("provision_tool", "aiueos-provision-esp.py")
nvme, oracle, pin = update2.nvme, update2.oracle, update2.pin
N = oracle.FLOOR


def provisioned(out, name, version):
    p = out / name
    nvme.fat32_disk(out, p)
    assert update2.osmeta(p.read_bytes()) is None, "the plain fixture must have no OSMETA.BIN"
    assert tool.main([str(p), "--version", str(version)]) == 0
    return p


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"):
        setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    blob, cases = oracle.fw_file()
    fw_all = out / "all.bin"
    fw_all.write_bytes(blob)
    img = oracle.image()
    by = {c["name"]: c for c in cases}
    assert by["floor-equal"]["code"] == 9 and by["floor-above"]["code"] == 15

    def one(name, case):
        data, _ = oracle.fw_file([case])
        p = out / (name + ".bin")
        p.write_bytes(data)
        return p

    def install(name, disk, case, want_install, want_floor_seen, want_floor_after, installed):
        before = disk.read_bytes()
        original = nvme.fat32_files(before)[1]["BOOTX64 EFI"][0]
        r = update2.boot(args, out, name, disk, "3", one(name, case), events)
        assert r["hook"] == 51, (name, r["hook"])
        assert r["install"] == want_install, (name, "install result", r["install"], "wanted", want_install)
        after = disk.read_bytes()
        v, files = nvme.fat32_files(after)
        changed = [i for i in range(0, len(before), 512) if after[i:i + 512] != before[i:i + 512]]
        assert all(v["base"] <= i < v["end"] for i in changed), "a write outside the ESP"
        assert files["BOOTX64 EFI"][0] == (img if installed else original), (name, "BOOTX64.EFI")
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

    # ---- positive: the provisioned fixture, no provisioning hook ----
    disk = provisioned(out, "provisioned.img", N)
    template = disk.read_bytes()
    meta = update2.osmeta(template)
    assert meta is not None and meta[1][:8] == b"OSUPMETA"
    events.append(dict(name="provision-esp", version=N, osmetaSha256=hashlib.sha256(meta[1]).hexdigest(), osmetaBytes=len(meta[1])))
    r = update2.boot(args, out, "provision-cases", disk, None, fw_all, events)
    assert r["marker"] == update2.MARKER and r["count"] == len(cases), (hex(r["marker"]), r["count"])
    bad = [(c["name"], hex(r["results"][k]), c["code"], c["mask"]) for k, c in enumerate(cases)
           if r["results"][k] != c["code"] + 256 * c["mask"]]
    assert not bad, ("results differ from the oracle", bad)
    assert r["floor"]["loaded"] == 1 and r["floor"]["value"] == N and r["floor"]["advance"] == 0, r["floor"]
    assert r["floor"]["provision"] == 0, "the provisioning hook must not have run"
    assert disk.read_bytes() == template, "a verify-only boot wrote the disk"
    events.append(dict(name="provision-cases-checked", cases=len(cases), floorSeen=N, diskUnchanged=True))
    install("provision-equal", disk, "floor-equal", 9, N, None, False)
    install("provision-above", disk, "floor-above", 15, N, 6, True)

    # ---- negative controls ----
    p = out / "absent.img"
    nvme.fat32_disk(out, p)
    install("neg-absent", p, "two-of-three-0-1", 10, None, None, False)
    p = provisioned(out, "wronghash.img", N)
    at = update2.osmeta(p.read_bytes())[0]
    raw = bytearray(p.read_bytes())
    raw[at + 3 * 4096 + 100] ^= 1                    # published slot payload; its SHA-256 and the head's copy stay
    p.write_bytes(bytes(raw))
    install("neg-wrong-hash", p, "two-of-three-0-1", 10, None, None, False)
    p = provisioned(out, "floorhigh.img", 6)
    install("neg-floor-high", p, "floor-above", 9, 6, None, False)
    assert by["floor-above"]["code"] == 15, "with the right floor this header is admitted"
    p = provisioned(out, "floorlow.img", 3)
    install("neg-floor-low", p, "floor-equal", 15, 3, 4, True)
    assert by["floor-equal"]["code"] == 9, "with the right floor this header is refused"
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_PROVISION_ESP_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)), tool=pin(HERE / "aiueos-provision-esp.py"),
                  oracle=pin(HERE / "update2_oracle.py"), events=events, network="none (-nic none)", testKeysOnly=True,
                  provisioningHookUsed=False, productionSignerSet=False, physicalHardware=False)
    (out / "native-provision-esp-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"):
        p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
