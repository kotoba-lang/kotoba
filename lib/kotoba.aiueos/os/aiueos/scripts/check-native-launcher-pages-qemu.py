#!/usr/bin/env python3
"""ADR-0285 / JUN-811: observe the paged launcher and the window-slot rules of the native desktop in QEMU.

Keys are synthetic QEMU input. The checks read the guest's surface (slot->app words 25..28, launcher page word 29, window
records, titles), so they observe guest decisions, not pixels, except that page 1 must scan out differently from page 0.
Run it on the same media the build gates use; it is not yet one of the build script's pinned gates.
"""
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

import native_regions

HERE = Path(__file__).resolve().parent
OPS_LIMIT = 259  # surface words 480.. hold 6-word draw ops; word 416 is the count, 427 the overflow flag


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


TITLES = {1: "Murakumo", 2: "Itonami", 3: "Yataverse", 4: "Aozora", 9: "Bunsho", 10: "Hyokeisan", 11: "Zuhyo", 12: "Tokei"}


def main(media, efi, kernel, font, qemu, firmware, out):
    image = kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120)
    context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ
    out.mkdir(parents=True, exist_ok=False)
    args = [str(qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
            "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}",
            "-drive", f"file={media},format=raw,if=ide,snapshot=on", "-boot", "order=c", "-nic", "none",
            "-display", "none", "-no-reboot", "-serial", "file:serial.log", "-qmp", "stdio"]
    (out / "command.json").write_text(json.dumps(args, indent=2) + "\n")
    log = open(out / "qemu.log", "wb")
    p = subprocess.Popen(args, cwd=out, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, bufsize=0)
    old = Path.cwd()
    os.chdir(out)
    seq = 0
    events = []
    ops_seen = []
    try:
        assert select.select([p.stdout], [], [], 15)[0], "QMP greeting timeout"
        assert "QMP" in json.loads(p.stdout.readline())

        def call(name, data=None):
            nonlocal seq
            seq += 1
            row = dict(execute=name, id=seq)
            if data is not None:
                row["arguments"] = data
            p.stdin.write(json.dumps(row).encode() + b"\n")
            while True:
                assert select.select([p.stdout], [], [], 10)[0], ("QMP response timeout", name)
                row = json.loads(p.stdout.readline())
                if row.get("id") == seq:
                    assert "error" not in row, row
                    return row["return"]

        def hmp(s):
            return call("human-monitor-command", {"command-line": s})

        def dump(at, n, name):
            assert hmp(f"pmemsave 0x{at:x} {n} {name}") == ""
            return (out / name).read_bytes()

        def title(surface, window):
            words = surface[32 + 32 * (window - 1):64 + 32 * (window - 1)]
            return "".join(chr(c) for c in words[:words.index(0)]) if 0 in words else None

        def state():
            surface = struct.unpack(f"<{native_regions.WINDOW_BYTES // 4}I",
                                    dump(context + native_regions.SURFACE_OFFSET, native_regions.WINDOW_BYTES, "surface.bin"))
            work = struct.unpack(f"<{native_regions.WINDOW_BYTES // 4}I",
                                 dump(context + native_regions.CONTEXT_OFFSET, native_regions.WINDOW_BYTES, "desktop-context.bin"))
            return dict(windows=surface[1], focus=surface[2], slotApps=list(surface[25:29]), page=surface[29],
                        goalLength=surface[2038], titles={i: title(surface, i) for i in range(1, 5)},
                        open=[surface[5 + 5 * i] for i in range(surface[1])], perPage=work[130],
                        ops=surface[416], opsOverflow=surface[427], magic=work[72], keys=work[73], lastKey=work[77], started=work[78], completed=work[79])

        def wait(name, predicate, timeout=120):
            end = time.monotonic() + timeout
            s = None
            while time.monotonic() < end:
                assert p.poll() is None, ("guest exited", p.returncode)
                s = state()
                if predicate(s) and s["started"] == s["completed"]:
                    assert s["opsOverflow"] == 0 and 0 < s["ops"] <= OPS_LIMIT, ("draw list outside its budget", name, s["ops"], s["opsOverflow"])
                    ops_seen.append((s["windows"], s["ops"]))
                    events.append(dict(name=name, state=s))
                    return s
                time.sleep(.2)
            raise AssertionError((name, "state not reached", s))

        def key(qcode, last, prev):
            call("send-key", dict(keys=[dict(type="qcode", data=qcode)], **{"hold-time": 60}))
            return wait("key " + qcode, lambda s: s["keys"] > prev["keys"] and s["lastKey"] == last and s["completed"] > prev["completed"])

        def shot(name):
            assert hmp(f"screendump {name}.ppm") == ""
            raw = (out / (name + ".ppm")).read_bytes()
            return raw[re.match(rb"P6\s+\d+\s+\d+\s+255\s", raw).end():]

        call("qmp_capabilities")
        s = wait("first-frame", lambda s: s["magic"] == 0x31545844 and s["completed"] >= 1)
        assert s["windows"] == 0 and s["slotApps"] == [1, 2, 3, 4] and s["page"] == 0, s
        assert s["perPage"] == 8, ("1280-wide row shows 8 apps per page", s["perPage"])
        page0 = shot("page0")
        # Itonami goal draft in slot 2, then close the window: the draft must keep slot 2 away from foreign apps.
        s = key("2", 3, s)
        assert s["windows"] == 1 and s["focus"] == 2 and s["slotApps"][1] == 2
        s = key("a", 30, s)
        draft = s["goalLength"]
        assert draft > 12
        s = key("esc", 1, s)
        assert s["windows"] == 0 and s["goalLength"] == draft
        # PgDn turns to page 1; the row scans out differently and no window opens.
        s = key("pgdn", 81, s)
        assert s["page"] == 1 and s["windows"] == 0
        assert shot("page1") != page0, "page 1 did not reach the scanout"
        s = key("1", 2, s)  # app 9 -> first free slot (1)
        assert s["windows"] == 1 and s["slotApps"] == [9, 2, 3, 4] and s["titles"][1] == TITLES[9], s
        s = key("2", 3, s)  # app 10 -> slot 2 is held by the Itonami draft, so slot 3
        assert s["windows"] == 2 and s["slotApps"] == [9, 2, 10, 4] and s["titles"][3] == TITLES[10], s
        assert s["goalLength"] == draft
        s = key("1", 2, s)  # app 9 again: focuses its window, opens no second one
        assert s["windows"] == 2 and s["focus"] == 1 and s["slotApps"] == [9, 2, 10, 4], s
        s = key("3", 4, s)  # app 11 -> slot 4
        assert s["windows"] == 3 and s["slotApps"] == [9, 2, 10, 11] and s["titles"][4] == TITLES[11], s
        s = key("4", 5, s)  # app 12: slots 1,3,4 open and slot 2 protected, so refused
        assert s["windows"] == 3 and s["slotApps"] == [9, 2, 10, 11], ("launch must be refused with no free slot", s)
        # PgUp, then app 1 returns to its home slot 1 and replaces app 9 there.
        s = key("pgup", 73, s)
        assert s["page"] == 0
        s = key("1", 2, s)
        assert s["slotApps"] == [1, 2, 10, 11] and s["titles"][1] == TITLES[1] and s["windows"] == 3, s
        assert s["goalLength"] == draft, "Itonami draft lost"
        # Worst case for the draw list: four open windows and a full 8-button page 0.
        s = key("4", 5, s)  # app 4 -> home slot 4, replaces app 11
        assert s["slotApps"] == [1, 2, 10, 4] and s["windows"] == 3, s
        s = key("2", 3, s)  # app 2 -> home slot 2 (its window was closed, draft kept)
        assert s["windows"] == 4 and s["page"] == 0 and s["slotApps"] == [1, 2, 10, 4], s
        assert s["goalLength"] == draft
        four = s["ops"]
        # Paging clamps at both ends.
        s = key("pgup", 73, s)
        assert s["page"] == 0
        for _ in range(3):
            s = key("pgdn", 81, s)
        assert s["page"] == 2, ("18 apps at 8 per page end on page 2", s["page"])
        report = dict(status="PASS_NATIVE_LAUNCHER_PAGES_QEMU", observer=pin(Path(__file__)),
                      kernel=pin(kernel), efi=pin(efi), media=pin(media), font=pin(font), qemu=pin(qemu), firmware=pin(firmware),
                      events=events, opsLimit=OPS_LIMIT, opsFourWindowsFullPage=four, opsMaxObserved=max(o for _, o in ops_seen),
                      guestEmulation="QEMU TCG", physicalHardware=False, syntheticInputProvesHumanConsent=False)
        (out / "native-launcher-pages-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
        print(report["status"])
    finally:
        if p.poll() is None:
            try:
                call("quit")
            except Exception:
                pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.terminate()
                p.wait(timeout=5)
        p.stdin.close()
        p.stdout.close()
        log.close()
        os.chdir(old)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for n in ["media", "efi", "kernel", "font", "qemu", "firmware", "output"]:
        ap.add_argument("--" + n, type=Path, required=True)
    a = ap.parse_args()
    main(*(getattr(a, n).resolve() for n in ["media", "efi", "kernel", "font", "qemu", "firmware", "output"]))
