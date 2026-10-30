#!/usr/bin/env python3
"""Run the native post-quantum and secure-channel known-answer gates and their mutants
(JUN-352 P1b: SHA-3, ML-KEM-768, ML-DSA-65; AWAI-117: X25519, ChaCha20-Poly1305 and
XChaCha20-Poly1305, the pqh-v1 hybrid KEM; JUN-352: AES and AES-GCM; AWAI-102: X-Wing, Noise, Noise XXhfs and its identity payload).

Each gate is one unity source: the library bodies with their `ns` forms removed, the
`sha3/` alias dropped, then the gate body. The gate's main returns a bitmask; a pass is
every bit set. Each mutant changes one line of a library body and must not pass.
Runs on Linux arm64 (the aarch64 payload packed into an aarch64-linux runner image, as
the arm64 owner lane does), on Apple Silicon (Mac root and packager, through
lib/kotoba.hata/scripts/native_gate.py) and on Linux x86_64 (KX64 under the native
runner). The pinned x86_64 KX64 profile refuses string literals (E7101 detail 16), which
the gates use for their vectors, so x86_64 is not run in CI yet.
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib/kotoba.hata/scripts'))
from native_gate import NativeGate  # noqa: E402

SHA3 = 'lib/gov.nist.sha3/kotoba/sha3/core.kotoba'
GATES = {
    'sha3': dict(bodies=[SHA3], gate='lib/gov.nist.sha3/kotoba/sha3/native_gate.kotoba', passing=63, mutants={
        'constant': (SHA3, '0x0000000000008082', '0x0000000000008083'),
        'suffix': ('lib/gov.nist.sha3/kotoba/sha3/core.kotoba', '(sponge bytes 136 6 32))', '(sponge bytes 136 1 32))'),
    }),
    'mlkem': dict(bodies=[SHA3, 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba'],
                  gate='lib/gov.nist.mlKem/kotoba/mlkem/native_gate.kotoba', passing=63, mutants={
        'zeta': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(vector-i64 1 1729 ', '(vector-i64 1 1730 '),
        'mask': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(if (= differ 0) 0 255)', '(if (= differ 0) 255 0)'),
        'cbd': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(md (- x y))', '(md (- y x))'),
    }),
    'mldsa': dict(bodies=[SHA3, 'lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba'],
                  gate='lib/gov.nist.mlDsa/kotoba/mldsa/native_gate.kotoba', passing=31, mutants={
        'ctx': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba', '(vector-i64 0 (vector-count ctx))', '(vector-i64 1 (vector-count ctx))'),
        'hint': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                 '(and (> p idx) (>= (vector-at hb (- p 1)) (vector-at hb p))) -1', 'false -1'),
        'znorm': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                  '(if (or (= (vector-count h) 0) (>= (vnorm z) 524092)) false', '(if (= (vector-count h) 0) false'),
    }),
}

# Module gates (AWAI-117) are built as modules from the library files, not as a unity
# source. A gate with groups runs one image per group through a one-line entry module,
# because one image holds only 10-20 X25519 multiplications.
X25519 = {'x25519/field.kotoba': 'lib/org.ietf.x25519/kotoba/x25519/field.kotoba',
          'x25519/core.kotoba': 'lib/org.ietf.x25519/kotoba/x25519/core.kotoba'}
CHACHA = {f'chacha20/{n}.kotoba': f'lib/org.ietf.chacha20Poly1305/kotoba/chacha20/{n}.kotoba'
          for n in ['core', 'poly1305', 'aead', 'aead_params']}
MODULE_GATES = {
    'x25519': dict(files=dict(X25519, **{'x25519/native_gate.kotoba': 'lib/org.ietf.x25519/kotoba/x25519/native_gate.kotoba'}),
                   gate_ns='x25519.native-gate', groups={'a': 15, 'b': 7, 'c': 15}, mutants={
        'a24': ('x25519/core.kotoba', '0 121665))', '0 121666))'),
        'clamp': ('x25519/core.kotoba', '(bit-and (vector-at k 0) 248)', '(bit-and (vector-at k 0) 255)'),
        'mask': ('x25519/field.kotoba', '(bit-and limb 32767)', '(bit-and limb 65535)'),
    }),
    'chacha20': dict(files=dict(CHACHA, **{'chacha20/native_gate.kotoba': 'lib/org.ietf.chacha20Poly1305/kotoba/chacha20/native_gate.kotoba'}),
                     entry='chacha20/native_gate.kotoba', passing=255, mutants={
        'rotl': ('chacha20/core.kotoba', '(vector-at s a)) 16))', '(vector-at s a)) 15))'),
        'clamp': ('chacha20/poly1305.kotoba', '(bit-and t0 67108863)', '(bit-and t0 268435455)'),
        'final': ('chacha20/poly1305.kotoba', 'use-g (>= g4 0)', 'use-g false'),
        'tagcmp': ('chacha20/aead.kotoba', '(if (= differ 0) (c/xor-stream key 1 nonce ct) (vector-i64 -1))', '(c/xor-stream key 1 nonce ct)'),
        'hround': ('chacha20/core.kotoba', 'words (vector-i64 0 1 2 3 12 13 14 15)', 'words (vector-i64 0 1 2 3 11 13 14 15)'),
    }),
    'xwing': dict(files=dict(X25519, **{'sha3/core.kotoba': SHA3, 'mlkem/core.kotoba': 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba',
                                        'xwing/core.kotoba': 'lib/org.ietf.xwing/kotoba/xwing/core.kotoba',
                                        'xwing/native_gate.kotoba': 'lib/org.ietf.xwing/kotoba/xwing/native_gate.kotoba'}),
                  gate_ns='xwing.native-gate', groups={'a': 7, 'b': 7, 'c': 63}, mutants={
        'label': ('xwing/core.kotoba', '(vector-i64 92 46 47 47 94 92)', '(vector-i64 92 46 47 47 94 93)'),
        'order': ('xwing/core.kotoba', '(cat (cat (cat (cat ss-m ss-x) ct-x) pk-x) (label))', '(cat (cat (cat (cat ss-x ss-m) ct-x) pk-x) (label))'),
        'eseed': ('xwing/core.kotoba', 'ek-x (slice eseed 32 32)', 'ek-x (slice eseed 0 32)'),
    }),
    'noise': dict(files=dict(X25519, **CHACHA, **{'sha2/core.kotoba': 'lib/gov.nist.sha2/kotoba/sha2/core.kotoba',
                                                  'sha3/core.kotoba': SHA3, 'mlkem/core.kotoba': 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba',
                                                  'noise/native.kotoba': 'lib/kotoba.noise/kotoba/noise/native.kotoba',
                                                  'noise/native_gate.kotoba': 'lib/kotoba.noise/kotoba/noise/native_gate.kotoba'}),
                  gate_ns='noise.native-gate', groups={g: 31 for g in ['nn-i', 'nn-r', 'xx-i', 'xx-r', 'ik-i', 'ik-r']}, mutants={
        'hkdf': ('noise/native.kotoba', '(h/hmac-sha256 temp (cat o1 (vector-i64 2)))', '(h/hmac-sha256 temp (cat o1 (vector-i64 3)))'),
        'esse': ('noise/native.kotoba', '(= token 4) (if init (x/x25519-bytes e rs) (x/x25519-bytes s re))',
                 '(= token 4) (if init (x/x25519-bytes s re) (x/x25519-bytes e rs))'),
        'premsg': ('noise/native.kotoba', '(if (= pattern 2) (mix-hash st5', '(if false (mix-hash st5'),
    }),
    'xxhfs': dict(files=dict(X25519, **CHACHA, **{'sha2/core.kotoba': 'lib/gov.nist.sha2/kotoba/sha2/core.kotoba',
                                                  'sha3/core.kotoba': SHA3, 'mlkem/core.kotoba': 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba',
                                                  'noise/native.kotoba': 'lib/kotoba.noise/kotoba/noise/native.kotoba',
                                                  'noise/xxhfs_gate.kotoba': 'lib/kotoba.noise/kotoba/noise/xxhfs_gate.kotoba'}),
                  gate_ns='noise.xxhfs-gate', groups={'i': 63, 'r': 63}, mutants={
        'w-mixkey': ('noise/native.kotoba', '(recur (+ i 1) (mix-key (slice o 0 1646) (slice kc 0 32))', '(recur (+ i 1) (slice o 0 1646)'),
        'r-mixkey': ('noise/native.kotoba', '(recur (+ i 1) (mix-key (slice o 0 1646) ss) (+ pos n))', '(recur (+ i 1) (slice o 0 1646) (+ pos n))'),
        'e1-hash': ('noise/native.kotoba', '(let [o (encrypt-and-hash st (slice (kem-pair st) 0 1184))]', '(let [o (cat st (slice (kem-pair st) 0 1184))]'),
        'kem-half': ('noise/native.kotoba', '(k/decaps (slice (kem-pair o) 1184 2400)', '(k/decaps (slice (kem-pair o) 0 2400)'),
    }),
    'identity': dict(files=dict(X25519, **CHACHA, **{'sha2/core.kotoba': 'lib/gov.nist.sha2/kotoba/sha2/core.kotoba',
                                                     'sha3/core.kotoba': SHA3, 'mlkem/core.kotoba': 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba',
                                                     'mldsa/core.kotoba': 'lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                                                     'ed25519/selfhost.kotoba': 'lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba',
                                                     'noise/native.kotoba': 'lib/kotoba.noise/kotoba/noise/native.kotoba',
                                                     'noise/identity.kotoba': 'lib/kotoba.noise/kotoba/noise/identity.kotoba',
                                                     'noise/identity_gate.kotoba': 'lib/kotoba.noise/kotoba/noise/identity_gate.kotoba'}),
                     gate_ns='noise.identity-gate', groups={'i': 127, 'r': 127}, mutants={
        'no-want': ('noise/identity.kotoba', '       (same? (slice p 0 1984) want)\n', ''),
        'no-dsa': ('noise/identity.kotoba', '              (dsa/verify (slice p 32 1952) msg (vector-i64) (slice p 2048 3309))))))', '              true))))'),
        'no-ed': ('noise/identity.kotoba', '         (and (ed/verify? (slice p 0 32) msg (slice p 1984 64))', '         (and true'),
    }),
    'aes': dict(files={f'aes/{n}.kotoba': f'lib/gov.nist.aes/kotoba/aes/{n}.kotoba' for n in ['core', 'gcm', 'native_gate']},
                gate_ns='aes.native-gate', groups={'a': 15, 'b': 7, 'c': 7}, mutants={
        'sbox': ('aes/core.kotoba', '(vector-i64 99 124 119 123', '(vector-i64 99 124 119 122'),
        'mixcol': ('aes/core.kotoba', '(bit-xor (bit-xor x0 (bit-xor x1 a1)) (bit-xor a2 a3))', '(bit-xor (bit-xor x0 x1) (bit-xor a2 a3))'),
        'sub8': ('aes/core.kotoba', 'sub (and (> nk 6) (= (rem i nk) 4))', 'sub false'),
        'gfred': ('aes/gcm.kotoba', '(bit-xor v0 3774873600)', '(bit-xor v0 3758096384)'),
        'carry': ('aes/gcm.kotoba', '(vector-i64 (vector-at cb 0) (vector-at cb 1) (vector-at cb 2) (bit-and (+ (vector-at cb 3) 1) 4294967295))',
                  '(vector-i64 (vector-at cb 0) (vector-at cb 1) (+ (vector-at cb 2) (quot (+ (vector-at cb 3) 1) 4294967296)) (bit-and (+ (vector-at cb 3) 1) 4294967295))'),
        'tagcmp': ('aes/gcm.kotoba', '(if (= differ 0) (gctr sched (inc32 j) ct) (vector-i64 -1))', '(gctr sched (inc32 j) ct)'),
    }),
    'pqh': dict(files=dict(X25519, **{'sha3/core.kotoba': SHA3, 'mlkem/core.kotoba': 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba',
                                      'sha2/core.kotoba': 'lib/gov.nist.sha2/kotoba/sha2/core.kotoba',
                                      'pqh/hybrid.kotoba': 'lib/kotoba.pqh/kotoba/pqh/hybrid.kotoba',
                                      'pqh/native_gate.kotoba': 'lib/kotoba.pqh/kotoba/pqh/native_gate.kotoba'}),
                gate_ns='pqh.native-gate', groups={'a': 7, 'b': 15, 'c': 15}, mutants={
        'salt': ('pqh/hybrid.kotoba', '(vector-i64 101 116 122 104', '(vector-i64 100 116 122 104'),
        'transcript': ('pqh/hybrid.kotoba', '(h/sha256 (cat (cat (cat eph-pub ct) rx-pub) r-ek))', '(h/sha256 (cat (cat eph-pub ct) rx-pub))'),
        'lowcheck': ('pqh/hybrid.kotoba', '(if (not (x/contributory? ss-x)) (vector-i64)\n            (let [eph-pub',
                     '(if false (vector-i64)\n            (let [eph-pub'),
    }),
}

def module_files(spec, change=None):
    files = {}
    for name, path in spec['files'].items():
        data = (ROOT / path).read_text()
        if change and change[0] == name:
            assert data.count(change[1]) == 1, (name, change)
            data = data.replace(change[1], change[2])
        files[name] = data.encode()
    return files

def module_results(gate, name, spec, label, files):
    """Run every group (or the gate's own main) and return {group: result}."""
    out = {}
    if 'groups' not in spec:
        try:
            gate.run(label + '-run', gate.build(label, spec['entry'], files), spec['passing'])
            out['main'] = spec['passing']
        except AssertionError:
            out['main'] = None
        return out
    for grp, expected in spec['groups'].items():
        entry = f'pq/{name}_gate_{grp.replace("-", "_")}.kotoba'
        fs = dict(files)
        fs[entry] = (f'(ns pq.{name}-gate-{grp} (:require [{spec["gate_ns"]} :as g]) (:export [main]))\n'
                     f'(defn main [] :i64 (g/group-{grp}))\n').encode()
        try:
            gate.run(f'{label}-{grp}-run', gate.build(f'{label}-{grp}', entry, fs), expected)
            out[grp] = expected
        except AssertionError:
            out[grp] = None
    return out

def strip_ns(text):
    return re.sub(r'^\(ns [^\n]*\n(?:[^\n]*\n)*?[^\n]*\)\)\n', '', text, count=1, flags=re.M)

def unity(name, spec, change=None):
    parts = [f'(ns pq.{name}-gate (:export [main]))\n']
    for path in spec['bodies'] + [spec['gate']]:
        text = (ROOT / path).read_text()
        if change and change[0] == path:
            assert text.count(change[1]) == 1, (name, change)
            text = text.replace(change[1], change[2])
        parts.append(strip_ns(text).replace('sha3/', '') if path != spec['gate'] else strip_ns(text))
    return ''.join(parts).encode()

class LinuxArm:
    """Linux aarch64: compile to an aarch64 payload, pack it into the runner (from
    --runner-source) as an aarch64-linux image, and read main's result from the
    structured report."""
    def __init__(self, args):
        assert (platform.system(), platform.machine()) in {('Linux', 'aarch64'), ('Linux', 'arm64')}
        self.compiler = args.compiler.resolve()
        assert hashlib.sha256(self.compiler.read_bytes()).hexdigest() == args.compiler_sha256
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=False, mode=0o700)
        # The compiler reads only inside its resource scope, so the runner source is copied in.
        self.runner_source = self.out / 'runner.kotoba'
        self.runner_source.write_bytes(args.runner_source.read_bytes())
        self.observations, self.artifacts = [], {}

    def env(self, **extra):
        # The compiler reads sources and the lock through the scoped resource capability.
        return dict(PATH='/nonexistent', KEXE_STACK_BYTES='8388608', KEXE_CAP_RESOURCES_35=str(self.out), **extra)

    def call(self, label, argv, env=None):
        start = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=self.out, capture_output=True, timeout=900,
                                env=env or self.env())
        (self.out / (label + '.stdout')).write_bytes(result.stdout)
        (self.out / (label + '.stderr')).write_bytes(result.stderr)
        self.observations.append(dict(name=label, exit=result.returncode, seconds=round(time.monotonic() - start, 3)))
        print(label, result.returncode, result.stderr.decode(errors='replace')[:300], flush=True)
        return result

    def build(self, label, entry, files):
        root = self.out / label / 'src'
        for name, data in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(data)
        source = root / entry
        lock = self.out / (label + '.ksl')
        lock.write_text(f'KSL1\nentry {source}\nroot {root}\n' + ''.join(
            f'file {hashlib.sha256(data).hexdigest()} {root / name}\n' for name, data in sorted(files.items())))
        flags = ['--source-path', root, '--source-lock', lock,
                 '--source-lock-sha256', hashlib.sha256(lock.read_bytes()).hexdigest()]
        for step, argv in [('check', [self.compiler, 'check', source, *flags]),
                           ('compile', [self.compiler, 'compile', source, '--target', 'aarch64-macos',
                                        '--output', self.out / (label + '.kseed'), *flags]),
                           ('pack', [self.compiler, 'compile', self.runner_source, '--target', 'aarch64-linux',
                                     '--output', self.out / (label + '.elf'), '--format', 'packed',
                                     '--payload', self.out / (label + '.kseed')])]:
            r = self.call(f'{label}-{step}', argv)
            assert r.returncode == 0 and not r.stderr, (label, step, r.returncode, r.stderr[-500:])
        image = self.out / (label + '.elf')
        image.chmod(0o755)
        self.artifacts[label] = dict(imageSHA256=hashlib.sha256(image.read_bytes()).hexdigest(),
                                     sources={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})
        return image

    def run(self, label, image, expected):
        # wire 37 only: the SHA-3 gate prints its oracle lines; nothing else is granted
        r = self.call(label, [image], self.env(KEXE_STRUCTURED_REPORT='1', KEXE_ALLOW='37'))
        match = re.search(rb':result (-?[0-9]+)', r.stdout)
        self.observations[-1]['result'] = int(match[1]) if match else None
        print(label, 'result', self.observations[-1]['result'], flush=True)
        assert r.returncode == 0 and match and int(match[1]) == expected, (label, r.returncode, r.stdout[-300:])
        return r

    def finish(self, status, **details):
        (self.out / 'evidence.json').write_text(json.dumps(dict(
            status=status, compilerSHA256=hashlib.sha256(self.compiler.read_bytes()).hexdigest(),
            runnerSourceSHA256=hashlib.sha256(self.runner_source.read_bytes()).hexdigest(),
            host=[platform.system(), platform.machine()], artifacts=self.artifacts,
            observations=self.observations, **details), indent=2) + '\n')
        print(status, flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--runner', type=Path, help='Linux x86_64: the native runner')
    parser.add_argument('--runner-source', type=Path, help='Linux arm64: the runner source to pack into')
    parser.add_argument('--packager', type=Path, help='macOS: the Mac packager')
    parser.add_argument('--packager-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gate = LinuxArm(args) if platform.system() == 'Linux' and platform.machine() in ('aarch64', 'arm64') else NativeGate(args)
    results = {}
    for name, spec in GATES.items():
        entry = f'pq/{name}_gate.kotoba'
        image = gate.build(name, entry, {entry: unity(name, spec)})
        gate.run(name + '-pass', image, spec['passing'])
        results[name] = dict(passing=spec['passing'], mutants={})
        for label, change in spec['mutants'].items():
            mutant = gate.build(f'{name}-{label}', entry, {entry: unity(name, spec, change)})
            try:
                gate.run(f'{name}-{label}-detected', mutant, spec['passing'])
                detected = False
            except AssertionError:
                detected = True
            results[name]['mutants'][label] = detected
            assert detected, (name, label, 'mutant passed the gate')
    for name, spec in MODULE_GATES.items():
        passing = module_results(gate, name, spec, name, module_files(spec))
        assert None not in passing.values(), (name, passing)
        results[name] = dict(passing=passing, mutants={})
        for label, change in spec['mutants'].items():
            got = module_results(gate, name, spec, f'{name}-{label}', module_files(spec, change))
            detected = None in got.values()
            results[name]['mutants'][label] = detected
            assert detected, (name, label, 'mutant passed every group')
    gate.finish('PASS_PQ_NATIVE_GATES', gates=results)

if __name__ == '__main__':
    main()
