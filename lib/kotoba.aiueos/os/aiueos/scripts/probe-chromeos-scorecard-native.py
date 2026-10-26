#!/usr/bin/env python3
"""Build and exercise the native scorecard core on macOS without hosted runtimes.

This is a schema/point-ledger probe with native qualification-release RSA
verification and referenced serial-log digest checks. It does not qualify
other evidence, freshness, or hardware.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[3]
GITHUB = next(parent for parent in ROOT.parents if parent.name == 'github')
WORKSPACES = GITHUB / 'workspaces'
SOURCE = ROOT / 'os/aiueos/kotoba/aiueos/chromeos_scorecard.kotoba'
CARD = ROOT / 'os/aiueos/qualification/chromeos-scorecard-v1.edn'
NEGATIVES = {
    'required-weight': (b':weight 3 :required true', b':weight 4 :required true'),
    'duplicate-id': (b'{:id :A2 :category', b'{:id :A1 :category'),
    'missing-receipt': (
        b'"receipt os/aiueos/qualification/receipts/vm-20261024/a1-qmp60/receipt.edn"',
        b'"record os/aiueos/qualification/receipts/vm-20261024/a1-qmp60/receipt.edn"'),
    'owner-unconfirmed': (b':confirmed-by-owner true', b':confirmed-by-owner false'),
    'unknown-category': (b'{:id :A1 :category :boot', b'{:id :A1 :category :bogus'),
    'missing-signed-release-reference': (
        b'"receipt os/aiueos/qualification/receipts/vm-20261025/signed-release/receipt.edn"',
        b'"record os/aiueos/qualification/receipts/vm-20261025/signed-release/receipt.edn"'),
}
RECEIPT_NEGATIVES = ('missing-receipt-file', 'red-verdict',
                     'bad-release-signature-field', 'missing-release-verdict',
                     'tampered-release-json', 'tampered-release-signature',
                     'rehashed-invalid-signature', 'tampered-serial-log',
                     'missing-serial-log', 'tampered-secondary-serial-log',
                     'missing-secondary-serial-log', 'tampered-i3-scale-log',
                     'missing-i3-scale-log', 'tampered-i3-scanout-log',
                     'missing-i3-scanout-log')
A1_RECEIPT = Path('os/aiueos/qualification/receipts/vm-20261024/a1-qmp60/receipt.edn')
SETTINGS_RECEIPT = Path(
    'os/aiueos/qualification/receipts/vm-20261024/settings/receipt.edn')
SIGNED_RELEASE_RECEIPT = Path(
    'os/aiueos/qualification/receipts/vm-20261025/signed-release/receipt.edn')
SIGNED_RELEASE_JSON = SIGNED_RELEASE_RECEIPT.with_name(
    'aiueos-x86_64-build-receipt.json')
SIGNED_RELEASE_SIGNATURE = SIGNED_RELEASE_RECEIPT.with_name(
    'aiueos-x86_64-build-receipt.sig')
I3_RECEIPT = Path(
    'os/aiueos/qualification/receipts/vm-20261026/i3-display-scaling-external/receipt.edn')
# I2 has synthetic battery input and separate sleep-run evidence. The
# remaining rows also lack evidence this native core can fully admit.
UNVERIFIED_ROWS = ('A5', 'C9', 'F2', 'G1', 'G3', 'G5', 'H1', 'H2',
                   'H3', 'I2', 'I6')
EXPECTED_LEDGER = (
    b'AIUEOS_SCORE 53\n'
    b'AIUEOS_CATEGORY boot weight=10 pass=9 gap=1\n'
    b'AIUEOS_CATEGORY identity weight=6 pass=6 gap=0\n'
    b'AIUEOS_CATEGORY shell weight=15 pass=14 gap=1\n'
    b'AIUEOS_CATEGORY input weight=12 pass=9 gap=3\n'
    b'AIUEOS_CATEGORY web weight=20 pass=0 gap=20\n'
    b'AIUEOS_CATEGORY storage weight=9 pass=3 gap=6\n'
    b'AIUEOS_CATEGORY security weight=9 pass=3 gap=6\n'
    b'AIUEOS_CATEGORY update weight=9 pass=1 gap=8\n'
    b'AIUEOS_CATEGORY power weight=10 pass=8 gap=2\n'
)


def admitted_subset(card):
    """Demote only current pass rows without complete native admission."""
    for row_id in UNVERIFIED_ROWS:
        pattern = (rb'(\{:id :' + row_id.encode() +
                   rb'\s(?:(?!\n  \{:id).)*?:status ):pass(?=\s+:qemu-progress)')
        card, count = re.subn(pattern, rb'\1:unachieved', card,
                              count=1, flags=re.S)
        if count != 1:
            raise ValueError(f'unverified row anchor changed: {row_id}')
    return card


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def committed_identity(path):
    git_root = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                                   cwd=ROOT, capture_output=True, timeout=30,
                                   check=True).stdout.decode().strip())
    relative = path.relative_to(git_root)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=git_root,
                            capture_output=True, timeout=30, check=True).stdout.decode().strip()
    checked = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=git_root,
                             capture_output=True, timeout=30, check=False)
    return commit, checked.returncode == 0 and checked.stdout == path.read_bytes()


def run(image, directory, *args, timeout=120):
    """Give a native program only the caller-owned FD3 file root."""
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    saved = None
    relocated = fd != 3
    try:
        if relocated:
            try:
                saved = os.dup(3)
            except OSError:
                pass
            os.dup2(fd, 3)
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'TMPDIR': str(directory),
               'TMP': str(directory), 'TEMP': str(directory)}
        return subprocess.run([str(image), *map(str, args)], cwd=directory,
                              env=env, pass_fds=(3,), capture_output=True,
                              timeout=timeout, check=False)
    finally:
        if relocated:
            if saved is None:
                os.close(3)
            else:
                os.dup2(saved, 3)
                os.close(saved)
        os.close(fd)


def require_image(path, expected_sha):
    if not path.is_file() or digest(path) != expected_sha:
        raise ValueError(f'native image pin mismatch: {path}')
    checked = subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(path)],
                             capture_output=True, timeout=30, check=False)
    if checked.returncode:
        raise ValueError(f'native image signature invalid: {path.name}')


def require_native(result, operation):
    if result.returncode or result.stderr:
        raise ValueError(f'{operation} failed ({result.returncode}): '
                         + result.stderr.decode(errors='replace')[-600:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--packager', type=Path, required=True)
    parser.add_argument('--packager-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='new private directory under github/workspaces')
    args = parser.parse_args()
    compiler, packager = args.compiler.resolve(), args.packager.resolve()
    output = args.output.resolve()
    if output.exists() or not output.parent.is_relative_to(WORKSPACES):
        parser.error('--output must be a new github/workspaces directory')
    require_image(compiler, args.compiler_sha256)
    require_image(packager, args.packager_sha256)
    output.mkdir(parents=True, mode=0o700)
    source = output / 'scorecard.kotoba'
    shutil.copyfile(SOURCE, source)
    source_sha = digest(source)
    canonical_card = CARD.read_bytes()
    original_sha = hashlib.sha256(canonical_card).hexdigest()
    card_bytes = admitted_subset(canonical_card)
    commit, source_at_commit = committed_identity(SOURCE)
    _, card_at_commit = committed_identity(CARD)

    require_native(run(compiler, output, 'compile', source.name, '--target',
                       'aarch64-macos', '--output', 'scorecard.kseed'), 'compile')
    extraction = require_native(run(compiler, output, 'extract-native',
                                    'scorecard.kseed', '--symbol', 'main',
                                    '--output', 'scorecard.raw'), 'extract')
    match = re.search(rb':offset (\d+), :length (\d+)', extraction)
    if match is None or int(match.group(2)) != (output/'scorecard.raw').stat().st_size:
        raise ValueError('native entry extraction mismatch')
    require_native(run(packager, output, 'scorecard-unsigned.macho',
                       'scorecard.raw', 'fs2-cli-stdio-general',
                       match.group(1).decode()), 'package')
    executable = output / 'scorecard.macho'
    shutil.copyfile(output/'scorecard-unsigned.macho', executable)
    executable.chmod(0o755)
    signed = subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-',
                             str(executable)], capture_output=True, timeout=30)
    if signed.returncode:
        raise ValueError('native output signing failed')
    require_image(executable, digest(executable))
    linked = subprocess.run(['/usr/bin/otool', '-L', str(executable)],
                            capture_output=True, timeout=30)
    if linked.returncode or linked.stdout.splitlines() != [f'{executable}:'.encode()]:
        raise ValueError('native output has an undeclared dylib dependency')

    observations = {}
    for name in ('positive', 'canonical-refusal', *NEGATIVES,
                 *RECEIPT_NEGATIVES):
        directory = output / name
        directory.mkdir(mode=0o700)
        target_receipts = directory/'os/aiueos/qualification/receipts'
        target_receipts.parent.mkdir(parents=True)
        shutil.copytree(ROOT/'os/aiueos/qualification/receipts', target_receipts)
        if name == 'positive':
            data = card_bytes
            expected_exit, expected_stdout = 0, EXPECTED_LEDGER
        elif name == 'canonical-refusal':
            data = canonical_card
            expected_exit, expected_stdout = 1, b'AIUEOS_SCORE -1\n'
        elif name in NEGATIVES:
            before, after = NEGATIVES[name]
            if before not in card_bytes:
                raise ValueError(f'negative control anchor missing: {name}')
            data = card_bytes.replace(before, after, 1)
            expected_exit, expected_stdout = 1, b'AIUEOS_SCORE -1\n'
        else:
            data = card_bytes
            expected_exit, expected_stdout = 1, b'AIUEOS_SCORE -1\n'
            target = directory/(
                SIGNED_RELEASE_RECEIPT if name in
                ('bad-release-signature-field', 'missing-release-verdict')
                else SIGNED_RELEASE_JSON if name == 'tampered-release-json'
                else SIGNED_RELEASE_SIGNATURE if name in
                ('tampered-release-signature', 'rehashed-invalid-signature')
                else A1_RECEIPT.with_name('kernel-serial.log') if name in
                ('tampered-serial-log', 'missing-serial-log')
                else SETTINGS_RECEIPT.with_name('kernel-serial.log.boot1') if name in
                ('tampered-secondary-serial-log', 'missing-secondary-serial-log')
                else I3_RECEIPT.with_name('scale-run-serial.log') if name in
                ('tampered-i3-scale-log', 'missing-i3-scale-log')
                else I3_RECEIPT.with_name('scanout-two-run-serial.log') if name in
                ('tampered-i3-scanout-log', 'missing-i3-scanout-log')
                else A1_RECEIPT)
            if name in ('missing-receipt-file', 'missing-serial-log',
                        'missing-secondary-serial-log', 'missing-i3-scale-log',
                        'missing-i3-scanout-log'):
                target.unlink()
            elif name == 'bad-release-signature-field':
                receipt_bytes = target.read_bytes()
                changed, count = re.subn(
                    rb':signature-sha256 "[0-9a-f]{64}"',
                    b':signature-sha256 "invalid"', receipt_bytes, count=1)
                if count != 1:
                    raise ValueError('release signature field anchor missing')
                target.write_bytes(changed)
            elif name == 'missing-release-verdict':
                receipt_bytes = target.read_bytes()
                before = b'"image-bound"'
                if before not in receipt_bytes:
                    raise ValueError('image-bound verdict anchor missing')
                target.write_bytes(receipt_bytes.replace(
                    before, b'"image-unbound"', 1))
            elif name in ('tampered-release-json', 'tampered-release-signature',
                          'tampered-serial-log', 'tampered-secondary-serial-log',
                          'tampered-i3-scale-log', 'tampered-i3-scanout-log'):
                artifact_bytes = target.read_bytes()
                if not artifact_bytes:
                    raise ValueError('release artifact empty')
                target.write_bytes(bytes([artifact_bytes[0] ^ 1]) + artifact_bytes[1:])
            elif name == 'rehashed-invalid-signature':
                artifact_bytes = target.read_bytes()
                if len(artifact_bytes) != 256:
                    raise ValueError('release signature size changed')
                mutated = artifact_bytes[:-1] + bytes([artifact_bytes[-1] ^ 1])
                target.write_bytes(mutated)
                receipt = directory/SIGNED_RELEASE_RECEIPT
                updated, count = re.subn(
                    rb':signature-sha256 "[0-9a-f]{64}"',
                    b':signature-sha256 "' + hashlib.sha256(mutated).hexdigest().encode()
                    + b'"', receipt.read_bytes(), count=1)
                if count != 1:
                    raise ValueError('release signature digest anchor missing')
                receipt.write_bytes(updated)
            else:
                receipt_bytes = target.read_bytes()
                if b':green? true' not in receipt_bytes:
                    raise ValueError('red verdict anchor missing')
                target.write_bytes(receipt_bytes.replace(b':green? true',
                                                         b':green? false', 1))
        (directory/'scorecard.edn').write_bytes(data)
        result = run(executable, directory)
        observations[name] = {'exit': result.returncode,
                              'stdout': result.stdout.decode(errors='replace'),
                              'inputSha256': hashlib.sha256(data).hexdigest()}
        if (result.returncode != expected_exit or result.stdout != expected_stdout
                or result.stderr):
            raise ValueError(f'native scorecard {name} mismatch: {observations[name]}')

    # A different public modulus must reject the same intact receipt and
    # signature. This checks that the native RSA path actually binds the key.
    wrong_dir = output/'wrong-public-modulus'
    wrong_dir.mkdir(mode=0o700)
    original = source.read_bytes()
    key = re.search(rb'\(def MODULUS "([0-9A-F]{512})"\)', original)
    if key is None:
        raise ValueError('native qualification modulus anchor missing')
    modulus = key.group(1)
    altered = modulus[:1] + (b'3' if modulus[1:2] != b'3' else b'2') + modulus[2:]
    wrong_source = wrong_dir/'scorecard-wrong-key.kotoba'
    wrong_source.write_bytes(original.replace(modulus, altered, 1))
    require_native(run(compiler, wrong_dir, 'compile', wrong_source.name,
                       '--target', 'aarch64-macos', '--output', 'wrong.kseed'),
                   'wrong-key compile')
    extraction = require_native(run(compiler, wrong_dir, 'extract-native',
                                    'wrong.kseed', '--symbol', 'main',
                                    '--output', 'wrong.raw'), 'wrong-key extract')
    match = re.search(rb':offset (\d+), :length (\d+)', extraction)
    if match is None or int(match.group(2)) != (wrong_dir/'wrong.raw').stat().st_size:
        raise ValueError('wrong-key entry extraction mismatch')
    require_native(run(packager, wrong_dir, 'wrong-unsigned.macho', 'wrong.raw',
                       'fs2-cli-stdio-general', match.group(1).decode()),
                   'wrong-key package')
    wrong_image = wrong_dir/'wrong.macho'
    shutil.copyfile(wrong_dir/'wrong-unsigned.macho', wrong_image)
    wrong_image.chmod(0o755)
    signed = subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-',
                             str(wrong_image)], capture_output=True, timeout=30)
    if signed.returncode:
        raise ValueError('wrong-key output signing failed')
    result = run(wrong_image, output/'positive')
    observations['wrong-public-modulus'] = {
        'exit': result.returncode,
        'stdout': result.stdout.decode(errors='replace'),
        'sourceSha256': digest(wrong_source)}
    if (result.returncode != 1 or result.stdout != b'AIUEOS_SCORE -1\n'
            or result.stderr):
        raise ValueError('native wrong-key refusal mismatch')

    report = {'schema': 'aiueos.native-scorecard-core-probe.v1',
              'status': 'CORE_SCHEMA_PASS_EVIDENCE_PENDING',
              'sourceCommit': commit, 'sourceAtCommit': source_at_commit,
              'scorecardAtCommit': card_at_commit,
              'sourceSha256': source_sha, 'scorecardSha256': original_sha,
              'admittedSubsetSha256': hashlib.sha256(card_bytes).hexdigest(),
              'diagnosticDemotedRows': UNVERIFIED_ROWS,
              'canonicalAdmitted': False,
              'compilerSha256': digest(compiler), 'packagerSha256': digest(packager),
              'executableSha256': digest(executable),
              'observations': observations,
              'receiptFieldsVerified': True, 'evidenceArtifactsVerified': False,
              'referencedReceiptSerialDigestsVerified': True,
              'signedReleaseReceiptFileDigestsVerified': True,
              'qualificationReleaseSignatureVerified': True,
              'releaseSignatureVerified': False,
              'evidenceFreshnessVerified': False, 'physicalHardwareQualified': False,
              'linuxJvmNodeExecuted': False}
    (output/'native-scorecard-core.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AIUEOS_CHROMEOS_SCORECARD_CORE_OK', output/'native-scorecard-core.json')


if __name__ == '__main__':
    main()
