#!/usr/bin/env python3
"""JUN-813 stage 5c follow-up: host-side gate for aiueos-provision-esp.py (macOS only: the fixture ESP is made with hdiutil).

Builds the nvme gate's FAT32 fixture ESP (check-native-nvme-qemu.fat32_disk: GPT, FAT32, \\EFI\\ITONAMI\\BOOTX64.EFI), runs the REAL
provisioning command on it, extracts OSMETA.BIN with the update2 gate's own extractor (check-native-update2-qemu.osmeta) and checks:
  * the file is byte-identical to a journal built here by an independent re-implementation of native/update_journal.kotoba's format
    (ref_journal / ref_verify below are written from the Kotoba source and the journal QEMU gate's offsets, share no code with the tool);
  * every rule native/esp.kotoba `record-file` imposes: size 20480, attribute byte, first cluster 4096-aligned, one contiguous chain
    through every FAT copy, disjoint from the other files, inside the GPT ESP, FAT copies equal; only ESP sectors changed;
  * the active-image digest field is the SHA-256 of \\EFI\\ITONAMI\\BOOTX64.EFI on the same ESP; floor = active = N, phase 0, generation 1.
Refusals (exit status 2, disk byte-identical afterwards): missing --version / 0 / negative / non-numeric / 2^63, missing \\EFI\\ITONAMI\\,
missing BOOTX64.EFI, existing valid OSMETA.BIN without --replace, existing invalid OSMETA.BIN without --replace, no placeable free run,
no free directory slot in BOOTX64.EFI's block; --replace rewrites in place (also lowering the floor). Not tested: block devices, 4096-byte
logical blocks, FAT16, real hardware.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import zlib
from pathlib import Path

if not __debug__:
    raise RuntimeError("the gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tool = load("provision_tool", "aiueos-provision-esp.py")
update2 = load("update2_gate", "check-native-update2-qemu.py")
nvme = update2.nvme


def ref_journal(version, image_sha256):
    """Independent builder: page table of the 5 x 4096 byte file, from update_journal.kotoba's `initialize` + `publish 1`."""
    pages = [bytearray(4096) for _ in range(5)]
    pages[0][0:8] = b"OSUPMETA"
    pages[0][8:12] = (1).to_bytes(4, "little")
    pages[0][12:16] = (128).to_bytes(4, "little")
    rec = bytearray(512)
    rec[0:4] = bytes.fromhex("4f534a53")            # 0x534a534f little endian
    rec[4:8] = (1).to_bytes(4, "little")
    rec[8:12] = (1).to_bytes(4, "little")           # generation
    rec[24:32] = version.to_bytes(8, "little")      # active
    rec[32:40] = version.to_bytes(8, "little")      # floor
    rec[64:96] = image_sha256
    rec[480:512] = hashlib.sha256(bytes(rec[0:480])).digest()
    head = bytearray(512)
    head[0:4] = bytes.fromhex("4f534a48")           # 0x484a534f little endian
    head[4:8] = (1).to_bytes(4, "little")
    head[8:12] = (1).to_bytes(4, "little")
    head[12:16] = (2 + 1 % 2).to_bytes(4, "little")
    head[480:512] = rec[480:512]
    pages[1][:512] = head
    pages[3][:512] = rec
    return b"".join(bytes(p) for p in pages)


def ref_verify(raw):
    """Independent `load` + `valid`: returns dict(floor, active, phase, generation, digest) or raises AssertionError."""
    assert len(raw) == 20480
    u32 = lambda b, o: int.from_bytes(b[o:o + 4], "little")
    u64 = lambda b, o: int.from_bytes(b[o:o + 8], "little")
    assert raw[0:8] == b"OSUPMETA" and u32(raw, 8) == 1 and u32(raw, 12) == 128 and raw[16:512] == bytes(496)
    head = raw[4096:4608]
    gen, sector = u32(head, 8), u32(head, 12)
    assert u32(head, 0) == 0x484A534F and u32(head, 4) == 1 and 0 < gen < 2**32 - 1 and sector == 2 + gen % 2
    assert head[16:480] == bytes(464)
    rec = raw[sector * 4096:sector * 4096 + 512]
    assert hashlib.sha256(rec[:480]).digest() == rec[480:] == head[480:]
    assert u32(rec, 0) == 0x534A534F and u32(rec, 4) == 1 and u32(rec, 8) == gen and u32(rec, 12) <= 7
    phase, active, floor, cand = u32(rec, 16), u64(rec, 24), u64(rec, 32), u64(rec, 40)
    assert 0 < active < 2**63 and 0 < floor < 2**63 and floor >= active
    assert rec[48:64] == bytes(16) and rec[64:96] != bytes(32) and rec[128:480] == bytes(352)
    assert phase in (0, 3) and cand == 0 and u32(rec, 20) == 0 and rec[96:128] == bytes(32)
    return dict(floor=floor, active=active, phase=phase, generation=gen, digest=rec[64:96])


def fixture(out, name):
    p = out / name
    nvme.fat32_disk(out, p)
    return p


def volume_facts(raw):
    v = nvme.fat32_volume(raw)
    efi = nvme.fat32_dir(raw, v, v["root"])["EFI        "][0]
    own = nvme.fat32_dir(raw, v, efi)["ITONAMI    "][0]
    return v, nvme.fat32_dir(raw, v, own)


def run(args):
    """In-process main(); returns (exit status, stderr text)."""
    import contextlib, io
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        try:
            rc = tool.main(args)
        except SystemExit as e:
            rc = e.code
    return rc, err.getvalue()


def mutate(path, fn):
    raw = bytearray(path.read_bytes())
    fn(raw)
    path.write_bytes(bytes(raw))


def main(a):
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    events = []
    # ---- happy path ----
    disk = fixture(out, "esp.img")
    before = disk.read_bytes()
    assert update2.osmeta(before) is None
    N = 7
    rc, _ = run([str(disk), "--version", str(N)])
    assert rc == 0, rc
    after = disk.read_bytes()
    v, entries = volume_facts(after)
    meta = update2.osmeta(after)
    assert meta is not None
    at, blob = meta
    boot = nvme.fat32_files(after)[1]["BOOTX64 EFI"][0]
    want = ref_journal(N, hashlib.sha256(boot).digest())
    assert blob == want, "OSMETA.BIN differs from the independent reference journal"
    facts = ref_verify(blob)
    assert facts["floor"] == facts["active"] == N and facts["phase"] == 0 and facts["generation"] == 1
    assert facts["digest"] == hashlib.sha256(boot).digest()
    first, size, entry_at = entries["OSMETA  BIN"]
    assert size == 20480 and after[entry_at + 11] & 31 == 0 and at % 4096 == 0
    chain = nvme.fat32_chain(after, v, first)
    assert chain == list(range(first, first + len(chain))) and len(chain) * v["cluster"] >= 20480
    assert at == v["data"] + (first - 2) * v["cluster"] and at + 20480 <= v["end"]
    others = set()
    for nm, (c, _, _) in entries.items():
        if nm != "OSMETA  BIN":
            others |= set(nvme.fat32_chain(after, v, c))
    assert not others & set(chain), "OSMETA.BIN clusters overlap another file"
    for k in range(1, v["fats"]):
        assert after[v["fat"]:v["fat"] + v["fat_bytes"]] == after[v["fat"] + k * v["fat_bytes"]:v["fat"] + (k + 1) * v["fat_bytes"]]
    changed = [i for i in range(0, len(before), 512) if after[i:i + 512] != before[i:i + 512]]
    assert all(v["base"] <= i < v["end"] for i in changed), "write outside the ESP"
    assert nvme.fat32_files(after)[1]["BOOTX64 EFI"][0] == nvme.fat32_files(before)[1]["BOOTX64 EFI"][0]
    assert after[:512 * 2] == before[:512 * 2] and after[-512 * 33:] == before[-512 * 33:], "GPT touched"
    events.append(dict(name="provision", version=N, sha256=hashlib.sha256(blob).hexdigest(), size=len(blob), diskOffset=at,
                       firstCluster=first, clusters=len(chain), changedSectors=len(changed)))
    # replace in place: lower the floor on purpose
    rc, _ = run([str(disk), "--version", "3"])
    assert rc == 2 and disk.read_bytes() == after, "an existing valid journal must not be overwritten"
    events.append(dict(name="refuse-existing-valid", rc=rc))
    rc, _ = run([str(disk), "--version", "3", "--replace"])
    assert rc == 0
    assert update2.osmeta(disk.read_bytes())[1] == ref_journal(3, hashlib.sha256(boot).digest())
    events.append(dict(name="replace-in-place", rc=rc, floor=3))
    # ---- refusals: nothing written ----
    def refuse(name, path, argv, want_text):
        snap = path.read_bytes()
        rc, err = run(argv)
        assert rc == 2, (name, rc, err)
        assert path.read_bytes() == snap, (name, "a refusal wrote to the disk")
        assert want_text in err, (name, err)
        events.append(dict(name=name, rc=rc))

    fresh = fixture(out, "fresh.img")
    for label, bad in (("version-zero", "0"), ("version-negative", "-5"), ("version-text", "abc"), ("version-2^63", str(1 << 63)), ("version-float", "4.5")):
        snap = fresh.read_bytes()
        rc, err = run([str(fresh), "--version", bad])
        assert rc == 2 and fresh.read_bytes() == snap and "--version" in err, (label, rc, err)
        events.append(dict(name="refuse-" + label, rc=rc))
    snap = fresh.read_bytes()
    rc, err = run([str(fresh)])
    assert rc == 2 and fresh.read_bytes() == snap and "--version" in err
    events.append(dict(name="refuse-version-missing", rc=rc))

    p = fixture(out, "nodir.img")
    v0, e0 = volume_facts(p.read_bytes())
    efi = nvme.fat32_dir(p.read_bytes(), v0, v0["root"])["EFI        "][0]
    ent = nvme.fat32_dir(p.read_bytes(), v0, efi)["ITONAMI    "][2]
    mutate(p, lambda r: r.__setitem__(slice(ent, ent + 7), b"XTONAMI"))
    refuse("refuse-missing-itonami-dir", p, [str(p), "--version", "7"], "ITONAMI")

    p = fixture(out, "noboot.img")
    v0, e0 = volume_facts(p.read_bytes())
    mutate(p, lambda r: r.__setitem__(e0["BOOTX64 EFI"][2], 0xE5))
    refuse("refuse-missing-bootx64", p, [str(p), "--version", "7"], "BOOTX64.EFI")

    p = fixture(out, "badmeta.img")
    p.write_bytes(disk.read_bytes())
    mutate(p, lambda r: r.__setitem__(update2.osmeta(bytes(r))[0] + 3 * 4096 + 100, r[update2.osmeta(bytes(r))[0] + 3 * 4096 + 100] ^ 1))
    refuse("refuse-existing-invalid", p, [str(p), "--version", "7"], "invalid journal")

    p = fixture(out, "nofree.img")
    def fill(r):
        vv = nvme.fat32_volume(bytes(r))
        for c in range(2, vv["fat_bytes"] // 4):
            for k in range(vv["fats"]):
                o = vv["fat"] + k * vv["fat_bytes"] + 4 * c
                if struct.unpack_from("<I", r, o)[0] & 0x0FFFFFFF == 0:
                    struct.pack_into("<I", r, o, 0x0FFFFFFF)
    mutate(p, fill)
    refuse("refuse-no-contiguous-run", p, [str(p), "--version", "7"], "contiguous")

    p = fixture(out, "noslot.img")
    v0, e0 = volume_facts(p.read_bytes())
    boot_at = e0["BOOTX64 EFI"][2]
    def occupy(r):
        sector = boot_at - boot_at % 512
        for q in range(sector, sector + 512, 32):
            if r[q] in (0, 0xE5):
                r[q:q + 32] = b"FILLER  DAT" + bytes([0x20]) + bytes(20)
    mutate(p, occupy)
    refuse("refuse-no-directory-slot", p, [str(p), "--version", "7"], "free directory entry")
    status = "PASS_PROVISION_ESP_HOST"
    (out / "provision-esp-host.json").write_text(json.dumps(dict(
        status=status, events=events, tool=hashlib.sha256(Path(tool.__file__).read_bytes()).hexdigest(),
        gate=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reused=["check-native-nvme-qemu.py fat32_disk/fat32_* (fixture and FAT walk)", "check-native-update2-qemu.py osmeta() (extractor)",
                "check-native-update-journal-qemu.py offsets (marker 0, head 4096, slot generation 1 at 3*4096, hash over 480)"],
        notTested="block devices, 4096-byte blocks, FAT16, physical hardware"), indent=2) + "\n")
    print(status, len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
