#!/usr/bin/env python3
"""Broker votes over authenticated sessions between processes (AWAI-102), on Linux arm64.

Each replica runs as its own process and serves its vote over a Noise XXhfs + ML-KEM-768
session with Ed25519 + ML-DSA-65 identities (lib/kotoba.noise, ADR-0001), over the
static runtime's native TCP wires, each exchange in one hata.wire envelope. The
coordinator dials each replica, sends the prepared request and stores the bound vote;
the existing broker driver then has to assemble a quorum certificate from those votes.
A second session per replica then carries the commit (sequence 0) and the attest
(sequence 1), and the broker driver must decide a fresh committed head from those
attestations. Three controls must be refused: a coordinator expecting another replica's
identity, a request whose id was made for another position, and a commit replayed where
the attest belongs.

Python only starts processes, passes paths and reads results; the native images build
and verify every message. Builds as scripts/check-pq-native.py does on the arm64 lane
(aarch64 payload packed into the runner). Run inside Linux arm64, e.g. the podman
machine; all traffic stays on 127.0.0.1 (--network none).
"""
import argparse
import hashlib
import importlib.util
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]
ROOT = LIB.parents[1]
spec = importlib.util.spec_from_file_location('check_pq_native', ROOT / 'scripts' / 'check-pq-native.py')
PQ = importlib.util.module_from_spec(spec); spec.loader.exec_module(PQ)
spec = importlib.util.spec_from_file_location('check_broker_native', LIB / 'scripts' / 'check-broker-native.py')
BR = importlib.util.module_from_spec(spec); spec.loader.exec_module(BR)

# every namespace this driver may reach, by file; the closure is computed from :require
CANDIDATES = {
    **{f'hata/{n}.kotoba': LIB / f'src/hata/{n}.kotoba' for n in
       ['codec', 'admission', 'authority', 'quorum', 'seal', 'store_io', 'read', 'replica', 'wire',
        'broker', 'store', 'audit']},
    'hata/broker_fixture.kotoba': LIB / 'test/broker_fixture.kotoba',
    'kototama/effect_origins.kotoba': LIB.parent / 'kotoba.kototama/src/kototama/effect_origins.kotoba',
    'hata/quorum_fixture.kotoba': LIB / 'test/quorum_fixture.kotoba',
    'hata/authority_fixture.kotoba': LIB / 'test/authority_fixture.kotoba',
    'hata/session_native_test.kotoba': LIB / 'test/session_native.kotoba',
    'ed25519/selfhost.kotoba': LIB.parent / 'org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba',
    'sha2/core.kotoba': LIB.parent / 'gov.nist.sha2/kotoba/sha2/core.kotoba',
    'sha3/core.kotoba': LIB.parent / 'gov.nist.sha3/kotoba/sha3/core.kotoba',
    'mlkem/core.kotoba': LIB.parent / 'gov.nist.mlKem/kotoba/mlkem/core.kotoba',
    'mldsa/core.kotoba': LIB.parent / 'gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
    'x25519/field.kotoba': LIB.parent / 'org.ietf.x25519/kotoba/x25519/field.kotoba',
    'x25519/core.kotoba': LIB.parent / 'org.ietf.x25519/kotoba/x25519/core.kotoba',
    **{f'chacha20/{n}.kotoba': LIB.parent / f'org.ietf.chacha20Poly1305/kotoba/chacha20/{n}.kotoba'
       for n in ['core', 'poly1305', 'aead', 'aead_params']},
    **{f'noise/{n}.kotoba': LIB.parent / f'kotoba.noise/kotoba/noise/{n}.kotoba' for n in ['native', 'identity', 'frame', 'tcp']},
}

def closure(entry):
    by_ns = {}
    for name, path in CANDIDATES.items():
        m = re.search(rb'\(ns ([a-z0-9.-]+)', path.read_bytes())
        by_ns[m[1].decode()] = name
    todo, seen = [entry], set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for ns in re.findall(rb'\[([a-z0-9.-]+) :as ', CANDIDATES[name].read_bytes()):
            todo.append(by_ns[ns.decode()])
    return {n: CANDIDATES[n].read_bytes() for n in sorted(seen)}

NET = '35,38,43,44,45,46,47'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--compiler-sha256', help='refuse a compiler image with another digest')
    p.add_argument('--runner-source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    actual = hashlib.sha256(a.compiler.read_bytes()).hexdigest()
    assert a.compiler_sha256 in (None, actual), ('compiler digest', actual)
    a.compiler_sha256 = actual
    gate = PQ.LinuxArm(a)
    broker = gate.build('broker', 'hata/broker_native_test.kotoba', BR.sources(True))
    session = gate.build('session', 'hata/session_native_test.kotoba', closure('hata/session_native_test.kotoba'))

    def env(**grants):
        return gate.env(KEXE_STRUCTURED_REPORT='1', KEXE_ALLOW=NET, KEXE_FUEL='100000000000', **grants)
    def result(stdout):
        m = re.search(rb':result (-?[0-9]+)', stdout)
        return int(m[1]) if m else None
    def run(label, image, args, expected, **grants):
        r = gate.call(label, [image, *args], env(**grants))
        got = result(r.stdout)
        gate.observations[-1]['result'] = got
        if label.endswith('-ask'):
            print(label, 'took', gate.observations[-1].get('seconds'), flush=True)
        assert got == expected, (label, r.returncode, got, r.stdout[-300:], r.stderr[-300:])
        return got
    def exchange(label, mode, index, port, want_ask, want_serve, serve='serve-vote'):
        addr = f'127.0.0.1:{port}'
        node = gate.out / f'node{index}'
        server = subprocess.Popen([str(session), serve, str(node), addr, str(index)], cwd=gate.out,
                                  env=env(KEXE_CAP_RESOURCES_43=addr), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)
        try:
            run(f'{label}-ask', session, [mode, str(coordinator), addr, str(index)], want_ask, KEXE_CAP_RESOURCES_45=addr)
        finally:
            out, err = server.communicate(timeout=600)
        (gate.out / f'{label}-serve.stdout').write_bytes(out); (gate.out / f'{label}-serve.stderr').write_bytes(err)
        got = result(out)
        gate.observations.append(dict(name=f'{label}-serve', exit=server.returncode, result=got))
        print(f'{label}-serve', server.returncode, got, flush=True)
        assert (got == want_serve) if want_serve is not None else (got is None or got < 0), (label, server.returncode, got, err[-300:])

    coordinator = gate.out / 'coordinator'
    for d in [coordinator] + [gate.out / f'node{i}' for i in range(4)]:
        d.mkdir(mode=0o700)
    run('prepare', broker, ['prepare', str(coordinator), ''], 1)
    for i in range(4):
        run(f'create-{i}', broker, ['replica-create', str(gate.out / f'node{i}'), str(i)], 3)
    for i in range(3):
        exchange(f'vote-{i}', 'ask-vote', i, 47200 + i, 1, 1)
    run('certificate-from-session-votes', broker, ['certificate', str(coordinator), ''], 1)
    # a second session per replica: commit at sequence 0, attest at sequence 1
    for i in range(3):
        exchange(f'commit-attest-{i}', 'ask-commit-attest', i, 47220 + i, 1, 1, serve='serve-commit-attest')
    run('fresh-read-from-session-attestations', broker, ['fresh', str(coordinator), ''], 1)
    # controls, against replica 3: they must not produce a vote
    exchange('wrong-identity-refused', 'ask-wrong', 3, 47210, -31, None)
    exchange('replayed-request-refused', 'ask-replay', 3, 47211, -33, None)
    assert not (coordinator / 'vote3').exists(), 'a control produced a vote'
    # the commit replayed where the attest belongs: the replica's sequence check refuses it
    (gate.out / 'node3' / 'request').write_bytes((coordinator / 'request').read_bytes())
    exchange('replayed-commit-refused', 'ask-commit-replay', 3, 47230, -55, None, serve='serve-commit-attest')
    assert not (coordinator / 'att3').exists(), 'a control produced an attestation'
    # unauthenticated peers against a guarded listener (replica 3): each failed handshake
    # is closed within the 10 s read deadline and costs one unit of the listener's budget
    def peer(port, kind):
        s = socket.create_connection(('127.0.0.1', port), timeout=30)
        t0 = time.monotonic()
        if kind == 'garbage':
            s.sendall(b'\x00\x10' + bytes(range(16)))
        elif kind == 'truncated':
            s.sendall(b'\x03\xe8' + b'x' * 10)
        try:
            while s.recv(65536):
                pass
        except ConnectionResetError:
            pass
        s.close()
        took = time.monotonic() - t0
        gate.observations.append(dict(name=f'unauthenticated-{kind}', closed_after_s=round(took, 2)))
        print(f'unauthenticated-{kind} closed after {took:.2f}s', flush=True)
        assert took < 20, (kind, took)
    def guarded(label, port, budget, attacks, want_ask, want_serve):
        addr = f'127.0.0.1:{port}'
        server = subprocess.Popen([str(session), 'serve-guarded', str(gate.out / 'node3'), addr, '3', str(budget)],
                                  cwd=gate.out, env=env(KEXE_CAP_RESOURCES_43=addr),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)
        try:
            for kind in attacks:
                if kind == 'wrong-identity':
                    run(f'{label}-wrong-identity', session, ['ask-wrong', str(coordinator), addr, '3'], -31,
                        KEXE_CAP_RESOURCES_45=addr)
                else:
                    peer(port, kind)
            time.sleep(0.3)
            run(f'{label}-ask', session, ['ask-vote', str(coordinator), addr, '3'], want_ask, KEXE_CAP_RESOURCES_45=addr)
        finally:
            out, err = server.communicate(timeout=600)
            (gate.out / f'{label}-serve.stdout').write_bytes(out); (gate.out / f'{label}-serve.stderr').write_bytes(err)
            print(f'{label}-serve output', out[-200:], err[-200:], flush=True)
        got = result(out)
        gate.observations.append(dict(name=f'{label}-serve', exit=server.returncode, result=got))
        print(f'{label}-serve', server.returncode, got, flush=True)
        assert got == want_serve, (label, server.returncode, got, err[-300:])
    attacks = ['silent', 'garbage', 'truncated', 'wrong-identity']
    # replica 3 already committed this request in the replayed-commit control, so its
    # answer is 12 (not the next position): that answer, bound to the request id, is the vote
    guarded('guarded-vote', 47240, 5, attacks, 12, 12)
    assert (coordinator / 'vote3').exists(), 'the guarded listener gave no vote'
    (coordinator / 'vote3').unlink()
    # failures up to the budget (3): the listener stops before any vote
    guarded('guarded-budget-exhausted', 47241, 3, attacks[:3], -31, -62)
    assert not (coordinator / 'vote3').exists(), 'an exhausted listener produced a vote'
    # The effect: the sink installs the certified fence, the coordinator reserves a claim
    # whose votes and commits travel over sessions too, and the claim is executed over a
    # session. The sink takes entry, certificate, command and body only from the session;
    # broker/execute re-checks them right there, before it dispatches.
    sink = gate.out / 'sink'
    sink.mkdir(mode=0o700)
    for name in ['request', 'certificate']:
        shutil.copyfile(coordinator / name, sink / name)
    run('sink-install-fence', broker, ['install', str(sink), ''], 1)
    for name in ['request', 'certificate']:
        (sink / name).unlink()
    run('reserve-claim', broker, ['reserve', str(coordinator), ''], 1)
    for i in range(3):
        exchange(f'claim-vote-{i}', 'ask-vote', i, 47250 + i, 1, 1)
    run('claim-certificate-from-session-votes', broker, ['certificate', str(coordinator), ''], 1)
    for i in range(3):
        exchange(f'claim-commit-attest-{i}', 'ask-commit-attest', i, 47260 + i, 1, 1, serve='serve-commit-attest')
    def execute(label, mode, port, want):
        addr = f'127.0.0.1:{port}'
        server = subprocess.Popen([str(session), 'serve-execute', str(sink), addr], cwd=gate.out,
                                  env=env(KEXE_CAP_RESOURCES_43=addr), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)
        try:
            run(f'{label}-ask', session, [mode, str(coordinator), addr], want, KEXE_CAP_RESOURCES_45=addr)
        finally:
            out, err = server.communicate(timeout=600)
            (gate.out / f'{label}-serve.stdout').write_bytes(out); (gate.out / f'{label}-serve.stderr').write_bytes(err)
        got = result(out)
        gate.observations.append(dict(name=f'{label}-serve', exit=server.returncode, result=got))
        print(f'{label}-serve', server.returncode, got, flush=True)
        assert got == want, (label, server.returncode, got, err[-300:])
    # a body other than the committed one: refused at dispatch, and nothing is consumed
    execute('execute-tampered-body-refused', 'ask-execute-tampered', 47270, 0)
    run('no-object-after-refusal', broker, ['empty-object', str(sink), ''], 1)
    execute('execute-over-session', 'ask-execute', 47271, 1)
    execute('execute-duplicate-no-second-effect', 'ask-execute', 47272, 2)
    run('object-after-session-execute', broker, ['object', str(sink), ''], 1)
    gate.finish('PASS_NATIVE_BROKER_SESSIONS', replicas=3, controls=6, effects=1)

if __name__ == '__main__':
    main()
