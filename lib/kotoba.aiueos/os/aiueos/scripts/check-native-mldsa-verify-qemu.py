#!/usr/bin/env python3
"""JUN-813 stage 4 (ADR-0286): the native desktop kernel verifies ML-DSA-65 signatures (aiueos.mldsa-verify, FIPS 204 Algorithm 8).

Before the desktop starts the guest reads the fw_cfg file opt/aiueos/mldsa (QEMU only, never a disk or the network): a public key and
nine signatures made by the independent Python reference (valid x2, wrong message, flipped c-tilde, flipped z, three malformed hints,
||z|| out of bound). It computes mu = SHAKE256(SHAKE256(pk) || M') and verifies each; the verify code and the first 12 bytes of mu
per case go to the browser context (byte 1280 + 16 k). This gate boots once, waits for the first completed frame, reads the marker
(effects word 51 = "MV01") and compares codes and mu with scripts/mldsa_verify_oracle.py. No key in this gate is a real key; QEMU TCG only.
"""
import native_regions
import argparse, hashlib, json, os, re, select, struct, subprocess, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MARKER = int.from_bytes(b"MV01", "big")
import mldsa_verify_oracle as oracle
BLOB, CASES = oracle.fw_file()

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    fwfile = out / "mldsa-cases.bin"; fwfile.write_bytes(BLOB)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-fw_cfg", f"name=opt/aiueos/mldsa,file={fwfile}", "-nic", "none", "-display", "none", "-no-reboot", "-serial", "none", "-monitor", "stdio"]
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
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline and words(79, 1)[0] < 1: pass
        frames = words(79, 1)[0]; assert frames >= 1, "no first frame"
        events.append(dict(name="first-frame", framesCompleted=frames))
        marker = words(2048 + 51, 1)[0]
        assert marker == MARKER, ("the sampling self-test did not finish", hex(marker))
        assert words(319, 1)[0] == len(CASES), "case count"
        for k, c in enumerate(CASES):
            raw = words(320 + 4 * k, 4)
            mu = b"".join(x.to_bytes(4, "little") for x in raw[1:])
            assert raw[0] == c["code"] and mu == c["mu"][:12], (c["name"], raw[0], c["code"], mu.hex(), c["mu"][:12].hex())
            matches.append(c["name"])
        changed = bytearray(CASES[0]["sig"]); changed[500] ^= 1
        assert oracle.expected(oracle.cases()[0], CASES[0]["mp"], bytes(changed))[0] != CASES[0]["code"], "negative control"
        events.append(dict(name="verify-cases", marker=hex(marker), matches=matches))
        send("quit", 0.5)
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_MLDSA_VERIFY_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)), reference=pin(oracle.REF / "reference.py"), events=events,
                  signing=False, physicalHardware=False, syntheticInput=False)
    (out / "native-mldsa-verify-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], matches)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
