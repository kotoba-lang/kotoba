#!/usr/bin/env python3
"""JUN-805 (ADR-0287): the native desktop kernel runs the CSSOM layout slice and then the draw slice (cssom.draw-k: the laid-out box table becomes a
draw list of rect fills and borders with Q6 coordinates in a shared region, kernel-dialect region code) over a deterministic grid.

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/draw (QEMU only, never a disk or the network): [case count:2 big endian]
then per case [stream length:2][viewport width:4, Q6 raw][style wire stream], made by lib/kotoba.cssom/scripts/draw_k_cases.py (hand-derived draw
lists, component trees with colours, bounds, refusals, a seeded random grid). For each case it writes to the debug console (I/O port 0xe9, QEMU
-debugcon file:...) the layout status, the whole box table and the RAW WORDS of the draw-list region (header slot and op slots, see
native/draw-entry.kotoba). This observer boots once, waits for the first frame, reads the marker (effects word 51 = "DL01"), reads the debug
console file and checks from the case table and from the independent host reference (draw_k_cases.expected, decode) and not from the kernel:
  * the layout status of every case whose status is fixed, and the element count;
  * the structure of the region (magic, slot size, reserved words, op count <= 255, op codes and roles, element indices);
  * the draw list of every case equals the reference run on the kernel's own box table (status, offending element, every op);
  * for the hand-derived cases the kernel box table equals the hand-derived one on the fields the hand table fixes and the draw list equals the
    hand-derived list op for op (px written out from the CSS rules; the reference is also checked against them before the kernel is looked at).
QEMU TCG only; no key is used.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, sys, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"DL01", "big")
HERE = Path(__file__).resolve().parent
CASES_PY = HERE.parents[2].parent / "kotoba.cssom" / "scripts" / "draw_k_cases.py"
sys.path.insert(0, str(CASES_PY.parent))
import layout_k_cases as K  # noqa: E402
import draw_k_cases as D  # noqa: E402

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
    """The records of the debug console: DLSTART!, then per case A5 5A k layout-status nn off dh draw-status, 22 words per element and, when the
    layout ran, the raw words of the draw-list region (8 per slot: the header and as many ops as header word 1 says), then DLEND!!!."""
    a = data.find(b"DLSTART!"); b = data.find(b"DLEND!!!", a)
    assert a >= 0 and b > a, ("the draw records are not in the debug console", a, b)
    body, pos, out = data[a + 8:b], 0, []
    while pos < len(body):
        assert body[pos:pos + 2] == b"\xa5\x5a", ("record sync", pos)
        k, status, nn, off, dh, dstatus = struct.unpack_from("<IiIIII", body, pos + 2)
        pos += 26
        words = [sgn(w) for w in struct.unpack_from("<%dI" % (22 * nn), body, pos)]
        pos += 88 * nn
        region = []
        if status >= 0:
            count = struct.unpack_from("<I", body, pos + 4)[0]
            assert count <= D.MAX_OPS, ("op count", count)
            region = list(struct.unpack_from("<%dI" % (8 * (count + 1)), body, pos))
            pos += 32 * (count + 1)
        out.append(dict(index=k, status=-status if status < 0 else 0, nodes=nn, off=off, dh=sgn(dh), table=words, drawStatus=sgn(dstatus), region=region))
    assert [r["index"] for r in out] == list(range(ncases)), ("records are not in order", len(out), ncases)
    return out

def check_case(c, rec):
    """The disagreements of one record with the case table and the independent reference; empty when the kernel agrees."""
    bad = []
    if c["status"] is not None and rec["status"] != c["status"]:
        return [("layout status", rec["status"], c["status"])]
    if rec["status"] != 0:
        return [("layout refused where the draw stage must run", rec["status"])] if c.get("dstatus") is not None else []
    nn = rec["nodes"]
    if nn != len(K.flat(c["doc"])):
        return [("element count", nn)]
    try:
        hdr, ops = D.decode(rec["region"], nn)
    except AssertionError as e:
        return [("region structure", str(e)[:120])]
    table = rec["table"]
    st, eops, eoff = D.expected(c, table)
    if hdr["status"] != st or rec["drawStatus"] != (hdr["count"] if st == 0 else -st):
        bad.append(("draw status", hdr["status"], rec["drawStatus"], st))
    if ops != eops:
        bad.append(("ops differ from the reference", len(ops), len(eops), next((i for i, (x, y) in enumerate(zip(ops, eops)) if x != y), min(len(ops), len(eops)))))
    if st == 20 and rec["off"] != eoff:
        bad.append(("offending element", rec["off"], eoff))
    if hdr["height"] != rec["dh"]:
        bad.append(("document height in the header", hdr["height"], rec["dh"]))
    if c.get("dstatus") is not None and st != c["dstatus"]:
        bad.append(("draw status against the case table", st, c["dstatus"]))
    if c.get("ops") is not None and ops != D.hand_ops(c):
        bad.append(("ops differ from the hand-derived list", len(ops), len(c["ops"])))
    if c.get("boxes"):
        words, masks, _dm = K.hand_table(c)
        if not all(table[i] == w for i, w in enumerate(words) if (i % 22 == 0) or ((masks[i // 22] >> (i % 22)) & 1)):
            bad.append(("box table differs from the hand-derived one",))
    return bad

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    cases = D.all_cases()
    blob, blobs = fixture(cases)
    fwfile = out / "draw-cases.bin"; fwfile.write_bytes(blob)
    debugcon = out / "debugcon.bin"
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/draw,file={fwfile}", "-debugcon", f"file:{debugcon}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
        assert marker == MARKER, ("the draw self-test did not finish", hex(marker))
        marker_count = words(319, 1)[0]
        assert marker_count == len(cases), "case count"
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    consoles = parse_console(debugcon.read_bytes(), len(cases))
    bad, records = [], []
    for k, c in enumerate(cases):
        rec = consoles[k]
        rec["name"] = c["name"]
        problems = check_case(c, rec)
        records.append(rec)
        if problems:
            bad.append((c["name"], problems[:3]))
    matches = [r["name"] for r in records if r["name"] not in {b[0] for b in bad}]
    events.append(dict(name="draw-cases", cases=len(cases), recorded=len(records), matches=len(matches), handDerived=sum(1 for c in cases if c.get("ops") is not None),
                       layoutRefusals=sum(1 for r in records if r["status"] != 0), drawRefusals=sum(1 for r in records if r["drawStatus"] < 0), marker=hex(marker)))
    report = dict(status="PASS_NATIVE_DRAW_K_QEMU" if not bad else "FAIL_NATIVE_DRAW_K_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), cases=pin(CASES_PY), fixture=pin(fwfile),
                  records=records, mismatches=bad, events=events, signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-draw-qemu.json").write_text(json.dumps(report) + "\n")
    print(report["status"], len(matches), "of", len(cases))
    if bad:
        print("draw records differ from the case table or the reference (name, problems):", bad[:10], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
