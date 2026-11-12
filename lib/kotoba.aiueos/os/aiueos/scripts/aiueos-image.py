#!/usr/bin/env python3
"""AWAI-122 stage 3: sign an OS image and serve it to the debug desktop over the RTL8168 link.

A signed image is a 128-byte header followed by the image bytes. The header is a 64-byte manifest
  0  "AIUEIMG1"   8 bytes
  8  version      8 bytes, little endian (at least 1)
 16  size         8 bytes, little endian (the image bytes that follow, at most 32 MiB)
 24  reserved     8 bytes, zero
 32  SHA-256 of the image
then an Ed25519 signature over those 64 bytes. The board pins the image-signing public key in
native/update.kotoba; its seed is a 32-byte file kept outside the repository.

  aiueos-image.py sign --key SEED --version N [--ledger FILE] IMAGE OUT     # OUT = header + IMAGE
  aiueos-image.py ledger-lookup --digest HEX [--ledger FILE]                # which version was this image signed as
  aiueos-image.py serve SIGNED                              # answer the board's requests
  aiueos-image.py fixture                                   # the kernel self-test constants

JUN-942 version ledger: every `sign` appends one JSON line {digest, version, date, signer, format, file} to an append-only operator-side
ledger (default ~/.itonami/aiueos-image-ledger.jsonl, mode 0600, directory 0700; --ledger FILE overrides) BEFORE the signed file is written. The
digest is the SHA-256 of the image bytes, which is what \\EFI\\ITONAMI\\BOOTX64.EFI hashes to on a board that runs the image; signer is the first
16 hex digits of SHA-256 of the Ed25519 public key; format is "AIUEIMG1". A ledger that cannot be appended to (unwritable, a symlink, not
mode 0600, an existing malformed line) stops the signing: nothing is skipped silently. The same digest is never signed at a second version
(refused), so a digest has exactly one version. `ledger-lookup` answers "which N does this board run": it prints VERSION N and the records,
exit 0; 1 when the digest is not in the ledger; 2 for an unreadable or malformed ledger; 3 when the ledger holds two versions for the digest.
The ledger is a lookup aid kept by the operator, not a signed or tamper-evident record; see docs/runbook-provision-board.md.

serve answers each "AIUEGET1" request (UDP 7796: boot nonce, stream offset, length) with one
"AIUEDAT1" datagram to UDP 7795 (nonce, offset, length, then the bytes at that offset of SIGNED),
sent to the link's broadcast address (--broadcast, as aiueos-remote.py). The pull itself is started with `aiueos-remote.py update` (verify only) or `install` (AWAI-122 stage 4:
verify, write the ESP's staging file, read it back, then swap it in as BOOTX64.EFI).
The server is not trusted: the board checks the signature and the digest, and nothing is written.
"""
import argparse, hashlib, importlib.util, json, os, re, socket, stat, struct, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("aiueos_remote", HERE / "aiueos-remote.py")
remote = importlib.util.module_from_spec(spec); spec.loader.exec_module(remote)

MAGIC = b"AIUEIMG1"
LIMIT = 32 << 20
# RFC 8032 section 7.1 test 1: the published seed, used only for the kernel self-test fixture.
TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
FIXTURE_SIZE = 5000


def manifest(version, image):
    assert 1 <= version < 1 << 63 and 0 < len(image) <= LIMIT
    return MAGIC + struct.pack("<QQQ", version, len(image), 0) + hashlib.sha256(image).digest()


def signed_with_key(seed, version, image):
    """(header + image, Ed25519 public key)."""
    m = manifest(version, image)
    sig, pub = remote.sign(seed, m)
    return m + sig + image, pub


def signed(seed, version, image):
    return signed_with_key(seed, version, image)[0]


# ---- JUN-942: the operator-side version ledger ----
FORMAT = "AIUEIMG1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def default_ledger():
    return Path.home() / ".itonami" / "aiueos-image-ledger.jsonl"


def key_id(pub):
    return hashlib.sha256(pub).hexdigest()[:16]


def read_ledger(path):
    """All records, in order. A missing file is an empty ledger; any malformed line raises ValueError naming it (never skipped)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    rows = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line:
            continue
        try:
            row = json.loads(line)
            ok = (isinstance(row, dict) and isinstance(row.get("digest"), str) and HEX64.fullmatch(row["digest"])
                  and type(row.get("version")) is int and 1 <= row["version"] < 1 << 63
                  and all(isinstance(row.get(k), str) and row[k] for k in ("date", "signer", "format", "file")))
        except ValueError:
            ok = False
        if not ok:
            raise ValueError("%s line %d is not a ledger record" % (path, number))
        rows.append(row)
    if text and not text.endswith("\n"):
        raise ValueError("%s ends in a partial line" % path)
    return rows


def append_ledger(path, digest, version, signer, file_name):
    """Append one record. Raises SystemExit (nothing signed) when the ledger is unusable or already holds this digest at another version."""
    path = Path(path)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise SystemExit("REFUSED: the version ledger %s cannot be opened for appending (%s); nothing was signed" % (path, error))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise SystemExit("REFUSED: the version ledger %s must be a regular file with mode 0600; nothing was signed" % path)
        try:
            known = [row for row in read_ledger(path) if row["digest"] == digest]
        except ValueError as error:
            raise SystemExit("REFUSED: %s; nothing was signed" % error)
        if any(row["version"] != version for row in known):
            raise SystemExit("REFUSED: the ledger already has this image (sha256 %s) signed as version %d; a digest keeps one version, change the image to sign another"
                             % (digest, known[0]["version"]))
        row = dict(digest=digest, version=version, date=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   signer=signer, format=FORMAT, file=file_name)
        line = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        try:
            if os.write(fd, line) != len(line):
                raise OSError("short write")
            os.fsync(fd)
        except OSError as error:
            raise SystemExit("REFUSED: appending to the version ledger %s failed (%s); nothing was signed" % (path, error))
    finally:
        os.close(fd)
    return row


def ledger_lookup(path, digest):
    """(exit status, text) for `ledger-lookup`."""
    digest = digest.strip().lower()
    if not HEX64.fullmatch(digest):
        return 2, "--digest must be 64 hex digits"
    try:
        rows = [row for row in read_ledger(path) if row["digest"] == digest]
    except (ValueError, OSError) as error:
        return 2, "LEDGER UNREADABLE: %s" % error
    if not rows:
        return 1, "NOT FOUND: sha256 %s is not in %s (an image signed on another machine, or not signed here)" % (digest, path)
    versions = sorted({row["version"] for row in rows})
    body = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    if len(versions) > 1:
        return 3, "AMBIGUOUS: the ledger holds versions %s for sha256 %s; do not guess\n%s" % (versions, digest, body)
    return 0, "VERSION %d\n%s" % (versions[0], body)


def fixture_image():
    return bytes((i * 31 + (i >> 8) * 7 + 1) & 255 for i in range(FIXTURE_SIZE))


def serve(path, bind, broadcast):
    data = path.read_bytes()
    assert data[:8] == MAGIC and len(data) == 128 + struct.unpack_from("<Q", data, 16)[0], "not a signed image"
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind((bind, 7796))
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    served, last, start = 0, -1, None
    print(f"serving {path} ({len(data)} bytes) on UDP 7796", flush=True)
    while True:
        payload, _ = rx.recvfrom(2048)
        if len(payload) < 28 or payload[:8] != b"AIUEGET1": continue
        nonce, offset, length = struct.unpack_from("<QQI", payload, 8)
        if length > 1024 or offset > len(data): continue
        chunk = data[offset:offset + length]
        tx.sendto(b"AIUEDAT1" + struct.pack("<QQI", nonce, offset, len(chunk)) + chunk, (broadcast, 7795))
        if start is None: start = time.time()
        served += 1
        if offset <= last: print(f"repeat request at {offset}", flush=True)
        last = offset
        if offset + length >= len(data):
            print(f"last chunk served: {served} datagrams in {time.time() - start:.1f} s", flush=True)
            served, last, start = 0, -1, None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign"); s.add_argument("--key", type=Path, required=True)
    s.add_argument("--version", type=int, required=True); s.add_argument("image", type=Path); s.add_argument("out", type=Path)
    s.add_argument("--ledger", type=Path, help="append-only version ledger (default ~/.itonami/aiueos-image-ledger.jsonl)")
    k = sub.add_parser("ledger-lookup"); k.add_argument("--digest", required=True, help="SHA-256 of the board's \\EFI\\ITONAMI\\BOOTX64.EFI, 64 hex digits")
    k.add_argument("--ledger", type=Path)
    v = sub.add_parser("serve"); v.add_argument("signed", type=Path); v.add_argument("--bind", default="0.0.0.0")
    v.add_argument("--broadcast", default="10.77.0.255")
    sub.add_parser("fixture")
    args = p.parse_args()
    if args.cmd == "sign":
        if args.key.stat().st_mode & 0o077: raise SystemExit("the key file must not be readable by others")
        seed = args.key.read_bytes(); assert len(seed) == 32, "the key file must hold a 32-byte seed"
        image = args.image.read_bytes()
        blob, pub = signed_with_key(seed, args.version, image)
        digest = hashlib.sha256(image).hexdigest()
        ledger = args.ledger or default_ledger()
        append_ledger(ledger, digest, args.version, key_id(pub), args.out.name)    # before the signed file exists; refuses, never skips
        args.out.write_bytes(blob)
        print(args.out, digest)
        print("ledger %s: version %d" % (ledger, args.version), file=sys.stderr)
    elif args.cmd == "ledger-lookup":
        status, text = ledger_lookup(args.ledger or default_ledger(), args.digest)
        print(text, file=sys.stderr if status else sys.stdout)
        raise SystemExit(status)
    elif args.cmd == "serve":
        serve(args.signed, args.bind, args.broadcast)
    else:
        header = signed(TEST_SEED, 1, fixture_image())[:128]
        print(" ".join(f"{i} {b}" for i, b in enumerate(header)))


if __name__ == "__main__":
    main()
