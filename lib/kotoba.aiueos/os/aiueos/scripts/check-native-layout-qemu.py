#!/usr/bin/env python3
"""JUN-134/135/920 (ADR-0287): the native desktop kernel runs the CSSOM layout slice (cssom.flow-k, cssom.box-k over cssom.cascade-k and its three
modules, with the Q6 modules length-q6, block-width-q6, block-style-q6, margin-collapse-q6: normal block flow of the styled node table into a box
table, all kernel-dialect region code) over a deterministic grid.

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/layout (QEMU only, never a disk or the network): [case count:2 big endian]
then per case [stream length:2][viewport width:4, Q6 raw][style wire stream], made by lib/kotoba.cssom/scripts/layout_k_cases.py (hand-derived
documents, the real component trees with the real sheet and with a block sheet, a seeded random grid, the bounds from each side, refusals). For
each case it leaves a record at browser-context byte 4096 + 8 k (see native/layout-entry.kotoba) and writes the whole box table to the debug
console (I/O port 0xe9, QEMU -debugcon file:...). This observer boots once, waits for the first frame, reads the marker (effects word 51 = "LY01"),
reads the debug console file and the browser-context records, and checks from the case table and not from the kernel: the status of every case
whose status is fixed, the element count of every case that runs and, for the hand-derived cases, the Q6 raw of every fixed box field and the
document height. It records the whole table of every case in the receipt (records), where scripts/check-layout-k-native-macos.py (in
lib/kotoba.cssom) compares it with the host-native f64 reference. QEMU TCG only; no key is used.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, sys, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"LY01", "big")
HERE = Path(__file__).resolve().parent
CASES_PY = HERE.parents[2].parent / "kotoba.cssom" / "scripts" / "layout_k_cases.py"
sys.path.insert(0, str(CASES_PY.parent))
import layout_k_cases as K  # noqa: E402

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def fixture(cases):
    blobs = [K.blob(c) for c in cases]
    assert len(cases) <= 480 and all(len(b) <= 65535 + 6 for b in blobs)
    return struct.pack(">H", len(cases)) + b"".join(blobs), blobs

def expected_nodes(case):
    return len(K.flat(case["doc"])) if case["doc"] is not None else 0

def sgn(x):
    return x - (1 << 32) if x >= (1 << 31) else x

def parse_console(data, ncases):
    """The records of the debug console: LYSTART!, then per case A5 5A k status nn off dh and 22 words per element, then LYEND!!!."""
    a = data.find(b"LYSTART!"); b = data.find(b"LYEND!!!", a)
    assert a >= 0 and b > a, ("the layout records are not in the debug console", a, b)
    body, pos, out = data[a + 8:b], 0, []
    while pos < len(body):
        assert body[pos:pos + 2] == b"\xa5\x5a", ("record sync", pos)
        k, status, nn, off, dh = struct.unpack_from("<IiIII", body, pos + 2)
        pos += 22
        words = [sgn(w) for w in struct.unpack_from("<%dI" % (22 * nn), body, pos)]
        pos += 88 * nn
        out.append(dict(index=k, status=-status if status < 0 else 0, nodes=nn, off=off, dh=sgn(dh), table=words))
    assert [r["index"] for r in out] == list(range(ncases)), ("records are not in order", len(out), ncases)
    return out

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    cases = K.all_cases()
    blob, blobs = fixture(cases)
    fwfile = out / "layout-cases.bin"; fwfile.write_bytes(blob)
    debugcon = out / "debugcon.bin"
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    dump = out / "records.bin"
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/layout,file={fwfile}", "-debugcon", f"file:{debugcon}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=out, bufsize=1)
    def send(line, wait=0.3):
        proc.stdin.write(line + "\n"); proc.stdin.flush(); time.sleep(wait)
    def drain():
        t = ""
        while select.select([proc.stdout], [], [], 0.1)[0]:
            ch = os.read(proc.stdout.fileno(), 65536).decode(errors="replace")
            if not ch: break
            t += ch
        return t
    def words(first, count):
        for attempt in range(40):       # the monitor may not be up yet, or the host may be loaded
            drain(); send(f"xp /{count}wx {work + 4 * first:#x}", 0.6)
            f = re.findall(r"0x([0-9a-f]{8})", drain())
            if len(f) >= count: return [int(x, 16) for x in f[-count:]]
            time.sleep(1)
        raise AssertionError(("no monitor answer", first, count))
    events, matches, records = [], [], []
    try:
        deadline = time.monotonic() + 3000
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        while time.monotonic() < deadline and words(2048 + 51, 1)[0] != MARKER: time.sleep(2)
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the style self-test did not finish", hex(marker))
        assert words(319, 1)[0] == len(cases), "case count"
        raw = b""
        for first in range(0, 2 * len(cases), 64):
            n = min(64, 2 * len(cases) - first)
            raw += b"".join(struct.pack("<I", w) for w in words(1024 + first, n))
        assert len(raw) == 8 * len(cases), (len(raw), len(cases))
        dump.write_bytes(raw)
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    consoles = parse_console(debugcon.read_bytes(), len(cases))
    bad, ctx_bad = [], []
    for k, c in enumerate(cases):
        lo, hi = struct.unpack_from("<II", raw, 8 * k)
        ctx = dict(dh=sgn(lo), nodes=hi & 255, off=(hi >> 8) & 255, status=hi >> 24)
        rec = consoles[k]
        rec["name"] = c["name"]
        if (ctx["status"], ctx["nodes"] if ctx["status"] == 0 else 0) != (rec["status"], rec["nodes"] if rec["status"] == 0 else 0):
            ctx_bad.append((c["name"], ctx, rec["status"], rec["nodes"]))
        if rec["status"] == 0 and ctx["dh"] != rec["dh"]:
            ctx_bad.append((c["name"], "document height", ctx["dh"], rec["dh"]))
        records.append(rec)
        ok = c["status"] is None or rec["status"] == c["status"]
        if ok and rec["status"] == 0:
            ok = rec["nodes"] == expected_nodes(c)
            if ok and c.get("boxes"):
                words, masks, _dm = K.hand_table(c)
                t = rec["table"]
                ok = all(t[i] == w for i, w in enumerate(words) if (i % 22 == 0) or ((masks[i // 22] >> (i % 22)) & 1))
                if ok and c.get("doch") is not None:
                    ok = rec["dh"] == K.Q(c["doch"])
        (matches if ok else bad).append(c["name"] if ok else (c["name"], rec["status"], rec["nodes"], c["status"]))
    assert not ctx_bad, ("the browser-context records disagree with the debug console", ctx_bad[:5])
    events.append(dict(name="layout-cases", cases=len(cases), recorded=len(records), matches=len(matches), handDerived=sum(1 for c in cases if c.get("boxes")),
                       refusals=sum(1 for r in records if r["status"] != 0), marker=hex(marker)))
    report = dict(status="PASS_NATIVE_LAYOUT_K_QEMU" if not bad else "FAIL_NATIVE_LAYOUT_K_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), cases=pin(CASES_PY), fixture=pin(fwfile),
                  records=records, mismatches=bad, events=events, signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-layout-qemu.json").write_text(json.dumps(report) + "\n")
    print(report["status"], len(matches), "of", len(cases))
    if bad:
        print("layout records differ from the case table (name, status, nodes, expected status):", bad[:10], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
