#!/usr/bin/env python3
"""Observe native broker/quorum decisions; only stage/transport process bytes."""
import argparse
import shutil
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from native_gate import LIB, NativeGate

def sources(integration=False, read=False, audit=False):
    # Exact declared closure; never infer/resolve/flatten the guest language.
    mapping = {f'hata/{n}.kotoba': LIB / f'src/hata/{n}.kotoba'
               for n in ['codec', 'admission', 'authority', 'quorum']}
    mapping.update({f'hata/{n}.kotoba': LIB / f'test/{f}.kotoba' for n,f in [
        ('authority_fixture','authority_fixture'), ('quorum_fixture','quorum_fixture'),
        ('quorum_native_test','quorum_native')]})
    mapping.update({
        'ed25519/selfhost.kotoba': LIB.parent / 'org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba',
        'sha2/core.kotoba': LIB.parent / 'gov.nist.sha2/kotoba/sha2/core.kotoba',
        'kototama/effect_origins.kotoba': LIB.parent / 'kotoba.kototama/src/kototama/effect_origins.kotoba',
    })
    if read:
        # Fresh read (AWAI-103): pure verdicts, no filesystem capability.
        mapping.pop('hata/quorum_native_test.kotoba')
        mapping.pop('kototama/effect_origins.kotoba')
        mapping.update({'hata/read.kotoba': LIB / 'src/hata/read.kotoba',
                        'hata/read_native_test.kotoba': LIB / 'test/read_native.kotoba'})
    if audit:
        # Audit history (AWAI-106): pure verdicts, no filesystem capability.
        mapping.pop('hata/quorum_native_test.kotoba')
        mapping.pop('kototama/effect_origins.kotoba')
        mapping.update({'hata/audit.kotoba': LIB / 'src/hata/audit.kotoba',
                        'hata/audit_native_test.kotoba': LIB / 'test/audit_native.kotoba'})
    if integration:
        mapping.pop('hata/quorum_native_test.kotoba')
        mapping['hata/read.kotoba'] = LIB / 'src/hata/read.kotoba'
        mapping['hata/audit.kotoba'] = LIB / 'src/hata/audit.kotoba'
        mapping.update({f'hata/{n}.kotoba': LIB / f'src/hata/{n}.kotoba'
                        for n in ['seal', 'replica', 'store_io', 'store', 'broker']})
        mapping.update({'hata/broker_fixture.kotoba': LIB / 'test/broker_fixture.kotoba',
                        'hata/broker_native_test.kotoba': LIB / 'test/broker_native.kotoba'})
    return {name: path.read_bytes() for name,path in mapping.items()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--runner', type=Path, help='Linux: the native runner')
    parser.add_argument('--packager', type=Path, help='macOS: the Mac packager (JUN-593)')
    parser.add_argument('--packager-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gate = NativeGate(args)
    image = gate.build('quorum', 'hata/quorum_native_test.kotoba', sources())
    gate.run('quorum-and-existing-admission', image)
    auditor = gate.build('audit', 'hata/audit_native_test.kotoba', sources(audit=True))
    gate.run('audit-history-verdicts', auditor)
    # Negative control: an auditor that does not check the parent link accepts a
    # history whose entries are certified but not chained.
    unchained = sources(audit=True)
    before = b'(c/equal? (c/slice desc 4 4) prev)'
    assert unchained['hata/audit.kotoba'].count(before) == 1
    unchained['hata/audit.kotoba'] = unchained['hata/audit.kotoba'].replace(before, b'true')
    gate.run('unchained-auditor-detected', gate.build('audit-unchained-control', 'hata/audit_native_test.kotoba', unchained), 4004)
    reader = gate.build('read', 'hata/read_native_test.kotoba', sources(read=True))
    gate.run('fresh-read-verdicts', reader)
    # Negative control: a reader that ignores pending votes adopts the stale
    # committed head instead of recovering the undistributed certificate.
    blind = sources(read=True)
    before = b'votes (if (= (vector-count best) 0) (vector-i64) (votes-for batch offs top best))'
    assert blind['hata/read.kotoba'].count(before) == 1
    blind['hata/read.kotoba'] = blind['hata/read.kotoba'].replace(before, b'votes (vector-i64)')
    gate.run('pending-blind-reader-detected', gate.build('read-blind-control', 'hata/read_native_test.kotoba', blind), 3003)
    driver = gate.build('broker', 'hata/broker_native_test.kotoba', sources(True))
    coordinator = gate.out / 'coordinator'
    sink = gate.out / 'sink'
    nodes = [gate.out / ('replica' + str(i)) for i in range(4)]
    for directory in [coordinator, sink, *nodes]:
        directory.mkdir(mode=0o700)
    def run(label, mode, base, expected=1, option=''):
        return gate.run(label, driver, expected, [mode, base, option], '35,38', base)
    def copy(source, target, names):
        for name in names:
            shutil.copyfile(source / name, target / name)
    def fresh(label, indices, expected, stale=()):
        # The coordinator receives attestations as opaque bytes; only the
        # native guest signs, verifies and decides.
        for k, i in enumerate(indices):
            run(f'{label}-attest-{i}', 'attest-stale' if i in stale else 'attest', nodes[i], option=str(i))
            shutil.copyfile(nodes[i] / 'attestation', coordinator / f'att{k}')
        run(label, 'fresh', coordinator, expected)
    def certify(label, coord=None):
        coord = coord or coordinator
        # Opaque byte transport. Only the native guest chooses/verifies votes.
        for i in range(3):
            copy(coord, nodes[i], ['request'])
            run(label + '-vote-' + str(i), 'vote', nodes[i], option=str(i))
            shutil.copyfile(nodes[i] / 'response', coord / ('vote' + str(i)))
            if label == 'fence' and i == 1:
                run('partition-two-votes-refused', 'reject-two', coordinator)
                shutil.copyfile(coordinator / 'request', coordinator / 'original')
                run('conflicting-proposal', 'conflict', coordinator)
                copy(coordinator, nodes[0], ['request'])
                run('restart-cannot-equivocate', 'no-equivocation', nodes[0])
                shutil.copyfile(coordinator / 'original', coordinator / 'request')
                copy(coordinator, nodes[0], ['request'])
                if gate.darwin:
                    process = gate.fd3([driver, 'vote-hold', *gate.guest_args([nodes[0]]), '0'], popen=True)
                else:
                    env = dict(gate.env('35,38', nodes[0]), KEXE_FUEL='100000000000', KEXE_STRUCTURED_REPORT='1')
                    process = subprocess.Popen([str(gate.runner), str(driver), '0', '0', 'x86_64', '35,38',
                                                '--', 'vote-hold', str(nodes[0]), '0'], env=env,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                deadline = time.monotonic() + 60
                try:
                    while not (nodes[0] / 'ready').exists():
                        assert process.poll() is None and time.monotonic() < deadline, 'native vote ACK missing'
                        time.sleep(.01)
                    process.kill()
                    stdout, stderr = process.communicate(timeout=10)
                    assert process.returncode == -signal.SIGKILL
                    (gate.out / 'vote-after-ack-kill.stdout').write_bytes(stdout)
                    (gate.out / 'vote-after-ack-kill.stderr').write_bytes(stderr)
                    gate.observations.append(dict(name='vote-after-durable-ack-SIGKILL', exit=process.returncode))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                run('conflict-after-kill', 'conflict', coordinator)
                copy(coordinator, nodes[0], ['request'])
                run('crash-restart-cannot-equivocate', 'no-equivocation', nodes[0])
                shutil.copyfile(coordinator / 'original', coordinator / 'request')
        if label == 'claim':
            # Votes held, certificate not yet distributed (coordinator may be lost).
            fresh('fresh-qc-undistributed-recovered', [0, 1, 2], 2)
            fresh('fresh-two-votes-unresolved', [0, 1, 3], 3)
            fresh('fresh-stale-attestation-refused', [0, 1, 2], 0, stale=(2,))
        run(label + '-assemble', 'certificate', coord)
        for i in range(4):
            copy(coord, nodes[i], ['request', 'certificate'])
            run(label + '-commit-' + str(i), 'commit', nodes[i], 2, str(i))
            run(label + '-read-' + str(i), 'current', nodes[i], option=str(i))
    run('prepare', 'prepare', coordinator)
    for i in range(4):
        run('create-' + str(i), 'replica-create', nodes[i], 3, str(i))
    certify('fence')
    shutil.copyfile(coordinator / 'certificate', coordinator / 'fence-certificate')
    copy(coordinator, sink, ['request', 'certificate'])
    run('install', 'install', sink)
    run('install-retry', 'install', sink, 2)
    fresh('fresh-committed-fence', [1, 2, 3], 1)
    shutil.copyfile(coordinator / 'latest', gate.out / 'fence-latest')
    shutil.copyfile(coordinator / 'latest', nodes[3] / 'latest')
    run('fresh-value-recovered', 'block', nodes[3])
    run('audit-after-fence', 'audit', nodes[2], option='2')
    run('reserve', 'reserve', coordinator)
    certify('claim')
    copy(coordinator, sink, ['request', 'certificate', 'command'])
    history = gate.out / 'historical-claim'
    history.mkdir(mode=0o700)
    copy(coordinator, history, ['request', 'certificate', 'command'])
    for missing in ['catalog', 'effects', 'intents', 'grants', 'policy', 'available', 'world']:
        run('origin-' + missing, 'deny-origin', sink, 0, missing)
    run('body-mismatch', 'bad-body', sink, 0)
    run('forged-certificate', 'bad-certificate', sink, 0)
    run('empty-before-effect', 'empty-object', sink)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, 'effect-race-' + str(i), 'race-execute', sink, 1, 'race' + str(i))
                   for i in range(2)]
        for future in futures:
            future.result()
    run('one-effect-in-race', 'race-verdict', sink)
    run('duplicate-no-second-effect', 'execute', sink, 2)
    run('read-object', 'object', sink)
    run('expire-object', 'expired-object', sink)
    # Reconciliation is local, but uses the same verified sink receipt bytes.
    copy(sink, coordinator, ['broker.state'])
    run('settle', 'settle', coordinator)
    run('completed', 'completed', coordinator)
    run('publish-completion', 'publish-completion', coordinator)
    certify('completion')
    copy(coordinator, sink, ['request', 'certificate'])
    run('consume-completion-checkpoint', 'checkpoint', sink)
    run('checkpoint-retry', 'checkpoint', sink, 2)
    copy(history, sink, ['request', 'certificate', 'command'])
    run('completed-claim-cannot-reexecute', 'execute', sink, 2)
    run('recover', 'recover', coordinator)
    certify('epoch8-fence')
    copy(coordinator, sink, ['request', 'certificate'])
    run('install-epoch8', 'install', sink, option='epoch8')
    copy(history, sink, ['request', 'certificate', 'command'])
    run('fenced-old-writer', 'execute', sink, 0)
    run('audit-after-history', 'audit', nodes[1], option='1')
    tampered = sorted(nodes[3].glob('quorum-log-*'))[0]
    tampered.write_bytes(tampered.read_bytes().replace(b'awai.quorum.log.v1\n', b'awai.quorum.log.v1\n0', 1))
    run('audit-tampered-record-refused', 'audit', nodes[3], -31, option='3')
    for block in nodes[0].glob('quorum-value-*'):
        block.write_bytes(b'corrupt')
    run('retained-data-corruption-refused', 'corrupt-current', nodes[0])
    shutil.copyfile(gate.out / 'fence-latest', nodes[0] / 'latest')
    run('fresh-corrupt-value-refused', 'block', nodes[0], -21)
    # A second sink is an isolated test fixture, never a production failover
    # replica. It demonstrates conservative abandonment of an unexecuted claim.
    abandoned = gate.out / 'abandoned'
    abandoned.mkdir(mode=0o700)
    # Recover the original fence bytes from the transport fixture.
    shutil.copyfile(coordinator / 'original', abandoned / 'request')
    shutil.copyfile(coordinator / 'fence-certificate', abandoned / 'certificate')
    run('abandon-install', 'install', abandoned)
    copy(history, abandoned, ['request', 'certificate', 'command'])
    run('abandon-expired-no-effect', 'abandon-expired', abandoned, 3)
    run('abandon-terminal-no-replay', 'execute', abandoned, 3)
    run('abandon-object-empty', 'empty-object', abandoned)
    # AWAI-103: a new writer restores the latest certified C0 state from a fresh
    # read and stays inactive until the sink durably holds its epoch fence.
    writer = gate.out / 'writer2'
    writer.mkdir(mode=0o700)
    fresh('restore-read', [1, 2, 3], 1)
    shutil.copyfile(coordinator / 'latest', nodes[1] / 'latest')
    run('restore-fetch-value', 'fetch', nodes[1])
    shutil.copyfile(coordinator / 'latest', writer / 'latest')
    shutil.copyfile(nodes[1] / 'value', writer / 'value')
    run('writer-restore', 'restore', writer, option='epoch8')
    run('writer-restore-twice-refused', 'restore', writer, 2, option='epoch8')
    run('restored-writer-inactive', 'inactive', writer, option='epoch8')
    run('restored-writer-recovers-epoch9', 'recover9', writer, option='epoch8')
    certify('epoch9-fence', writer)
    (writer / 'sinkack').mkdir(mode=0o700)
    run('activate-without-fence-ack-refused', 'activate', writer, 2, option='epoch9')
    shutil.copyfile(sink / 'broker.state', writer / 'sinkack' / 'broker.state')
    run('activate-on-old-fence-refused', 'activate', writer, 2, option='epoch9')
    copy(writer, sink, ['request', 'certificate'])
    run('install-epoch9', 'install', sink, option='epoch9')
    shutil.copyfile(sink / 'broker.state', writer / 'sinkack' / 'broker.state')
    run('activate-after-durable-fence', 'activate', writer, option='epoch9')
    run('activated-writer-not-gated', 'active', writer, option='epoch9')
    copy(history, sink, ['request', 'certificate', 'command'])
    run('epoch8-writer-fenced', 'execute', sink, 0)
    mutant = sources(True)
    source = mutant['hata/replica.kotoba']
    before = b'(if (persist base next (c/slice identity 1 32))\n              (c/append (vector-i64 1)'
    assert source.count(before) == 1
    mutant['hata/replica.kotoba'] = source.replace(before, b'(if true\n              (c/append (vector-i64 1)')
    bypass = gate.build('non-durable-vote-control', 'hata/broker_native_test.kotoba', mutant)
    control = gate.out / 'non-durable-voter'
    control.mkdir(mode=0o700)
    gate.run('control-create', bypass, 3, ['replica-create', control, '0'], '35,38', control)
    shutil.copyfile(coordinator / 'original', control / 'request')
    gate.run('control-first-vote', bypass, 1, ['vote', control, '0'], '35,38', control)
    run('control-conflicting-request', 'conflict', coordinator)
    copy(coordinator, control, ['request'])
    gate.run('non-durable-vote-detected', bypass, -17, ['no-equivocation', control, '0'], '35,38', control)
    gate.finish('PASS_NATIVE_BROKER_QUORUM', distributedHostsQualified=False,
                effectProvider='bounded-managed-object', fixedRoster=4, quorum=3)

if __name__ == '__main__':
    main()
