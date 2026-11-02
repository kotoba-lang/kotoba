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
  aiueos-remote.py --key SEED usb-select 0x0600  # profile6 only, one xHCI host at a time
  aiueos-remote.py --key SEED --wait 600 update   # pull and verify the image `aiueos-image.py serve` offers
  aiueos-remote.py --key SEED --wait 600 install  # pull, verify and install it as BOOTX64.EFI on the ESP

This tool only signs, sends and observes; the board decides. It is a diagnostic channel for the opt-in
debug entry on a direct cable, not a product remote-access service.
"""
import argparse, hashlib, json, socket, struct, time, zlib
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


def receive_band(sock, nonce, counter, first, count, seconds):
    """Reject stale/malformed bands; never fill missing pixels with black."""
    chunks = {}; geometry = None; until = time.monotonic()+seconds
    while time.monotonic() < until:
        try: data, _ = sock.recvfrom(4096)
        except socket.timeout: continue
        if len(data) < 34 or data[:8] != b'AIUEBND2': continue
        _,boot,request,y,chunk,fmt,width,height,valid = struct.unpack_from('<8sQQHBBHHH',data)
        if (boot,request) != (nonce,counter): continue
        if not (len(data)==834 and 0<width<=3200 and first+count<=height<=8192 and
                first<=y<first+count and fmt in (0,1) and chunk<(width+199)//200 and
                valid==min(200,width-chunk*200)):
            raise RuntimeError('malformed native screenshot band')
        if geometry is None: geometry=(width,height,fmt)
        if geometry != (width,height,fmt): raise RuntimeError('band geometry changed')
        rgb=bytearray()
        for at in range(34,34+valid*4,4):
            a,b,c,_=data[at:at+4];rgb.extend((a,b,c) if fmt==0 else (c,b,a))
        key=(y,chunk); value=bytes(rgb)
        if key in chunks and chunks[key] != value: raise RuntimeError('conflicting band duplicate')
        chunks[key]=value
        if len(chunks)==count*((width+199)//200):
            return width,height,b''.join(chunks[y,c] for y in range(first,first+count) for c in range((width+199)//200))
    raise RuntimeError('incomplete native screenshot band')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--key", type=Path, required=True, help="32-byte Ed25519 seed file (mode 0600)")
    p.add_argument("--broadcast", default="10.77.0.255")
    p.add_argument("--wait", type=float, default=15.0, help="seconds to wait for the nonce and replies")
    p.add_argument("--nonce", type=lambda value: int(value, 0), help="explicit last-observed boot nonce when periodic discovery is unavailable; stale values are refused by the board")
    p.add_argument("command", choices=("ping", "reboot", "key", "type", "shot", "update", "install", "usb-select", "bt-probe", "ble-init", "ble-crypto", "ble-scan", "ble-connect", "ble-status", "ble-firmware", "render-stats", "pointer", "console-key"))
    p.add_argument("value", nargs="?")
    args = p.parse_args()
    if args.nonce is not None and not 0 < args.nonce < 1 << 64:
        p.error("--nonce must be a nonzero unsigned 64-bit boot nonce")
    if args.key.stat().st_mode & 0o077:
        raise SystemExit("the key file must not be readable by others")
    seed = args.key.read_bytes()
    assert len(seed) == 32, "the key file must hold a 32-byte seed"
    log = listen(7799, 0.5)
    shots = listen(7797, 0.5) if args.command == "shot" else None
    nonce = args.nonce if args.nonce is not None else wait_nonce(log, args.wait)
    counter = time.time_ns()
    print(f"nonce {nonce:016x}")
    if args.command == "ping":
        send(args, seed, nonce, counter, 1, 0); print(reply(log, {0xC001}, args.wait))
    elif args.command in ("pointer", "console-key"):
        if args.value is None:
            p.error(args.command + " requires an argument")
        if args.command == "pointer":
            try:
                x, y, pressed = (int(v, 0) for v in args.value.split(','))
            except (ValueError, TypeError):
                p.error("pointer expects x,y,left-button (0 or 1)")
            if not (0 <= x < 8192 and 0 <= y < 8192 and pressed in (0, 1)):
                p.error("pointer outside finite coordinate/button range")
            command, argument = 18, x | (y << 13) | (pressed << 26)
        else:
            try: argument = int(args.value, 0)
            except ValueError: p.error("console-key expects a scan code")
            if not 0 < argument < 128: p.error("scan code outside1..127")
            command = 19
        send(args, seed, nonce, counter, command, argument)
        accepted = reply(log, {0xC000+command}, args.wait)
        if accepted is None or accepted[0] == 0xC0FF or accepted[1] != counter:
            raise RuntimeError(f"console input not accepted: {accepted}")
        print(json.dumps(dict(command=args.command, acceptedCounter=counter, argument=argument,
                              presentationConfirmed=False)))
    elif args.command == "render-stats":
        if args.value is not None:
            p.error("render-stats takes no argument")
        send(args, seed, nonce, counter, 17, 0)
        values = {}; complete = False
        for tag, value in records(log, time.monotonic() + args.wait):
            if 0xC380 <= tag <= 0xC397:
                values[tag] = value
            if tag == 0xC0FF:
                raise RuntimeError(f"renderer statistics refused: {value}")
            if tag == 0xC011 and value == counter:
                complete = True
                break
        if not complete or len(values) != 24:
            raise RuntimeError("incomplete renderer statistics reply")
        names = ('cyclesPerMS', 'listCycles', 'damageCycles', 'composeCycles', 'cacheCycles',
                 'totalCycles', 'sceneLastCycles', 'sceneMaxCycles', 'pointerLastCycles',
                 'sceneFrames', 'pointerFrames', 'profileFrames', 'tiles', 'tileStores',
                 'lastMode', 'tiledFrames', 'sceneListCycles', 'sceneDamageCycles',
                 'sceneCacheCycles', 'sceneTotalCycles', 'tileRasterCycles', 'tileCopyCycles',
                 'sceneTileRasterCycles', 'sceneTileCopyCycles')
        print(json.dumps(dict(zip(names, (values[0xC380+i] for i in range(24)))), sort_keys=True))
    elif args.command == "reboot":
        send(args, seed, nonce, counter, 2, 0); print(reply(log, {0xC002}, args.wait))
    elif args.command in ("update", "install"):
        # AWAI-122 stage 3: the board pulls the image, then reports KDBG 0xC120..0xC127 and 0xC005;
        # stage 4 (install) also writes the ESP and reports 0xC130..0xC136 and 0xC006.
        done = 0xC005 if args.command == "update" else 0xC006
        send(args, seed, nonce, counter, 5 if args.command == "update" else 6, 0)
        for tag, value in records(log, time.monotonic() + args.wait):
            if 0xC120 <= tag <= 0xC127 or 0xC130 <= tag <= 0xC136 or tag in (0xC141, done, 0xC0FF):
                print(f"{tag:04x} {value:016x}", flush=True)
            if tag in (done, 0xC0FF):
                break
    elif args.command in ("usb-select", "bt-probe", "ble-init", "ble-crypto", "ble-scan", "ble-connect", "ble-status", "ble-firmware"):
        slot = int(args.value, 0)
        if not 0 <= slot <= 65535:
            raise SystemExit("PCI slot must be bus<<8 | device<<3 | function (0..65535)")
        done = {"usb-select": 0xC007, "bt-probe": 0xC008, "ble-init": 0xC009, "ble-crypto": 0xC00A, "ble-scan": 0xC00B, "ble-connect": 0xC00C, "ble-status": 0xC00D, "ble-firmware": 0xC010}[args.command]
        send(args, seed, nonce, counter, {"usb-select": 7, "bt-probe": 8, "ble-init": 9, "ble-crypto": 10, "ble-scan": 11, "ble-connect": 12, "ble-status": 13, "ble-firmware": 16}[args.command], slot)
        for tag, value in records(log, time.monotonic() + args.wait):
            if tag in (done, 0xC0FF) or 0xC170 <= tag <= 0xC172 or 0xC180 <= tag <= 0xC1FF:
                print(f"{tag:04x} {value:016x}", flush=True)
            if tag in (done, 0xC0FF):
                break
        else:
            raise SystemExit("no USB selection result received")
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
