#!/usr/bin/env python3
"""ADR-0275 W8: the idle native desktop sends no frame, measured with a NIC attached.

One QEMU run, disk-first, with an e1000e NIC on a user (slirp) netdev whose traffic is written to a pcap (QEMU
filter-dump), and a host port forwarded into it. Frame counts are read at four checkpoints, so no pcap timestamp
(which is not on the host clock) is needed:
  A  the desktop's first completed frame is seen (polled from the guest's own frame counter)
  B  after an idle window with no input and no host traffic
  C  after the host connects to the forwarded port: slirp then sends the guest an ARP request, which proves the
     capture is recording on this netdev in this run (a control that does not depend on firmware chatter)
  D  after keyboard input (open Itonami, type)
Pass: no frame with the guest NIC's MAC as source after A; count(B) == count(A); the capture grew at C by frames
from slirp only (slirp may retransmit its ARP request afterwards; those frames are host-originated and are reported). e1000e because the loader's sealed PCI configuration does not admit virtio-net-pci (the desktop
does not boot; the loader writes F on the debug console); e1000e and rtl8139 boot. The firmware phase (before A)
may contain guest frames (IPv6 duplicate-address detection, 0 to 2 per run); they are counted, not excluded from
the report. Keys are synthetic. This is what the guest emits on a virtual NIC under QEMU TCG with this image; it
does not qualify a physical NIC or a driver.
"""
import argparse, hashlib, json, os, re, select, socket, struct, subprocess, time
import native_regions
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
MAC = "52:54:00:aa:bb:01"
NIC = "e1000e (user netdev, hostfwd), capture = QEMU filter-dump"

def pin(p):
    raw = Path(p).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def frames(pcap):
    d = Path(pcap).read_bytes() if Path(pcap).exists() else b""
    if len(d) < 24: return []
    assert struct.unpack("<I", d[:4])[0] == 0xa1b2c3d4 and struct.unpack("<I", d[20:24])[0] == 1, "not an ethernet pcap"
    off, out = 24, []
    while off + 16 <= len(d):
        _, _, cl, _ = struct.unpack("<IIII", d[off:off + 16])
        if off + 16 + cl > len(d): break
        out.append(d[off + 16:off + 16 + cl]); off += 16 + cl
    return out

def src(f): return f[6:12].hex(":")

def main(a):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(a, n, getattr(a, n).resolve(strict=True))
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(a.media)
    image = a.kernel.read_bytes()
    rw = struct.unpack_from("<IIQQQQQQ", image, 120); context = rw[3]
    assert rw[5] == native_regions.RW_MEMSZ and context in (0x200000, 0x400000), (hex(context), hex(rw[5]))
    work = context + native_regions.CONTEXT_OFFSET
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    cap = out / "idle.pcap"
    cmd = [str(a.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "128M", "-smp", "1",
           "-drive", f"if=pflash,format=raw,readonly=on,file={a.firmware}",
           "-drive", f"file={a.media},format=raw,if=ide,snapshot=on", "-boot", "order=c",
           "-netdev", f"user,id=n0,hostfwd=tcp:127.0.0.1:{port}-:80", "-device", f"e1000e,netdev=n0,mac={MAC}",
           "-object", f"filter-dump,id=f0,netdev=n0,file={cap}", "-display", "none", "-no-reboot",
           "-serial", "none", "-monitor", "stdio"]
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
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and word(79) < 1: pass
        assert word(79) >= 1, "no first frame"
        A = frames(cap)                                   # checkpoint A: first completed frame
        time.sleep(a.idle_seconds)
        B = frames(cap); done = word(79)                  # checkpoint B: after the idle window
        try: socket.create_connection(("127.0.0.1", port), timeout=2).close()
        except OSError: pass                              # nothing answers in the guest; the stimulus is the point
        time.sleep(3)
        C = frames(cap)                                   # checkpoint C: control stimulus recorded
        send("sendkey 2", 1.5); send("sendkey a", 1.5); time.sleep(5)
        D = frames(cap); send("quit", 0.5)               # checkpoint D: after keyboard input
    finally:
        try: proc.wait(timeout=15)
        except Exception: proc.kill()
    guest_after_A = [f for f in D[len(A):] if src(f) == MAC]
    assert len(B) == len(A), ("frames appeared during the idle window", len(A), len(B), [f[:14].hex(":") for f in B[len(A):][:3]])
    stim = C[len(B):]
    assert stim, "control: the host connection produced no recorded frame, so the capture is unproven"
    assert all(src(f) != MAC for f in stim), "control frames must come from slirp, not the guest"
    assert not guest_after_A, ("the guest sent frames after its first completed frame", len(guest_after_A))
    late = D[len(C):]                                # slirp may retransmit its ARP request after the stimulus: not the guest
    assert all(src(f) != MAC for f in late), ("the guest sent frames after keyboard input", len(late))
    assert pin(a.media) == media_before, "media changed"
    report = dict(status="PASS_NATIVE_IDLE_SILENT_QEMU", kernel=pin(a.kernel), efi=pin(a.efi), media=media_before,
                  font=pin(a.font), firmware=pin(a.firmware), observer=pin(Path(__file__)),
                  events=[dict(name="first-frame", framesInCaptureBefore=len(A), guestFramesBefore=len([f for f in A if src(f) == MAC])),
                          dict(name="idle", seconds=a.idle_seconds, framesCompleted=done, newFrames=len(B) - len(A)),
                          dict(name="control", newFrames=len(stim), sources=sorted({src(f) for f in stim}), kind="slirp ARP after host connect"),
                          dict(name="input", keys=["2", "a"], newFrames=len(late), sources=sorted({src(f) for f in late}))],
                  measuredGuestFramesAfterFirstFrame=len(guest_after_A), capture=pin(cap), nic=NIC,
                  physicalHardware=False, syntheticInput=True)
    (out / "native-idle-silent-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], "guest-frames-after-first-frame", len(guest_after_A), "control-frames", len(stim))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    p.add_argument("--idle-seconds", type=int, default=30)
    main(p.parse_args())
