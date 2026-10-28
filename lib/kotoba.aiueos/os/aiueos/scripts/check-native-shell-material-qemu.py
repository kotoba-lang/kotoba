#!/usr/bin/env python3
"""Observe real native materials and pointer/keyboard feedback in private QEMU.

This is a pixel/state observer, never a hosted replacement for the compositor.
No NIC, physical disk, service request or trusted user approval is involved.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


desktop = module("desktop_observer", HERE / "check-native-desktop-qemu.py")
draft = module("draft_observer", HERE / "check-native-draft-restart-qemu.py")


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main(args):
    if not __debug__:
        raise RuntimeError("the assertion gate must not run with Python -O")
    for name in ("media", "efi", "kernel", "font", "qemu", "firmware"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    before = pin(args.media)
    guest = draft.Guest(args, out / "guest", None)
    events = []
    screenshots = []

    def state():
        s = guest.dump(guest.context + 0x238000, "surface.bin")
        c = guest.dump(guest.context + 0x23a000, "context.bin")
        n = s[2038]
        return dict(magic=c[72], keys=c[73], lastKey=c[77],
                    frames=c[79], framesStarted=c[78], packets=c[75],
                    x=c[50], y=c[51], pressed=c[67], reduced=c[99], selected=c[100],
                    renderError=c[101], focus=s[2], windows=s[1], pending=c[87],
                    width=s[3], height=s[4],
                    goal="".join(chr(v) for v in s[224:224+n]),
                    ops=[list(s[480+6*i:486+6*i]) for i in range(min(s[416], 259))],
                    opCount=s[416], overflow=s[427])

    guest.state = state

    def wait(name, predicate):
        s = guest.wait(name, predicate, timeout=150)
        assert s["renderError"] == 0 and s["overflow"] == 0 and 0 < s["opCount"] <= 259, s
        for kind, x, y, a, b, _ in s["ops"]:
            assert 1 <= kind <= 6 and x >= 0 and y >= 0
            width, height = (b, 16) if kind == 2 else (a, b)
            assert x + width <= s["width"] and y + height <= s["height"], (kind, x, y, a, b)
        return s

    def key(name, code, predicate):
        previous = state()
        guest.key(code)
        return wait(name, lambda s: s["keys"] > previous["keys"] and s["frames"] > previous["frames"] and predicate(s))

    def screenshot(name):
        assert guest.hmp(f"screendump {name}.ppm") == ""
        path = guest.directory / (name + ".png")
        pixels = desktop.ppm_png(guest.directory / (name + ".ppm"), path)
        screenshots.append(dict(name=name, file="guest/" + path.name, **pin(path)))
        return pixels

    def pixel(pixels, x, y, width=1280):
        at = 3 * (y * width + x)
        return tuple(pixels[at:at+3])

    def move_to(x, y):
        for _ in range(40):
            s = state()
            dx, dy = x - s["x"], y - s["y"]
            if abs(dx) <= 1 and abs(dy) <= 1:
                return
            guest.call("input-send-event", {"events": [
                {"type": "rel", "data": {"axis": "x", "value": max(-100, min(100, dx))}},
                {"type": "rel", "data": {"axis": "y", "value": max(-100, min(100, dy))}}]})
            wait("move", lambda now: now["packets"] > s["packets"] and now["frames"] > s["frames"])
        raise AssertionError(("pointer target not reached", x, y, state()))

    def tile(s, color):
        found = [op for op in s["ops"] if op[0] == 5 and op[5] == color]
        assert len(found) == 1, found
        return found[0][1:5]

    def record(name, s, **extra):
        events.append(dict(name=name, opCount=s["opCount"], **extra))

    try:
        first = wait("first-frame", lambda s: s["magic"] == 0x31545844 and s["frames"] >= 1)
        assert first["windows"] == 0 and first["selected"] == 0 and first["reduced"] == 0
        width, height = first["width"], first["height"]
        assert (width, height) == (1280, 800)
        left, top = (width - 184) // 2, height - 52
        pixels = screenshot("material-home")
        expected = desktop.expected_background(height - 28, height)
        assert pixel(pixels, 100, 100) == desktop.expected_background(100, height)
        assert pixel(pixels, left, top) == desktop.expected_background(top, height), "dock corner must reveal the background"
        tint, alpha = (248, 250, 255), 176
        glass = tuple((a * (255-alpha) + b * alpha) // 255 for a, b in zip(expected, tint))
        assert pixel(pixels, left+4, height-28) == glass, (pixel(pixels, left+4, height-28), glass)
        record("first-frame-materials", first, glassPixel=list(glass), gradient=True, roundedCorner=True)

        selected = key("keyboard-focus", "right", lambda s: s["selected"] == 1)
        assert selected["windows"] == 0 and selected["pending"] == 0
        assert any(op[0] == 3 and op[5] == 0x6755ff for op in selected["ops"])
        screenshot("keyboard-focus")
        key("keyboard-cancel", "esc", lambda s: s["selected"] == 0 and s["windows"] == 0)
        key("keyboard-first", "right", lambda s: s["selected"] == 1)
        key("keyboard-wrap-left", "left", lambda s: s["selected"] == 4)
        key("keyboard-wrap-right", "right", lambda s: s["selected"] == 1)
        record("dock-keyboard-focus", selected, selected=1, wrapAndCancel=True)
        key("keyboard-next", "right", lambda s: s["selected"] == 2)
        launched = key("keyboard-launch", "ret", lambda s: s["focus"] == 2 and s["selected"] == 0)
        assert launched["windows"] == 1 and launched["pending"] == 0
        typed = key("goal", "a", lambda s: s["goal"] == "Goal (RAM):\na")
        record("dock-keyboard-launch", typed, windows=1, goalPreserved=True)

        icon_left, icon_top = left+8+44, height-46
        move_to(icon_left+18, icon_top+18)
        hover = wait("hover", lambda s: s["selected"] == 0 and s["pressed"] == 0)
        assert tile(hover, 0x1cf46738) == [icon_left-2, icon_top-4, 40, 40]
        hovered = screenshot("dock-hover")
        record("dock-pointer-hover", hover, tile=tile(hover, 0x1cf46738))

        guest.call("input-send-event", {"events": [{"type": "btn", "data": {"button": "left", "down": True}}]})
        pressed = wait("press", lambda s: s["pressed"] == 1 and s["frames"] > hover["frames"])
        assert tile(pressed, 0x1cf46738) == [icon_left+1, icon_top+1, 34, 34]
        assert screenshot("dock-pressed") != hovered
        record("dock-pointer-press", pressed, tile=tile(pressed, 0x1cf46738))
        guest.call("input-send-event", {"events": [{"type": "btn", "data": {"button": "left", "down": False}}]})
        released = wait("release", lambda s: s["pressed"] == 0 and s["frames"] > pressed["frames"])
        assert released["windows"] == 1 and released["goal"] == "Goal (RAM):\na" and released["pending"] == 0
        record("dock-pointer-release", released, noImplicitOperation=True)

        calm = key("reduced-effects", "f10", lambda s: s["reduced"] == 1)
        assert tile(calm, 0x1cf46738) == [icon_left, icon_top, 36, 36]
        assert pixel(screenshot("reduced-effects"), left+4, height-28) == tint
        record("reduced-effects", calm, opaqueGlass=True, stationaryTile=True)
        restored = key("effects-restored", "f10", lambda s: s["reduced"] == 0)
        assert tile(restored, 0x1cf46738) == [icon_left-2, icon_top-4, 40, 40]
        assert restored["goal"] == "Goal (RAM):\na" and restored["pending"] == 0
        record("effects-restored", restored, goalPreserved=True)
        key("return-home", "esc", lambda s: s["windows"] == 0 and s["focus"] == 0)
        move_to((width-704)//2+176+80, (height-240)//2+90)
        previous = state()
        guest.call("input-send-event", {"events": [{"type": "btn", "data": {"button": "left", "down": True}}]})
        opened = wait("home-card-launch", lambda s: s["pressed"] == 1 and s["frames"] > previous["frames"])
        assert opened["focus"] == 2 and opened["windows"] == 1 and opened["pending"] == 0
        guest.call("input-send-event", {"events": [{"type": "btn", "data": {"button": "left", "down": False}}]})
        before_release = opened["frames"]
        opened = wait("home-card-release", lambda s: s["pressed"] == 0 and s["frames"] > before_release)
        assert opened["goal"] == "Goal (RAM):\na"
        record("home-pointer-launch", opened, goalPreserved=True, noImplicitOperation=True)
    finally:
        guest.close()
    assert pin(args.media) == before
    result = dict(status="PASS_NATIVE_SHELL_MATERIAL_QEMU", events=events, screenshots=screenshots,
                  kernel=pin(args.kernel), efi=pin(args.efi), media=before, font=pin(args.font),
                  observer=pin(Path(__file__)), desktopObserver=pin(HERE/"check-native-desktop-qemu.py"),
                  transportObserver=pin(HERE/"check-native-draft-restart-qemu.py"),
                  guestEmulation="QEMU TCG", physicalHardware=False,
                  syntheticInputProvesHumanConsent=False, backdropBlur=False,
                  opticalRefraction=False, frameRateQualified=False, audioHaptics=False)
    (out/"native-shell-material-qemu.json").write_text(json.dumps(result, indent=2)+"\n")
    print(result["status"], len(events))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    main(parser.parse_args())
