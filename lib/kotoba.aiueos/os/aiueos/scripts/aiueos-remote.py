#!/usr/bin/env python3
"""AWAI-119 stage 3: send signed commands to the debug desktop over the RTL8168 link.

The board broadcasts its boot nonce as KDBG tag 0xC000 on UDP 7799. A command is one UDP datagram to
port 7798 (sent to the link's broadcast address): "AIUECMD1", nonce, counter, command, argument, then an
Ed25519 signature over those 32 bytes with the operator's key (a 32-byte seed file, kept outside the
repository; its public key is pinned in native/remote_cmd.kotoba). Replies are KDBG records on 7799;
a screenshot arrives on 7797 and is written as a PNG.

  aiueos-remote.py --key SEED ping
  aiueos-remote.py --key SEED key 2          # scan code 0x02 (the "1" key)
  aiueos-remote.py --key SEED type aba       # make codes for a-z and space
  aiueos-remote.py --key SEED shot out.png
  aiueos-remote.py --key SEED reboot

This tool only signs, sends and observes; the board decides. It is a diagnostic channel for the opt-in
debug entry on a direct cable, not a product remote-access service.
"""
import argparse, hashlib, socket, struct, time, zlib
from pathlib import Path

# --- RFC 8032 Ed25519 (signing on the operator's Mac) ---
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_BX = 0x216936D3CD6E53FEC0A4E231FDD6DC5C692CC7609525A7B2C9562D608F25D51A
_BY = 0x6666666666666666666666666666666666666666666666666666666666666658
_B = (_BX, _BY, 1, _BX * _BY % _P)


def _add(p, q):
    x1, y1, z1, t1 = p; x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P; b = (y1 + x1) * (y2 + x2) % _P
    c = t1 * t2 * 2 * _D % _P; d = 2 * z1 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, h * g % _P, f * g % _P, e * h % _P)


def _mul(s, p):
    r = (0, 1, 1, 0)
    for i in range(255, -1, -1):
        r = _add(r, r)
        if (s >> i) & 1: r = _add(r, p)
    return r


def _enc(p):
    x, y, z, _ = p; zi = pow(z, _P - 2, _P); x = x * zi % _P; y = y * zi % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def sign(seed, msg):
    h = hashlib.sha512(seed).digest()
    a = bytearray(h[:32]); a[0] &= 248; a[31] &= 127; a[31] |= 64
    a = int.from_bytes(a, "little")
    pub = _enc(_mul(a, _B))
    r = int.from_bytes(hashlib.sha512(h[32:] + msg).digest(), "little") % _L
    big_r = _enc(_mul(r, _B))
    k = int.from_bytes(hashlib.sha512(big_r + pub + msg).digest(), "little") % _L
    return big_r + ((r + k * a) % _L).to_bytes(32, "little"), pub


SCAN = {**{c: v for c, v in zip("qwertyuiop", range(16, 26))},
        **{c: v for c, v in zip("asdfghjkl", range(30, 39))},
        **{c: v for c, v in zip("zxcvbnm", range(44, 51))}, " ": 57}


def listen(port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
    s.bind(("", port)); s.settimeout(timeout)
    return s


def records(sock, until):
    while time.monotonic() < until:
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        parts = data.decode(errors="replace").split()
        if len(parts) == 3 and parts[0] == "AIUEOS_KDBG":
            yield int(parts[1], 16), int(parts[2], 16)


def wait_nonce(sock, seconds):
    for tag, value in records(sock, time.monotonic() + seconds):
        if tag == 0xC000:
            return value
    raise SystemExit("no boot nonce (KDBG 0xC000) heard on UDP 7799")


def send(args, seed, nonce, counter, command, argument):
    msg = b"AIUECMD1" + struct.pack("<QQII", nonce, counter, command, argument)
    sig, _ = sign(seed, msg)
    out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    out.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    out.sendto(msg + sig, (args.broadcast, 7798))


def reply(sock, tags, seconds):
    for tag, value in records(sock, time.monotonic() + seconds):
        if tag in tags or tag == 0xC0FF:
            return tag, value
    return None


def write_png(path, width, height, rows):
    raw = b"".join(b"\x00" + rows.get(y, bytes(3 * width)) for y in range(height))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--key", type=Path, required=True, help="32-byte Ed25519 seed file (mode 0600)")
    p.add_argument("--broadcast", default="10.77.0.255")
    p.add_argument("--wait", type=float, default=15.0, help="seconds to wait for the nonce and replies")
    p.add_argument("command", choices=("ping", "reboot", "key", "type", "shot"))
    p.add_argument("value", nargs="?")
    args = p.parse_args()
    if args.key.stat().st_mode & 0o077:
        raise SystemExit("the key file must not be readable by others")
    seed = args.key.read_bytes()
    assert len(seed) == 32, "the key file must hold a 32-byte seed"
    log = listen(7799, 0.5)
    shots = listen(7797, 0.5) if args.command == "shot" else None
    nonce = wait_nonce(log, args.wait)
    counter = time.time_ns()
    print(f"nonce {nonce:016x}")
    if args.command == "ping":
        send(args, seed, nonce, counter, 1, 0); print(reply(log, {0xC001}, args.wait))
    elif args.command == "reboot":
        send(args, seed, nonce, counter, 2, 0); print(reply(log, {0xC002}, args.wait))
    elif args.command == "key":
        send(args, seed, nonce, counter, 3, int(args.value, 0)); print(reply(log, {0xC003}, args.wait))
    elif args.command == "type":
        for i, ch in enumerate(args.value):
            send(args, seed, nonce, counter + i, 3, SCAN[ch]); print(ch, reply(log, {0xC003}, args.wait))
    elif args.command == "shot":
        send(args, seed, nonce, counter, 4, 0)
        assert shots is not None
        rows, width, height, fmt, last = {}, 0, 0, 0, 0.0
        until = time.monotonic() + max(args.wait, 30)
        while time.monotonic() < until:
            try:
                data, _ = shots.recvfrom(4096)
            except socket.timeout:
                if rows and time.monotonic() > last + 2: break
                continue
            if data[:8] != b"AIUESHOT": continue
            y, chunk, fmt, width = struct.unpack_from("<HBBH", data, 8)
            px = data[14:14 + 800]
            rgb = b"".join((px[i + 2:i + 3] + px[i + 1:i + 2] + px[i:i + 1]) if fmt == 1 else px[i:i + 3]
                           for i in range(0, len(px), 4))
            row = bytearray(rows.get(y, bytes(3 * width)))
            row[600 * chunk:600 * chunk + len(rgb)] = rgb
            rows[y] = bytes(row[:3 * width]); height = max(height, y + 1); last = time.monotonic()
        write_png(args.value or "aiueos-shot.png", width, height, rows)
        print(f"{len(rows)} rows, {width}x{height} -> {args.value}", reply(log, {0xC004}, 5))


if __name__ == "__main__":
    main()
