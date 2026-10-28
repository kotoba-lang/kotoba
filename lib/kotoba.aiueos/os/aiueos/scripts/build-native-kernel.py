#!/usr/bin/env python3
"""Stage immutable inputs and invoke native Amu; Python never compiles/packages.

A successful build is an artifact candidate, not an ISR/live/desktop verdict.
No hosted compiler, source trimming, unpinned mode or packaging fallback.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
OS = REPO / 'os/aiueos'
DEPENDENCIES = OS / 'native/source-dependencies.json'
VARIABLES = {
    'capability-link-frame': 'AIUEOS_LINK_FRAME_SOURCE_PATH',
    'capability-dma-map': 'AIUEOS_DMA_MAP_SOURCE_PATH',
    'capability-mmio-map': 'AIUEOS_MMIO_MAP_SOURCE_PATH',
    'capability-net-transport': 'AIUEOS_NET_TRANSPORT_SOURCE_PATH',
    'org-ietf-tcp': 'AIUEOS_ORG_IETF_TCP_SOURCE_PATH',
}


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def path_text(path):
    value = str(path)
    if not value.isascii() or any(c.isspace() for c in value) or ':' in value:
        raise ValueError('KSL1 requires bounded ASCII paths without whitespace or colons')
    return value


def inspect_linux_elf(data, machine):
    if (len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01'
            or struct.unpack_from('<H', data, 16)[0] != 2
            or struct.unpack_from('<H', data, 18)[0] != machine):
        raise ValueError('selected compiler must be a native static Linux ELF64 executable')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phsize, phnum = struct.unpack_from('<HH', data, 54)
    if phsize != 56 or not 1 <= phnum <= 256 or phoff + phsize * phnum > len(data):
        raise ValueError('compiler has an invalid ELF program header table')
    kinds = [struct.unpack_from('<I', data, phoff + i * phsize)[0] for i in range(phnum)]
    if any(kind in (2, 3) for kind in kinds) or 1 not in kinds:
        raise ValueError('compiler must have loadable segments and no dynamic/interpreter program header')
    return dict(format='loaderless-static-ELF64', declaredDynamicLibraries=[])


def macho_command_string(data, offset, size, minimum):
    if size < minimum:
        raise ValueError('truncated Mach-O path command')
    start = struct.unpack_from('<I', data, offset + 8)[0]
    if not minimum <= start < size:
        raise ValueError('invalid Mach-O path offset')
    raw = data[offset + start:offset + size].split(b'\0', 1)
    if len(raw) != 2 or not raw[0]:
        raise ValueError('unterminated Mach-O path')
    try:
        return raw[0].decode('ascii')
    except UnicodeDecodeError as exc:
        raise ValueError('non-ASCII Mach-O path') from exc


def inspect_macos_arm64(data):
    if len(data) < 32 or data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('selected compiler must be a thin Mach-O64 executable')
    _, cpu, subtype, kind, commands, size, flags, _ = struct.unpack_from('<8I', data)
    if cpu != 0x0100000c or (subtype & 0x00ffffff) != 0 or kind != 2:
        raise ValueError('selected compiler must be a macOS arm64 executable')
    if (flags & 0x00200085) != 0x00200085:
        raise ValueError('macOS compiler lacks required dynamic-link executable flags')
    if not 1 <= commands <= 256 or size > 1048576 or 32 + size > len(data):
        raise ValueError('compiler has an invalid Mach-O load command table')
    offset, end = 32, 32 + size
    text_extent = None
    entry = False
    main_offset = None
    libraries = []
    for _ in range(commands):
        if offset + 8 > end:
            raise ValueError('truncated Mach-O load command')
        command, length = struct.unpack_from('<II', data, offset)
        if length < 8 or length % 8 or offset + length > end:
            raise ValueError('invalid Mach-O load command size')
        if command == 0x19:  # LC_SEGMENT_64
            if length < 72:
                raise ValueError('truncated Mach-O segment')
            name = data[offset + 8:offset + 24].split(b'\0', 1)[0]
            fileoff, filesize = struct.unpack_from('<QQ', data, offset + 40)
            initprot, sections = struct.unpack_from('<II', data, offset + 60)
            if length < 72 + sections * 80 or fileoff + filesize > len(data):
                raise ValueError('invalid Mach-O segment extent')
            if (initprot & 6) == 6:
                raise ValueError('writable executable Mach-O segment')
            if name == b'__TEXT' and (initprot & 4) and filesize:
                if text_extent is not None:
                    raise ValueError('duplicate executable Mach-O text segment')
                text_extent = (fileoff, fileoff + filesize)
        elif command == 0x80000028:  # LC_MAIN
            if length < 24:
                raise ValueError('truncated Mach-O entry command')
            entry = True
            main_offset = struct.unpack_from('<Q', data, offset + 8)[0]
        elif command == 0x5:  # LC_UNIXTHREAD
            if length <= 8:
                raise ValueError('truncated Mach-O thread entry')
            entry = True
        elif command == 0xe:  # LC_LOAD_DYLINKER
            if macho_command_string(data, offset, length, 12) != '/usr/lib/dyld':
                raise ValueError('undeclared Mach-O dynamic linker')
        elif command == 0xc:  # LC_LOAD_DYLIB
            if length < 24:
                raise ValueError('truncated Mach-O library command')
            library = macho_command_string(data, offset, length, 24)
            if library != '/usr/lib/libSystem.B.dylib':
                raise ValueError('undeclared Mach-O dynamic library: ' + library)
            libraries.append(library)
        elif command in (0x10, 0x18, 0x20, 0x27, 0x80000018, 0x8000001c,
                         0x8000001f, 0x80000023):
            raise ValueError('Mach-O command can broaden dynamic dependencies')
        elif command == 0x1d:  # LC_CODE_SIGNATURE
            if length < 16:
                raise ValueError('truncated Mach-O code signature command')
            signature_offset, signature_size = struct.unpack_from('<II', data, offset + 8)
            if signature_offset + signature_size > len(data):
                raise ValueError('invalid Mach-O code signature extent')
        # Metadata, symbol tables, and dyld fixup tables cannot name an
        # additional library without a load command admitted above.
        elif command not in (0x2, 0xb, 0x1a, 0x22, 0x26, 0x29, 0x2a, 0x32,
                             0x80000022, 0x80000033, 0x80000034):
            raise ValueError('unrecognized Mach-O load command')
        offset += length
    if (offset != end or text_extent is None or not entry
            or (main_offset is not None and not text_extent[0] <= main_offset < text_extent[1])):
        raise ValueError('compiler lacks a complete Mach-O text/entry graph')
    return dict(format='Mach-O64-arm64', declaredDynamicLibraries=sorted(set(libraries)))


def inspect_current_host_image(data):
    system, architecture = platform.system(), platform.machine().lower()
    if system == 'Linux' and architecture in ('x86_64', 'aarch64', 'arm64'):
        profile = inspect_linux_elf(data, 62 if architecture == 'x86_64' else 183)
        host = ('x86_64' if architecture == 'x86_64' else 'aarch64') + '-linux'
    elif system == 'Darwin' and architecture in ('arm64', 'aarch64'):
        profile = inspect_macos_arm64(data)
        host = 'aarch64-macos'
    else:
        raise ValueError('unsupported native Amu compiler host')
    return dict(host=host, **profile)


def native_tool_spec(profile):
    target = profile['host']
    if target not in ('x86_64-linux', 'aarch64-linux', 'aarch64-macos'):
        raise ValueError('unsupported native tool target')
    return target, '.macho' if target == 'aarch64-macos' else '.elf'


def verify_macos_compiler_launch(compiler):
    signature = subprocess.run(
        ['/usr/bin/codesign', '--verify', '--strict', str(compiler)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=10, check=False)
    if signature.returncode != 0:
        raise ValueError('macOS compiler code signature did not verify')
    try:
        probe = subprocess.run(
            [str(compiler)], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
            env={'PATH': '/usr/bin:/bin'}, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('macOS compiler did not start its native CLI') from exc
    if probe.returncode != 2 or b'seed: E1 usage: seed ' not in probe.stderr:
        raise ValueError('macOS compiler did not answer its native CLI probe')


def select_native_compiler(amu):
    amu = amu.resolve()
    descriptor = json.loads((amu / 'native-product.json').read_text())
    override = os.environ.get('AIUEOS_AMU_SELFHOST_BIN')
    compiler = Path(override).resolve() if override else amu / descriptor['entry']
    expected = os.environ.get('AIUEOS_AMU_SELFHOST_SHA256') if override else descriptor['image']['sha256']
    if not expected or pin(compiler)['sha256'] != expected:
        raise ValueError('compiler requires its exact immutable SHA256 pin (AIUEOS_AMU_SELFHOST_SHA256 for a candidate)')
    profile = inspect_current_host_image(compiler.read_bytes())
    if not override and descriptor.get('host') != profile['host']:
        raise ValueError('native-product host does not match this machine')
    if profile['host'] == 'aarch64-macos':
        verify_macos_compiler_launch(compiler)
        profile['launchProbe'] = 'native-cli-usage-v1'
    return compiler, expected, profile


def main(amu):
    amu = amu.resolve()
    compiler, expected, compiler_profile = select_native_compiler(amu)
    out = Path(os.environ.get('AIUEOS_NATIVE_OUT', REPO / 'build/aiueos-native')).resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='aiueos.native-kernel-candidate.v1', state='STAGING', compiler=pin(compiler),
                 compilerProfile=compiler_profile,
                 compilerHost=[platform.system(), platform.machine()], nativeCompilerExecution=True,
                 JVMNodeOrGraalFallback=False, cCompilerOrLoader=False, runtimeQualified=False,
                 mediaQualified=False, desktopInputQualified=False, calls=[])

    def save():
        (out / 'build-state.json').write_text(json.dumps(state, indent=2) + '\n')

    save()
    try:
        payload_text = os.environ.get('AIUEOS_NATIVE_BOOT_PAYLOAD')
        payload = Path(payload_text).resolve() if payload_text else None
        payload_pin = pin(payload) if payload else None
        if payload and (payload_pin['sha256'] != os.environ.get('AIUEOS_NATIVE_BOOT_PAYLOAD_SHA256') or payload_pin['bytes'] > 524288):
            raise ValueError('boot payload requires its immutable SHA256 and bounded size')
        state['bootPayload'] = payload_pin
        entry = Path(os.environ.get('AIUEOS_NATIVE_KERNEL_SOURCE', OS / 'native/kernel.kotoba')).resolve()
        roots = [REPO / 'os', OS, OS / 'kotoba']
        owners = {}
        manifest = json.loads(DEPENDENCIES.read_text())
        assert manifest['schema'] == 'aiueos.native-source-dependencies.v1'
        for dep in manifest['dependencies']:
            repo = dep['repo']
            root = Path(os.environ.get(VARIABLES[repo], REPO.parent / repo / 'kotoba')).resolve()
            roots.append(root)
            for relative, digest in dep['files'].items():
                file = root / str(Path(relative).relative_to('kotoba'))
                if pin(file)['sha256'] != digest:
                    raise ValueError(f'owner source pin drift: {repo}/{relative}')
                owners[file] = dict(commit=dep['commit'], sha256=digest)
        for p in [entry, out, *roots]:
            path_text(p)
        scope = ':'.join(map(str, [*roots, out, *([payload.parent] if payload else [])]))
        # KEXE_SECCOMP opt-in passes through when the caller sets it: the
        # hardened runtime fails closed with `kexe-runtime: resource limit
        # setup failed` where seccomp(2) is unavailable (measured 2026-10-26 in
        # an emulated container); native Linux never sets it and is unchanged.
        _kexe = {'KEXE_SECCOMP': os.environ['KEXE_SECCOMP']} if os.environ.get('KEXE_SECCOMP') else {}
        env = dict(PATH='/nonexistent', KEXE_STACK_BYTES='8388608', KEXE_CAP_RESOURCES_35=scope, **_kexe)
        source_args = [value for root in roots for value in ['--source-path', str(root)]]

        def run(name, args):
            result = subprocess.run([str(compiler), *map(str, args)], env=env, capture_output=True, timeout=3600)
            for suffix, raw in [('stdout', result.stdout), ('stderr', result.stderr)]:
                (out / f'{name}.{suffix}').write_bytes(raw)
            state['calls'].append(dict(name=name, exit=result.returncode, argv=list(map(str, args)),
                                       stdout=pin(out / f'{name}.stdout'), stderr=pin(out / f'{name}.stderr')))
            save()
            if result.returncode or result.stderr:
                state['state'] = 'BLOCKED_NATIVE_' + name.upper().replace('-', '_')
                raise RuntimeError(f'{name}: native compiler exit {result.returncode}: {result.stderr.decode(errors="replace").strip()[:600]}')
            return result.stdout

        discovered = run('discover', ['modules', entry, *source_args]).decode('ascii')
        modules = []
        for line in discovered.splitlines():
            namespace, file = line.split(' ', 1)
            path = Path(file)
            path_text(path)
            if not namespace or not path.is_absolute() or path in [p for _, p in modules]:
                raise ValueError('invalid or duplicate native module discovery row')
            if not any(path.is_relative_to(root) for root in roots):
                raise ValueError('native module outside declared roots')
            modules.append((namespace, path))
        if not modules or entry not in [p for _, p in modules]:
            raise ValueError('native discovery did not include the complete entry graph')
        sources = {p: pin(p) for _, p in modules}
        for file, identity in sources.items():
            if any(file.is_relative_to(root) for root in roots[3:]) and (file not in owners or identity['sha256'] != owners[file]['sha256']):
                raise ValueError(f'undeclared owner source: {file}')
        lock = out / 'kernel.ksl'
        lock.write_text('KSL1\nentry ' + str(entry) + '\n'
                        + ''.join(f'root {root}\n' for root in roots)
                        + ''.join(f'file {sources[p]["sha256"]} {p}\n' for p in sorted(sources)))
        state.update(state='LOCKED', sourceLock=pin(lock), sourceModuleCount=len(modules),
                     sourceGraph=[dict(namespace=n, path=str(p), **sources[p]) for n, p in modules],
                     ownerManifest=pin(DEPENDENCIES))
        save()
        fuel = str(int(os.environ.get('AIUEOS_NATIVE_FUEL', '1073741824')))
        if int(fuel) <= 0:
            raise ValueError('fuel must be positive')
        images = []
        for name in ['KERNEL.ELF', 'KERNEL.reproduced.ELF']:
            image = out / name
            run('compile-' + name, ['compile', entry, '--target', 'x86_64-aiueos-kernel-v1',
                '--artifact', 'image', '--output', image, '--fuel', fuel, *source_args,
                '--source-lock', lock, '--source-lock-sha256', pin(lock)['sha256']])
            if not image.is_file():
                raise ValueError('native compiler returned without an image')
            images.append(pin(image))
        if images[0] != images[1] or {p: pin(p) for p in sources} != sources or pin(compiler)['sha256'] != expected:
            raise ValueError('native reproduction or immutable input readback differs')
        efi_images = []
        for name in ['BOOTX64.EFI', 'BOOTX64.reproduced.EFI']:
            efi = out / name
            run('package-' + name, ['package-aiueos-boot', out / 'KERNEL.ELF',
                '--output', efi, *(['--payload', payload] if payload else []), '--pci-resources', 'v1'])
            if not efi.is_file() or efi.read_bytes().count((out / 'KERNEL.ELF').read_bytes()) != 1:
                raise ValueError('native EFI does not contain the exact kernel once')
            efi_images.append(pin(efi))
        if efi_images[0] != efi_images[1] or {p: pin(p) for p in sources} != sources or pin(compiler)['sha256'] != expected or (payload and pin(payload) != payload_pin):
            raise ValueError('native EFI reproduction or immutable input readback differs')
        state.update(state='NATIVE_IMAGE_CANDIDATE', images=images, efiImages=efi_images,
                     bootProtocol='pci-resources-v1',
                     qualification='native artifact reproduction only; ISR/live/runtime gates remain required')
        save()
        print(state['state'], len(modules), 'locked modules; reproduced ELF and PCI v6 EFI')
    except Exception as exc:
        if not state['state'].startswith('BLOCKED_'):
            state['state'] = 'BLOCKED_INPUT_OR_REPRODUCTION'
        state['error'] = str(exc)
        save()
        raise


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: build-native-kernel.py AMU_SOURCE')
    try:
        main(Path(sys.argv[1]))
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
