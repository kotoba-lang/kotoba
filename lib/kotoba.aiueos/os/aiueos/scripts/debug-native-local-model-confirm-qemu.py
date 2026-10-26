#!/usr/bin/env python3
"""Exercise a fresh native Itonami Y/N choice and local model in two QEMU boots.

No VNC, guest agent, network, host model service or human key press is used.
QMP keys verify the guest decision path; they do not prove a human approved it.
"""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import time


HERE = Path(__file__).resolve().parent
ENTRY = "/os/aiueos/native/user-elf-v2-local-model-entry.kotoba"
ELF_SHA256 = "6d5ec74da6197788a5e778b8903cc40f001602c4c19cb4701d2620a948208e6d"
USER_ENTRY = "/os/aiueos/native/user-elf-v3-local-model-entry.kotoba"
USER_ELF_SHA256 = "108174e896008ac4b523450acd57d16b2b37ba3eb31f6b21d3ad3874344ca4ec"
USER_V4_ENTRY = "/os/aiueos/native/user-elf-v4-local-model-entry.kotoba"
USER_V4_ELF_SHA256 = "68ccbb8fee87c9bc25d46765f34b825003c7d49eecd07ea75ffbffad2c46632a"
PROMPT_TITLE = "AIUEOS local model Goal? y/n"
if not __debug__:
    raise RuntimeError("the QEMU assertion gate must not run with Python -O")


def load_base():
    path = HERE / "debug-native-user-v2-durable-unattended.py"
    spec = importlib.util.spec_from_file_location("durable_guest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(base, qmp, directory, context):
    row = base.state(qmp, directory, context)
    work = struct.unpack("<2048I", (directory / "desktop-context.bin").read_bytes())
    surface = struct.unpack("<2048I", (directory / "surface.bin").read_bytes())
    title_words = surface[64:96]
    title_length = title_words.index(0) if 0 in title_words else len(title_words)
    row.update(pending=work[87], approved=work[88], modelToken=work[89],
               title="".join(chr(cp) for cp in title_words[:title_length]))
    return row


def wait(base, qmp, directory, context, name, predicate, timeout=65):
    deadline = time.monotonic() + timeout
    current = None
    while time.monotonic() < deadline:
        current = snapshot(base, qmp, directory, context)
        (directory / "last-state.json").write_text(json.dumps(current, indent=2) + "\n")
        if (current["magic"] == 0x31545844 and current["profile"] == 4
                and current["draftEnabled"] == 1 and current["frames"] >= 1
                and current["frames"] == current["framesStarted"]
                and predicate(current)):
            (directory / (name + ".json")).write_text(json.dumps(current, indent=2) + "\n")
            return current
        time.sleep(.2)
    (directory / "registers-last.txt").write_text(qmp.hmp("info registers"))
    raise AssertionError((name, current))


def endpoint(base, qmp, directory, code, request, elf, expected, goal, user_call):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        registers = qmp.hmp("info registers")
        (directory / "registers-last.txt").write_text(registers)
        rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
        cpl_match = re.search(r"\bCPL=([0-3])", registers)
        data = qmp.dump(request, 4096, "request-after.bin", directory)
        result = struct.unpack_from("<Q", data)[0]
        if rip_match and cpl_match:
            rip, cpl = int(rip_match.group(1), 16), int(cpl_match.group(1))
            if cpl == 3 and code <= rip < code + 4096 and result == expected:
                qmp.call("stop")
                code_bytes = qmp.dump(code, 4096, "code-final.bin", directory)
                final = qmp.dump(request, 4096, "request-final.bin", directory)
                code_length = 478 if user_call else 330
                assert code_bytes[:code_length] == elf[4096:4096 + code_length]
                assert struct.unpack_from("<I", final, 256)[0] == len(goal)
                assert final[260:260 + len(goal)] == goal.encode("ascii")
                assert final[260 + len(goal):320] == bytes(60 - len(goal))
                if user_call:
                    assert struct.unpack_from("<I", final, 128)[0] == 1364350539
                    assert final[132:136] == bytes((2, 6, 0, 0))
                    assert struct.unpack_from("<I", final, 136)[0] == len(goal)
                    assert final[140:140 + len(goal)] == goal.encode("ascii")
                    assert final[140 + len(goal):232] == bytes(92 - len(goal))
                    assert final[316:320] == bytes(4), "host prefilled user token"
                else:
                    assert struct.unpack_from("<I", final, 316)[0] == expected
                assert struct.unpack_from("<Q", final, 8)[0] == 255
                return {"rip": rip, "cpl": cpl, "result": result,
                        "modelTokenInput": 0 if user_call else expected,
                        "userRequestEnvelope": user_call,
                        "codeMatchesPinnedElf": True}
        time.sleep(.2)
    failure = snapshot(base, qmp, directory, request - 0x21000)
    kernel_state = qmp.dump(request - 0x21000 + 32768, 512,
                            "kernel-user-context-after-failure.bin", directory)
    failure["userHandler"] = {
        "savedRSP": struct.unpack_from("<Q", kernel_state, 0)[0],
        "savedRIP": struct.unpack_from("<Q", kernel_state, 8)[0],
        "savedRFLAGS": struct.unpack_from("<Q", kernel_state, 16)[0],
        "savedRDI": struct.unpack_from("<Q", kernel_state, 24)[0],
        "savedRAX": struct.unpack_from("<Q", kernel_state, 32)[0],
        "active": struct.unpack_from("<Q", kernel_state, 64)[0],
        "lastReturn": struct.unpack_from("<Q", kernel_state, 72)[0],
    }
    (directory / "endpoint-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
    qmp.dump(code, 4096, "code-after-failure.bin", directory)
    raise AssertionError(("approved local model token did not reach CPL3", failure))


def model_expected_token(goal):
    """Read the frozen 27x27 model data, independently of the guest code."""
    matrix_path = HERE.parent / "contracts/micro-infer-transitions-v1.edn"
    source = matrix_path.read_text(encoding="utf-8")
    match = re.search(r"\n\s*:rows\s*\[", source)
    if match is None:
        raise ValueError("micro-infer contract has no rows vector")
    start = match.end() - 1
    depth = 0
    end = None
    for offset in range(start, len(source)):
        if source[offset] == "[":
            depth += 1
        elif source[offset] == "]":
            depth -= 1
            if depth == 0:
                end = offset + 1
                break
    if end is None:
        raise ValueError("micro-infer rows vector is not closed")
    body = source[start:end]
    row_texts = re.findall(r"\[([0-9\s]+)\]", body)
    rows = [list(map(int, row.split())) for row in row_texts]
    if (re.sub(r"\s+", "", re.sub(r"\[[0-9\s]+\]", "", body)) != "[]"
            or len(rows) != 27 or any(len(row) != 27 for row in rows)
            or any(value < 0 or value > 5 for row in rows for value in row)):
        raise ValueError("micro-infer contract is not a 27x27 nibble matrix")
    input_row = rows[ord(goal[-1]) - ord("a") + 1]
    peak = max(input_row)
    if peak == 0:
        raise ValueError("Goal ends in a model row with no output")
    return ord(" abcdefghijklmnopqrstuvwxyz"[input_row.index(peak)]), matrix_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--firmware", type=Path)
    parser.add_argument("--boot-media", type=Path,
                        help="matching native GPT/FAT16 image for the two positive boots")
    parser.add_argument("--goal", default="awai a",
                        help="1-51 lowercase letters/spaces, ending in a letter with model output")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z ]{0,50}[a-z]", args.goal):
        parser.error("--goal requires 1-51 lowercase letters/spaces, ending in a letter")
    try:
        expected_token_value, matrix_path = model_expected_token(args.goal)
    except ValueError as exc:
        parser.error(str(exc))
    base = load_base()
    build = args.build_dir.resolve(strict=True)
    receipt = build / "build-state.json"
    if not receipt.is_file():
        parser.error("build_dir requires build-state.json")
    built = json.loads(receipt.read_text())
    entry = built.get("kernelEntry")
    user_call = entry in (USER_ENTRY, USER_V4_ENTRY)
    layout_v2 = entry == USER_V4_ENTRY
    if built.get("state") != "MACOS_NATIVE_IMAGE_CANDIDATE" or entry not in (ENTRY, USER_ENTRY, USER_V4_ENTRY):
        parser.error("build is not the local-model confirmation candidate")
    if user_call and built.get("bootUserTarget") != (
            "x86_64-aiueos-user-v4" if layout_v2 else "x86_64-aiueos-user-v3"):
        parser.error("user syscall candidate requires its matching Amu user target")
    args.kernel, args.efi = build / "KERNEL.ELF", build / "BOOTX64.EFI"
    font, slot = build / "source/boot-font.bin", build / "source/boot-user-slot.bin"
    for name, path, expected in (("kernel", args.kernel, built["kernel"]),
                                 ("efi", args.efi, built["efi"]),
                                 ("font", font, built["bootFont"]),
                                 ("slot", slot, built["bootUserSlot"])):
        if path.is_symlink() or not path.is_file() or base.pin(path) != expected:
            parser.error(f"{name} differs from build receipt")
    graph = built.get("sourceGraph", {})
    for relative in ("native/user-elf-v4-local-model-entry.kotoba" if layout_v2 else
                     "native/user-elf-v3-local-model-entry.kotoba" if user_call
                     else "native/user-elf-v2-local-model-entry.kotoba",
                     "native/desktop.kotoba", "native/draft_store.kotoba",
                     "native/micro_infer.kotoba"):
        source = HERE.parent / relative
        if (source.is_symlink() or not source.is_file()
                or base.pin(source) != graph.get("/os/aiueos/" + relative)):
            parser.error(f"{relative} differs from build receipt")
    user_source = HERE.parent / ("native/itonami-local-model-user-v3.kotoba" if user_call
                                 else "native/itonami-local-model-user-v2.kotoba")
    user_elf = build / "boot-user.elf"
    if (user_source.is_symlink() or not user_source.is_file()
            or base.pin(user_source) != built.get("bootUserSource")
            or user_elf.is_symlink() or not user_elf.is_file()
            or base.pin(user_elf) != built.get("bootUserElf")):
        parser.error("Amu user source or ELF differs from build receipt")
    kernel, efi, slot_bytes = args.kernel.read_bytes(), args.efi.read_bytes(), slot.read_bytes()
    elf_size = struct.unpack_from("<Q", slot_bytes, 16)[0]
    elf = slot_bytes[64:64 + elf_size]
    if (len(slot_bytes) != 524288 or struct.unpack_from("<QQ", slot_bytes) !=
            (0x0031444c50554941, 3 if layout_v2 else 2) or elf_size != 8280
            or any(slot_bytes[64 + elf_size:])
            or base.pin(slot)["sha256"] != built["bootUserSlot"]["sha256"]
            or base.hashlib.sha256(elf).hexdigest() !=
            (USER_V4_ELF_SHA256 if layout_v2 else USER_ELF_SHA256 if user_call else ELF_SHA256)
            or elf != user_elf.read_bytes()
            or efi.count(kernel) != 1 or efi.count(slot_bytes) != 1
            or efi.count(font.read_bytes()) != 1):
        parser.error("kernel, EFI or model user payload differs")
    media = None
    if args.boot_media is not None:
        media = args.boot_media.resolve(strict=True)
        if args.boot_media.is_symlink() or not media.is_file():
            parser.error("boot media must be a regular non-symlink file")
        reader = base.import_file("media_reader", "check-native-media-format.py")
        reader.verify(media, args.efi)
    args.boot_media = media
    media_pin = base.pin(media) if media is not None else None
    header = struct.unpack_from("<IIQQQQQQ", kernel, 120)
    if header[:4] != (1, 6, 2097152 if layout_v2 else 1048576,
                       0x300000 if layout_v2 else 0x200000):
        parser.error("unexpected native context layout")
    context, code, request = header[3], header[3] + 0x20000, header[3] + 0x21000
    qemu_name = args.qemu or shutil.which("qemu-system-x86_64")
    if qemu_name is None:
        parser.error("QEMU missing; pass --qemu")
    args.qemu = Path(qemu_name).resolve(strict=True)
    args.firmware = (args.firmware or args.qemu.parent.parent / "share/qemu/edk2-x86_64-code.fd").resolve(strict=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or build.parent / f"{build.name}-model-debug-{stamp}-{os.getpid()}").resolve()
    if output.exists():
        parser.error("output must be a new private directory")
    output.mkdir(mode=0o700)
    disk = output / "draft.raw"
    blank = bytearray(128 * 512)
    struct.pack_into("<4I", blank, 0, 0x49415741, 0x54465244, 1, 128)
    disk.write_bytes(blank)
    goal, expected_token = args.goal, expected_token_value
    boots = []
    for ordinal in (1, 2):
        directory = output / f"boot-{ordinal}"
        process, qmp, log = base.boot(args, directory, disk)
        try:
            expected_goal = goal if ordinal == 2 else ""
            current = wait(base, qmp, directory, context, "boot",
                           lambda s: s["goal"] == base.PREFIX + expected_goal
                           and s["restore"] == ordinal - 1 and s["pending"] == 0
                           and s["approved"] == 0 and s["modelToken"] == 0)
            base.key(qmp, "2")
            current = wait(base, qmp, directory, context, "open",
                           lambda s: s["focus"] == 2 and s["keys"] > current["keys"])
            if ordinal == 1:
                for index, letter in enumerate(goal, 1):
                    before = current["keys"]
                    base.key(qmp, letter)
                    current = wait(base, qmp, directory, context, f"edit-{index}",
                                   lambda s, i=index, p=before:
                                   s["goal"] == base.PREFIX + goal[:i] and s["keys"] > p)
                before = current["keys"]
                base.key(qmp, "f5")
                committed = wait(base, qmp, directory, context, "commit",
                                 lambda s: s["commit"] == 1 and s["generation"] == 1
                                 and s["keys"] > before)
                boots.append({"boot": 1, "committed": committed})
            else:
                assert current["generation"] == 1
                visible = base.screenshot(qmp, directory, font.read_bytes(), goal, "restored-goal")
                base.key(qmp, "ret")
                pending = wait(base, qmp, directory, context, "pending",
                               lambda s: s["pending"] == 1 and s["approved"] == 0
                               and s["modelToken"] == 0 and s["title"] == PROMPT_TITLE)
                assert qmp.dump(request, 4096, "request-pending.bin", directory)[256:320] == bytes(64)
                assert qmp.dump(code, 4096, "code-pending.bin", directory)[:478 if user_call else 330] == bytes(478 if user_call else 330)
                approval_ppm = directory / "approval.ppm"
                approval_png = directory / "approval.png"
                qmp.call("screendump", {"filename": str(approval_ppm)})
                base.import_file("desktop_pixels", "check-native-desktop-qemu.py").ppm_png(
                    approval_ppm, approval_png)
                base.key(qmp, "n")
                denied = wait(base, qmp, directory, context, "denied",
                              lambda s: s["pending"] == 0 and s["approved"] == 0
                              and s["submitted"] == 0 and s["modelToken"] == 0
                              and s["title"] == "Itonami")
                assert qmp.dump(request, 4096, "request-denied.bin", directory)[256:320] == bytes(64)
                assert qmp.dump(code, 4096, "code-denied.bin", directory)[:478 if user_call else 330] == bytes(478 if user_call else 330)
                registers = qmp.hmp("info registers")
                assert re.search(r"\bCPL=0\b", registers)
                base.key(qmp, "ret")
                wait(base, qmp, directory, context, "pending-again",
                     lambda s: s["pending"] == 1 and s["title"] == PROMPT_TITLE)
                base.key(qmp, "y")
                user = endpoint(base, qmp, directory, code, request, elf, expected_token, goal, user_call)
                after = snapshot(base, qmp, directory, context)
                assert after["approved"] == (0 if user_call else 1)
                assert after["modelToken"] == expected_token
                boots.append({"boot": 2, "restored": current, "pending": pending,
                              "denied": denied, "screenshot": visible,
                              "approvalScreenshot": {"image": str(approval_png),
                                                     "pin": base.pin(approval_png)},
                              "userEndpoint": user})
        finally:
            base.close(process, qmp, log)
        if ordinal == 1:
            first = disk.read_bytes()
            assert first != bytes(blank) and first[:512] == blank[:512]
            assert first[2048:] == blank[2048:]
        else:
            assert disk.read_bytes() == first, "model operation changed the Goal draft disk"
    # A changed code byte in the sealed slot must fail before the guest copies
    # either user page or computes the local model. Keep the original EFI and
    # the marked disk immutable across this independent third boot.
    original_efi = args.efi
    changed = bytearray(efi)
    changed[efi.index(slot_bytes) + 64 + 4096 + 20] ^= 1
    assert sum(a != b for a, b in zip(efi, changed)) == 1
    modified_efi = output / "modified-slot.EFI"
    modified_efi.write_bytes(changed)
    args.efi = modified_efi
    args.boot_media = None  # The altered EFI is tested through its own FAT boot.
    directory = output / "modified-slot"
    process, qmp, log = base.boot(args, directory, disk)
    try:
        wait(base, qmp, directory, context, "boot",
             lambda s: s["goal"] == base.PREFIX + goal and s["restore"] == 1)
        base.key(qmp, "2")
        wait(base, qmp, directory, context, "open", lambda s: s["focus"] == 2)
        base.key(qmp, "ret")
        wait(base, qmp, directory, context, "pending",
             lambda s: s["pending"] == 1 and s["title"] == PROMPT_TITLE)
        base.key(qmp, "y")
        samples, last_rip = 0, None
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline and samples < 12:
            registers = qmp.hmp("info registers")
            rip_match = re.search(r"\bRIP=([0-9a-f]+)", registers, re.I)
            cpl_match = re.search(r"\bCPL=([0-3])", registers)
            page = qmp.dump(request, 4096, "request-refused.bin", directory)
            code_page = qmp.dump(code, 4096, "code-refused.bin", directory)
            current = snapshot(base, qmp, directory, context)
            if rip_match and cpl_match:
                rip, cpl = int(rip_match.group(1), 16), int(cpl_match.group(1))
                assert cpl != 3, "modified user ELF reached CPL3"
                if (cpl == 0 and page[:320] == bytes(320)
                        and code_page[:478 if user_call else 330] == bytes(478 if user_call else 330)
                        and current["modelToken"] == 0):
                    samples = samples + 1 if rip == last_rip else 1
                    last_rip = rip
                else:
                    samples = 0
            time.sleep(.2)
        assert samples >= 12, "modified slot refusal endpoint unavailable"
        modified = {"cpl": 0, "stableRip": last_rip, "samples": samples,
                    "userPagesUnchanged": True, "modelNotRun": True}
    finally:
        base.close(process, qmp, log)
        args.efi = original_efi
        args.boot_media = media
    assert disk.read_bytes() == first, "modified slot boot changed the draft disk"
    if media is not None:
        assert base.pin(media) == media_pin, "boot media changed during QEMU snapshot runs"
    report = {"schema": "aiueos.native-local-model-confirm-qemu.v2",
              "status": ("PASS_NATIVE_USER_MODEL_SYSCALL_AFTER_RESTORE" if user_call
                         else "PASS_NATIVE_LOCAL_MODEL_DENY_APPROVE_CPL3_AFTER_RESTORE"),
              "kernelEntry": entry, "userOriginatedModelCall": user_call,
              "build": str(build), "kernel": base.pin(args.kernel), "efi": base.pin(args.efi),
              "bootMedia": media_pin, "positiveBootsFromMedia": media is not None,
              "modifiedSlotBoot": "modified-efi-fat-directory",
              "slot": base.pin(slot), "font": base.pin(font),
              "userSource": base.pin(user_source), "userElf": base.pin(user_elf),
              "qemu": base.pin(args.qemu), "firmware": base.pin(args.firmware),
              "observer": base.pin(Path(__file__)),
              "userElfSha256": USER_V4_ELF_SHA256 if layout_v2 else USER_ELF_SHA256 if user_call else ELF_SHA256,
              "goal": goal, "expectedToken": expected_token,
              "modelContract": base.pin(matrix_path), "boots": boots,
              "modifiedSlotRefusal": modified,
              "scratchDisk": base.pin(disk), "qmpTransport": "private-stdio",
              "vncUsed": False, "networkUsed": False, "humanPasswordRequired": False,
              "syntheticKeysProveHumanConsent": False,
              "externalOperation": False, "agentLoop": False,
              "D2WorkspaceCodec": False, "signedHeadAuthority": False,
              "releaseAdmission": False, "physicalHardware": False}
    path = output / "debug-summary.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "receipt": str(path),
                      "token": expected_token, "screen": boots[1]["screenshot"]["image"]}))


if __name__ == "__main__":
    sys.exit(main())
