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

  aiueos-image.py sign --key SEED --version N IMAGE OUT     # OUT = header + IMAGE
  aiueos-image.py serve SIGNED                              # answer the board's requests
  aiueos-image.py fixture                                   # the kernel self-test constants

serve answers each "AIUEGET1" request (UDP 7796: boot nonce, stream offset, length) with one
"AIUEDAT1" datagram to UDP 7795 (nonce, offset, length, then the bytes at that offset of SIGNED),
sent to the link's broadcast address (--broadcast, as aiueos-remote.py). The pull itself is started with `aiueos-remote.py update` (verify only) or `install` (AWAI-122 stage 4:
verify, write the ESP's staging file, read it back, then swap it in as BOOTX64.EFI).
The server is not trusted: the board checks the signature and the digest, and nothing is written.
"""
import argparse, hashlib, importlib.util, socket, struct, time
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


def signed(seed, version, image):
    m = manifest(version, image)
    sig, _ = remote.sign(seed, m)
    return m + sig + image


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
    v = sub.add_parser("serve"); v.add_argument("signed", type=Path); v.add_argument("--bind", default="0.0.0.0")
    v.add_argument("--broadcast", default="10.77.0.255")
    sub.add_parser("fixture")
    args = p.parse_args()
    if args.cmd == "sign":
        if args.key.stat().st_mode & 0o077: raise SystemExit("the key file must not be readable by others")
        seed = args.key.read_bytes(); assert len(seed) == 32, "the key file must hold a 32-byte seed"
        args.out.write_bytes(signed(seed, args.version, args.image.read_bytes()))
        print(args.out, hashlib.sha256(args.image.read_bytes()).hexdigest())
    elif args.cmd == "serve":
        serve(args.signed, args.bind, args.broadcast)
    else:
        header = signed(TEST_SEED, 1, fixture_image())[:128]
        print(" ".join(f"{i} {b}" for i, b in enumerate(header)))


if __name__ == "__main__":
    main()
