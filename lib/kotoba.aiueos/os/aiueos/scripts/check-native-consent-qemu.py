#!/usr/bin/env python3
"""Drive the native desktop's consent surface (ADR-0275 W1) in QEMU and check it.

Boots the consent-entry image (goal-model profile), opens Itonami, types a Goal and presses
Enter, then checks, from guest memory and from the rendered frame:
  the panel is the whole desktop (no dock, nothing to click under it), N and the Deny
  button deny, the Allow button approves exactly as Y does, and a launcher key/click while
  the request is pending does nothing. HMP keys and clicks are synthetic and prove no human
  consent. Reads guest words with xp and pixels from screendump; no guest agent, NIC or VNC.
"""
import argparse, hashlib, json, re, struct, subprocess, sys, tempfile, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")

def pin(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

# --- reference Ed25519 (RFC 8032) used to check what the guest derived and signed ---
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

def _dec(b):
    y = int.from_bytes(b, "little"); sign = y >> 255; y &= (1 << 255) - 1
    if y >= _P: return None
    u = (y * y - 1) % _P; v = (_D * y * y + 1) % _P
    x = pow(u * pow(v, _P - 2, _P), (_P + 3) // 8, _P)
    if (v * x * x - u) % _P: x = x * pow(2, (_P - 1) // 4, _P) % _P
    if (v * x * x - u) % _P: return None
    if (x & 1) != sign: x = _P - x
    return (x, y, 1, x * y % _P)

def ed_public(seed):
    h = bytearray(hashlib.sha512(seed).digest()[:32]); h[0] &= 248; h[31] &= 127; h[31] |= 64
    return _enc(_mul(int.from_bytes(h, "little"), _B))

def ed_verify(pub, msg, sig):
    a = _dec(pub); r = _dec(sig[:32])
    if a is None or r is None: return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L: return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _enc(_mul(s, _B)) == _enc(_add(r, _mul(k, a)))

def _kdf(pw, salt, iters):
    h = hashlib.sha512(pw.ljust(32, b"\0") + salt).digest()
    for _ in range(iters - 1): h = hashlib.sha512(h + salt).digest()
    return h

def unseal(pw, blob, iters=1024):
    """The aiueos.keyseal construction: blob = salt16 || ct32 || tag16; None when the tag does not match."""
    salt, ct, tag = blob[:16], blob[16:48], blob[48:]
    k = _kdf(pw, salt, iters)
    if hashlib.sha512(k[32:] + salt + ct).digest()[:16] != tag: return None
    return bytes(a ^ b for a, b in zip(ct, k[:32]))

def main(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    image = args.kernel.read_bytes()
    rw = struct.unpack_from('<IIQQQQQQ', image, 120)
    context = rw[3]
    assert rw[5] == 0x240000 and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    surface, work = context + 0x238000, context + 0x23a000
    # A provisioned 64 KiB scratch disk (test fixture, as in the draft restart gate): the draft save (F5) then really
    # runs against it and uses the browser context scratch 512..2559.
    scratch = out / "scratch.raw"
    raw_disk = bytearray(128 * 512)
    struct.pack_into("<4I", raw_disk, 0, 0x49415741, 0x54465244, 1, 128)
    scratch.write_bytes(raw_disk)
    cmd = [str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware}",
           "-drive", f"file={args.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-nic", "none", "-display", "none", "-no-reboot", "-monitor", "stdio",
           "-device", "isa-ide,id=draft-controller", "-drive", f"file={scratch},format=raw,if=none,id=draft,cache=directsync",
           "-device", "ide-hd,drive=draft,bus=draft-controller.0,unit=1,serial=AWAI90DRAFT000001"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, cwd=out, bufsize=1)
    import os, select
    def send(line, wait=0.4):
        proc.stdin.write(line + "\n"); proc.stdin.flush(); time.sleep(wait)
    def drain():
        text = ""
        while select.select([proc.stdout], [], [], 0.2)[0]:
            chunk = os.read(proc.stdout.fileno(), 65536).decode(errors="replace")
            if not chunk: break
            text += chunk
        return text
    def read(addr):
        drain(); send(f"xp /1wx {addr:#x}", 0.5)
        found = re.findall(r"[0-9a-f]{16}: 0x([0-9a-f]{8})", drain())
        assert found, ("xp gave nothing", hex(addr))
        return int(found[-1], 16)
    S = lambda i: read(surface + 4 * i)
    W = lambda i: read(work + 4 * i)
    events = []
    def event(name, **detail):
        events.append(dict(name=name, **detail))
    def screenshot(name):
        send(f"screendump {name}.ppm", 2.0)
        raw = (out / f"{name}.ppm").read_bytes()
        _, dims, _, pixels = raw.split(b"\n", 3)
        width, height = map(int, dims.split())
        return width, height, pixels
    def pixel(shot, x, y):
        width, _, pixels = shot
        o = 3 * (y * width + x)
        return tuple(pixels[o:o + 3])
    try:
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if W(79) >= 1: break
            time.sleep(2)
        assert W(79) >= 1, "no first frame"
        event("first-frame", frames=W(79))
        # W3a: word 90 reports the CPU's entropy instructions (QEMU -cpu max has both); availability only,
        # two RDRAND draws are checked to be non-zero and different.
        entropy = W(90)
        assert entropy == 7, hex(entropy)
        draw_a, draw_b = W(91), W(92)
        # Two draws of the guest's RDRAND (QEMU draws them from the host): each is non-zero and they differ
        # (a stuck source or a failed instruction would give 0 or a repeat).
        assert draw_a != 0 and draw_b != 0 and draw_a != draw_b, (hex(draw_a), hex(draw_b))
        event("entropy-probe", flags=entropy, rdrand=bool(entropy & 1), rdseed=bool(entropy & 2),
              leaf7=bool(entropy & 4), drawn=True, distinctNonZeroDraws=True)
        send("sendkey 2", 1.5); send("sendkey a", 1.5)
        assert S(1) == 1 and S(2) == 2 and S(2038) == 13, (S(1), S(2), S(2038))
        event("itonami-goal-typed", goalLength=S(2038))
        def move_to(x, y):
            for _ in range(60):
                cx, cy = S(2046) - 1, S(2047)
                dx, dy = x - cx, y - cy
                if abs(dx) <= 2 and abs(dy) <= 2: return cx, cy
                step = lambda v: max(-100, min(100, v))
                send(f"mouse_move {step(dx)} {step(dy)}", 0.4)
            raise AssertionError(("pointer did not reach target", x, y, S(2046), S(2047), W(40), W(41), W(87), hex(S(2039))))
        def click():
            send("mouse_button 1", 0.5); send("mouse_button 0", 1.5)
        # window collapse (roll up to the titlebar): F9, then the control left of close
        wx, wy, ww, wh = S(6), S(7), S(8), S(9)
        full = wh
        assert wh > 100 and ww > 100, (wx, wy, ww, wh)
        send("sendkey f9", 1.5)
        assert S(9) == 29 and S(2038) == 13, S(9)
        shot = screenshot("collapsed")
        assert pixel(shot, wx + 100, wy + 60) != (255, 255, 255), "collapsed window still has a body"
        send("sendkey f9", 1.5)
        assert S(9) == full and S(7) == wy, (S(9), S(7))
        event("collapse-key", collapsed=29, restored=full)
        move_to(wx + ww - 36, wy + 14); click()
        assert S(9) == 29 and S(2038) == 13
        click()
        assert S(9) == full and S(2038) == 13
        event("collapse-click", collapsed=29, restored=full, goalLength=S(2038))
        send("sendkey ret", 1.5)
        assert W(87) == 1 and S(2039) == 1 and W(88) == 0 and W(85) == 0
        shot = screenshot("consent-open")
        width, height, _ = shot
        px, py = (width - 480) // 2, (height - 224) // 2
        allow = pixel(shot, px + 24 + 70, py + 164 + 4)
        assert allow == (60, 179, 34), allow
        assert pixel(shot, width // 2, height - 30) == (0x8f, 0xb5, 0xd8), "dock still drawn under the panel"
        assert pixel(shot, px + 1, py + 100) == (0x3b, 0x82, 0xff), "panel border missing"
        event("consent-open", panel=[px, py, 480, 224], allowPixel=allow, dockHidden=True)
        # modal: a launcher key and a launcher click do nothing while the request is pending
        send("sendkey 3", 1.5)
        assert S(1) == 1 and W(87) == 1 and S(2039) == 1
        event("launcher-key-ignored", windows=S(1))
        move_to(150, 14); click()
        assert S(1) == 1 and W(87) == 1 and S(2039) == 1
        event("launcher-click-ignored", windows=S(1))
        # N denies
        send("sendkey n", 1.5)
        assert W(87) == 0 and S(2039) == 0 and W(88) == 0 and W(85) == 0 and S(2038) == 13
        shot = screenshot("after-key-deny")
        assert pixel(shot, width // 2, height - 30) != (0x8f, 0xb5, 0xd8), "dock not back after deny"
        event("key-deny", goalLength=S(2038), approved=W(88))
        # Deny button
        send("sendkey ret", 1.5); assert W(87) == 1 and S(2039) == 1
        move_to(px + 180 + 70, py + 164 + 18); click()
        assert W(87) == 0 and S(2039) == 0 and W(88) == 0 and W(85) == 0 and S(2038) == 13
        event("pointer-deny", approved=W(88), goalLength=S(2038))
        # Esc denies
        send("sendkey ret", 1.5); assert W(87) == 1 and S(2039) == 1
        send("sendkey esc", 1.5)
        assert W(87) == 0 and S(2039) == 0 and W(88) == 0 and W(85) == 0
        event("esc-deny", approved=W(88))
        # Allow button approves exactly as Y does: pending 0, approved 1, loop stop 1.
        # Word 2039 keeps the Allow count in bits 1 and up (W2): the home line
        # "Approved: n" changes only in its digit, and only after an Allow.
        # --- ADR-0277 W3: the device key through its own consent request (F8) ---
        # Deny first: N closes the request and no entropy is consumed (the seed bytes stay 0).
        seed_words = lambda: [W(928 + i) for i in range(8)]
        assert S(2039) == 0 and seed_words() == [0] * 8 and W(94) == 0
        send("sendkey f8", 1.5); assert W(87) == 2 and S(2039) == 3, (W(87), S(2039))
        key_panel = screenshot("key-request")
        send("sendkey n", 1.5)
        assert W(87) == 0 and S(2039) == 0 and seed_words() == [0] * 8 and W(94) == 3
        event("key-deny", seedBytes=seed_words(), approvedCount=0)
        # Allow by key Y: a 32-byte seed is drawn, the public key derived, a proof message signed.
        # Allow on the key request opens the passphrase request; no entropy is drawn until it is confirmed.
        def panel_band(shot, y0, y1):
            wd = shot[0]
            return [shot[2][3 * (y * wd + x):3 * (y * wd + x) + 3] for y in range(py + y0, py + y1) for x in range(px + 20, px + 460)]
        keyname = lambda ch: "spc" if ch == " " else ch
        def type_text(text):
            for ch in text: send("sendkey " + keyname(ch), 0.6)
        send("sendkey f8", 1.5); assert W(87) == 2 and S(2039) == 3
        send("sendkey y", 1.5)
        assert W(87) == 4 and S(2039) == 3 + 2**31 and seed_words() == [0] * 8, (W(87), hex(S(2039)))
        pass_panel = screenshot("passphrase-request")
        assert panel_band(pass_panel, 52, 100) != panel_band(key_panel, 52, 100), "the passphrase panel must read differently"
        # too short: Enter is ignored; letters count, stars follow; Backspace removes one; Esc cancels and wipes
        type_text("abc"); assert S(2039) == 3 + 2**31 + 3 * 256 and W(95) == 3
        typed_panel = screenshot("passphrase-typed")
        def stars(shot):
            wd = shot[0]
            return sum(1 for y in range(py + 104, py + 128) for x in range(px + 120, px + 200)
                       if shot[2][3 * (y * wd + x):3 * (y * wd + x) + 3] != b"\xff\xff\xff")
        assert stars(pass_panel) == 0 and stars(typed_panel) > 10, (stars(pass_panel), stars(typed_panel))
        assert panel_band(typed_panel, 164, 200) == panel_band(pass_panel, 164, 200), "only the passphrase line changes"
        send("sendkey ret", 1.5); assert W(87) == 4 and seed_words() == [0] * 8, "a 3-letter passphrase must be ignored"
        type_text("d"); assert W(95) == 4 and S(2039) == 3 + 2**31 + 4 * 256
        send("sendkey backspace", 0.8); assert W(95) == 3 and S(2039) == 3 + 2**31 + 3 * 256
        assert [W(832 + i) for i in range(8)] != [0] * 8, "the typed letters are in the buffer"
        send("sendkey esc", 1.5)
        assert W(87) == 0 and S(2039) == 0 and W(94) == 6 and W(95) == 0, (W(87), hex(S(2039)), W(94))
        assert seed_words() == [0] * 8 and [W(832 + i) for i in range(8)] == [0] * 8, "cancel must wipe and draw nothing"
        event("passphrase-cancel", seedBytes=seed_words(), bufferWiped=True)
        # Allow, then a real passphrase, then Enter: the seed is drawn, the proof signed, the seed sealed
        send("sendkey f8", 1.5); assert W(87) == 2 and S(2039) == 3
        send("sendkey y", 1.5); assert W(87) == 4
        type_text("correct horsex"); send("sendkey backspace", 0.8)
        assert W(95) == 13 and S(2039) == 3 + 2**31 + 13 * 256
        send("sendkey ret", 6.0)
        assert W(87) == 0 and W(94) == 1, (W(87), W(94))
        assert W(97) == 1 and W(96) == 0, ("the sealed blob must be stored on the scratch disk", W(97), W(96))
        flags = S(2039)
        assert flags & 3 == 0 and (flags >> 2) & 15 == 1 and (flags >> 6) & 1 == 1, hex(flags)
        seed = b"".join(struct.pack("<I", W(928 + i)) for i in range(8))
        pub = b"".join(struct.pack("<I", W(320 + i)) for i in range(8))
        sig = b"".join(struct.pack("<I", W(768 + i)) for i in range(16))
        proof = b"itonami-w3-key-proof"
        assert seed != bytes(32) and len(set(seed)) > 8, "seed looks empty or constant"
        assert pub == ed_public(seed), ("the guest public key is not the key of its seed", pub.hex())
        blob = b"".join(struct.pack("<I", W(848 + i)) for i in range(16))
        assert unseal(b"correct horse", blob) == seed, "the sealed blob does not open to the seed under the passphrase"
        assert unseal(b"correct horsf", blob) is None and unseal(b"correct", blob) is None, "a wrong passphrase must not open the blob"
        assert blob[16:48] != seed and blob[:16] != bytes(16), "the seed must not be stored in the clear and the salt must be drawn"
        assert [W(832 + i) for i in range(8)] == [0] * 8, "the passphrase buffer must be wiped after sealing"
        assert ed_verify(pub, proof, sig), "the guest signature does not verify under its public key"
        # negative controls: a foreign key, a changed message and a changed signature are refused
        foreign = ed_public(bytes(range(32)))
        assert not ed_verify(foreign, proof, sig), "a foreign key must not verify"
        assert not ed_verify(pub, proof + b"!", sig), "a changed message must not verify"
        assert not ed_verify(pub, proof, sig[:63] + bytes([sig[63] ^ 1])), "a changed signature must not verify"
        fp = (flags >> 7) & 0xffffff
        assert fp == int.from_bytes(pub[:3], "big"), (hex(fp), pub[:3].hex())
        key_home = screenshot("key-home")
        # a second request is refused while a key exists (one device key per boot)
        send("sendkey f8", 1.5); assert W(87) == 0 and S(2039) == flags
        event("key-allow", sealed=True, blob=blob.hex(), fingerprint=pub[:3].hex(), publicKey=pub.hex(), proofMessage=proof.decode(),
              signature=sig.hex(), verifies=True, foreignKeyRefused=True, changedMessageRefused=True,
              changedSignatureRefused=True, seedDisplayed=False, persisted=False)
        # --- W3 consent-bound signing (F7): a sign request of its own kind, its own consent text ---
        base = S(2039)
        sig_words = lambda: [W(800 + i) for i in range(16)]
        challenge = b"itonami-w3-sign-test"
        assert W(87) == 0 and base & 3 == 0 and (base >> 31) == 0 and sig_words() == [0] * 16
        send("sendkey f7", 1.5)
        assert W(87) == 3 and S(2039) == base + 2**31 + 3, (W(87), hex(S(2039)))
        sign_panel = screenshot("sign-request")
        assert panel_band(sign_panel, 52, 100) == panel_band(key_panel, 52, 100), "service/endpoint lines must be the key request's"
        assert panel_band(sign_panel, 100, 156) != panel_band(key_panel, 100, 156), "action/data lines must differ from the key request"
        send("sendkey n", 1.5)
        assert W(87) == 0 and S(2039) == base and sig_words() == [0] * 16 and W(94) == 5
        event("sign-deny", signatureWords=sig_words(), approvedCount=(S(2039) >> 2) & 15, signed=False)
        send("sendkey f7", 1.5); assert W(87) == 3
        send("sendkey y", 3.0)
        assert W(87) == 0 and W(94) == 4 and S(2039) & 3 == 0 and (S(2039) >> 31) == 0, (W(87), W(94), hex(S(2039)))
        assert (S(2039) >> 2) & 15 == ((base >> 2) & 15) + 1 and (S(2039) >> 6) & 1 == 1
        pub2 = b"".join(struct.pack("<I", W(320 + i)) for i in range(8))
        sig2 = b"".join(struct.pack("<I", W(800 + i)) for i in range(16))
        assert pub2 == pub and sig2 != bytes(64)
        assert ed_verify(pub2, challenge, sig2), "the challenge signature does not verify under the device key"
        assert not ed_verify(foreign, challenge, sig2), "a foreign key must not verify"
        assert not ed_verify(pub2, challenge + b"!", sig2), "a changed challenge must not verify"
        assert not ed_verify(pub2, proof, sig2), "a challenge signature must not verify as the key proof"
        assert not ed_verify(pub2, challenge, sig), "the key-proof signature must not verify as the challenge signature"
        event("sign-allow", challenge=challenge.decode(), signature=sig2.hex(), verifies=True,
              foreignKeyRefused=True, changedChallengeRefused=True, notTheKeyProof=True,
              approvedCount=(S(2039) >> 2) & 15, seedDisplayed=False)
        # A draft save (F5) works in the browser context bytes 512..2559; the key seed must live outside them.
        generation_before = W(82)
        send("sendkey f5", 3.0)
        assert W(82) > generation_before, ("the draft save did not run", generation_before, W(82))
        send("sendkey f7", 1.5); assert W(87) == 3
        send("sendkey y", 3.0)
        sig3 = b"".join(struct.pack("<I", W(800 + i)) for i in range(16))
        assert ed_verify(pub2, challenge, sig3), "the device key seed did not survive a draft save"
        assert sig3 == sig2, "Ed25519 is deterministic: the same seed must give the same signature"
        event("draft-after-key", generation=W(82), signatureUnchanged=True, verifies=True)
        move_to(px + 24 + 70, py + 164 + 18)
        before_allow = screenshot("before-allow")
        assert (S(2039) >> 2) & 15 == 3 and S(2039) & 3 == 0
        send("sendkey ret", 1.5); assert W(87) == 1 and S(2039) & 3 == 1
        move_to(px + 24 + 70, py + 164 + 18); click()
        assert W(87) == 0 and (S(2039) >> 2) & 15 == 4 and S(2039) & 3 == 0 and W(88) == 1 and W(85) == 1
        after_allow = screenshot("after-allow")
        w0, h0, p0 = before_allow
        assert (w0, h0) == after_allow[:2]
        # The Approved line of the Itonami home sits at body y + 100 + 20*2 =
        # window y + 28 + ...; compare only the band under the goal field
        # (x 180..300, y 180..205 in the 1280x800 desktop). Allow also retitles
        # the window, so the whole-frame difference is larger than the digit.
        def band(raw):
            return [raw[2][3 * (y * raw[0] + x):3 * (y * raw[0] + x) + 3]
                    for y in range(180, 205) for x in range(180, 300)]
        assert band(before_allow) != band(after_allow), "the Approved digit did not change after Allow"
        changed_cols = sorted({i % 120 for i, (u, v) in enumerate(zip(band(before_allow), band(after_allow))) if u != v})
        assert changed_cols and min(changed_cols) >= 80 and max(changed_cols) - min(changed_cols) < 10, changed_cols
        # The Itonami home also states "Network: off" and "Telemetry: none" (rows y 205..222 and
        # 225..242): both bands must carry ink on the white body, and the band under them must not.
        def ink(raw, y0, y1):
            w = raw[0]
            return sum(1 for y in range(y0, y1) for x in range(180, 330)
                       if raw[2][3 * (y * w + x):3 * (y * w + x) + 3] != b"\xff\xff\xff")
        network_ink, telemetry_ink, below_ink = (ink(after_allow, 205, 223), ink(after_allow, 225, 243),
                                                 ink(after_allow, 275, 320))
        keys_ink = ink(after_allow, 255, 273)
        assert network_ink > 20 and telemetry_ink > 20 and keys_ink > 20 and below_ink == 0, (network_ink, telemetry_ink, keys_ink, below_ink)
        event("pointer-allow", pending=W(87), approved=W(88), stop=W(85),
              approvedCount=(S(2039) >> 2) & 15, changedColumns=[changed_cols[0] + 180, changed_cols[-1] + 180],
              networkInk=network_ink, telemetryInk=telemetry_ink, keysHintInk=keys_ink)
    finally:
        try: send("quit", 0.5)
        except Exception: pass
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    media_after = pin(args.media)
    assert media_before == media_after, "media changed"
    report = dict(status="PASS_NATIVE_CONSENT_QEMU", kernel=pin(args.kernel), efi=pin(args.efi),
                  media=media_after, font=pin(args.font), firmware=pin(args.firmware),
                  observer=pin(Path(__file__)), events=events,
                  syntheticInputProvesHumanConsent=False, guestEmulation="QEMU TCG",
                  physicalHardware=False)
    (out / "native-consent-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    main(p.parse_args())
