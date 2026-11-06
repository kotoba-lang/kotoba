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
    # The signed Mac root has shipped with 47-, 48-, 49- and 61-module source
    # graphs (the count only has to be plausible). The descriptor's fullSource digest below binds the exact
    # ordered graph; a stale or truncated manifest must still be refused.
    if len(names) < 47 or len(set(names)) != len(names):
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
    # the gates keep one region table (native_regions.py); the compiler's definition (Amu seed/97) must equal it
    sys.path.insert(0, str(HERE))
    import native_regions
    import native_text_margin
    native_regions.verify_amu(amu)
    native_regions.verify_layout(amu, OS / "native/layout-table.json")
    # the app catalog is generated from app_catalog.json (JUN-811); a hand-edited or stale one is refused before any compile
    stale = subprocess.run([sys.executable, "-I", str(HERE / "gen-app-catalog.py"), "check"], capture_output=True, text=True)
    if stale.returncode:
        raise ValueError("app catalog is stale against app_catalog.json: " + stale.stdout.strip())
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
    if os.environ.get("AIUEOS_CSSOM_K_SOURCE_PATH"):      # JUN-920: the style gate's mutant builds stage mutated cssom region modules
        env["AIUEOS_CSSOM_K_SOURCE_PATH"] = os.environ["AIUEOS_CSSOM_K_SOURCE_PATH"]
    for name, variable in OWNER_ENV.items():
        root = owners / name / "kotoba"
        if root.is_symlink() or not root.is_dir():
            raise ValueError("missing canonical owner source: " + name)
        env[variable] = str(root)
        source_root_pins[name] = root.name
    scripts = {
        name: HERE / name for name in (
            "build-kotoba-native-desktop.sh", "build-native-desktop-macos.py",
            "build-native-font-macos.py", "build-native-bluetooth-payload-macos.py", "build-native-kernel-macos.py",
            "build-native-media-macos.py", "native_media_retention.py", "check-native-desktop-qemu.py",
            "check-native-draft-restart-qemu.py", "check-native-consent-qemu.py",
            "check-native-idle-silent-qemu.py", "check-native-cid-qemu.py", "check-native-sha512-qemu.py", "check-native-keccak-qemu.py", "check-native-mldsa-ntt-qemu.py", "mldsa_ntt_oracle.py", "check-native-mldsa-sample-qemu.py", "mldsa_sample_oracle.py", "check-native-mldsa-verify-qemu.py", "mldsa_verify_oracle.py", "check-native-imgsig-qemu.py", "imgsig_oracle.py", "check-native-style-qemu.py", "check-native-layout-qemu.py", "check-native-flex-qemu.py", "check-native-grid-qemu.py", "check-native-update2-qemu.py", "update2_oracle.py", "check-native-provision-esp-qemu.py", "aiueos-provision-esp.py", "check-native-builder-layout-qemu.py", "check-builder-layout.py", "check-provision-esp.py", "make-release-image.py", "aiueos-image.py", "check-native-catalog-qemu.py", "cat_oracle.py", "check-native-fresh-qemu.py", "fresh_oracle.py", "check-native-prodsig-qemu.py", "prodsig_oracle.py", "check-native-rtc-qemu.py", "rtc_probe_decode.py", "check-native-gf25519-qemu.py", "check-native-ed25519-qemu.py", "check-native-keyseal-qemu.py", "check-native-keystore-qemu.py", "check-native-dapps-qemu.py", "check-native-nvme-qemu.py", "check-native-input-state-qemu.py",
            "check-native-media-format.py", "native_regions.py", "native_ops.py", "native_text_margin.py",
            "check-native-shell-material-qemu.py", "check-native-gui-effects-qemu.py", "check-native-launcher-pages-qemu.py",
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

        payload_pin = font_state["padded"]
        if args.bluetooth_firmware:
            if args.profile != "input-state":
                raise ValueError("Bluetooth firmware bundle requires input-state profile")
            bundle = output / "bluetooth-payload"
            call("bluetooth-payload", scripts["build-native-bluetooth-payload-macos.py"], [
                "--amu-source", amu, "--compiler-image", compiler,
                "--compiler-sha256", args.compiler_sha256,
                "--packager-image", packager, "--packager-sha256", args.packager_sha256,
                "--font", padded, "--output", bundle])
            bundle_state = json.loads((bundle / "native-bluetooth-payload.json").read_text())
            padded = bundle / "aiueos-ble-payload.bin"
            payload_pin = bundle_state["payload"]
            if bundle_state["state"] != "PASS_NATIVE_BLE_PAYLOAD" or pin(padded) != payload_pin:
                raise ValueError("Bluetooth payload receipt mismatch")
            state["bluetoothFirmware"] = bundle_state

        kernel_entry = ("workspace-entry.kotoba" if args.profile == "local-draft"
                        else "consent-entry.kotoba" if args.profile in ("consent", "keystore")
                        else "cid-entry.kotoba" if args.profile == "cid"
                        else "sha512-entry.kotoba" if args.profile == "sha512"
                        else "keccak-entry.kotoba" if args.profile == "keccak"
                        else "mldsa-ntt-entry.kotoba" if args.profile == "mldsa-ntt"
                        else "mldsa-sample-entry.kotoba" if args.profile == "mldsa-sample"
                        else "mldsa-verify-entry.kotoba" if args.profile == "mldsa-verify"
                        else "imgsig-entry.kotoba" if args.profile == "imgsig"
                        else "style-entry.kotoba" if args.profile == "style"
                        else "layout-entry.kotoba" if args.profile == "layout"
                        else "flex-entry.kotoba" if args.profile == "flex"
                        else "grid-entry.kotoba" if args.profile == "grid"
                        else "gf-entry.kotoba" if args.profile == "gf25519"
                        else "ed-entry.kotoba" if args.profile == "ed25519"
                        else "keyseal-entry.kotoba" if args.profile == "keyseal"
                        else "dapps-entry.kotoba" if args.profile == "dapps"
                        else "input-entry.kotoba" if args.profile == "input-state"
                        else "desktop-debug-entry.kotoba" if args.profile in ("nvme", "update2", "provision", "builder-layout", "catalog", "fresh", "prodsig", "rtc")
                        else "desktop-entry.kotoba")
        call("kernel", scripts["build-native-kernel-macos.py"], [
            "--compiler-image", compiler, "--compiler-sha256", args.compiler_sha256,
            "--kernel-source", OS / "native" / kernel_entry,
            "--kernel-target", args.kernel_target,
            "--fuel", FUEL, "--payload", padded,
            "--payload-sha256", payload_pin["sha256"], "--output", kernel])
        kernel_state = json.loads((kernel / "build-state.json").read_text())
        efi = kernel / "BOOTX64.EFI"
        image = kernel / "KERNEL.ELF"
        # JUN-813 (ADR-0286 amendment 7): update.kotoba imports aiueos.imgsig-prodkeys, one module more than the counts below for every graph that has it
        graph_names = list(kernel_state["sourceGraph"])
        update_in_graph = any(n.endswith("/native/update.kotoba") for n in graph_names)
        if update_in_graph != any(n.endswith("/kotoba/aiueos/imgsig_prodkeys.kotoba") for n in graph_names):
            raise ValueError("the production signer keys module must be in the kernel graph exactly when update.kotoba is")
        if (kernel_state["state"] != "MACOS_NATIVE_IMAGE_CANDIDATE"
                or kernel_state["sourceModuleCount"] != ({"style": 55, "layout": 61, "flex": 54, "grid": 53}.get(args.profile, 51) + (1 if update_in_graph else 0))
                or kernel_state["fuel"] != FUEL
                or kernel_state["compiler"] != compiler_pin
                or pin(efi) != kernel_state["efi"] or pin(image) != kernel_state["kernel"]
                or kernel_state["bootPayload"] != payload_pin):
            raise ValueError("kernel or EFI build receipt mismatch")
        # JUN-811: the compiler prints no code extent when the kernel fits, so estimate the margin under its cap
        layout = json.loads((OS / "native/layout-table.json").read_text())
        rung = next(row for row in layout["rungs"].values() if row["target"] == args.kernel_target)
        text_margin = native_text_margin.text_margin(image.read_bytes(), rung["compilerTextCapBytes"],
                                                     args.compiler_sha256, rung)
        if args.profile == "desktop" and text_margin["state"] == "FAIL":
            raise ValueError("kernel text margin is below the minimum: " + json.dumps(text_margin, sort_keys=True))
        if text_margin["state"] == "WARN":
            print("warning: kernel text margin is low: " + json.dumps(text_margin, sort_keys=True), file=sys.stderr)

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
                        else "check-native-keccak-qemu.py" if args.profile == "keccak"
                        else "check-native-mldsa-ntt-qemu.py" if args.profile == "mldsa-ntt"
                        else "check-native-mldsa-sample-qemu.py" if args.profile == "mldsa-sample"
                        else "check-native-mldsa-verify-qemu.py" if args.profile == "mldsa-verify"
                        else "check-native-imgsig-qemu.py" if args.profile == "imgsig"
                        else "check-native-style-qemu.py" if args.profile == "style"
                        else "check-native-layout-qemu.py" if args.profile == "layout"
                        else "check-native-flex-qemu.py" if args.profile == "flex"
                        else "check-native-grid-qemu.py" if args.profile == "grid"
                        else "check-native-gf25519-qemu.py" if args.profile == "gf25519"
                        else "check-native-ed25519-qemu.py" if args.profile == "ed25519"
                        else "check-native-keyseal-qemu.py" if args.profile == "keyseal"
                        else "check-native-keystore-qemu.py" if args.profile == "keystore"
                        else "check-native-dapps-qemu.py" if args.profile == "dapps"
                        else "check-native-input-state-qemu.py" if args.profile == "input-state"
                        else "check-native-nvme-qemu.py" if args.profile == "nvme"
                        else "check-native-update2-qemu.py" if args.profile == "update2"
                        else "check-native-provision-esp-qemu.py" if args.profile == "provision"
                        else "check-native-builder-layout-qemu.py" if args.profile == "builder-layout"
                        else "check-native-catalog-qemu.py" if args.profile == "catalog"
                        else "check-native-fresh-qemu.py" if args.profile == "fresh"
                        else "check-native-prodsig-qemu.py" if args.profile == "prodsig"
                        else "check-native-rtc-qemu.py" if args.profile == "rtc"
                        else "check-native-desktop-qemu.py")
        guest_args = [
            "--media", disk, "--efi", efi, "--kernel", image,
            "--qemu", qemu, "--firmware", firmware, "--font", padded,
            "--output", guest]
        if args.expect_stuck_entropy:
            if args.profile != "consent":
                raise ValueError("--expect-stuck-entropy needs --profile consent")
            guest_args.append("--expect-stuck-entropy")
        call("qemu", scripts[guest_script], guest_args)
        receipt_name = ("native-draft-restart.json" if args.profile == "local-draft"
                        else "native-consent-qemu.json" if args.profile == "consent"
                        else "native-idle-silent-qemu.json" if args.profile == "idle"
                        else "native-cid-qemu.json" if args.profile == "cid"
                        else "native-sha512-qemu.json" if args.profile == "sha512"
                        else "native-keccak-qemu.json" if args.profile == "keccak"
                        else "native-mldsa-ntt-qemu.json" if args.profile == "mldsa-ntt"
                        else "native-mldsa-sample-qemu.json" if args.profile == "mldsa-sample"
                        else "native-mldsa-verify-qemu.json" if args.profile == "mldsa-verify"
                        else "native-imgsig-qemu.json" if args.profile == "imgsig"
                        else "native-style-qemu.json" if args.profile == "style"
                        else "native-layout-qemu.json" if args.profile == "layout"
                        else "native-flex-qemu.json" if args.profile == "flex"
                        else "native-grid-qemu.json" if args.profile == "grid"
                        else "native-gf25519-qemu.json" if args.profile == "gf25519"
                        else "native-ed25519-qemu.json" if args.profile == "ed25519"
                        else "native-keyseal-qemu.json" if args.profile == "keyseal"
                        else "native-keystore-qemu.json" if args.profile == "keystore"
                        else "native-dapps-qemu.json" if args.profile == "dapps"
                        else "native-input-state-qemu.json" if args.profile == "input-state"
                        else "native-nvme-qemu.json" if args.profile == "nvme"
                        else "native-update2-qemu.json" if args.profile == "update2"
                        else "native-provision-esp-qemu.json" if args.profile == "provision"
                        else "native-builder-layout-qemu.json" if args.profile == "builder-layout"
                        else "native-catalog-qemu.json" if args.profile == "catalog"
                        else "native-fresh-qemu.json" if args.profile == "fresh"
                        else "native-prodsig-qemu.json" if args.profile == "prodsig"
                        else "native-rtc-qemu.json" if args.profile == "rtc"
                        else "native-desktop-qemu.json")
        observed = json.loads((guest / receipt_name).read_text())
        expected_status = ("PASS_NATIVE_CONSENT_STUCK_ENTROPY" if args.expect_stuck_entropy
                           else "PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE" if args.profile == "local-draft"
                           else "PASS_NATIVE_CONSENT_QEMU" if args.profile == "consent"
                           else "PASS_NATIVE_IDLE_SILENT_QEMU" if args.profile == "idle"
                           else "PASS_NATIVE_CID_QEMU" if args.profile == "cid"
                           else "PASS_NATIVE_SHA512_QEMU" if args.profile == "sha512"
                           else "PASS_NATIVE_KECCAK_QEMU" if args.profile == "keccak"
                           else "PASS_NATIVE_MLDSA_NTT_QEMU" if args.profile == "mldsa-ntt"
                           else "PASS_NATIVE_MLDSA_SAMPLE_QEMU" if args.profile == "mldsa-sample"
                           else "PASS_NATIVE_MLDSA_VERIFY_QEMU" if args.profile == "mldsa-verify"
                           else "PASS_NATIVE_IMGSIG_QEMU" if args.profile == "imgsig"
                           else "PASS_NATIVE_STYLE_K_QEMU" if args.profile == "style"
                           else "PASS_NATIVE_LAYOUT_K_QEMU" if args.profile == "layout"
                           else "PASS_NATIVE_FLEX_K_QEMU" if args.profile == "flex"
                           else "PASS_NATIVE_GRID_K_QEMU" if args.profile == "grid"
                           else "PASS_NATIVE_GF25519_QEMU" if args.profile == "gf25519"
                           else "PASS_NATIVE_ED25519_QEMU" if args.profile == "ed25519"
                           else "PASS_NATIVE_KEYSEAL_QEMU" if args.profile == "keyseal"
                           else "PASS_NATIVE_KEYSTORE_QEMU" if args.profile == "keystore"
                           else "PASS_NATIVE_DAPPS_QEMU" if args.profile == "dapps"
                           else "PASS_NATIVE_USB_HID_NVME_STATE_QEMU" if args.profile == "input-state"
                           else "PASS_NATIVE_NVME_READ_QEMU" if args.profile == "nvme"
                           else "PASS_NATIVE_UPDATE2_QEMU" if args.profile == "update2"
                           else "PASS_NATIVE_PROVISION_ESP_QEMU" if args.profile == "provision"
                           else "PASS_NATIVE_BUILDER_LAYOUT_QEMU" if args.profile == "builder-layout"
                           else "PASS_NATIVE_CATALOG_QEMU" if args.profile == "catalog"
                           else "PASS_NATIVE_FRESH_QEMU" if args.profile == "fresh"
                           else "PASS_NATIVE_PRODSIG_QEMU" if args.profile == "prodsig"
                           else "PASS_NATIVE_RTC_PROBE_QEMU" if args.profile == "rtc"
                           else "PASS_NATIVE_DESKTOP_INPUT_QEMU")
        expected_events = (12 if args.profile == "local-draft"
                           else 18 if args.expect_stuck_entropy
                           else 22 if args.profile == "consent"
                           else 4 if args.profile == "idle"
                           else 4 if args.profile == "ed25519"
                           else 16 if args.profile == "keystore"
                           else 11 if args.profile == "dapps"
                           else 12 if args.profile == "input-state"
                           else 7 if args.profile == "nvme"
                           else 12 if args.profile == "update2"
                           else 8 if args.profile in ("provision", "builder-layout")
                           else 3 if args.profile == "catalog"
                           else 7 if args.profile == "fresh"
                           else 5 if args.profile == "prodsig"
                           else 7 if args.profile == "rtc"
                           else 2 if args.profile in ("cid", "sha512", "keccak", "mldsa-ntt", "mldsa-sample", "mldsa-verify", "imgsig", "style", "layout", "flex", "grid", "gf25519", "keyseal") else 24)
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
        elif args.profile == "keccak":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "keccak-outputs"]
                    or observed["events"][1]["matches"] != ["shake128-empty", "shake256-abc", "shake128-200-squeeze-400"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("keccak verdict is incomplete")
        elif args.profile == "mldsa-ntt":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "ntt-records"]
                    or observed["events"][1]["matches"] != ["ntt-p", "ntt-q", "mul", "intt-product", "roundtrip"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("mldsa-ntt verdict is incomplete")
        elif args.profile == "mldsa-sample":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "sample-records"]
                    or observed["events"][1]["matches"] != ["expand-a-0-0", "expand-a-5-4", "sample-in-ball", "unpack10", "unpack20",
                                                            "rsub20", "unpack4", "pack4", "pack10", "hint-bitmap", "hint-refusals"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("mldsa-sample verdict is incomplete")
        elif args.profile == "mldsa-verify":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "verify-cases"]
                    or observed["events"][1]["matches"] != ["valid-a", "valid-b", "wrong-message", "flip-ctilde", "flip-z",
                                                            "hint-order", "hint-padding", "hint-limit", "z-over-bound"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("mldsa-verify verdict is incomplete")
        elif args.profile == "imgsig":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "admission-cases"]
                    or observed["events"][1]["matches"] != ["two-signers", "three-signers", "order-2-0", "one-signer", "duplicate-id",
                                                            "unknown-id", "ed-half-bad", "ml-half-bad", "ed25519-only", "mldsa-only",
                                                            "manifest-tamper", "wrong-context", "bad-magic", "count-zero", "count-five",
                                                            "manifest-reserved", "pad-nonzero-first", "pad-nonzero-last",
                                                            "entry-reserved-4", "entry-reserved-7", "layout-68", "layout-127",
                                                            "count-four-dup", "count-four-last-counts", "id-256", "id-65536",
                                                            "id-16777216"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("imgsig verdict is incomplete")
        elif args.profile == "layout":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "layout-cases"]
                    or observed["events"][1]["cases"] != observed["events"][1]["recorded"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("layout verdict is incomplete")
        elif args.profile == "style":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "style-cases"]
                    or observed["events"][1]["cases"] != observed["events"][1]["matches"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("style verdict is incomplete")
        elif args.profile == "flex":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "flex-cases"]
                    or observed["events"][1]["cases"] != observed["events"][1]["matches"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("flex verdict is incomplete")
        elif args.profile == "grid":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "grid-cases"]
                    or observed["events"][1]["cases"] != observed["events"][1]["matches"]
                    or observed["signing"] or observed["physicalHardware"]):
                raise ValueError("grid verdict is incomplete")
        elif args.profile == "gf25519":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "gf25519"]
                    or len(observed["events"][1]["cases"]) != 3
                    or observed["signing"] or observed["pointArithmetic"] or observed["physicalHardware"]):
                raise ValueError("gf25519 verdict is incomplete")
        elif args.profile == "ed25519":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "ed25519-pubkey", "ed25519-sign", "ed25519-verify"]
                    or len(observed["events"][1]["keys"]) != 3
                    or len(observed["events"][2]["signatures"]) != 3
                    or not observed["signing"] or observed["deviceKey"] or observed["physicalHardware"]):
                raise ValueError("ed25519 verdict is incomplete")
        elif args.profile == "keystore":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != [
                        "key-button-create", "key-button-two-windows", "boot1-create", "boot2-locked", "unlock-wrong-passphrase", "attempt-delay", "delay-after-reboot", "unlock-right-passphrase", "sign-after-unlock",
                        "lock", "unlock-after-lock", "forget-wrong-passphrase", "attempt-count-after-reboot", "forget", "forgotten-after-reboot",
                        "lock-refused-unstored"]
                    or not observed["persistedAcrossReboot"] or not observed["wrongPassphraseRefused"]
                    or observed["physicalHardware"] or observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("keystore verdict is incomplete")
        elif args.profile == "dapps":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != [
                        "first-frame", "dapps-initial", "itonami-local-refusal", "itonami-local-model", "murakumo-run-recorded",
                        "yataverse-store", "aozora-no-key", "device-key-create", "aozora-sign-deny",
                        "aozora-panel-text", "aozora-sign-allow"]
                    or observed["network"] != "none (-nic none)" or observed["dnsResolved"]
                    or observed["physicalHardware"] or observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("dapps verdict is incomplete")
        elif args.profile == "input-state":
            if (observed["physicalHardware"] or observed["syntheticInputProvesHumanConsent"]
                    or observed["D2WorkspaceCodec"] or observed["BluetoothQualified"]
                    or observed["USBHubQualified"]):
                raise ValueError("input/state qualification boundary changed")
        elif args.profile == "nvme":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["nvme-fat32", "nvme-fat16-media", "nvme-4096", "nvme-absent",
                                                                       "nvme-install", "nvme-install-again", "nvme-install-tampered"]
                    or [row["result"] for row in observed["events"][:4]] != [15, 15, 15, 1]
                    or [row["esp"] for row in observed["events"][:4]] != [15, 15, 3, 1]
                    or not all(row["desktopKeptRunning"] for row in observed["events"][:4])
                    or not all(row.get("diskUnchanged") for row in observed["events"][:3])
                    or [row["updateSelfTest"] for row in observed["events"][:4]] != [[15, 1, 7]] * 4
                    or [row["install"] for row in observed["events"][4:]] != [15, 15, 7]
                    or not observed["events"][5].get("noNewClusters")
                    or not observed["writesOnlyThroughInstallHook"] or observed["physicalHardware"]):
                raise ValueError("nvme verdict is incomplete")
        elif args.profile == "update2":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["update2-provision", "update2-cases", "update2-install", "update2-replay", "update2-newer",
                                                                                     "update2-crash-before-advance", "update2-crash-repeat", "update2-crash-refused",
                                                                                     "update2-tampered", "update2-one-signer", "update2-journal-corrupt", "update2-journal-absent"]
                    or observed["events"][1]["matches"] != ["two-of-three-0-1", "two-of-three-2-0", "three-signers", "one-signer", "ml-half-bad",
                                                            "ed-half-bad", "tampered-image", "tampered-manifest", "duplicate-id", "unknown-id",
                                                            "production-mode", "bad-magic", "count-zero", "manifest-reserved", "version-zero",
                                                            "size-too-big", "entry-reserved-4", "entry-reserved-7", "pad-nonzero-first",
                                                            "pad-nonzero-last", "layout-68", "layout-127", "count-five", "count-four-dup",
                                                            "count-four-last-counts", "id-256", "id-65536", "id-16777216", "wrong-context",
                                                            "floor-above", "floor-equal", "floor-below", "v1-above-floor", "v1-equal-floor",
                                                            "v1-below-floor", "catalog-context-both", "catalog-context-one", "fresh-context-both", "stream-broken-after-verify"]
                    or [row["install"] for row in observed["events"][2:]] != [15, 9, 15, 15, 15, 9, 7, 1, 10, 10]
                    or [row.get("floorAfter") for row in observed["events"][2:]] != [5, None, 6, None, 5, None, None, None, None, None]
                    or not observed.get("versionFloorHashCheckedNotSigned")
                    or not observed["testKeysOnly"] or observed["productionSignerSet"] or observed["physicalHardware"]):
                raise ValueError("update2 verdict is incomplete")
        elif args.profile == "catalog":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["catalog-cases", "catalog-storage-restored", "catalog-regression"]
                    or len(observed["events"][0]["matches"]) != observed["events"][0]["cases"]
                    or observed["events"][0]["admitted"] != ["two-of-three-0-1", "two-of-three-2-0", "three-signers", "full-64-entries",
                                                             "title-31-chars-ok", "size-max-ok"]
                    or not observed["events"][1]["diskUnchanged"] or not observed["events"][2]["desktopStillDraws"]
                    or not observed["testKeysOnly"] or observed["productionSignerSet"] or not observed["notWiredToDesktop"]
                    or observed["physicalHardware"]):
                raise ValueError("catalog verdict is incomplete")
        elif args.profile == "prodsig":
            # JUN-813 amendment 7: production mode admits exactly the golden fixtures (signed once with the real, verification-only slots)
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["prodsig-provision", "prodsig-image", "prodsig-catalog", "prodsig-fresh",
                                                                       "prodsig-regression"]
                    or observed["events"][1]["admitted"] != ["golden-image-production"]
                    or observed["events"][2]["admitted"] != ["golden-catalog-production"]
                    or observed["events"][3]["admitted"] != ["golden-freshness-production"]
                    or any(len(observed["events"][i]["matches"]) != observed["events"][i]["cases"] for i in (1, 2, 3))
                    or any(observed["events"][i]["testModeAdmits"] != ["test-keys-header-under-test-keys"] for i in (1, 2, 3))
                    or not observed["events"][4]["diskUnchanged"] or not observed["events"][4]["desktopStillDraws"]
                    or not observed["productionSignerSet"] or not observed["verificationOnlySignerSet"]
                    or observed["privateKeysInRepository"] or not observed["goldenSignedOnceWithRealSlots"]
                    or not observed["notWiredToDesktop"] or observed["physicalHardware"]):
                raise ValueError("prodsig verdict is incomplete")
        elif args.profile == "fresh":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["fresh-clock-probes", "fresh-clock-decoder", "fresh-cases",
                                                                       "fresh-cases-clock-ahead", "fresh-cases-no-clock",
                                                                       "fresh-storage-restored", "fresh-regression"]
                    or len(observed["events"][0]["probes"]) != 5
                    or len(observed["events"][2]["matches"]) != observed["events"][2]["cases"]
                    or len(observed["events"][3]["matches"]) != observed["events"][3]["cases"]
                    or len(observed["events"][4]["matches"]) != observed["events"][4]["cases"]
                    or sorted(observed["events"][2]["admittedStates"]) != sorted(["two-of-three-0-1", "two-of-three-2-0", "three-signers",
                                                                                 "expired-one-hour-ago-30-day-lifetime", "expired-two-months-ago",
                                                                                 "fresh-three-hours-left", "issued-23-hours-ahead-within-skew",
                                                                                 "issued-two-days-ahead-clock-behind", "lifetime-exactly-30-days",
                                                                                 "version-one", "version-max-signed"])
                    or not observed["events"][5]["diskUnchanged"] or not observed["events"][6]["desktopStillDraws"]
                    or not observed["testKeysOnly"] or observed["productionSignerSet"] or not observed["notWiredToDesktop"]
                    or observed["physicalHardware"] or not observed["clockIsQemuNotABoard"]):
                raise ValueError("fresh verdict is incomplete")
        elif args.profile == "rtc":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["rtc-default-host", "rtc-vm-2026-11-06", "rtc-vm-leap-day-2028", "rtc-vm-2100-03-01",
                                                                       "rtc-vm-before-build-floor", "rtc-decoder-negative-controls", "rtc-regression"]
                    or [row["verdict"] for row in observed["events"][:5]] != [1, 1, 1, 0, 0]
                    or observed["decoder"] != script_pins["rtc_probe_decode.py"]
                    or not observed["readOnly"] or not observed["clockIsQemuNotABoard"] or observed["physicalHardware"]):
                raise ValueError("rtc verdict is incomplete")
        elif args.profile == "provision":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["provision-esp", "provision-cases-checked", "provision-equal",
                                                                       "provision-above", "neg-absent", "neg-wrong-hash", "neg-floor-high", "neg-floor-low"]
                    or [row["install"] for row in observed["events"][2:]] != [9, 15, 10, 10, 9, 15]
                    or [row.get("floorAfter") for row in observed["events"][2:]] != [None, 6, None, None, None, 4]
                    or observed["provisioningHookUsed"] or not observed["testKeysOnly"] or observed["productionSignerSet"] or observed["physicalHardware"]):
                raise ValueError("provision verdict is incomplete")
        elif args.profile == "builder-layout":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["builder-esp", "builder-cases-checked", "builder-equal",
                                                                       "builder-above", "neg-absent", "neg-wrong-hash", "neg-floor-high", "neg-floor-low"]
                    or [row["install"] for row in observed["events"][2:]] != [9, 15, 10, 10, 9, 15]
                    or [row.get("floorAfter") for row in observed["events"][2:]] != [None, 5, None, None, None, 4]
                    or not observed["eachInstallKeptEfiBoot"] or observed["firmwareBootOfLayout"]
                    or observed["provisioningHookUsed"] or not observed["testKeysOnly"] or observed["productionSignerSet"] or observed["physicalHardware"]):
                raise ValueError("builder-layout verdict is incomplete")
        elif args.profile == "keyseal":
            if (observed["font"] != font_state["padded"]
                    or [row["name"] for row in observed["events"]] != ["first-frame", "keyseal-seal-open"]
                    or not observed["sealed"] or observed["deviceKey"] or observed["physicalHardware"]):
                raise ValueError("keyseal verdict is incomplete")
        elif args.profile == "consent":
            if (observed["font"] != font_state["padded"]
                    or observed["transportObserver"] != script_pins["check-native-draft-restart-qemu.py"]
                    or observed["desktopObserver"] != script_pins["check-native-desktop-qemu.py"]
                    or not observed["inputSynchronizedWithCompletedFrames"]
                    or [row["name"] for row in observed["events"]] != [
                        "first-frame", "entropy-probe", "itonami-goal-typed", "collapse-key", "collapse-click",
                        "consent-open",
                        "launcher-key-ignored", "launcher-click-ignored", "minimize-and-dock-blocked-by-consent", "key-deny",
                        "pointer-deny", "esc-deny", "key-request-blocks-background-pointer", "key-deny", "key-request-pointer", "passphrase-pointer", "passphrase-cancel"]
                       + (["stuck-entropy-refused"] if args.expect_stuck_entropy else
                          ["key-allow", "sign-deny", "sign-allow", "draft-after-key", "pointer-allow"])
                    or observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("consent surface verdict is incomplete")
        elif (observed["font"] != font_state["padded"]
              or [row["codepoint"] for row in observed["renderedGoalGlyphs"]] != [97, 98, 97]
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
                    or len(iso_observed["events"]) != expected_events
                    or iso_observed["kernel"] != kernel_state["kernel"]
                    or iso_observed["efi"] != kernel_state["efi"]
                    or iso_observed["iso"] != media_state["iso"]
                    or iso_observed["independentISO"]["status"] !=
                       "PASS_INDEPENDENT_NATIVE_EL_TORITO_ISO_READBACK"
                    or iso_observed["observer"] != script_pins["check-native-desktop-qemu.py"]
                    or [row["codepoint"] for row in iso_observed["renderedGoalGlyphs"]] != [97, 98, 97]):
                raise ValueError("ISO QEMU guest observation is not bound to this build")
        material_observed = None
        if args.profile == "desktop":
            call("qemu-material", scripts["check-native-shell-material-qemu.py"], [
                "--media", disk, "--efi", efi, "--kernel", image, "--font", padded,
                "--qemu", qemu, "--firmware", firmware, "--output", output / "qemu-material"])
            material_observed = json.loads((output / "qemu-material/native-shell-material-qemu.json").read_text())
            if (material_observed["status"] != "PASS_NATIVE_SHELL_MATERIAL_QEMU"
                    or material_observed["kernel"] != kernel_state["kernel"]
                    or material_observed["efi"] != kernel_state["efi"]
                    or material_observed["media"] != media_state["image"]
                    or material_observed["observer"] != script_pins["check-native-shell-material-qemu.py"]
                    or material_observed["desktopObserver"] != script_pins["check-native-desktop-qemu.py"]
                    or material_observed["transportObserver"] != script_pins["check-native-draft-restart-qemu.py"]
                    or [row["name"] for row in material_observed["events"]] != [
                        "first-frame-materials", "dock-keyboard-focus", "dock-keyboard-launch",
                        "dock-pointer-hover", "dock-pointer-press", "dock-pointer-release",
                        "reduced-effects", "effects-restored", "home-pointer-launch"]
                    or material_observed["physicalHardware"] or material_observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("native shell materials observation is not bound to this build")
        launcher_observed = None
        if args.profile == "desktop":
            call("qemu-launcher-pages", scripts["check-native-launcher-pages-qemu.py"], [
                "--media", disk, "--efi", efi, "--kernel", image, "--font", padded,
                "--qemu", qemu, "--firmware", firmware, "--output", output / "qemu-launcher-pages"])
            launcher_observed = json.loads((output / "qemu-launcher-pages/native-launcher-pages-qemu.json").read_text())
            if (launcher_observed["status"] != "PASS_NATIVE_LAUNCHER_PAGES_QEMU"
                    or launcher_observed["kernel"] != kernel_state["kernel"]
                    or launcher_observed["efi"] != kernel_state["efi"]
                    or launcher_observed["media"] != media_state["image"]
                    or launcher_observed["font"] != font_state["padded"]
                    or launcher_observed["qemu"] != qemu_pin or launcher_observed["firmware"] != firmware_pin
                    or launcher_observed["observer"] != script_pins["check-native-launcher-pages-qemu.py"]
                    or launcher_observed["opsFourWindowsFullPage"] > launcher_observed["opsLimit"]
                    or launcher_observed["physicalHardware"] or launcher_observed["syntheticInputProvesHumanConsent"]):
                raise ValueError("launcher pages observation is not bound to this build")
        gui_observed = []
        if args.profile == "desktop":
            for name, options in (("absent", []), ("audio", ["--audio"]),
                                  ("muted", ["--audio", "--muted"])):
                destination = output / ("qemu-effects-" + name)
                call("qemu-effects-" + name, scripts["check-native-gui-effects-qemu.py"], [
                    "--media", disk, "--efi", efi, "--kernel", image, "--font", padded,
                    "--qemu", qemu, "--firmware", firmware, "--output", destination, *options])
                effect = json.loads((destination / "native-gui-effects.json").read_text())
                if (effect["status"] != "PASS_NATIVE_GUI_EFFECTS_QEMU"
                        or len(effect["events"]) != 8
                        or effect["kernel"] != kernel_state["kernel"]
                        or effect["efi"] != kernel_state["efi"]
                        or effect["media"] != media_state["image"]
                        or effect["font"] != font_state["padded"]
                        or effect["qemu"] != qemu_pin or effect["firmware"] != firmware_pin
                        or effect["observer"] != script_pins["check-native-gui-effects-qemu.py"]
                        or effect["transport"] != script_pins["check-native-draft-restart-qemu.py"]
                        or effect["physicalHardware"] or effect["smooth60FPSQualified"]
                        or effect["trustedHumanConsent"]):
                    raise ValueError("GUI effects observation is not bound to this build: " + name)
                if name == "absent" and effect["audio"] is not None:
                    raise ValueError("missing-device control unexpectedly has audio")
                if name != "absent" and (effect["audio"] is None
                        or (effect["audio"]["peak"] == 0) != (name == "muted")):
                    raise ValueError("native WAV positive/mute control failed")
                gui_observed.append(effect)
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
                            else "MACOS_NATIVE_KECCAK_QEMU_CANDIDATE" if args.profile == "keccak"
                            else "MACOS_NATIVE_MLDSA_NTT_QEMU_CANDIDATE" if args.profile == "mldsa-ntt"
                            else "MACOS_NATIVE_MLDSA_SAMPLE_QEMU_CANDIDATE" if args.profile == "mldsa-sample"
                            else "MACOS_NATIVE_MLDSA_VERIFY_QEMU_CANDIDATE" if args.profile == "mldsa-verify"
                            else "MACOS_NATIVE_IMGSIG_QEMU_CANDIDATE" if args.profile == "imgsig"
                            else "MACOS_NATIVE_STYLE_K_QEMU_CANDIDATE" if args.profile == "style"
                            else "MACOS_NATIVE_LAYOUT_K_QEMU_CANDIDATE" if args.profile == "layout"
                            else "MACOS_NATIVE_FLEX_K_QEMU_CANDIDATE" if args.profile == "flex"
                            else "MACOS_NATIVE_GRID_K_QEMU_CANDIDATE" if args.profile == "grid"
                            else "MACOS_NATIVE_GF25519_QEMU_CANDIDATE" if args.profile == "gf25519"
                            else "MACOS_NATIVE_ED25519_QEMU_CANDIDATE" if args.profile == "ed25519"
                            else "MACOS_NATIVE_KEYSEAL_QEMU_CANDIDATE" if args.profile == "keyseal"
                            else "MACOS_NATIVE_KEYSTORE_QEMU_CANDIDATE" if args.profile == "keystore"
                            else "MACOS_NATIVE_DAPPS_QEMU_CANDIDATE" if args.profile == "dapps"
                            else "MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE"),
                     font=font_state["padded"], kernel=kernel_state["kernel"], textMargin=text_margin,
                     efi=kernel_state["efi"], media=media_state["image"], iso=media_state["iso"],
                     guestEvents=len(observed["events"]),
                     guestInputQualified=True, nativeFormatEmission=True,
                     isoBootQualified=iso_observed is not None,
                     nativeShellMaterialsQualified=material_observed is not None,
                     nativeLauncherPagesQualified=launcher_observed is not None,
                     nativeLauncherPagesEvents=len(launcher_observed["events"]) if launcher_observed else 0,
                     nativeLauncherPagesOpsFourWindows=launcher_observed["opsFourWindowsFullPage"] if launcher_observed else None,
                     nativeGUIEffectsQualified=len(gui_observed) == 3,
                     nativeGUIEffectsEvents=sum(len(g["events"]) for g in gui_observed),
                     nativePCMDevice="Intel 8086:2415 AC97" if gui_observed else None,
                     native60FPSQualified=False,
                     nativeShellMaterialEvents=len(material_observed["events"]) if material_observed else 0,
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
                                    else "Mac native Keccak (SHAKE128/256) sponge self-test on QEMU"
                                    if args.profile == "keccak"
                                    else "Mac native ML-DSA-65 polynomial (NTT) self-test on QEMU"
                                    if args.profile == "mldsa-ntt"
                                    else "Mac native ML-DSA-65 sampling (ExpandA, SampleInBall, hint unpack) and bit packing self-test on QEMU"
                                    if args.profile == "mldsa-sample"
                                    else "Mac native ML-DSA-65 signature verification (nine signatures from the Python reference) on QEMU"
                                    if args.profile == "mldsa-verify"
                                    else "Mac native AIUEIMG2 multi-signer admission (sixteen headers, 2-of-3 Ed25519 plus ML-DSA-65, test keys) on QEMU"
                                    if args.profile == "imgsig"
                                    else "Mac native CSSOM style slice (selector matching, specificity, cascade, inheritance as kernel region code) against the host reference grid on QEMU"
                                    if args.profile == "style"
                                    else "Mac native CSSOM layout slice (normal block flow into a box table as kernel region code) against the host f64 reference grid on QEMU"
                                    if args.profile == "layout"
                                    else "Mac native CSSOM flex lines of up to sixteen items (grow, scaled shrink, clamp, freeze, justify-content, auto margins as kernel region code) against the host exact grid on QEMU"
                                    if args.profile == "flex"
                                    else "Mac native CSSOM grid track sizing and table column widths (layout.cljk track-sizes, distribute-fr, distribute-equally-with-caps, table-column-widths, distribute-excess as kernel region code) against the host references on QEMU"
                                    if args.profile == "grid"
                                    else "Mac native GF(2^255-19) arithmetic self-test on QEMU"
                                    if args.profile == "gf25519"
                                    else "Mac native Ed25519 public keys from RFC 8032 seeds on QEMU"
                                    if args.profile == "ed25519"
                                    else "Mac native passphrase key sealing self-test (seal, open, wrong passphrase, changed blob) on QEMU"
                                    if args.profile == "keyseal"
                                    else "Mac native sealed device key survives a reboot; a wrong passphrase is refused (two boots, QEMU)"
                                    if args.profile == "keystore"
                                    else "Mac native installed itonami dapps run their offline cores with no NIC (QEMU)"
                                    if args.profile == "dapps"
                                    else "Mac native USB boot HID (PS/2 disabled) and NVMe app-state cold/crash restore on QEMU"
                                    if args.profile == "input-state"
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
    parser.add_argument("--bluetooth-firmware", choices=("v1",), help="explicit pinned Realtek bundle in native font padding")
    parser.add_argument("--profile", choices=("desktop", "local-draft", "consent", "idle", "cid", "sha512", "keccak", "mldsa-ntt", "mldsa-sample", "mldsa-verify", "imgsig", "style", "layout", "flex", "grid", "update2", "provision", "builder-layout", "catalog", "fresh", "prodsig", "rtc", "gf25519", "ed25519", "keyseal", "keystore", "dapps", "nvme", "input-state"), default="desktop")
    parser.add_argument("--distribution", choices=("aiueos", "awai"), default="aiueos")
    parser.add_argument("--expect-stuck-entropy", action="store_true",
                        help="JUN-482 negative control: the native sources draw from a constant entropy source; "
                             "the consent gate must see the device-key draw refused")
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
