#!/usr/bin/env python3
"""Stage and build the locked AIUEOS kernel/EFI with an arm64 Mac Amu image.

The signed Kotoba/Amu executable discovers, compiles and packages. Python
copies immutable source bytes into one FD3 scope, verifies pins and records
artifacts. This creates candidates, not a boot, desktop or release verdict.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess


REPO = Path(__file__).resolve().parents[3]
OS = REPO / "os/aiueos"
DEPENDENCIES = OS / "native/source-dependencies.json"
OWNER_ENV = {
    "capability-link-frame": "AIUEOS_LINK_FRAME_SOURCE_PATH",
    "capability-dma-map": "AIUEOS_DMA_MAP_SOURCE_PATH",
    "capability-mmio-map": "AIUEOS_MMIO_MAP_SOURCE_PATH",
    "capability-net-transport": "AIUEOS_NET_TRANSPORT_SOURCE_PATH",
    "org-ietf-tcp": "AIUEOS_ORG_IETF_TCP_SOURCE_PATH",
}
FUEL = 1073741824


def pin(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verify_compiler(path, expected):
    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
        raise ValueError("the Mac builder requires Apple Silicon")
    if pin(path)["sha256"] != expected:
        raise ValueError("Mac compiler immutable digest mismatch")
    binary = path.read_bytes()
    if len(binary) < 32 or struct.unpack_from("<IiiI", binary) != (0xfeedfacf, 0x100000c, 0, 2):
        raise ValueError("the compiler is not an arm64 Mach-O executable")
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(path)],
                   capture_output=True, check=True)
    dependencies = subprocess.run(["/usr/bin/otool", "-L", str(path)],
                                  capture_output=True, check=True).stdout.splitlines()
    if dependencies != [f"{path}:".encode()]:
        raise ValueError("the compiler has undeclared dylib dependencies")


def stage_file(source, dest, expected=None):
    if source.is_symlink() or not source.is_file():
        raise ValueError("source is missing or a symlink: " + str(source))
    raw = source.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if expected and actual != expected:
        raise ValueError("owner source pin drift: " + str(source))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return {"bytes": len(raw), "sha256": actual}


def main(args):
    compiler = args.compiler_image.resolve(strict=True)
    verify_compiler(compiler, args.compiler_sha256)
    if args.kernel_source.is_symlink():
        raise ValueError("kernel entry must not be a symlink")
    kernel_source = args.kernel_source.resolve(strict=True)
    if not kernel_source.is_relative_to(OS):
        raise ValueError("kernel entry must be a local AIUEOS source")
    entry = "/" + kernel_source.relative_to(REPO).as_posix()
    if args.fuel < 1 or args.fuel > 9223372036854775807:
        raise ValueError("fuel must be a positive i64")
    if bool(args.payload) != bool(args.payload_sha256):
        raise ValueError("boot payload requires both path and SHA-256 pin")
    if bool(args.font) != bool(args.font_sha256) or bool(args.user_slot) != bool(args.user_slot_sha256):
        raise ValueError("font and user slot each require a path and SHA-256 pin")
    if (bool(args.user_source) != bool(args.user_source_sha256)
            or bool(args.user_source) != bool(args.user_elf_sha256)):
        raise ValueError("user source requires source and expected ELF SHA-256 pins")
    if args.user_source and args.user_slot:
        raise ValueError("choose generated user source or an existing user slot")
    if args.user_target in ("x86_64-aiueos-user-v3", "x86_64-aiueos-user-v4") and not args.user_source:
        raise ValueError("user-v3/v4 requires a pinned generated user source")
    if args.kernel_target == "x86_64-aiueos-kernel-v2":
        if (args.user_source or args.user_slot) and args.user_target != "x86_64-aiueos-user-v4":
            raise ValueError("kernel-v2 requires user-v4")
    elif args.user_target == "x86_64-aiueos-user-v4":
        raise ValueError("user-v4 requires kernel-v2")
    if ((args.font or args.user_slot or args.user_source)
            and (not args.font or not (args.user_slot or args.user_source) or args.payload)):
        raise ValueError("dual payload requires font and one user payload without legacy payload")
    if args.payload and args.payload.is_symlink():
        raise ValueError("boot payload must not be a symlink")
    payload = args.payload.resolve(strict=True) if args.payload else None
    if payload and (pin(payload)["sha256"] != args.payload_sha256
                    or pin(payload)["bytes"] > 524288):
        raise ValueError("boot payload pin or size mismatch")
    for source, expected, name in ((args.font, args.font_sha256, "font"),
                                   (args.user_slot, args.user_slot_sha256, "user slot")):
        if source and (source.is_symlink() or pin(source)["sha256"] != expected
                       or pin(source)["bytes"] != 524288):
            raise ValueError(name + " requires a regular pinned 512 KiB file")
    font = args.font.resolve(strict=True) if args.font else None
    user_slot = args.user_slot.resolve(strict=True) if args.user_slot else None
    if args.user_source and args.user_source.is_symlink():
        raise ValueError("user source must not be a symlink")
    user_source = args.user_source.resolve(strict=True) if args.user_source else None
    if user_source and (not user_source.is_relative_to(OS / "native")
                        or pin(user_source)["sha256"] != args.user_source_sha256):
        raise ValueError("user source must be a pinned AIUEOS native source")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    stage = output / "source"
    stage.mkdir()
    state = {"schema": "aiueos.macos-native-kernel-candidate.v1", "state": "STAGING",
             "compiler": pin(compiler), "compilerHost": [platform.system(), platform.machine()],
             "linuxJVMNodeOrCCompiler": False, "bootQualified": False,
             "desktopInputQualified": False, "physicalHardwareQualified": False,
             "kernelEntry": entry, "fuel": args.fuel,
             "bootPayload": pin(payload) if payload else None,
             "bootFont": pin(font) if font else None,
             "bootUserSlot": pin(user_slot) if user_slot else None,
             "bootUserSource": pin(user_source) if user_source else None,
             "bootUserTarget": args.user_target if user_source else None,
             "bootUserElf": None, "calls": []}

    def save():
        (output / "build-state.json").write_text(json.dumps(state, indent=2) + "\n")

    save()
    try:
        sources = {}
        for directory in (OS / "native", OS / "kotoba", OS / "aiueos"):
            for source in sorted(directory.rglob("*.kotoba")):
                relative = source.relative_to(REPO)
                virtual = "/" + relative.as_posix()
                sources[virtual] = stage_file(source, stage / relative)
        owner_manifest = json.loads(DEPENDENCIES.read_text())
        if owner_manifest["schema"] != "aiueos.native-source-dependencies.v1":
            raise ValueError("unexpected owner dependency manifest")
        owners = {}
        for dependency in owner_manifest["dependencies"]:
            name = dependency["repo"]
            if name not in OWNER_ENV:
                raise ValueError("undeclared source owner")
            default = REPO.parent / name / "kotoba"
            root = Path(os.environ.get(OWNER_ENV[name], default)).resolve(strict=True)
            for relative, expected in dependency["files"].items():
                parts = Path(relative).parts
                if not parts or parts[0] != "kotoba" or ".." in parts:
                    raise ValueError("noncanonical owner source path")
                physical = root.joinpath(*parts[1:])
                virtual = "/owners/" + name + "/" + Path(relative).as_posix()
                identity = stage_file(physical, stage / virtual[1:], expected)
                owners[virtual] = {"commit": dependency["commit"], **identity}
                sources[virtual] = identity
        if payload:
            stage_file(payload, stage / "boot-payload.bin", args.payload_sha256)
        if font:
            stage_file(font, stage / "boot-font.bin", args.font_sha256)
            if user_slot:
                stage_file(user_slot, stage / "boot-user-slot.bin", args.user_slot_sha256)
        if user_source:
            stage_file(user_source, stage / "boot-user-source.kotoba", args.user_source_sha256)
        roots = ["/os", "/os/aiueos", "/os/aiueos/kotoba"]
        roots += ["/owners/" + dep["repo"] + "/kotoba" for dep in owner_manifest["dependencies"]]
        source_args = [part for root in roots for part in ("--source-path", root)]
        if entry not in sources:
            raise ValueError("kernel entry is outside staged Kotoba sources")
        scope = os.open(stage, os.O_RDONLY | os.O_DIRECTORY)
        if scope != 3:
            os.dup2(scope, 3)
            os.close(scope)
            scope = 3

        def run(name, command):
            result = subprocess.run([str(compiler), *command], cwd=stage, pass_fds=(scope,),
                                    capture_output=True, timeout=3600, env={"PATH": "/nonexistent"})
            for suffix, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
                (output / f"{name}.{suffix}").write_bytes(raw)
            state["calls"].append({"name": name, "argv": command, "exit": result.returncode,
                                   "stdout": pin(output / f"{name}.stdout"),
                                   "stderr": pin(output / f"{name}.stderr")})
            save()
            if result.returncode or result.stderr:
                state["state"] = "BLOCKED_NATIVE_" + name.upper().replace("-", "_")
                raise ValueError(f"{name}: native compiler exit {result.returncode}: "
                                 + result.stderr.decode(errors="replace")[:500])
            return result.stdout

        try:
            if user_source:
                user_images = []
                for name in ("boot-user.elf", "boot-user.reproduced.elf"):
                    run("compile-" + name, ["compile", "boot-user-source.kotoba",
                        "--target", args.user_target, "--output", name])
                    image = stage / name
                    if not image.is_file() or pin(image)["bytes"] != 8280:
                        raise ValueError("native compiler omitted the expected user-v2 ELF")
                    user_images.append(pin(image))
                if (user_images[0] != user_images[1]
                        or user_images[0]["sha256"] != args.user_elf_sha256):
                    raise ValueError("user-v2 ELF reproduction or expected digest differs")
                slots = []
                for name in ("boot-user-slot.bin", "boot-user-slot.reproduced.bin"):
                    run("package-" + name, ["package-aiueos-user-payload",
                        "boot-user.elf", "--output", name, "--version",
                        "v3" if args.user_target == "x86_64-aiueos-user-v4" else "v2"])
                    slot = stage / name
                    if not slot.is_file() or pin(slot)["bytes"] != 524288:
                        raise ValueError("native compiler omitted the user-v2 slot")
                    slots.append(pin(slot))
                if slots[0] != slots[1]:
                    raise ValueError("user-v2 slot reproduction differed")
                user_slot = stage / "boot-user-slot.bin"
                shutil.copyfile(stage / "boot-user.elf", output / "boot-user.elf")
                state.update(bootUserSlot=slots[0], bootUserElf=user_images[0],
                             userSlotReproduced=slots[1])
                save()
            discovered = run("discover", ["modules", entry, *source_args]).decode("ascii")
            modules = {}
            for line in discovered.splitlines():
                namespace, virtual = line.split(" ", 1)
                if not namespace or virtual in modules or virtual not in sources:
                    raise ValueError("unexpected or duplicate native module")
                modules[virtual] = namespace
            if entry not in modules:
                raise ValueError("native compiler omitted kernel entry")
            for virtual in modules:
                if virtual.startswith("/owners/") and virtual not in owners:
                    raise ValueError("undeclared owner module")
            locked = {name: sources[name] for name in sorted(modules)}
            lock = stage / "kernel.ksl"
            lock.write_text("KSL1\nentry " + entry + "\n"
                            + "".join("root " + root + "\n" for root in roots)
                            + "".join("file " + locked[name]["sha256"] + " " + name + "\n"
                                      for name in locked))
            state.update(state="LOCKED", sourceLock=pin(lock), sourceModuleCount=len(modules),
                         sourceGraph=locked, ownerManifest=pin(DEPENDENCIES), owners=owners)
            save()
            images = []
            for name in ("KERNEL.ELF", "KERNEL.reproduced.ELF"):
                run("compile-" + name, ["compile", entry, "--target", args.kernel_target,
                    "--artifact", "image", "--output", name, "--fuel", str(args.fuel), *source_args,
                    "--source-lock", "kernel.ksl", "--source-lock-sha256", pin(lock)["sha256"]])
                path = stage / name
                if not path.is_file():
                    raise ValueError("native compiler omitted kernel image")
                images.append(pin(path))
                shutil.copyfile(path, output / name)
                if pin(output / name) != images[-1]:
                    raise ValueError("copied kernel image differs")
            if images[0] != images[1]:
                raise ValueError("kernel reproduction differed")
            efi_images = []
            for name in ("BOOTX64.EFI", "BOOTX64.reproduced.EFI"):
                run("package-" + name, ["package-aiueos-boot", "KERNEL.ELF", "--output", name,
                    *(["--payload", "boot-payload.bin"] if payload else []),
                    *(["--font", "boot-font.bin", "--user-slot", "boot-user-slot.bin"] if font else []),
                    "--pci-resources", "v1"])
                path = stage / name
                if not path.is_file() or path.read_bytes().count((stage / "KERNEL.ELF").read_bytes()) != 1:
                    raise ValueError("EFI does not embed exact kernel once")
                if font:
                    raw = path.read_bytes()
                    font_bytes = (stage / "boot-font.bin").read_bytes()
                    slot_bytes = (stage / "boot-user-slot.bin").read_bytes()
                    if raw.count(font_bytes) != 1 or raw.count(slot_bytes) != 1 or raw.index(slot_bytes) != raw.index(font_bytes) + 524288:
                        raise ValueError("EFI font/user slot placement mismatch")
                efi_images.append(pin(path))
                shutil.copyfile(path, output / name)
                if pin(output / name) != efi_images[-1]:
                    raise ValueError("copied EFI differs")
            if efi_images[0] != efi_images[1]:
                raise ValueError("EFI reproduction differed")
            if (pin(compiler)["sha256"] != args.compiler_sha256 or pin(lock) != state["sourceLock"]
                    or pin(DEPENDENCIES) != state["ownerManifest"]):
                raise ValueError("compiler, lock or owner manifest changed during build")
            if payload and (pin(stage / "boot-payload.bin") != state["bootPayload"]
                            or pin(payload) != state["bootPayload"]):
                raise ValueError("boot payload changed during build")
            if font and (pin(stage / "boot-font.bin") != state["bootFont"]
                         or pin(font) != state["bootFont"]
                         or pin(stage / "boot-user-slot.bin") != state["bootUserSlot"]
                         or pin(user_slot) != state["bootUserSlot"]):
                raise ValueError("font or user slot changed during build")
            if user_source and (pin(user_source) != state["bootUserSource"]
                                or pin(stage / "boot-user-source.kotoba") != state["bootUserSource"]
                                or pin(stage / "boot-user.elf") != state["bootUserElf"]
                                or pin(output / "boot-user.elf") != state["bootUserElf"]
                                or pin(output / "source/boot-user-slot.bin") != state["bootUserSlot"]):
                raise ValueError("generated user source or ELF changed during build")
            if any(pin(stage / virtual[1:]) != sources[virtual] for virtual in modules):
                raise ValueError("module bytes changed during build")
            state.update(state="MACOS_NATIVE_IMAGE_CANDIDATE", kernel=images[0], efi=efi_images[0],
                         images=images, efiImages=efi_images,
                         qualification="native Mac artifact reproduction; boot and desktop gates remain open")
            save()
            print(state["state"], len(modules), "locked modules; reproduced ELF and EFI")
        finally:
            os.close(scope)
    except Exception as error:
        if not state["state"].startswith("BLOCKED_"):
            state["state"] = "BLOCKED_INPUT_OR_REPRODUCTION"
        state["error"] = str(error)
        save()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-image", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kernel-source", type=Path, default=OS / "native/kernel.kotoba")
    parser.add_argument("--fuel", type=int, default=FUEL)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--payload-sha256")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-sha256")
    parser.add_argument("--user-slot", type=Path)
    parser.add_argument("--user-slot-sha256")
    parser.add_argument("--user-source", type=Path)
    parser.add_argument("--user-source-sha256")
    parser.add_argument("--user-elf-sha256")
    parser.add_argument("--kernel-target", choices=("x86_64-aiueos-kernel-v1",
                                                     "x86_64-aiueos-kernel-v2"),
                        default="x86_64-aiueos-kernel-v1")
    parser.add_argument("--user-target", choices=("x86_64-aiueos-user-v2",
                                                  "x86_64-aiueos-user-v3",
                                                  "x86_64-aiueos-user-v4"),
                        default="x86_64-aiueos-user-v2")
    main(parser.parse_args())
