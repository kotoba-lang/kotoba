#!/usr/bin/env python3
"""AWAI-120 / ADR-0282: the four installed itonami dapps run their offline cores with no network.

One boot of the dapps-profile kernel (desktop profile 5) with QEMU `-nic none` and no scratch disk, as on a
machine with no cable and no draft medium. Through the actual desktop input path:
  Itonami   types a Goal, Enter opens the local-model request, Allow runs the micro model in place: the desktop
            keeps running (ctx word 85 stays 0) and the token is the Itonami title's last character;
  Murakumo  counts that run and shows the token;
  Yataverse Enter stores the 64-byte Goal record as a raw CIDv1; the guest's CID equals SHA-256 computed here,
            cid-v1-admit's code is 0 and the body shows the multibase base32 prefix;
  Aozora    Enter without a device key opens nothing; with a key (F8, Allow, passphrase) Enter opens the sign
            request with the Aozora panel text (surface word 30 = 1); Deny signs nothing; Allow signs the record
            and the signature verifies here under the guest's public key.
QEMU TCG and synthetic input: it proves no human consent and no physical-hardware behaviour.
"""
import native_regions
import argparse, base64, hashlib, importlib.util, json, time
from pathlib import Path

if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("keystore_gate", HERE / "check-native-keystore-qemu.py")
keystore = importlib.util.module_from_spec(spec); spec.loader.exec_module(keystore)
pin, ed_verify = keystore.pin, keystore.ed_verify
PASS = "correct horse"
GOAL = "aba"


def body(b, slot):
    out = []
    for i in range(64):
        cp = b.S(slot + i)
        if cp == 0: break
        out.append(chr(cp))
    return "".join(out)


def main(args):
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware"): setattr(args, n, getattr(args, n).resolve(strict=True))
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    media_before = pin(args.media)
    events = []
    b = keystore.Boot(args, out, "dapps", None)
    try:
        events.append(dict(name="first-frame", frames=b.W(79)))
        assert b.W(960) == 0x31505044, ("not the dapps profile", hex(b.W(960)))
        initial = {"murakumo": body(b, 160), "yataverse": body(b, 288), "aozora": body(b, 352)}
        assert initial == {"murakumo": "Local model\nRuns 0 last -\nOffline",
                           "yataverse": "Local blocks 0\nEnter stores Goal",
                           "aozora": "Outbox 0\nEnter signs Goal\nNot sent"}, initial
        events.append(dict(name="dapps-initial", bodies=initial))

        # Itonami: Goal, Enter, Allow -> the local model runs in place and the desktop keeps running.
        # The bigram has no successor for "b": that Allow runs the model, which refuses; nothing is recorded.
        b.send("sendkey 2", 1.5); b.type_text(GOAL[:2])
        assert b.S(2) == 2 and b.S(2038) == 14, (b.S(2), b.S(2038))
        b.send("sendkey ret", 1.5)
        assert b.W(87) == 1, b.W(87)
        b.send("sendkey y", 3.0)
        assert b.W(87) == 0 and b.W(85) == 0 and b.W(961) == 0 and b.W(962) == 0, (b.W(87), b.W(85), b.W(961))
        events.append(dict(name="itonami-local-refusal", goal=GOAL[:2], recorded=False, desktopKeptRunning=True))
        b.type_text(GOAL[2:])
        assert b.S(2038) == 12 + len(GOAL), b.S(2038)
        b.send("sendkey ret", 1.5)
        assert b.W(87) == 1 and b.S(2039) & 1 == 1, (b.W(87), hex(b.S(2039)))
        b.send("sendkey y", 3.0)
        token = b.W(962)
        assert b.W(87) == 0 and b.W(85) == 0 and b.S(2039) & 1 == 0, (b.W(87), b.W(85), hex(b.S(2039)))
        assert b.W(961) == 1 and (token == 32 or 97 <= token <= 122), (b.W(961), token)
        assert b.S(77) == token, ("the Itonami title must end in the token", b.S(77), token)
        frames = b.W(79); b.send("sendkey 1", 2.0)
        assert b.W(79) > frames, "the desktop must still draw after the local call"
        assert body(b, 160) == f"Local model\nRuns 1 last {chr(token)}\nOffline", body(b, 160)
        events.append(dict(name="itonami-local-model", goal=GOAL, token=chr(token), desktopKeptRunning=True))
        events.append(dict(name="murakumo-run-recorded", runs=1, body=body(b, 160)))

        # Yataverse: Enter stores the Goal record as a raw CIDv1
        record = GOAL.encode() + bytes(64 - len(GOAL))
        cid = bytes([1, 0x55, 0x12, 0x20]) + hashlib.sha256(record).digest()
        b.send("sendkey 3", 1.5); b.send("sendkey ret", 3.0)
        assert b.W(963) == 1 and b.W(992) == 0, (b.W(963), b.W(992))
        assert b.dump(b.work + 3856, 36) == cid, "the guest CID is not 01 55 12 20 + SHA-256 of the Goal record"
        text = "b" + base64.b32encode(cid).decode().lower().rstrip("=")
        assert body(b, 288) == f"Local blocks 1 ok\n{text[:17]}..", body(b, 288)
        events.append(dict(name="yataverse-store", cid=text, admitCode=0, body=body(b, 288)))

        # Aozora: no device key yet, so Enter opens nothing
        b.send("sendkey 4", 1.5); b.send("sendkey ret", 1.5)
        assert b.W(87) == 0 and b.S(30) == 0 and b.W(973) == 0, (b.W(87), b.S(30), b.W(973))
        assert body(b, 352) == "Outbox 0\nNo key, F8 makes one\nNot sent", body(b, 352)
        events.append(dict(name="aozora-no-key", opened=False))

        # a device key (RAM only: there is no scratch disk)
        b.send("sendkey f8", 1.5); assert b.W(87) == 2
        b.send("sendkey y", 1.5); assert b.W(87) == 4
        b.type_text(PASS); b.send("sendkey ret", 8.0)
        for _ in range(240):
            if b.W(87) == 0 and b.W(94) == 1: break
            time.sleep(0.5)
        assert b.W(87) == 0 and b.W(94) == 1 and (b.S(2039) >> 6) & 1 == 1, (b.W(87), b.W(94), hex(b.S(2039)))
        pub = b.words(320, 8)
        events.append(dict(name="device-key-create", fingerprint=pub[:3].hex(), storedOnDisk=b.W(97) == 1))

        # Aozora: Enter opens the post sign request; Deny signs nothing
        b.send("sendkey 4", 1.5); b.send("sendkey ret", 1.5)
        assert b.W(87) == 3 and b.S(30) == 1, (b.W(87), b.S(30))
        panel = b.screenshot("aozora-sign-request")
        b.send("sendkey n", 1.5)
        assert b.W(87) == 0 and b.S(30) == 0 and b.W(973) == 0 and b.words(976, 16) == bytes(64)
        events.append(dict(name="aozora-sign-deny", signed=False))
        # F7's test challenge keeps its own panel text
        b.send("sendkey f7", 1.5); assert b.W(87) == 3 and b.S(30) == 0
        challenge_panel = b.screenshot("challenge-sign-request")
        b.send("sendkey n", 1.5); assert b.W(87) == 0
        width, height = panel[0], panel[1]
        px, py = (width - 480) // 2, (height - 224) // 2
        action = lambda shot: b.band(shot, px + 20, px + 460, py + 104, py + 152)
        assert action(panel) != action(challenge_panel), "the Aozora sign panel must name the post, not the test challenge"
        events.append(dict(name="aozora-panel-text", differsFromChallenge=True))

        # Allow: the record is signed and verifies under the device key
        b.send("sendkey 4", 1.5); b.send("sendkey ret", 1.5)
        assert b.W(87) == 3 and b.S(30) == 1
        b.send("sendkey y", 3.0)
        for _ in range(120):
            if b.W(973) == 1: break
            time.sleep(0.5)
        sig = b.words(976, 16)
        assert b.W(87) == 0 and b.S(30) == 0 and b.W(973) == 1 and b.W(974) == 1, (b.W(87), b.S(30), b.W(973), b.W(974))
        assert ed_verify(pub, record, sig), "the post signature does not verify under the device key"
        assert not ed_verify(pub, b"itonami-w3-sign-test", sig)
        assert body(b, 352) == f"Outbox 1 signed\nkey {pub[:3].hex()}\nNot sent", body(b, 352)
        assert b.words(512, 256) == bytes(1024), "the signing buffer must be wiped"
        # the desktop is drawn again after Allow: no panel, the Aozora window in front
        frames = b.W(79)
        for _ in range(60):
            if b.W(79) > frames and b.S(2039) & 1 == 0: break
            b.send("sendkey 4", 1.0)
        final = b.screenshot("dapps-final")
        refused = b.read(b.work + native_regions.WINDOW_BYTES + 4 * 56)
        assert b.S(2039) & 1 == 0 and action(final) != action(panel), (
            "the consent panel is still on screen", hex(b.S(2039)), hex(refused), b.S(416), b.W(31), b.S(1))
        events.append(dict(name="aozora-sign-allow", verifies=True, signature=sig.hex(), body=body(b, 352)))
    finally:
        b.quit()
    assert pin(args.media) == media_before
    report = dict(status="PASS_NATIVE_DAPPS_QEMU", kernel=pin(args.kernel), efi=pin(args.efi), media=media_before,
                  firmware=pin(args.firmware), font=pin(args.font), observer=pin(Path(__file__)), events=events,
                  network="none (-nic none)", scratchDisk=False, dnsResolved=False,
                  syntheticInputProvesHumanConsent=False, physicalHardware=False)
    (out / "native-dapps-qemu.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], len(events))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("media", "efi", "kernel", "font", "qemu", "firmware", "output"): p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
