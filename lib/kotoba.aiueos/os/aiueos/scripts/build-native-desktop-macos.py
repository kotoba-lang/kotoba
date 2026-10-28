#!/usr/bin/env python3
"""Build AIUEOS on Apple Silicon and boot its exact media without a login.

Python stages, pins and observes. Amu/Kotoba native programs emit the font,
kernel, EFI and GPT/FAT16 media; QEMU QMP stdio checks the selected guest
desktop or the opt-in local-draft save and cold restore.
The output is a diagnostic VM candidate, never an installer or release.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys


HERE = Path(__file__).resolve().parent
OS = HERE.parent
OWNER_ENV = {
    "capability-link-frame": "AIUEOS_LINK_FRAME_SOURCE_PATH",
    "capability-dma-map": "AIUEOS_DMA_MAP_SOURCE_PATH",
    "capability-mmio-map": "AIUEOS_MMIO_MAP_SOURCE_PATH",
    "capability-net-transport": "AIUEOS_NET_TRANSPORT_SOURCE_PATH",
    "org-ietf-tcp": "AIUEOS_ORG_IETF_TCP_SOURCE_PATH",
}
FUEL = 9007199254740991


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verified_file(path, expected=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError("input must be a regular non-symlink file: " + str(path))
    actual = pin(path)
    if expected and actual["sha256"] != expected:
        raise ValueError("input digest mismatch: " + path.name)
    return actual


def verify_macho(path, expected):
    actual = verified_file(path, expected)
    raw = path.read_bytes()
    if len(raw) < 32 or struct.unpack_from("<IiiI", raw) != (0xfeedfacf, 0x100000c, 0, 2):
        raise ValueError("expected signed arm64 Mach-O: " + path.name)
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(path)],
                   check=True, capture_output=True)
    linked = subprocess.run(["/usr/bin/otool", "-L", str(path)],
                            check=True, capture_output=True).stdout.splitlines()
    if linked != [f"{path}:".encode()]:
        raise ValueError("undeclared dylib dependency: " + path.name)
    return actual


def repository_bootstrap(amu, args):
    supplied = (args.compiler_image, args.compiler_sha256,
                args.packager_image, args.packager_sha256)
    if any(value is not None for value in supplied):
        if not all(value is not None for value in supplied):
            raise ValueError("explicit Mac bootstrap requires four image/pin arguments")
        return None, None
    descriptor_path = amu / "seed/bootstrap/aarch64-macos/root.json"
    descriptor_pin = verified_file(descriptor_path)
    descriptor = json.loads(descriptor_path.read_text())
    # A root that knows kernel-v3 pins the previous compiler as its v1/v2 reference
    # (amu#1624); an older root only knows kernel-v1, whose code limit (1,044,480
    # bytes) the desktop exceeds, so it must be refused for any other target.
    if (args.kernel_target != "x86_64-aiueos-kernel-v1"
            and "kernelV2ReferenceCompiler" not in descriptor):
        raise ValueError(
            "the repository bootstrap compiler only knows x86_64-aiueos-kernel-v1, whose "
            "code limit (1,044,480 bytes) the desktop exceeds; pass --compiler-image/"
            "--compiler-sha256/--packager-image/--packager-sha256 of a compiler that knows "
            + args.kernel_target + ", or --kernel-target x86_64-aiueos-kernel-v1")
    if (descriptor.get("schema") != "amu.macos-arm64-selfhost-root.v1"
            or descriptor.get("status") != "diagnostic-candidate"
            or descriptor.get("fullManifest") != "seed/FULL-MANIFEST"):
        raise ValueError("unsupported repository Mac bootstrap descriptor")
    roles = {"compiler": "seed/bootstrap/aarch64-macos/amu-full-root.macho",
             "packager": "seed/bootstrap/aarch64-macos/kotoba-packager-root.macho"}
    for role, relative in roles.items():
        record = descriptor[role]
        if record["path"] != relative:
            raise ValueError("Mac bootstrap role path changed: " + role)
        if verified_file(amu / relative, record["sha256"]) != {
                key: record[key] for key in ("bytes", "sha256")}:
            raise ValueError("Mac bootstrap role size changed: " + role)
    source = descriptor["packagerSource"]
    if (source["path"] != "seed/macos-fs2-runtime-packager.kotoba"
            or verified_file(amu / source["path"], source["sha256"]) != {
                key: source[key] for key in ("bytes", "sha256")}):
        raise ValueError("Mac packager source changed")
    manifest = amu / descriptor["fullManifest"]
    verified_file(manifest)
    names = [line for line in manifest.read_text().splitlines()
             if line and not line.startswith("#")]
    # The signed Mac root has shipped with both the 47-module and 48-module
    # source graphs. The descriptor's fullSource digest below binds the exact
    # ordered graph; a stale or truncated manifest must still be refused.
    if len(names) not in (47, 48) or len(set(names)) != len(names):
        raise ValueError("Mac bootstrap manifest is not a complete native source graph")
    source_hash = hashlib.sha256()
    source_bytes = 0
    for name in names:
        part = Path(name)
        if part.is_absolute() or ".." in part.parts or part.parts[0] != "seed":
            raise ValueError("invalid Mac bootstrap source path")
        module = amu / part
        verified_file(module)
        raw = module.read_bytes() + b"\n"
        source_hash.update(raw)
        source_bytes += len(raw)
    source_pin = {"bytes": source_bytes, "sha256": source_hash.hexdigest()}
    if source_pin != descriptor["fullSource"]:
        raise ValueError("Mac bootstrap source graph changed")
    args.compiler_image = amu / roles["compiler"]
    args.compiler_sha256 = descriptor["compiler"]["sha256"]
    args.packager_image = amu / roles["packager"]
    args.packager_sha256 = descriptor["packager"]["sha256"]
    return descriptor_pin, source_pin


def main(args):
    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
        raise ValueError("the integrated Mac gate requires Apple Silicon")
    descriptor = HERE.parents[2] / "distributions" / args.distribution / "distribution.json"
    distribution_pin = verified_file(descriptor)
    if args.amu_source.is_symlink() or args.owner_repo_root.is_symlink():
        raise ValueError("source roots must not be symlinks")
    amu = args.amu_source.resolve(strict=True)
    owners = args.owner_repo_root.resolve(strict=True)
    if not amu.is_dir() or not owners.is_dir():
        raise ValueError("source roots must be directories")
    descriptor_pin, bootstrap_source_pin = repository_bootstrap(amu, args)
    compiler = args.compiler_image.resolve(strict=True)
    packager = args.packager_image.resolve(strict=True)
    qemu = args.qemu.resolve(strict=True)
    firmware = args.firmware.resolve(strict=True)
    font_source = args.font.resolve(strict=True)
    compiler_pin = verify_macho(compiler, args.compiler_sha256)
    packager_pin = verify_macho(packager, args.packager_sha256)
    qemu_pin = verified_file(qemu, args.qemu_sha256)
    firmware_pin = verified_file(firmware, args.firmware_sha256)
    font_pin = verified_file(font_source)
    if not os.access(qemu, os.X_OK):
        raise ValueError("QEMU is not executable")
    source_root_pins = {}
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "LANG": "C"}
    for name, variable in OWNER_ENV.items():
        root = owners / name / "kotoba"
        if root.is_symlink() or not root.is_dir():
            raise ValueError("missing canonical owner source: " + name)
        env[variable] = str(root)
        source_root_pins[name] = root.name
    scripts = {
        name: HERE / name for name in (
            "build-kotoba-native-desktop.sh", "build-native-desktop-macos.py",
            "build-native-font-macos.py", "build-native-kernel-macos.py",
            "build-native-media-macos.py", "check-native-desktop-qemu.py",
            "check-native-draft-restart-qemu.py", "check-native-consent-qemu.py",
            "check-native-idle-silent-qemu.py", "check-native-cid-qemu.py", "check-native-sha512-qemu.py", "check-native-gf25519-qemu.py", "check-native-ed25519-qemu.py", "check-native-keyseal-qemu.py", "check-native-keystore-qemu.py",
            "check-native-media-format.py",
        )
    }
    script_pins = {name: verified_file(path) for name, path in scripts.items()}
    owner_manifest = verified_file(OS / "native/source-dependencies.json")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    (output / "distribution.json").write_bytes(descriptor.read_bytes())
    # QEMU's snapshot overlay uses the host temporary directory. Keep it
    # inside this private task output so no global /var/tmp grant is needed.
    env["TMPDIR"] = str(output)
    env["TMP"] = str(output)
    env["TEMP"] = str(output)
    state = {
        "schema": "aiueos.macos-native-desktop-qemu-candidate.v1",
        "state": "STAGING", "profile": args.profile,
        "distribution": {"id": args.distribution,
                         "descriptor": {"path": "distribution.json", **distribution_pin}},
        "host": [platform.system(), platform.machine()],
        "compiler": compiler_pin, "packager": packager_pin,
        "amuBootstrapRoot": descriptor_pin,
        "amuBootstrapSource": bootstrap_source_pin,
        "qemu": qemu_pin, "firmware": firmware_pin, "fontSource": font_pin,
        "ownerManifest": owner_manifest, "ownerNames": sorted(source_root_pins),
        "scripts": script_pins, "fuel": FUEL, "calls": [],
        "linuxJVMNodeOrCCompiler": False, "releaseQualified": False,
        "physicalHardwareQualified": False,
    }

    def save():
        (output / "native-desktop-macos.json").write_text(json.dumps(state, indent=2) + "\n")

    def call(name, script, argv):
        result = subprocess.run([sys.executable, str(script), *map(str, argv)],
                                cwd=output, env=env, capture_output=True, timeout=3600)
        stdout = output / (name + ".stdout")
        stderr = output / (name + ".stderr")
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        state["calls"].append({"name": name, "exit": result.returncode,
                               "stdout": pin(stdout), "stderr": pin(stderr)})
        save()
        if result.returncode or result.stderr:
            state["state"] = "BLOCKED_" + name.upper()
            save()
            raise ValueError(f"{name} exited {result.returncode}: "
                             + result.stderr.decode(errors="replace")[-800:])
        print(name, "PASS", flush=True)

    save()
    try:
        font = output / "font"
        kernel = output / "kernel"
        media = output / "media"
        guest = output / "qemu"
        guest_iso = output / "qemu-iso"
        call("font", scripts["build-native-font-macos.py"], [
            "--amu-source", amu, "--compiler-image", compiler,
            "--compiler-sha256", args.compiler_sha256,
            "--packager-image", packager, "--packager-sha256", args.packager_sha256,
            "--font", font_source, "--output", font])
        font_state = json.loads((font / "native-font.json").read_text())
        padded = font / "aiueos-padded.fnt"
        if (font_state["state"] != "MACOS_NATIVE_FONT_CANDIDATE"
                or font_state["compiler"] != compiler_pin
                or font_state["packager"] != packager_pin
                or pin(padded) != font_state["padded"]):
            raise ValueError("font build receipt mismatch")

        kernel_entry = ("workspace-entry.kotoba" if args.profile == "local-draft"
                        else "consent-entry.kotoba" if args.profile in ("consent", "keystore")
                        else "cid-entry.kotoba" if args.profile == "cid"
                        else "sha512-entry.kotoba" if args.profile == "sha512"
                        else "gf-entry.kotoba" if args.profile == "gf25519"
                        else "ed-entry.kotoba" if args.profile == "ed25519"
                        else "keyseal-entry.kotoba" if args.profile == "keyseal"
                        else "desktop-entry.kotoba")
        call("kernel", scripts["build-native-kernel-macos.py"], [
            "--compiler-image", compiler, "--compiler-sha256", args.compiler_sha256,
            "--kernel-source", OS / "native" / kernel_entry,
            "--kernel-target", args.kernel_target,
            "--fuel", FUEL, "--payload", padded,
            "--payload-sha256", font_state["padded"]["sha256"], "--output", kernel])
        kernel_state = json.loads((kernel / "build-state.json").read_text())
        efi = kernel / "BOOTX64.EFI"
        image = kernel / "KERNEL.ELF"
        if (kernel_state["state"] != "MACOS_NATIVE_IMAGE_CANDIDATE"
                or kernel_state["sourceModuleCount"] != (36 if args.profile == "cid" else 35)
                or kernel_state["fuel"] != FUEL
                or kernel_state["compiler"] != compiler_pin
                or pin(efi) != kernel_state["efi"] or pin(image) != kernel_state["kernel"]
                or kernel_state["bootPayload"] != font_state["padded"]):
            raise ValueError("kernel or EFI build receipt mismatch")

        call("media", scripts["build-native-media-macos.py"], [
            "--amu-source", amu, "--compiler-image", compiler,
            "--compiler-sha256", args.compiler_sha256,
            "--packager-image", packager, "--packager-sha256", args.packager_sha256,
            "--efi", efi, "--efi-sha256", kernel_state["efi"]["sha256"],
            "--output", media])
        media_state = json.loads((media / "native-media.json").read_text())
        disk = media / "awai-native.img"
        iso = media / "awai-native.iso"
        if (media_state["state"] != "MACOS_NATIVE_MEDIA_CANDIDATE"
                or media_state["compiler"] != compiler_pin
                or media_state["packager"] != packager_pin
                or media_state["efi"] != kernel_state["efi"]
                or pin(disk) != media_state["image"]
                or pin(iso) != media_state["iso"]
                or media_state["independentISO"]["status"] !=
                   "PASS_INDEPENDENT_NATIVE_EL_TORITO_ISO_READBACK"):
            raise ValueError("media build receipt mismatch")

        guest_script = ("check-native-draft-restart-qemu.py" if args.profile == "local-draft"
                        else "check-native-consent-qemu.py" if args.profile == "consent"
                        else "check-native-idle-silent-qemu.py" if args.profile == "idle"
                        else "check-native-cid-qemu.py" if args.profile == "cid"
                        else "check-native-sha512-qemu.py" if args.profile == "sha512"
                        else "check-native-gf25519-qemu.py" if args.profile == "gf25519"
                        else "check-native-ed25519-qemu.py" if args.profile == "ed25519"
                        else "check-native-keyseal-qemu.py" if args.profile == "keyseal"
                        else "check-native-keystore-qemu.py" if args.profile == "keystore"
                        else "check-native-desktop-qemu.py")
        guest_args = [
            "--media", disk, "--efi", efi, "--kernel", image,
            "--qemu", qemu, "--firmware", firmware, "--font", padded,
            "--output", guest]
        call("qemu", scripts[guest_script], guest_args)
        receipt_name = ("native-draft-restart.json" if args.profile == "local-draft"
                        else "native-consent-qemu.json" if args.profile == "consent"
                        else "native-idle-silent-qemu.json" if args.profile == "idle"
                        else "native-cid-qemu.json" if args.profile == "cid"
                        else "native-sha512-qemu.json" if args.profile == "sha512"
                        else "native-gf25519-qemu.json" if args.profile == "gf25519"
                        else "native-ed25519-qemu.json" if args.profile == "ed25519"
                        else "native-keyseal-qemu.json" if args.profile == "keyseal"
                        else "native-keystore-qemu.json" if args.profile == "keystore"
                        else "native-desktop-qemu.json")
        observed = json.loads((guest / receipt_name).read_text())
        expected_status = ("PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE" if args.profile == "local-draft"
                           else "PASS_NATIVE_CONSENT_QEMU" if args.profile == "consent"
                           else "PASS_NATIVE_IDLE_SILENT_QEMU" if args.profile == "idle"
                           else "PASS_NATIVE_CID_QEMU" if args.profile == "cid"
                           else "PASS_NATIVE_SHA512_QEMU" if args.profile == "sha512"
                           else "PASS_NATIVE_GF25519_QEMU" if args.profile == "gf25519"
                           else "PASS_NATIVE_ED25519_QEMU" if args.profile == "ed25519"
                           else "PASS_NATIVE_KEYSEAL_QEMU" if args.profile == "keyseal"
                           else "PASS_NATIVE_KEYSTORE_QEMU" if args.profile == "keystore"
                           else "PASS_NATIVE_DESKTOP_INPUT_QEMU")
        expected_events = (12 if args.profile == "local-draft"
                           else 18 if args.profile == "consent"
                           else 4 if args.profile == "idle"
                           else 3 if args.profile == "ed25519"
                           else 5 if args.profile == "keystore"
                           else 2 if args.profile in ("cid", "sha512", "gf25519", "keyseal") else 12)
        if (observed["status"] != expected_status
                or len(observed["events"]) != expected_events
                or observed["kernel"] != kernel_state["kernel"]
                or observed["efi"] != kernel_state["efi"]
                or observed["media"] != media_state["image"]
                or observed["firmware"] != firmware_pin
                or observed["observer"] != script_pins[guest_script]
                or (args.profile == "desktop"
                    and observed.get("layoutTable") != pin(OS / "native/layout-table.json"))):
            raise ValueError("QEMU guest observation is not bound to this build")
        if args.profile == "local-draft":
            if (not observed["nativeATACommit"] or not observed["coldProcessBoot"]
                    or not observed["previousCommitAfterUncommittedCrash"]
                    or observed["D2WorkspaceCodec"] or observed["signedHeadAuthority"]
                    or observed["releaseAdmission"]
                    or observed["font"] != font_state["padded"]
                    or [row["goal"] for row in observed["visibleGoalScreenshots"]] != ["ab", "ab", "abd"]
                    or any(row["inkPixels"] <= 0
                           for shot in observed["visibleGoalScreenshots"]
                           for row in shot["glyphs"])):
                raise ValueError("local-draft persistence verdict is incomplete")
        elif args.profile == "idle":
            if (observed["font"] != font_state["padded"]
                    or observed["measuredGuestFramesAfterFirstFrame"] != 0
                    or [row["name"] for row in observed["events"]] != [
                        "first-frame", "idle", "control", "input"]
                    or observed["events"][1]["newFrames"] != 0
                    or observed["events"][2]["newFrames"] < 1
                    or observed["physicalHardware"]):
                raise ValueError("idle-silent verdict is incomplete")
        elif args.profile == "cid":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "cid-admit"]
                    or observed["events"][1]["codes"] != [0, 8, 4, 3]
                    or observed["urlSchemeHandler"] or observed["physicalHardware"]):
                raise ValueError("cid admission verdict is incomplete")
        elif args.profile == "sha512":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "sha512-digests"]
                    or observed["events"][1]["matches"] != ["abc", "fips-two-block", "abd"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("sha512 verdict is incomplete")
        elif args.profile == "gf25519":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "gf25519"]
                    or len(observed["events"][1]["cases"]) != 3
                    or observed["signing"] or observed["pointArithmetic"] or observed["physicalHardware"]):
                raise ValueError("gf25519 verdict is incomplete")
        elif args.profile == "ed25519":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "ed25519-pubkey", "ed25519-sign"]
                    or len(observed["events"][1]["keys"]) != 3
                    or len(observed["events"][2]["signatures"]) != 3
                    or not observed["signing"] or observed["deviceKey"] or observed["physicalHardware"]):
                raise ValueError("ed25519 verdict is incomplete")
        elif args.profile == "keystore":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != [
                        "boot1-create", "boot2-locked", "unlock-wrong-passphrase", "unlock-right-passphrase", "sign-after-unlock"]
                    or not observed["persistedAcrossReboot"] or not observed["wrongPassphraseRefused"]
                    or observed["physicalHardware"] or observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("keystore verdict is incomplete")
        elif args.profile == "keyseal":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "keyseal-seal-open"]
                    or not observed["sealed"] or observed["deviceKey"] or observed["physicalHardware"]):
                raise ValueError("keyseal verdict is incomplete")
        elif args.profile == "consent":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != [
                        "first-frame", "entropy-probe", "itonami-goal-typed", "collapse-key", "collapse-click",
                        "consent-open",
                        "launcher-key-ignored", "launcher-click-ignored", "key-deny",
                        "pointer-deny", "esc-deny", "key-deny", "passphrase-cancel", "key-allow",
                        "sign-deny", "sign-allow", "draft-after-key", "pointer-allow"]
                    or observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("consent surface verdict is incomplete")
        elif (observed["font"] != font_state["padded"]
              or [row["codepoint"] for row in observed["renderedGoalGlyphs"]] != [97, 98]
              or any(row["inkPixels"] <= 0 for row in observed["renderedGoalGlyphs"])):
            raise ValueError("normal desktop visible Goal verdict is incomplete")
        iso_observed = None
        if args.profile == "desktop":
            call("qemu-iso", scripts["check-native-desktop-qemu.py"], [
                "--media", disk, "--iso", iso, "--efi", efi, "--kernel", image,
                "--qemu", qemu, "--firmware", firmware, "--font", padded,
                "--output", guest_iso])
            iso_observed = json.loads((guest_iso / "native-desktop-qemu.json").read_text())
            if (iso_observed["status"] != "PASS_NATIVE_DESKTOP_INPUT_QEMU"
                    or len(iso_observed["events"]) != 12
                    or iso_observed["kernel"] != kernel_state["kernel"]
                    or iso_observed["efi"] != kernel_state["efi"]
                    or iso_observed["iso"] != media_state["iso"]
                    or iso_observed["independentISO"]["status"] !=
                       "PASS_INDEPENDENT_NATIVE_EL_TORITO_ISO_READBACK"
                    or iso_observed["observer"] != script_pins["check-native-desktop-qemu.py"]
                    or [row["codepoint"] for row in iso_observed["renderedGoalGlyphs"]] != [97, 98]):
                raise ValueError("ISO QEMU guest observation is not bound to this build")
        if (pin(compiler) != compiler_pin or pin(packager) != packager_pin
                or (descriptor_pin is not None and
                    repository_bootstrap(amu, argparse.Namespace(
                        compiler_image=None, compiler_sha256=None,
                        packager_image=None, packager_sha256=None,
                        kernel_target=args.kernel_target)) !=
                    (descriptor_pin, bootstrap_source_pin))
                or pin(qemu) != qemu_pin or pin(firmware) != firmware_pin
                or pin(font_source) != font_pin
                or pin(descriptor) != distribution_pin
                or pin(OS / "native/source-dependencies.json") != owner_manifest
                or any(pin(scripts[name]) != identity for name, identity in script_pins.items())):
            raise ValueError("tool or source changed during integrated build")
        state.update(state=("MACOS_NATIVE_DRAFT_RESTORE_QEMU_CANDIDATE"
                            if args.profile == "local-draft"
                            else "MACOS_NATIVE_CONSENT_QEMU_CANDIDATE" if args.profile == "consent"
                            else "MACOS_NATIVE_IDLE_SILENT_QEMU_CANDIDATE" if args.profile == "idle"
                            else "MACOS_NATIVE_CID_QEMU_CANDIDATE" if args.profile == "cid"
                            else "MACOS_NATIVE_SHA512_QEMU_CANDIDATE" if args.profile == "sha512"
                            else "MACOS_NATIVE_GF25519_QEMU_CANDIDATE" if args.profile == "gf25519"
                            else "MACOS_NATIVE_ED25519_QEMU_CANDIDATE" if args.profile == "ed25519"
                            else "MACOS_NATIVE_KEYSEAL_QEMU_CANDIDATE" if args.profile == "keyseal"
                            else "MACOS_NATIVE_KEYSTORE_QEMU_CANDIDATE" if args.profile == "keystore"
                            else "MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE"),
                     font=font_state["padded"], kernel=kernel_state["kernel"],
                     efi=kernel_state["efi"], media=media_state["image"], iso=media_state["iso"],
                     guestEvents=len(observed["events"]),
                     guestInputQualified=True, nativeFormatEmission=True,
                     isoBootQualified=iso_observed is not None,
                     localDraftRestoreQualified=args.profile == "local-draft",
                     qualification=("Mac native local-draft save and cold restore on QEMU"
                                    if args.profile == "local-draft"
                                    else "Mac native consent surface (Allow, Deny, modal) on QEMU"
                                    if args.profile == "consent"
                                    else "Mac native idle desktop emits no guest frame on a captured virtual NIC (QEMU)"
                                    if args.profile == "idle"
                                    else "Mac native CID admission self-test (accept, digest, multihash, codec) on QEMU"
                                    if args.profile == "cid"
                                    else "Mac native SHA-512 self-test (FIPS 180-4 vectors) on QEMU"
                                    if args.profile == "sha512"
                                    else "Mac native GF(2^255-19) arithmetic self-test on QEMU"
                                    if args.profile == "gf25519"
                                    else "Mac native Ed25519 public keys from RFC 8032 seeds on QEMU"
                                    if args.profile == "ed25519"
                                    else "Mac native passphrase key sealing self-test (seal, open, wrong passphrase, changed blob) on QEMU"
                                    if args.profile == "keyseal"
                                    else "Mac native sealed device key survives a reboot; a wrong passphrase is refused (two boots, QEMU)"
                                    if args.profile == "keystore"
                                    else "Mac native GPT and EFI El Torito ISO QEMU desktop input")
                     + "; D2 workspace, release and physical gates separate")
        save()
        print(state["state"], state["media"]["sha256"])
    except Exception as error:
        if not state["state"].startswith("BLOCKED_"):
            state["state"] = "BLOCKED_INTEGRATED_BUILD"
        state["error"] = str(error)
        save()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amu-source", type=Path, required=True)
    parser.add_argument("--owner-repo-root", type=Path, required=True)
    parser.add_argument("--compiler-image", type=Path)
    parser.add_argument("--compiler-sha256")
    parser.add_argument("--packager-image", type=Path)
    parser.add_argument("--packager-sha256")
    parser.add_argument("--font", type=Path, default=OS / "fonts/aiueos-16.fnt")
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--qemu-sha256", required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--firmware-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("desktop", "local-draft", "consent", "idle", "cid", "sha512", "gf25519", "ed25519", "keyseal", "keystore"), default="desktop")
    parser.add_argument("--distribution", choices=("aiueos", "awai"), default="aiueos")
    # kernel-v3 (RW at 0x400000) leaves the packager about 3 MiB of room (the compiler's
    # text cap stays 2 MiB, native/layout-table.json) instead of kernel-v1's
    # 1,044,480 bytes (the packager's bounded-ELF admission requires RX to end below
    # RW). The desktop with the consent surface no longer fits v1, so v3 is the
    # default. It needs a compiler image that knows the target; the repository
    # bootstrap compiler is v1-only, so that route refuses v3 below.
    parser.add_argument("--kernel-target",
                        choices=("x86_64-aiueos-kernel-v1", "x86_64-aiueos-kernel-v3"),
                        default="x86_64-aiueos-kernel-v3")
    main(parser.parse_args())
