#!/usr/bin/env python3
"""JUN-813 stage 5a (ADR-0286 amendment 2): the native desktop kernel admits AIUEIMG2 headers by the multi-signer rule (aiueos.imgsig).

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/imgsig (QEMU only, never a disk or the network): twenty-seven 16 KiB
AIUEIMG2 headers made by scripts/imgsig_oracle.py with fixed public TEST keys (two, three and reordered signers; one signer, a duplicate
id, an unknown id, a bad Ed25519 half, a bad ML-DSA half, Ed25519-only, ML-DSA-only, a tampered manifest, a signature under another
context; bad magic, bad count, nonzero reserved; review hardening: nonzero entry padding / entry reserved / layout bytes 68..127, four entries, key ids 256, 65536 and 2^24). For each it runs Ed25519 and ML-DSA-65 verification per entry and applies the 2-of-3
rule; the verdict and the mask of counted slots go to the browser context (byte 1280 + 8 k). This gate boots once, waits for the first
frame, reads the marker (effects word 51 = "IS01") and compares verdicts and masks with the oracle, whose expectations come from the
independent Ed25519 and ML-DSA references. No key here is a real key; QEMU TCG only.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"IS01", "big")
import imgsig_oracle as oracle
BLOB, CASES = oracle.fw_file()

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    fwfile = out / "imgsig-cases.bin"; fwfile.write_bytes(BLOB)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/imgsig,file={fwfile}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
        drain(); send(f"xp /{count}wx {work + 4 * first:#x}", 0.6)
        f = re.findall(r"0x([0-9a-f]{8})", drain()); assert len(f) >= count, (first, count, len(f))
        return [int(x, 16) for x in f[-count:]]
    events, matches = [], []
    try:
        deadline = time.monotonic() + 3000
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the admission self-test did not finish", hex(marker))
        assert words(319, 1)[0] == len(CASES), "case count"
        bad = []
        for k, c in enumerate(CASES):
            raw = words(320 + 2 * k, 2)
            if raw[0] == c["code"] and raw[1] == c["mask"]: matches.append(c["name"])
            else: bad.append((c["name"], raw, c["code"], c["mask"]))
        assert not bad, ("admission cases differ from the oracle (name, got verdict+mask, want verdict, want mask)", bad)
        events.append(dict(name="admission-cases", marker=hex(marker), matches=matches))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_IMGSIG_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), reference=pin(oracle.REF / "reference.py"), edReference=pin(oracle.HERE / "check-native-consent-qemu.py"), events=events,
                  signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-imgsig-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], matches)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
