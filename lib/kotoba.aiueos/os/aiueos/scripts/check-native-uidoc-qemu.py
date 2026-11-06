#!/usr/bin/env python3
"""JUN-856 (ADR-0287): the native desktop kernel runs the UI-document front end (cssom.uidoc-k: a compact UI document in a shared region becomes the wire
stream of the style slice) and then the existing layout slice (cssom.flow-k) and draw slice (cssom.draw-k) on it, over a deterministic grid of real dapp
windows, component trees, hand cases, refusals and seeded random documents.

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/uidoc (QEMU only, never a disk or the network): [case count:2 big endian] then per
case [document length:2][viewport width:4, Q6 raw][compact document][wire length:2][canonical wire stream or nothing], made by
lib/kotoba.cssom/scripts/uidoc_k_cases.py. For each case it writes to the debug console (I/O port 0xe9, QEMU -debugcon file:...) the front end's status, the
text-placeholder counts, the wire stream it expanded, and for the expanded stream (path A) and for the canonical wire stream (path B, the existing input of
the draw gate) the layout status, the whole box table and the RAW WORDS of the draw-list region (native/uidoc-entry.kotoba). This observer boots once, waits
for the first frame, reads the marker (effects word 51 = "UD01"), reads the debug console file and checks from the case table and from the independent host
reference (uidoc_k_cases.ref_expand, draw_k_cases.expected / decode) and not from the kernel:
  * the front end's status equals the reference's (a refusal's status is written out in the case table) and the text counts match;
  * the expanded wire stream equals the reference's and the canonical stream of the case byte for byte;
  * path A (expanded) and path B (canonical) agree in every field: layout status, element count, offending element, box table, draw status, every op;
  * the draw list of each case equals the reference run on the kernel's own box table; a case marked expect_ok has layout and draw status 0;
  * for the hand-derived window the kernel box table equals the hand-derived one on the fields the table fixes and the draw list equals the hand-derived list.
QEMU TCG only; no key is used.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, sys, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"UD01", "big")
HERE = Path(__file__).resolve().parent
CASES_PY = HERE.parents[2].parent / "kotoba.cssom" / "scripts" / "uidoc_k_cases.py"
sys.path.insert(0, str(CASES_PY.parent))
import layout_k_cases as K  # noqa: E402
import draw_k_cases as D  # noqa: E402
import uidoc_k_cases as U  # noqa: E402

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def fixture(cases):
    blobs = [U.fixture_blob(c) for c in cases]
    assert len(cases) <= 480
    return struct.pack(">H", len(cases)) + b"".join(blobs), blobs

def sgn(x):
    return x - (1 << 32) if x >= (1 << 31) else x

def parse_path(body, pos):
    status, nn, off, dh, dstatus = struct.unpack_from("<iIIII", body, pos)
    pos += 20
    words = [sgn(w) for w in struct.unpack_from("<%dI" % (22 * nn), body, pos)]
    pos += 88 * nn
    region = []
    if status >= 0:
        count = struct.unpack_from("<I", body, pos + 4)[0]
        assert count <= D.MAX_OPS, ("op count", count)
        region = list(struct.unpack_from("<%dI" % (8 * (count + 1)), body, pos))
        pos += 32 * (count + 1)
    return dict(status=-status if status < 0 else 0, nodes=nn, off=off, dh=sgn(dh), table=words, drawStatus=sgn(dstatus), region=region), pos

def parse_console(data, cases):
    """The records of the debug console: UDSTART!, then per case A5 5A k front-end status text nodes text bytes, the wire stream when the front end ran,
    the PATH record of the expanded stream and, when the case has a canonical wire stream, the PATH record of that stream, then UDEND!!!."""
    a = data.find(b"UDSTART!"); b = data.find(b"UDEND!!!", a)
    assert a >= 0 and b > a, ("the uidoc records are not in the debug console", a, b)
    body, pos, out = data[a + 8:b], 0, []
    for k, c in enumerate(cases):
        assert body[pos:pos + 2] == b"\xa5\x5a", ("record sync", k, pos)
        idx, u, tx, tb = struct.unpack_from("<iiII", body, pos + 2)
        assert idx == k, ("records are not in order", idx, k)
        pos += 18
        rec = dict(index=k, name=c["name"], front=u, texts=tx, textBytes=tb, stream=b"", a=None, b=None)
        if u >= 0:
            rec["stream"] = body[pos:pos + u]
            pos += u
            rec["a"], pos = parse_path(body, pos)
        if c["wire"] is not None:
            rec["b"], pos = parse_path(body, pos)
        out.append(rec)
    assert pos == len(body), ("trailing bytes in the debug console", pos, len(body))
    return out

def check_path(c, rec, which):
    """The disagreements of one PATH record with the case table and the independent reference (as the draw observer's check)."""
    bad = []
    if c["status"] is not None and rec["status"] != c["status"]:
        return [(which + " layout status", rec["status"], c["status"])]
    if c.get("expect_ok") and (rec["status"] != 0 or rec["drawStatus"] < 0):
        return [(which + " expected to run", rec["status"], rec["drawStatus"])]
    if rec["status"] != 0 or c["doc"] is None:
        return [] if c["doc"] is not None or rec["status"] != 0 or rec["nodes"] == 0 else [(which + " elements without a document", rec["nodes"])]
    nn = rec["nodes"]
    if nn != len(K.flat(c["doc"])):
        return [(which + " element count", nn)]
    try:
        hdr, ops = D.decode(rec["region"], nn)
    except AssertionError as e:
        return [(which + " region structure", str(e)[:120])]
    table = rec["table"]
    st, eops, eoff = D.expected(c, table)
    if hdr["status"] != st or rec["drawStatus"] != (hdr["count"] if st == 0 else -st):
        bad.append((which + " draw status", hdr["status"], rec["drawStatus"], st))
    if ops != eops:
        bad.append((which + " ops differ from the reference", len(ops), len(eops), next((i for i, (x, y) in enumerate(zip(ops, eops)) if x != y), min(len(ops), len(eops)))))
    if st == 20 and rec["off"] != eoff:
        bad.append((which + " offending element", rec["off"], eoff))
    if hdr["height"] != rec["dh"]:
        bad.append((which + " document height in the header", hdr["height"], rec["dh"]))
    if c.get("dstatus") is not None and st != c["dstatus"]:
        bad.append((which + " draw status against the case table", st, c["dstatus"]))
    if c.get("ops") is not None and ops != D.hand_ops(c):
        bad.append((which + " ops differ from the hand-derived list", len(ops), len(c["ops"])))
    if c.get("doch") is not None and rec["dh"] != K.Q(c["doch"]):
        bad.append((which + " document height", rec["dh"], K.Q(c["doch"])))
    if c.get("boxes"):
        words, masks, _dm = K.hand_table(c)
        if not all(table[i] == w for i, w in enumerate(words) if (i % 22 == 0) or ((masks[i // 22] >> (i % 22)) & 1)):
            bad.append((which + " box table differs from the hand-derived one",))
    return bad

def check_case(c, rec):
    """The disagreements of one record with the case table and the independent references; empty when the kernel agrees."""
    st, wire, tx, tb = U.expected_front(c)
    if rec["front"] != st:
        return [("front-end status", rec["front"], st)]
    if st < 0:
        return []
    bad = []
    if (rec["texts"], rec["textBytes"]) != (tx, tb):
        bad.append(("text placeholders", (rec["texts"], rec["textBytes"]), (tx, tb)))
    if rec["stream"] != wire:
        bad.append(("wire stream differs from the reference", len(rec["stream"]), len(wire), next((i for i, (x, y) in enumerate(zip(rec["stream"], wire)) if x != y), -1)))
    if c["wire"] is not None and rec["stream"] != c["wire"]:
        bad.append(("wire stream differs from the canonical one", len(rec["stream"]), len(c["wire"])))
    bad += check_path(c, rec["a"], "expanded")
    if rec["b"] is not None:
        bad += check_path(c, rec["b"], "direct")
        if rec["a"] != rec["b"]:
            bad.append(("expanded and direct paths differ", [k for k in rec["a"] if rec["a"][k] != rec["b"][k]]))
    return bad

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    cases = U.all_cases()
    blob, blobs = fixture(cases)
    fwfile = out / "uidoc-cases.bin"; fwfile.write_bytes(blob)
    debugcon = out / "debugcon.bin"
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/uidoc,file={fwfile}", "-debugcon", f"file:{debugcon}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
        last_size, last_change = -1, time.monotonic()
        while time.monotonic() < deadline and words(2048 + 51, 1)[0] != MARKER:
            size = debugcon.stat().st_size if debugcon.exists() else 0
            if size != last_size:
                last_size, last_change = size, time.monotonic()
            elif time.monotonic() - last_change > 120:      # a guest that wrote nothing for two minutes has stopped (a mutant may fault or halt)
                raise AssertionError(("the guest stalled before the marker", size))
            time.sleep(2)
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the uidoc self-test did not finish", hex(marker))
        marker_count = words(319, 1)[0]
        assert marker_count == len(cases), "case count"
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    consoles = parse_console(debugcon.read_bytes(), cases)
    bad, records = [], []
    for k, c in enumerate(cases):
        rec = consoles[k]
        problems = check_case(c, rec)
        records.append(rec)
        if problems:
            bad.append((c["name"], problems[:3]))
    matches = [r["name"] for r in records if r["name"] not in {b[0] for b in bad}]
    events.append(dict(name="uidoc-cases", cases=len(cases), recorded=len(records), matches=len(matches), handDerived=sum(1 for c in cases if c.get("ops") is not None),
                       expanded=sum(1 for r in records if r["front"] >= 0), frontEndRefusals=sum(1 for r in records if r["front"] < 0),
                       layoutRefusals=sum(1 for r in records if r["a"] and r["a"]["status"] != 0), marker=hex(marker)))
    for r in records:
        r["stream"] = {"bytes": len(r["stream"]), "sha256": hashlib.sha256(r["stream"]).hexdigest()}
        if r["b"] is not None and r["a"] == r["b"]:
            r["b"] = "equal to a"
    report = dict(status="PASS_NATIVE_UIDOC_K_QEMU" if not bad else "FAIL_NATIVE_UIDOC_K_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), cases=pin(CASES_PY), fixture=pin(fwfile),
                  records=records, mismatches=bad, events=events, signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-uidoc-qemu.json").write_text(json.dumps(report) + "\n")
    print(report["status"], len(matches), "of", len(cases))
    if bad:
        print("uidoc records differ from the case table or the reference (name, problems):", bad[:10], file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
