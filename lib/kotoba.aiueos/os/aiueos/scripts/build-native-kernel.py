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


def select_native_compiler(amu):
    amu = amu.resolve()
    descriptor = json.loads((amu / 'native-product.json').read_text())
    override = os.environ.get('AIUEOS_AMU_SELFHOST_BIN')
    compiler = Path(override).resolve() if override else amu / descriptor['entry']
    expected = os.environ.get('AIUEOS_AMU_SELFHOST_SHA256') if override else descriptor['image']['sha256']
    if not expected or pin(compiler)['sha256'] != expected:
        raise ValueError('compiler requires its exact immutable SHA256 pin (AIUEOS_AMU_SELFHOST_SHA256 for a candidate)')
    data = compiler.read_bytes()
    machine = {'x86_64': 62, 'aarch64': 183, 'arm64': 183}.get(platform.machine())
    if (platform.system() != 'Linux' or not machine or data[:7] != b'\x7fELF\x02\x01\x01'
            or struct.unpack_from('<H', data, 18)[0] != machine):
        raise ValueError('run the selected static ELF compiler on its native Linux architecture')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phsize, phnum = struct.unpack_from('<HH', data, 54)
    if phsize != 56 or any(struct.unpack_from('<I', data, phoff + i * phsize)[0] in (2, 3) for i in range(phnum)):
        raise ValueError('compiler must have no dynamic/interpreter program header')
    return compiler, expected


def main(amu):
    amu = amu.resolve()
    compiler, expected = select_native_compiler(amu)
    out = Path(os.environ.get('AIUEOS_NATIVE_OUT', REPO / 'build/aiueos-native')).resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='aiueos.native-kernel-candidate.v1', state='STAGING', compiler=pin(compiler),
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
