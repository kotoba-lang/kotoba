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
  aiueos-image.py deploy --key SEED --remote-key RSEED --version N IMAGE
                                                            # sign, serve, install, reboot, check

serve answers each "AIUEGET1" request (UDP 7796: boot nonce, stream offset, length) with one
"AIUEDAT1" datagram to UDP 7795 (nonce, offset, length, then the bytes at that offset of SIGNED),
sent to the link's broadcast address (--broadcast, as aiueos-remote.py). The pull itself is started with `aiueos-remote.py update` (verify only) or `install` (AWAI-122 stage 4:
verify, write the ESP's staging file, read it back, then swap it in as BOOTX64.EFI).
The server is not trusted: the board checks the signature and the digest, and nothing is written.

deploy (AWAI-122 stage 5) is the disk-first development loop in one command: it signs IMAGE, serves it,
waits until the debug desktop's loop is running (its boot nonce heard three times), sends the signed install
command and requires install result 15 with BOOTX64.EFI hashing to IMAGE's SHA-256, then sends reboot and
waits for the next boot's ESP report (KDBG 0xc112..0xc115) to name the same SHA-256. It prints one JSON line.
That the next boot ran from disk follows only when nothing else serves the board (no PXE answer).
"""
import argparse, hashlib, importlib.util, json, socket, struct, sys, threading, time, types
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
    print(f"serving {path} ({len(data)} bytes) on UDP 7796", flush=True)
    serve_data(data, bind, broadcast, None)


def serve_data(data, bind, broadcast, stop):
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind((bind, 7796))
    rx.settimeout(0.5)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    served, last, start = 0, -1, None
    while stop is None or not stop.is_set():
        try:
            payload, _ = rx.recvfrom(2048)
        except socket.timeout:
            continue
        if len(payload) < 28 or payload[:8] != b"AIUEGET1": continue
        nonce, offset, length = struct.unpack_from("<QQI", payload, 8)
        if length > 1024 or offset > len(data): continue
        chunk = data[offset:offset + length]
        tx.sendto(b"AIUEDAT1" + struct.pack("<QQI", nonce, offset, len(chunk)) + chunk, (broadcast, 7795))
        if start is None: start = time.time()
        served += 1
        if offset <= last: print(f"repeat request at {offset}", file=sys.stderr, flush=True)
        last = offset
        if offset + length >= len(data):
            print(f"last chunk served: {served} datagrams in {time.time() - start:.1f} s", file=sys.stderr, flush=True)
            served, last, start = 0, -1, None


def read_seed(path):
    if path.stat().st_mode & 0o077: raise SystemExit(f"{path} must not be readable by others")
    seed = path.read_bytes(); assert len(seed) == 32, f"{path} must hold a 32-byte seed"
    return seed


def wait_loop(log, seconds):
    """The boot nonce once the desktop loop runs: the loop re-sends KDBG 0xC000, boot sends it once."""
    seen = {}
    for tag, value in remote.records(log, time.monotonic() + seconds):
        if tag == 0xC000:
            seen[value] = seen.get(value, 0) + 1
            if seen[value] >= 3: return value
    raise SystemExit("the debug desktop loop was not heard (KDBG 0xC000) on UDP 7799")


def deploy(args):
    image = args.image.read_bytes()
    sha = hashlib.sha256(image).hexdigest()
    data = signed(read_seed(args.key), args.version, image)
    rseed = read_seed(args.remote_key)
    stop = threading.Event()
    server = threading.Thread(target=serve_data, args=(data, "0.0.0.0", args.broadcast, stop), daemon=True)
    server.start()
    log = remote.listen(7799, 0.5)
    link = types.SimpleNamespace(broadcast=args.broadcast)
    report = dict(image=str(args.image), sha256=sha, version=args.version)
    try:
        nonce = wait_loop(log, args.wait)
        counter = time.time_ns()
        started = time.monotonic()
        remote.send(link, rseed, nonce, counter, 6, 0)
        got = {}
        for tag, value in remote.records(log, time.monotonic() + args.wait):
            if 0xC120 <= tag <= 0xC136 or tag in (0xC006, 0xC0FF): got[tag] = value
            if tag in (0xC006, 0xC0FF): break
        installed = "".join(f"{got.get(t, 0):016x}" for t in range(0xC133, 0xC137))
        report.update(nonce=f"{nonce:016x}", install=got.get(0xC006), refused=got.get(0xC0FF),
                      installSeconds=round(time.monotonic() - started, 1), bootx64AfterSwap=installed)
        if got.get(0xC006) != 15 or installed != sha:
            report["verdict"] = "INSTALL_FAILED"
            return report
        if args.no_reboot:
            report["verdict"] = "INSTALLED"
            return report
        remote.send(link, rseed, nonce, counter + 1, 2, 0)
        boot = {}
        for tag, value in remote.records(log, time.monotonic() + args.wait):
            if tag == 0xC000 and value != nonce: boot["nonce"] = value
            if "nonce" in boot and 0xC112 <= tag <= 0xC115: boot[tag] = value
            if all(t in boot for t in range(0xC112, 0xC116)): break
        booted = "".join(f"{boot.get(t, 0):016x}" for t in range(0xC112, 0xC116))
        report.update(rebootNonce=f"{boot.get('nonce', 0):016x}", bootx64AtNextBoot=booted,
                      verdict="DEPLOYED" if booted == sha else "REBOOT_UNCONFIRMED")
        return report
    finally:
        stop.set()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign"); s.add_argument("--key", type=Path, required=True)
    s.add_argument("--version", type=int, required=True); s.add_argument("image", type=Path); s.add_argument("out", type=Path)
    v = sub.add_parser("serve"); v.add_argument("signed", type=Path); v.add_argument("--bind", default="0.0.0.0")
    v.add_argument("--broadcast", default="10.77.0.255")
    sub.add_parser("fixture")
    d = sub.add_parser("deploy"); d.add_argument("--key", type=Path, required=True)
    d.add_argument("--remote-key", type=Path, required=True); d.add_argument("--version", type=int, required=True)
    d.add_argument("--broadcast", default="10.77.0.255"); d.add_argument("--wait", type=float, default=300.0)
    d.add_argument("--no-reboot", action="store_true"); d.add_argument("image", type=Path)
    args = p.parse_args()
    if args.cmd == "sign":
        seed = read_seed(args.key)
        args.out.write_bytes(signed(seed, args.version, args.image.read_bytes()))
        print(args.out, hashlib.sha256(args.image.read_bytes()).hexdigest())
    elif args.cmd == "serve":
        serve(args.signed, args.bind, args.broadcast)
    elif args.cmd == "deploy":
        report = deploy(args)
        print(json.dumps(report), flush=True)
        if report["verdict"] not in ("DEPLOYED", "INSTALLED"): raise SystemExit(1)
    else:
        header = signed(TEST_SEED, 1, fixture_image())[:128]
        print(" ".join(f"{i} {b}" for i, b in enumerate(header)))


if __name__ == "__main__":
    main()
