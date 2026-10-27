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

def main(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    image = args.kernel.read_bytes()
    rw = struct.unpack_from('<IIQQQQQQ', image, 120)
    context = rw[3]
    assert rw[5] == 0x240000 and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    surface, work = context + 0x238000, context + 0x23a000
    cmd = [str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware}",
           "-drive", f"file={args.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-nic", "none", "-display", "none", "-no-reboot", "-monitor", "stdio"]
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
            raise AssertionError("pointer did not reach target")
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
        move_to(px + 24 + 70, py + 164 + 18)
        before_allow = screenshot("before-allow")
        assert S(2039) == 0
        send("sendkey ret", 1.5); assert W(87) == 1 and S(2039) == 1
        move_to(px + 24 + 70, py + 164 + 18); click()
        assert W(87) == 0 and S(2039) == 2 and W(88) == 1 and W(85) == 1
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
                                                 ink(after_allow, 250, 290))
        assert network_ink > 20 and telemetry_ink > 20 and below_ink == 0, (network_ink, telemetry_ink, below_ink)
        event("pointer-allow", pending=W(87), approved=W(88), stop=W(85),
              approvedCount=S(2039) // 2, changedColumns=[changed_cols[0] + 180, changed_cols[-1] + 180],
              networkInk=network_ink, telemetryInk=telemetry_ink)
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
