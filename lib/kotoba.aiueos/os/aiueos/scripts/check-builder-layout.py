#!/usr/bin/env python3
"""JUN-942 host gate: the image builder lays out the native update path, and aiueos-image.py keeps a version ledger.

No QEMU, no hdiutil, no JVM: Python only. Builds a release image with the REAL builder command (make-release-image.py build, as a
subprocess) and checks the primary ESP with an independent reader (the nvme gate's FAT32 walk, check-native-nvme-qemu.fat32_*, plus
checks written here; the builder's and the provisioner's own readers are not used for the verdict):
  * EFI/BOOT/BOOTX64.EFI and EFI/ITONAMI/BOOTX64.EFI both hold the loader bytes, in disjoint clusters (the updater swaps the second);
  * EFI/ITONAMI/OSMETA.BIN is byte-identical to the independent reference journal of check-provision-esp.py (ref_journal / ref_verify,
    written from native/update_journal.kotoba and shared with no tool code) for floor = active = N and the digest of the ITONAMI loader;
  * every rule native/esp.kotoba `record-file` imposes: 20480 bytes, attribute byte, first cluster 4096-aligned, one contiguous chain,
    disjoint from every other file and directory of the volume, inside the GPT ESP, FAT copies equal, directory entry in BOOTX64.EFI's
    512-byte block, and at least two free entries left in that block (UPDATE.BIN and STATE.BIN are created there by the guest);
  * the build is deterministic (two builds are byte-identical) and the receipt's `update` block matches the image.
Negative controls (the layout check must FAIL on each): OSMETA.BIN dropped, journal slot byte changed, wrong N, OSMETA.BIN
entry moved off the 4096 alignment, the ITONAMI loader aliased to EFI/BOOT's clusters, one ITONAMI loader byte changed, ITONAMI missing.
Refusals (non-zero exit, no output file and no .partial left): --version missing / 0 / -1 / text / 2^63 on build and apply-update,
verify --version N+1, a journal that cannot be placed (no free run; no free directory entry; the builder's own call into the real
provisioner, with the free area filled first), an image from before the layout (`verify`).
apply-update: the updated image is laid out for its own version and loader and keeps the recovery partition byte-identical.
Version ledger (aiueos-image.py): sign appends {digest, version, date, signer, format, file} (mode 0600, directory 0700, JSON lines),
ledger-lookup answers VERSION N for the SHA-256 read from the built image's EFI/ITONAMI/BOOTX64.EFI, and refuses or reports: unknown
digest (1), malformed ledger (2), two versions (3), a ledger that is a symlink / mode 0644 / unwritable / malformed (sign refused, no
signed file written), the same digest at a second version (refused). The runbook flow then runs end to end on a board-like image:
ledger lookup -> N -> aiueos-provision-esp.py DISK --version N gives the journal the builder image had.
Not tested here: firmware boot of the layout (see check-native-builder-layout-qemu.py for the guest's own floor load), real hardware.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import struct
import subprocess
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


refs = load("provision_gate_refs", "check-provision-esp.py")        # ref_journal / ref_verify and the nvme gate's FAT32 reader
nvme = refs.nvme
builder = load("release_builder", "make-release-image.py")
IMAGE = HERE / "aiueos-image.py"
TOOL = HERE / "aiueos-provision-esp.py"
BUILDER = HERE / "make-release-image.py"
ESP_GUID = bytes.fromhex("28732ac11ff8d211ba4b00a0c93ec93b")
N = 7


def stream(label, n):
    out, i = b"", 0
    while len(out) < n:
        out += hashlib.sha256(("%s-%d" % (label, i)).encode()).digest()
        i += 1
    return out[:n]


def inputs(d, label="a"):
    """Deterministic synthetic inputs: the builder only needs MZ / ELF / newc magic (the gate boots nothing here)."""
    d.mkdir(parents=True, exist_ok=True)
    paths = dict(efi=d / "efi.bin", kernel=d / "kernel.elf", initramfs=d / "initrd.img")
    paths["efi"].write_bytes(b"MZ" + stream("efi" + label, 300001 - 2))
    paths["kernel"].write_bytes(b"\x7fELF" + stream("kernel" + label, 20000))
    paths["initramfs"].write_bytes(b"070701" + stream("initrd" + label, 3000))
    return paths


def run(argv, **kw):
    return subprocess.run([sys.executable, "-I"] + [str(a) for a in argv], capture_output=True, text=True, **kw)


def build(p, out, receipt, version):
    argv = [BUILDER, "build", "--efi", p["efi"], "--kernel", p["kernel"], "--initramfs", p["initramfs"], "--output", out, "--receipt", receipt]
    return run(argv + (["--version", str(version)] if version is not None else []))


# ---- the independent layout check (returns facts, raises AssertionError) ----
def tree(raw, v, cluster, prefix=""):
    """[(path, first, size, entry offset, is_dir)] below a directory, every entry, skipping . and .."""
    rows = []
    for name, (first, size, at) in nvme.fat32_dir(raw, v, cluster).items():
        if name in (".          ", "..         "):
            continue
        is_dir = bool(raw[at + 11] & 0x10)
        rows.append((prefix + "/" + name.strip(), first, size, at, is_dir))
        if is_dir:
            rows += tree(raw, v, first, prefix + "/" + name.strip())
    return rows


def file_bytes(raw, v, first, size):
    return b"".join(bytes(raw[v["data"] + (c - 2) * v["cluster"]:v["data"] + (c - 1) * v["cluster"]]) for c in nvme.fat32_chain(raw, v, first))[:size]


def check_layout(raw, loader, version):
    """Independent verdict on the builder's primary ESP. Raises AssertionError."""
    raw = bytes(raw)
    # GPT: first entry is the ESP; header and entry-array CRC32 (primary)
    hdr = bytearray(raw[512:512 + 92])
    crc = struct.unpack_from("<I", hdr, 16)[0]
    hdr[16:20] = bytes(4)
    assert zlib.crc32(bytes(hdr)) == crc, "GPT header CRC"
    lba, count, size, ecrc = struct.unpack_from("<QIII", hdr, 72)
    assert zlib.crc32(raw[lba * 512:lba * 512 + count * size]) == ecrc, "GPT entry CRC"
    assert raw[lba * 512:lba * 512 + 16] == ESP_GUID, "first GPT entry is not the ESP"
    v = nvme.fat32_volume(raw)
    assert v["bps"] == 512 and v["cluster"] >= 512 and v["cluster"] & (v["cluster"] - 1) == 0
    assert raw[v["base"] + 82:v["base"] + 90] == b"FAT32   "
    for k in range(1, v["fats"]):
        assert raw[v["fat"]:v["fat"] + v["fat_bytes"]] == raw[v["fat"] + k * v["fat_bytes"]:v["fat"] + (k + 1) * v["fat_bytes"]], "FAT copies differ"
    rows = tree(raw, v, v["root"])
    by = {p: (f, s, a, d) for p, f, s, a, d in rows}
    for need in ("/EFI/BOOT/BOOTX64 EFI", "/EFI/ITONAMI/BOOTX64 EFI", "/EFI/ITONAMI/OSMETA  BIN"):
        assert need in by, "missing " + need
    boot, own, meta = by["/EFI/BOOT/BOOTX64 EFI"], by["/EFI/ITONAMI/BOOTX64 EFI"], by["/EFI/ITONAMI/OSMETA  BIN"]
    assert file_bytes(raw, v, boot[0], boot[1]) == loader, "EFI/BOOT loader bytes"
    assert file_bytes(raw, v, own[0], own[1]) == loader, "EFI/ITONAMI loader bytes"
    chains = {p: set(nvme.fat32_chain(raw, v, f)) for p, (f, s, a, d) in by.items()}
    assert not chains["/EFI/BOOT/BOOTX64 EFI"] & chains["/EFI/ITONAMI/BOOTX64 EFI"], "the two loaders share clusters"
    for p, c in chains.items():
        if p != "/EFI/ITONAMI/OSMETA  BIN":
            assert not c & chains["/EFI/ITONAMI/OSMETA  BIN"], "OSMETA.BIN overlaps " + p
    # record-file rules
    first, size, at, _ = meta
    chain = nvme.fat32_chain(raw, v, first)
    assert size == 20480 and raw[at + 11] & 31 == 0, "OSMETA.BIN size or attribute byte"
    assert chain == list(range(first, first + len(chain))) and len(chain) * v["cluster"] >= 20480 and (len(chain) - 1) * v["cluster"] < 20480
    off = v["data"] + (first - 2) * v["cluster"]
    assert off % 4096 == 0, "OSMETA.BIN is not 4096-aligned"
    assert off + 20480 <= v["end"], "OSMETA.BIN outside the ESP"
    assert at // 512 == own[2] // 512, "OSMETA.BIN's directory entry is not in BOOTX64.EFI's 512-byte block"
    block = at - at % 512
    assert sum(1 for q in range(block, block + 512, 32) if raw[q] in (0, 0xE5)) >= 2, "no free entries left for UPDATE.BIN and STATE.BIN"
    blob = bytes(raw[off:off + 20480])
    assert blob == refs.ref_journal(version, hashlib.sha256(loader).digest()), "OSMETA.BIN differs from the reference journal"
    facts = refs.ref_verify(blob)
    assert facts["floor"] == facts["active"] == version and facts["phase"] == 0 and facts["generation"] == 1
    assert facts["digest"] == hashlib.sha256(file_bytes(raw, v, own[0], own[1])).digest()
    return dict(floor=facts["floor"], osmetaSha256=hashlib.sha256(blob).hexdigest(), diskOffset=off, firstCluster=first, clusters=len(chain),
                clusterBytes=v["cluster"], loaderSha256=hashlib.sha256(loader).hexdigest(), espBytes=v["end"] - v["base"],
                files=sorted(p for p, r in by.items() if not r[3]))


def mutate(raw, fn):
    raw = bytearray(raw)
    fn(raw)
    return bytes(raw)


def entry_of(raw, path):
    v = nvme.fat32_volume(raw)
    return {p: (f, s, a) for p, f, s, a, d in tree(raw, v, v["root"])}[path], v


def drop_osmeta(raw):
    """The ESP as a deployed board has it before provisioning: \\EFI\\ITONAMI\\ and its loader, no OSMETA.BIN, its clusters free again."""
    (first, size, at), v = entry_of(raw, "/EFI/ITONAMI/OSMETA  BIN")
    chain = nvme.fat32_chain(raw, v, first)

    def fn(r):
        r[at] = 0xE5
        for k in range(v["fats"]):
            for c in chain:
                struct.pack_into("<I", r, v["fat"] + k * v["fat_bytes"] + 4 * c, 0)
    return mutate(raw, fn)


def main(a):
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    events = []
    p = inputs(out / "in")
    loader = p["efi"].read_bytes()
    img, rcp = out / "a.img", out / "a.json"
    # ---- happy path: the real builder CLI ----
    r = build(p, img, rcp, N)
    assert r.returncode == 0, r.stderr
    raw = img.read_bytes()
    facts = check_layout(raw, loader, N)
    assert facts["clusterBytes"] == 512
    events.append(dict(name="build-and-layout", version=N, **{k: facts[k] for k in ("osmetaSha256", "diskOffset", "firstCluster", "clusters", "clusterBytes", "espBytes")},
                       loaderSha256=facts["loaderSha256"], files=facts["files"]))
    v = run([BUILDER, "verify", "--image", img, "--efi", p["efi"], "--kernel", p["kernel"], "--initramfs", p["initramfs"], "--version", str(N)])
    assert v.returncode == 0 and "AIUEOS_RELEASE_IMAGE_OK" in v.stdout, v.stderr
    receipt = json.loads(rcp.read_text())
    u = receipt["update"]
    assert u["version"] == N and u["EFI/ITONAMI/OSMETA.BIN"]["sha256"] == facts["osmetaSha256"] and u["EFI/ITONAMI/OSMETA.BIN"]["disk_offset"] == facts["diskOffset"]
    assert u["EFI/ITONAMI/BOOTX64.EFI"]["sha256"] == hashlib.sha256(loader).hexdigest() == receipt["artifacts"]["EFI/BOOT/BOOTX64.EFI"]["sha256"]
    assert receipt["disk"]["sha256"] == hashlib.sha256(raw).hexdigest()
    events.append(dict(name="verify-and-receipt", rc=v.returncode))
    # deterministic
    assert build(p, out / "b.img", out / "b.json", N).returncode == 0
    assert (out / "b.img").read_bytes() == raw and (out / "b.json").read_bytes() == rcp.read_bytes(), "the build is not deterministic"
    events.append(dict(name="deterministic", sha256=hashlib.sha256(raw).hexdigest()))
    # a different N changes only the journal
    assert build(p, out / "c.img", out / "c.json", 9).returncode == 0
    c = (out / "c.img").read_bytes()
    check_layout(c, loader, 9)
    assert sum(1 for i in range(0, len(raw), 512) if raw[i:i + 512] != c[i:i + 512]) <= 3 and len(raw) == len(c)
    events.append(dict(name="other-version", version=9))

    # ---- negative controls: the layout check must fail, for the stated reason ----
    def neg(name, image, want, version=N, ldr=loader):
        try:
            check_layout(image, ldr, version)
        except AssertionError as e:
            assert want in str(e), ("negative control %s failed for another reason" % name, str(e))
            events.append(dict(name=name, layoutCheck="failed as required", reason=str(e)))
            return
        raise SystemExit("negative control %s was NOT detected" % name)

    neg("neg-no-osmeta", drop_osmeta(raw), "missing /EFI/ITONAMI/OSMETA  BIN")
    at = facts["diskOffset"]
    neg("neg-wrong-hash", mutate(raw, lambda r: r.__setitem__(at + 3 * 4096 + 100, r[at + 3 * 4096 + 100] ^ 1)), "reference journal")
    neg("neg-wrong-n", raw, "reference journal", N + 1)
    (first, size, eat), vol0 = entry_of(raw, "/EFI/ITONAMI/OSMETA  BIN")

    def shift(r):
        """OSMETA.BIN moved one cluster up: same bytes, still contiguous and in the free area, but not 4096-aligned."""
        cs, n = vol0["cluster"], 20480 // vol0["cluster"]
        src = vol0["data"] + (first - 2) * cs
        r[src + cs:src + cs + 20480] = bytes(r[src:src + 20480])
        for k in range(vol0["fats"]):
            base = vol0["fat"] + k * vol0["fat_bytes"]
            for i in range(n + 1):
                struct.pack_into("<I", r, base + 4 * (first + i), 0)
            for i in range(n):
                struct.pack_into("<I", r, base + 4 * (first + 1 + i), 0x0FFFFFFF if i == n - 1 else first + 2 + i)
        struct.pack_into("<H", r, eat + 26, (first + 1) & 0xFFFF)
    neg("neg-misaligned", mutate(raw, shift), "4096-aligned")
    (bfirst, bsize, bat), _ = entry_of(raw, "/EFI/BOOT/BOOTX64 EFI")
    (ofirst, osize, oat), vol = entry_of(raw, "/EFI/ITONAMI/BOOTX64 EFI")
    neg("neg-aliased-loaders", mutate(raw, lambda r: (struct.pack_into("<H", r, oat + 26, bfirst & 0xFFFF), struct.pack_into("<H", r, oat + 20, bfirst >> 16))),
        "share clusters")
    ooff = vol["data"] + (ofirst - 2) * vol["cluster"]
    neg("neg-itonami-loader-differs", mutate(raw, lambda r: r.__setitem__(ooff + 100, r[ooff + 100] ^ 1)), "ITONAMI loader bytes")
    (ifirst, _, iat), _ = entry_of(raw, "/EFI/ITONAMI")
    neg("neg-no-itonami", mutate(raw, lambda r: r.__setitem__(iat, 0xE5)), "missing /EFI/ITONAMI/BOOTX64 EFI")

    # ---- refusals ----
    def refuse(name, argv, want, outputs=()):
        r = run(argv)
        assert r.returncode != 0 and want in r.stderr, (name, r.returncode, r.stderr[-300:])
        for o in outputs:
            assert not Path(o).exists() and not Path(str(o) + ".partial").exists(), (name, "left a file behind", o)
        events.append(dict(name=name, rc=r.returncode))

    base = [BUILDER, "build", "--efi", p["efi"], "--kernel", p["kernel"], "--initramfs", p["initramfs"]]
    for label, value in (("missing", None), ("zero", "0"), ("negative", "-1"), ("text", "abc"), ("2^63", str(1 << 63)), ("float", "2.5")):
        o = out / ("refuse-%s.img" % label)
        argv = base + ["--output", o, "--receipt", out / "refuse.json"] + (["--version", value] if value is not None else [])
        refuse("refuse-build-version-" + label, argv, "--version", [o, out / "refuse.json"])
    for label, value in (("missing", None), ("zero", "0")):
        o = out / ("refuse-update-%s.img" % label)
        argv = [BUILDER, "apply-update", "--image", img, "--efi", p["efi"], "--kernel", p["kernel"], "--initramfs", p["initramfs"],
                "--output", o, "--receipt", out / "refuse-update.json"] + (["--version", value] if value is not None else [])
        refuse("refuse-apply-update-version-" + label, argv, "--version", [o, out / "refuse-update.json"])
    refuse("refuse-verify-wrong-version", [BUILDER, "verify", "--image", img, "--version", str(N + 1)], "floor/active", [])
    legacy = out / "legacy.img"
    (lfirst, _, lat), _ = entry_of(raw, "/EFI/ITONAMI")
    legacy.write_bytes(mutate(raw, lambda r: r.__setitem__(lat, 0xE5)))
    refuse("refuse-verify-image-without-layout", [BUILDER, "verify", "--image", legacy], "ITONAMI", [])
    refuse("refuse-verify-image-without-osmeta", [BUILDER, "verify", "--image", (legacy.write_bytes(drop_osmeta(raw)), legacy)[1]], "OSMETA", [])

    # unplaceable journal: the builder's own call into the real provisioner, with the free area filled / the directory block full first
    real = builder.PROVISION.provision

    def fill_free(path):
        d = bytearray(Path(path).read_bytes())
        vv = nvme.fat32_volume(bytes(d))
        for cl in range(2, vv["fat_bytes"] // 4):
            for k in range(vv["fats"]):
                o = vv["fat"] + k * vv["fat_bytes"] + 4 * cl
                if struct.unpack_from("<I", d, o)[0] & 0x0FFFFFFF == 0:
                    struct.pack_into("<I", d, o, 0x0FFFFFFF)
        Path(path).write_bytes(bytes(d))

    def fill_block(path):
        d = bytearray(Path(path).read_bytes())
        (_, _, boot_at), _ = entry_of(bytes(d), "/EFI/ITONAMI/BOOTX64 EFI")
        sector = boot_at - boot_at % 512
        for q in range(sector, sector + 512, 32):
            if d[q] in (0, 0xE5):
                d[q:q + 32] = b"FILLER  DAT" + bytes([0x20]) + bytes(20)
        Path(path).write_bytes(bytes(d))

    for name, prep, want in (("refuse-unplaceable-no-free-run", fill_free, "contiguous"), ("refuse-unplaceable-no-directory-slot", fill_block, "free directory entry")):
        o = out / (name + ".img")
        builder.PROVISION.provision = lambda path, version, replace=False, block=512, _prep=prep: (_prep(path), real(path, version, replace, block))[1]
        try:
            try:
                builder.build_image(str(o), p["efi"], p["kernel"], p["initramfs"], N)
            except SystemExit as e:
                assert want in str(e) and str(e).startswith("REFUSED"), (name, str(e))
            else:
                raise SystemExit("%s: the builder did not refuse" % name)
        finally:
            builder.PROVISION.provision = real
        assert not o.exists() and not Path(str(o) + ".partial").exists(), (name, "left a file behind")
        events.append(dict(name=name, refused=True))

    # ---- apply-update: laid out for its own version and loader, recovery untouched ----
    p2 = inputs(out / "in2", "b")
    loader2 = p2["efi"].read_bytes()
    upd, urc = out / "u.img", out / "u.json"
    r = run([BUILDER, "apply-update", "--image", img, "--efi", p2["efi"], "--kernel", p2["kernel"], "--initramfs", p2["initramfs"],
             "--output", upd, "--receipt", urc, "--version", "8"])
    assert r.returncode == 0, r.stderr
    ur = upd.read_bytes()
    check_layout(ur, loader2, 8)
    rec = builder.RECOVERY_FIRST * 512, (builder.RECOVERY_LAST + 1) * 512
    assert ur[rec[0]:rec[1]] == raw[rec[0]:rec[1]], "apply-update touched the recovery partition"
    assert json.loads(urc.read_text())["update"]["version"] == 8
    events.append(dict(name="apply-update", version=8, recoveryUnchanged=True))

    # ---- version ledger ----
    led = out / "ledger"
    led.mkdir()
    seed = led / "seed.key"
    seed.write_bytes(stream("ledger-seed-test-only", 32))
    seed.chmod(0o600)
    ledger = led / "home" / ".itonami" / "ledger.jsonl"
    signed = led / "signed.bin"
    r = run([IMAGE, "sign", "--key", seed, "--version", str(N), "--ledger", ledger, p["efi"], signed])
    assert r.returncode == 0, r.stderr
    sha = hashlib.sha256(loader).hexdigest()
    assert signed.read_bytes()[:8] == b"AIUEIMG1" and signed.read_bytes()[128:] == loader
    assert stat.S_IMODE(ledger.stat().st_mode) == 0o600 and stat.S_IMODE(ledger.parent.stat().st_mode) == 0o700
    rows = [json.loads(x) for x in ledger.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["digest"] == sha and rows[0]["version"] == N and rows[0]["format"] == "AIUEIMG1" and rows[0]["file"] == "signed.bin"
    assert len(rows[0]["signer"]) == 16 and rows[0]["date"].endswith("Z") and set(rows[0]) == {"digest", "version", "date", "signer", "format", "file"}
    events.append(dict(name="ledger-sign", record=rows[0]))
    # the digest an operator reads off the board is the ITONAMI loader of the built image
    (of, osz, _), vol = entry_of(raw, "/EFI/ITONAMI/BOOTX64 EFI")
    board_digest = hashlib.sha256(file_bytes(raw, vol, of, osz)).hexdigest()
    r = run([IMAGE, "ledger-lookup", "--digest", board_digest.upper(), "--ledger", ledger])
    assert r.returncode == 0 and r.stdout.startswith("VERSION %d\n" % N), (r.stdout, r.stderr)
    events.append(dict(name="ledger-lookup", digest=board_digest, version=N))
    r = run([IMAGE, "ledger-lookup", "--digest", "0" * 64, "--ledger", ledger])
    assert r.returncode == 1 and "NOT FOUND" in r.stderr
    r = run([IMAGE, "ledger-lookup", "--digest", "xyz", "--ledger", ledger])
    assert r.returncode == 2
    r = run([IMAGE, "ledger-lookup", "--digest", sha, "--ledger", led / "absent.jsonl"])
    assert r.returncode == 1
    events.append(dict(name="ledger-lookup-not-found", rc=1))
    # same digest, other version: sign refused, no signed file, ledger unchanged
    before = ledger.read_bytes()
    r = run([IMAGE, "sign", "--key", seed, "--version", str(N + 1), "--ledger", ledger, p["efi"], led / "again.bin"])
    assert r.returncode != 0 and "already has this image" in r.stderr and not (led / "again.bin").exists() and ledger.read_bytes() == before
    r = run([IMAGE, "sign", "--key", seed, "--version", str(N), "--ledger", ledger, p["efi"], led / "same.bin"])
    assert r.returncode == 0 and len(ledger.read_text().splitlines()) == 2
    events.append(dict(name="ledger-refuse-second-version", rc=1))
    # a ledger holding two versions (edited by hand) is reported, not guessed
    amb = led / "amb.jsonl"
    amb.write_text("".join(json.dumps(dict(rows[0], version=x), sort_keys=True) + "\n" for x in (5, 6)))
    amb.chmod(0o600)
    r = run([IMAGE, "ledger-lookup", "--digest", sha, "--ledger", amb])
    assert r.returncode == 3 and "AMBIGUOUS" in r.stderr
    events.append(dict(name="ledger-lookup-ambiguous", rc=3))
    # unusable ledgers stop the signing (never skipped silently)
    def sign_refused(name, ledger_path, want):
        o = led / (name + ".bin")
        r = run([IMAGE, "sign", "--key", seed, "--version", "3", "--ledger", ledger_path, p["kernel"], o])
        assert r.returncode != 0 and want in r.stderr and not o.exists(), (name, r.returncode, r.stderr)
        events.append(dict(name=name, rc=r.returncode))

    open_mode = led / "mode644.jsonl"
    open_mode.write_text("")
    open_mode.chmod(0o644)
    sign_refused("ledger-refuse-mode-0644", open_mode, "0600")
    link = led / "link.jsonl"
    os.symlink(ledger, link)
    sign_refused("ledger-refuse-symlink", link, "cannot be opened")
    bad = led / "bad.jsonl"
    bad.write_text('{"digest": "zz"}\n')
    bad.chmod(0o600)
    sign_refused("ledger-refuse-malformed", bad, "not a ledger record")
    r = run([IMAGE, "ledger-lookup", "--digest", sha, "--ledger", bad])
    assert r.returncode == 2 and "UNREADABLE" in r.stderr
    ro = led / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        if os.geteuid() != 0:
            sign_refused("ledger-refuse-unwritable-dir", ro / "sub" / "l.jsonl", "cannot be opened")
    finally:
        ro.chmod(0o700)
    partial = led / "partial.jsonl"
    partial.write_text(json.dumps(rows[0]))
    partial.chmod(0o600)
    sign_refused("ledger-refuse-partial-line", partial, "partial line")

    # ---- the runbook flow on a board-like image (ITONAMI and its loader, no journal) ----
    board = out / "board.img"
    board.write_bytes(drop_osmeta(raw))
    r = run([IMAGE, "ledger-lookup", "--digest", board_digest, "--ledger", ledger])
    n_found = int(r.stdout.split()[1])
    assert n_found == N
    r = run([TOOL, board, "--version", str(n_found)])
    assert r.returncode == 0, r.stderr
    check_layout(board.read_bytes(), loader, N)
    assert board.read_bytes()[facts["diskOffset"]:facts["diskOffset"] + 20480] == raw[facts["diskOffset"]:facts["diskOffset"] + 20480]
    events.append(dict(name="runbook-flow", lookedUpVersion=n_found, provisionedFloor=N, sameJournalAsBuilderImage=True))
    status = "PASS_BUILDER_LAYOUT_HOST"
    (out / "builder-layout-host.json").write_text(json.dumps(dict(
        status=status, events=events,
        builder=hashlib.sha256(BUILDER.read_bytes()).hexdigest(), imageTool=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),
        provisioner=hashlib.sha256(TOOL.read_bytes()).hexdigest(), gate=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reused=["check-provision-esp.py ref_journal / ref_verify (independent reference journal)", "check-native-nvme-qemu.py fat32_* (independent FAT32 walk)"],
        syntheticInputs="MZ/ELF/newc magic plus deterministic bytes; nothing here is booted",
        notTested="firmware boot of the layout, block devices, real hardware"), indent=2) + "\n")
    print(status, len(events))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", type=Path, required=True)
    main(ap.parse_args())
