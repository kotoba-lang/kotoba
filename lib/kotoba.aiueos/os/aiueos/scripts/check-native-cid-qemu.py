#!/usr/bin/env python3
"""ADR-0275 W4 slice: the native desktop kernel decides CID questions with the shipped admission object.

Before the desktop starts, the guest runs aiueos.cid-v1-admit four times on the block "abc" and its raw CIDv1
(01 55 12 20 + sha256) and leaves the result codes in the browser context. This gate boots the image once,
waits for the first completed frame, and reads the marker (word 99) and the codes (words 100..103) over the
QEMU monitor. Expected: 0 (admitted), 8 (one block byte changed: digest mismatch), 4 (multihash code changed),
3 (codec changed to one that is not permitted). The three refusals are the negative controls; a kernel that
returned 0 for all four, or none, fails. There is no ipfs:// scheme handler and no network in this desktop:
this proves the kernel can decide that bytes are the content a CID names, not that a URL was opened.
Input is not used; QEMU TCG only.
"""
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = 0x43494431
EXPECTED = [0, 8, 4, 3]

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == 0x240000 and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + 0x23a000
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
    def word(i):
        drain(); send(f"xp /1wx {work + 4 * i:#x}", 0.3)
        f = re.findall(r"[0-9a-f]{16}: 0x([0-9a-f]{8})", drain()); assert f, "xp gave nothing"
        return int(f[-1], 16)
    events = []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and word(79) < 1: pass
        frames = word(79); assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = word(99); codes = [word(100 + i) for i in range(4)]
        assert marker == MARKER, ("the CID self-test did not finish", hex(marker))
        assert codes == EXPECTED, ("unexpected admission codes", codes)
        assert len(set(codes)) == 4 and codes[0] == 0 and all(c != 0 for c in codes[1:]), codes
        events.append(dict(name="cid-admit", marker=hex(marker), codes=codes,
                           meaning=["admitted", "digest mismatch", "multihash code", "codec not permitted"]))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_CID_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), events=events,
                  urlSchemeHandler=False, physicalHardware=False, syntheticInput=False)
    (out / "native-cid-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], codes)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
