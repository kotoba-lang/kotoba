#!/usr/bin/env python3
"""Stage pinned firmware and observe the native font/firmware payload producer."""
import argparse, hashlib, importlib.util, json, os, re, shutil, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent

def pin(p):
    b = p.read_bytes()
    return {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}

def main(a):
    spec = importlib.util.spec_from_file_location('native_font_builder', HERE / 'build-native-font-macos.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    compiler = a.compiler_image.resolve(strict=True); packager = a.packager_image.resolve(strict=True)
    helper.verify_macho(compiler, a.compiler_sha256); helper.verify_macho(packager, a.packager_sha256)
    vendor = HERE.parent / 'firmware/realtek'; provenance = json.loads((vendor / 'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        if pin(vendor / name) != {k: expected[k] for k in ('bytes', 'sha256')}:
            raise ValueError('firmware/provenance mismatch: ' + name)
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False, mode=0o700)
    root = a.amu_source.resolve(strict=True)
    parts = [root / ('seed/' + n) for n in ('00-ns-static.kotoba', '01-mem.kotoba', '02-io.kotoba')]
    parts.append(HERE.parent / 'native/bluetooth-firmware-payload.kotoba')
    (out / 'payload.kotoba').write_bytes(b''.join(p.read_bytes() + b'\n' for p in parts))
    shutil.copyfile(a.font, out / 'font.fnt')
    shutil.copyfile(vendor / 'rtl8851bu_fw.bin', out / 'firmware.bin')
    shutil.copyfile(vendor / 'rtl8761bu_config.bin', out / 'config.bin')
    state = {'schema': 'aiueos.native-ble-payload.v1', 'state': 'STAGING',
             'compiler': pin(compiler), 'packager': pin(packager), 'font': pin(a.font),
             'firmware': provenance, 'sourceParts': [{'name': p.name, **pin(p)} for p in parts], 'calls': []}
    def save(): (out / 'native-bluetooth-payload.json').write_text(json.dumps(state, indent=2) + '\n')
    fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
    if fd != 3: os.dup2(fd, 3); os.close(fd); fd = 3
    def run(name, cmd):
        r = subprocess.run(list(map(str, cmd)), cwd=out, pass_fds=(fd,), capture_output=True,
                           timeout=300, env={'PATH': '/nonexistent'})
        (out / (name + '.stdout')).write_bytes(r.stdout); (out / (name + '.stderr')).write_bytes(r.stderr)
        state['calls'].append({'name': name, 'exit': r.returncode, 'stdout': pin(out / (name + '.stdout')),
                               'stderr': pin(out / (name + '.stderr'))}); save()
        if r.returncode or r.stderr: raise ValueError(name + ': ' + r.stderr.decode(errors='replace')[:500])
        return r.stdout
    save()
    try:
        run('compile', [compiler, 'compile', 'payload.kotoba', '--target', 'aarch64-macos', '--output', 'payload.kseed'])
        raw = run('extract', [compiler, 'extract-native', 'payload.kseed', '--symbol', 'main', '--output', 'payload.raw'])
        m = re.search(rb':offset (\d+), :length (\d+), :arity 0\}', raw)
        if not m or int(m.group(2)) != pin(out / 'payload.raw')['bytes']: raise ValueError('native extraction mismatch')
        run('package', [packager, 'payload-unsigned.macho', 'payload.raw', 'fs2-cli-stdio-general', m.group(1).decode()])
        exe = out / 'payload.macho'; shutil.copyfile(out / 'payload-unsigned.macho', exe); exe.chmod(0o755)
        subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(exe)], check=True, capture_output=True)
        helper.verify_macho(exe, pin(exe)['sha256'])
        run('produce', [exe, 'font.fnt', 'firmware.bin', 'config.bin', 'aiueos-ble-payload.bin'])
        b = (out / 'aiueos-ble-payload.bin').read_bytes(); original = a.font.read_bytes()
        if (len(b) != 524288 or b[:327680] != original[:327680]
                or b[327680:377440] != (vendor / 'rtl8851bu_fw.bin').read_bytes()
                or b[377440:377446] != (vendor / 'rtl8761bu_config.bin').read_bytes()
                or b[377446:] != original[377446:]): raise ValueError('native payload readback mismatch')
        state.update(state='PASS_NATIVE_BLE_PAYLOAD', payload=pin(out / 'aiueos-ble-payload.bin'))
        save(); print(state['state'], state['payload']['sha256'])
    finally: os.close(fd)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('amu-source', 'compiler-image', 'packager-image', 'font', 'output'): p.add_argument('--' + n, type=Path, required=True)
    for n in ('compiler-sha256', 'packager-sha256'): p.add_argument('--' + n, required=True)
    main(p.parse_args())
