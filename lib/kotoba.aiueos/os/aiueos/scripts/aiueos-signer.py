#!/usr/bin/env python3
"""JUN-813 (ADR-0286 amendment 7): the signer-set tool. Pure Python, standard library only, no network.

The kernel pins three signer slots (ids 0..2) and admits an object when two distinct slots signed it; a slot signs with BOTH an Ed25519
key and an ML-DSA-65 key. This tool makes one slot's keys, signs the three object kinds with the slots you ask for, and emits the
public keys the kernel pins. The signer set made here is VERIFICATION-ONLY: all three slots live on one Mac (amendment 7).

  keygen --slot N [--replace]   make slot N: 32 random bytes for the Ed25519 seed and 32 for the ML-DSA-65 seed xi (os.urandom), the ML-DSA
                                keys by the repository's FIPS 204 reference. Written only under ~/.itonami/aiueos-signers/slot<N>/
                                (directories 0700, files 0600). Refuses to overwrite a slot without --replace. Prints only the sha256
                                fingerprints of the PUBLIC keys and the paths; never a seed.
  pubkeys [--from FILE]         the three slots' public keys as hex (public data), from the local slots or from a public-keys JSON.
  emit-pinned [--from FILE] [--out FILE] [--json-out FILE]
                                the Kotoba module aiueos.imgsig-prodkeys (ims-ed-word / ims-ml-word) and/or the public-keys JSON.
  sign-image   --version N [--slots 0,1] [--out FILE] IMAGE        AIUEIMG2: 16384-byte header followed by the image
  sign-catalog --version N [--slots 0,1] [--out FILE] BODY         AIUECAT1: header followed by the body (128 bytes per entry, 1..64)
  sign-fresh   --version N --issued T --valid-until T [--channel 1] [--slots 0,1] [--out FILE]   AIUEFRS1: the header only
  verify FILE --kind image|catalog|fresh [--from FILE]             check a signed object against public keys only

Header layout and contexts are the oracles' (scripts/imgsig_oracle.py, cat_oracle.py, fresh_oracle.py: ADR-0286 amendments 2, 5, 6), used by
import so there is one layout; tests/test_aiueos_signer.py checks the signed bytes against the independent references (RFC 8032 integer
Ed25519, the ACVP-checked ML-DSA-65 reference) and the kernel's pinned module against the public keys.
The tool refuses a key directory, or a seed file, that is readable by anyone but its owner, that is a symlink, or that lies inside a git
work tree. The seeds never enter the repository; only public keys do.
"""
import argparse
import hashlib
import json
import os
import stat
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgsig_oracle as o  # noqa: E402
import cat_oracle  # noqa: E402
import fresh_oracle  # noqa: E402
import update2_oracle  # noqa: E402

ref = o.ref
SCHEMA = "aiueos.imgsig-prodkeys.v1"
KINDS = {"image": b"AIUEIMG2", "catalog": b"AIUECAT1", "fresh": b"AIUEFRS1"}
ED_FILE, XI_FILE, PUB_FILE = "ed25519.seed", "mldsa65.xi", "public.json"
IMAGE_MAX = 33554432


class ToolError(SystemExit):
    pass


def die(msg):
    raise ToolError("aiueos-signer: " + msg)


# ---- where the keys live ---------------------------------------------------------------------------------------------------------
def signers_dir():
    """~/.itonami/aiueos-signers (HOME decides; the tests point it at a temporary directory)."""
    home = os.environ.get("HOME")
    if not home:
        die("HOME is not set")
    return Path(home) / ".itonami" / "aiueos-signers"


def slot_dir(n):
    return signers_dir() / ("slot%d" % n)


def in_git_work_tree(p):
    r = p.resolve()
    return any((q / ".git").exists() for q in [r, *r.parents])


def check_private(path, want_dir):
    """The key directory / seed file must be a real (not linked) object owned by this user and readable by nobody else."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        die("missing: %s" % path)
    if stat.S_ISLNK(st.st_mode):
        die("%s is a symbolic link" % path)
    if want_dir != stat.S_ISDIR(st.st_mode) or (not want_dir and not stat.S_ISREG(st.st_mode)):
        die("%s is not a %s" % (path, "directory" if want_dir else "regular file"))
    if st.st_uid != os.geteuid():
        die("%s is not owned by this user" % path)
    if st.st_mode & 0o077:
        die("%s is readable or writable by others (mode %o); expected %s" % (path, st.st_mode & 0o777, "0700" if want_dir else "0600"))


def check_store(n):
    base = signers_dir()
    # the application directory itself (~/.itonami) may be a link to its real home; the signer set below it may not be
    for d in (base, slot_dir(n)):
        check_private(d, True)
    if in_git_work_tree(slot_dir(n)):
        die("%s lies inside a git work tree" % slot_dir(n))
    for f in (ED_FILE, XI_FILE):
        check_private(slot_dir(n) / f, False)


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except BaseException:
        os.unlink(path)
        raise
    os.chmod(path, 0o600)


def mkdir_private(path):
    if not path.exists():
        path.mkdir(mode=0o700)
    os.chmod(path, 0o700)


# ---- keys --------------------------------------------------------------------------------------------------------------------------
def derive_public(ed_seed, xi):
    """(ed25519 public key, ML-DSA-65 public key) of a slot from its seeds: the integer reference and the FIPS 204 reference."""
    return o.ed_sign(ed_seed, b"")[0], ref.keygen(xi)[0]


def fingerprint(pub):
    return hashlib.sha256(pub).hexdigest()


def public_record(n, edpk, mlpk):
    return {"id": n, "ed25519": edpk.hex(), "mldsa65": mlpk.hex(),
            "ed25519-sha256": fingerprint(edpk), "mldsa65-sha256": fingerprint(mlpk)}


def load_seeds(n):
    check_store(n)
    ed = (slot_dir(n) / ED_FILE).read_bytes()
    xi = (slot_dir(n) / XI_FILE).read_bytes()
    if len(ed) != 32 or len(xi) != 32:
        die("slot %d: a seed file is not 32 bytes" % n)
    return ed, xi


def load_public_json(path):
    j = json.loads(Path(path).read_text())
    if j.get("schema") != SCHEMA or [s["id"] for s in j["slots"]] != [0, 1, 2]:
        die("%s is not a three-slot public-keys file (%s)" % (path, SCHEMA))
    out = []
    for s in j["slots"]:
        ed, ml = bytes.fromhex(s["ed25519"]), bytes.fromhex(s["mldsa65"])
        if len(ed) != 32 or len(ml) != 1952:
            die("%s: slot %d has a public key of the wrong length" % (path, s["id"]))
        if s["ed25519-sha256"] != fingerprint(ed) or s["mldsa65-sha256"] != fingerprint(ml):
            die("%s: slot %d fingerprint does not match its key" % (path, s["id"]))
        out.append((ed, ml))
    return out


def local_public():
    """The public keys of the three local slots (public.json written by keygen, re-derived from the seeds and compared)."""
    out = []
    for n in range(3):
        ed, xi = load_seeds(n)
        edpk, mlpk = derive_public(ed, xi)
        rec = json.loads((slot_dir(n) / PUB_FILE).read_text())
        if rec != public_record(n, edpk, mlpk):
            die("slot %d: public.json does not match the seeds" % n)
        out.append((edpk, mlpk))
    return out


def public_keys(from_file):
    return load_public_json(from_file) if from_file else local_public()


def public_json(pubs):
    return json.dumps({"schema": SCHEMA, "slots": [public_record(n, *p) for n, p in enumerate(pubs)]}, indent=2) + "\n"


def cmd_keygen(a):
    if not 0 <= a.slot <= 2:
        die("slot must be 0, 1 or 2")
    base = signers_dir()
    if not base.parent.exists():
        die("%s does not exist (the application directory is not created by this tool)" % base.parent)
    mkdir_private(base)
    d = slot_dir(a.slot)
    if in_git_work_tree(base):
        die("%s lies inside a git work tree" % base)
    if d.exists() or d.is_symlink():
        if not a.replace:
            die("slot %d already exists; pass --replace to overwrite it" % a.slot)
        check_private(d, True)
        for f in (ED_FILE, XI_FILE, PUB_FILE):
            if (d / f).exists():
                (d / f).unlink()
    mkdir_private(d)
    ed, xi = os.urandom(32), os.urandom(32)
    edpk, mlpk = derive_public(ed, xi)
    write_private(d / ED_FILE, ed)
    write_private(d / XI_FILE, xi)
    write_private(d / PUB_FILE, (json.dumps(public_record(a.slot, edpk, mlpk), indent=2) + "\n").encode())
    print("slot %d" % a.slot)
    print("  ed25519 public key sha256  %s" % fingerprint(edpk))
    print("  mldsa65 public key sha256  %s" % fingerprint(mlpk))
    print("  keys in %s (directory 0700, files 0600)" % d)


def cmd_pubkeys(a):
    for n, (ed, ml) in enumerate(public_keys(a.__dict__.get("from"))):
        print("slot %d ed25519 %s" % (n, ed.hex()))
        print("slot %d mldsa65 %s" % (n, ml.hex()))


def prodkeys_module(pubs):
    return o.emit_keys_module_from(
        [(None, ed, ml, None) for ed, ml in pubs], "aiueos.imgsig-prodkeys",
        ["GENERATED by scripts/aiueos-signer.py emit-pinned from fixtures/signers/prod-pubkeys.json. The PRODUCTION signer set's public keys,",
         "pinned for update.kotoba's production mode (test = 0). VERIFICATION-ONLY set: all three slots are kept on one Mac (ADR-0286 amendment 7)."])


def cmd_emit_pinned(a):
    pubs = public_keys(a.__dict__.get("from"))
    if a.json_out:
        Path(a.json_out).write_text(public_json(pubs))
    text = prodkeys_module(pubs)
    if a.out:
        Path(a.out).write_text(text)
    elif not a.json_out:
        sys.stdout.write(text)


# ---- signing -----------------------------------------------------------------------------------------------------------------------
def parse_slots(s):
    try:
        slots = [int(x) for x in s.split(",")]
    except ValueError:
        die("--slots is a comma list of slot ids")
    if not 1 <= len(slots) <= 4 or len(set(slots)) != len(slots) or any(not 0 <= x <= 2 for x in slots):
        die("--slots: distinct ids among 0, 1, 2")
    return slots


def sign_manifest(man, ctx, slots):
    """Header (16384 bytes) of AIUEIMG2 layout: one entry per requested slot, Ed25519 and ML-DSA-65 over the 64-byte manifest."""
    entries = []
    for n in slots:
        ed_seed, xi = load_seeds(n)
        edpk, sig = o.ed_sign(ed_seed, man)
        mlpk, mlsk = ref.keygen(xi)
        ml = ref.sign_mu(mlsk, ref.mu_of(mlpk, o.mprime(man, ctx)), os.urandom(32))
        entries.append(o.entry(n, sig, ml))
    return o.header(man, entries)


def image_manifest(version, image):
    if not (1 <= version < 1 << 63 and 0 < len(image) <= IMAGE_MAX):
        die("version must be 1..2^63-1 and the image 1..32 MiB")
    return KINDS["image"] + struct.pack("<QQ", version, len(image)) + bytes(8) + hashlib.sha256(image).digest()


def catalog_manifest(version, body):
    if not (1 <= version < 1 << 63 and body and len(body) % cat_oracle.ENT == 0 and len(body) // cat_oracle.ENT <= 64):
        die("version must be >= 1 and the body 128 * (1..64) bytes")
    return cat_oracle.manifest(body, version=version)


def fresh_manifest(version, issued, until, chan):
    top = 1 << 63
    if not (1 <= version < top and 1 <= issued < until < top and until - issued <= fresh_oracle.LIFETIME_MAX and chan == 1):
        die("freshness record: version >= 1, 1 <= issued < valid-until, lifetime <= 30 days, channel 1")
    return fresh_oracle.manifest(version, issued, until, chan)


def emit(a, data):
    if a.out:
        Path(a.out).write_bytes(data)
        print("wrote %s (%d bytes, sha256 %s)" % (a.out, len(data), hashlib.sha256(data).hexdigest()))
    else:
        sys.stdout.buffer.write(data)


def cmd_sign_image(a):
    img = Path(a.file).read_bytes()
    emit(a, sign_manifest(image_manifest(a.version, img), KINDS["image"], parse_slots(a.slots)) + img)


def cmd_sign_catalog(a):
    body = Path(a.file).read_bytes()
    emit(a, sign_manifest(catalog_manifest(a.version, body), KINDS["catalog"], parse_slots(a.slots)) + body)


def cmd_sign_fresh(a):
    emit(a, sign_manifest(fresh_manifest(a.version, a.issued, a.valid_until, a.channel), KINDS["fresh"], parse_slots(a.slots)))


# ---- verification (public keys only) -------------------------------------------------------------------------------------------------
def verify_header(hdr, kind, pubs):
    """Slots that count: pinned id, not seen, zero reserved/padding, Ed25519 and ML-DSA-65 valid under the public keys (independent references)."""
    ctx = KINDS[kind]
    if hdr[:8] != ctx or len(hdr) < o.HDR:
        return None
    count = struct.unpack_from("<I", hdr, 64)[0]
    if not 1 <= count <= 4 or hdr[68:128] != bytes(60) or hdr[24:32] != bytes(8) and kind == "image":
        return None
    man, seen = hdr[:64], []
    for i in range(count):
        e = hdr[128 + i * o.ENTRY:128 + (i + 1) * o.ENTRY]
        kid = struct.unpack_from("<I", e, 0)[0]
        if kid >= 3 or kid in seen or e[4:8] != bytes(4) or e[3381:] != bytes(11):
            continue
        edpk, mlpk = pubs[kid]
        if o.edr.ed_verify(edpk, man, e[8:72]) and ref.verify_mu(mlpk, ref.mu_of(mlpk, o.mprime(man, ctx)), e[72:3381]):
            seen.append(kid)
    return seen


def cmd_verify(a):
    raw = Path(a.file).read_bytes()
    seen = verify_header(raw[:o.HDR], a.kind, public_keys(a.__dict__.get("from")))
    if seen is None:
        die("not a well-formed %s header" % a.kind)
    ok = len(seen) >= o.M_REQ
    if ok and a.kind in ("image", "catalog"):
        body = raw[o.HDR:]
        want = raw[32:64]
        length = struct.unpack_from("<Q", raw, 16)[0]
        ok = len(body) == length and hashlib.sha256(body).digest() == want
    print("%s: slots %s, %s" % (a.kind, seen, "ADMITTED" if ok else "REFUSED"))
    if not ok:
        raise ToolError(1)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen"); k.add_argument("--slot", type=int, required=True); k.add_argument("--replace", action="store_true")
    k.set_defaults(fn=cmd_keygen)
    pk = sub.add_parser("pubkeys"); pk.add_argument("--from", dest="from", type=Path); pk.set_defaults(fn=cmd_pubkeys)
    e = sub.add_parser("emit-pinned"); e.add_argument("--from", dest="from", type=Path)
    e.add_argument("--out", type=Path); e.add_argument("--json-out", type=Path); e.set_defaults(fn=cmd_emit_pinned)
    for name, fn in (("sign-image", cmd_sign_image), ("sign-catalog", cmd_sign_catalog), ("sign-fresh", cmd_sign_fresh)):
        s = sub.add_parser(name)
        s.add_argument("--version", type=int, required=True)
        s.add_argument("--slots", default="0,1")
        s.add_argument("--out", type=Path)
        if name == "sign-fresh":
            s.add_argument("--issued", type=int, required=True); s.add_argument("--valid-until", type=int, required=True)
            s.add_argument("--channel", type=int, default=1)
        else:
            s.add_argument("file", type=Path)
        s.set_defaults(fn=fn)
    v = sub.add_parser("verify"); v.add_argument("file", type=Path); v.add_argument("--kind", choices=sorted(KINDS), required=True)
    v.add_argument("--from", dest="from", type=Path); v.set_defaults(fn=cmd_verify)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
