#!/usr/bin/env python3
"""Run a fresh Itonami Goal UI probe without VNC or manual guest input."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build_dir', type=Path,
                        help='one complete native desktop local-draft build')
    parser.add_argument('--goal', default='ab',
                        help='lowercase Goal body to enter and verify (default: ab)')
    parser.add_argument('--output', type=Path,
                        help='new private observation directory; defaults beside the build')
    parser.add_argument('--verify-restore', action='store_true',
                        help='also run the isolated F5 save, cold restart and refusal gate')
    args = parser.parse_args()
    build = args.build_dir.resolve()
    if not build.is_dir():
        parser.error('build_dir must be an existing directory')
    if not re.fullmatch(r'[a-z ]{1,51}', args.goal) or not any(c != ' ' for c in args.goal):
        parser.error('--goal must contain 1-51 lowercase letters or spaces, including a letter')
    if args.output is None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        output = build.parent / f'{build.name}-qmp-debug-{stamp}-{os.getpid()}'
    else:
        output = args.output.resolve()
    if output.exists():
        parser.error('observation directory must not exist')
    keys = ['2'] + ['space' if c == ' ' else c for c in args.goal]
    command = [sys.executable,
               str(Path(__file__).with_name('debug-native-desktop-qmp.py')),
               '--build-dir', str(build), '--local-draft',
               '--output', str(output), '--keys', *keys,
               '--expect-focus', '2', '--expect-draft-enabled', '1',
               '--expect-generation', '0', '--expect-restore-code', '0',
               '--expect-commit-code', '0',
               '--expect-goal', 'Goal local:\n'+args.goal,
               '--expect-visible-goal', args.goal]
    result = subprocess.run(command, check=False)
    restore_result = None
    restore_path = output/'restore/native-draft-restart.json'
    if result.returncode == 0 and args.verify_restore:
        qemu_name = shutil.which('qemu-system-x86_64')
        if qemu_name is None:
            parser.error('QEMU not found; cannot verify cold restore')
        qemu = Path(qemu_name).resolve()
        firmware = qemu.parent.parent/'share/qemu/edk2-x86_64-code.fd'
        restore_command = [sys.executable,
                           str(Path(__file__).with_name('check-native-draft-restart-qemu.py')),
                           '--media', str(build/'media/awai-native.img'),
                           '--efi', str(build/'kernel/BOOTX64.EFI'),
                           '--kernel', str(build/'kernel/KERNEL.ELF'),
                           '--font', str(build/'font/aiueos-padded.fnt'),
                           '--qemu', str(qemu), '--firmware', str(firmware),
                           '--output', str(output/'restore')]
        restore_result = subprocess.run(restore_command, check=False)
    report_path = output/'debug.json'
    if report_path.is_file():
        report = json.loads(report_path.read_text())
        restore_passed = (restore_result is not None and
                          restore_result.returncode == 0 and restore_path.is_file() and
                          json.loads(restore_path.read_text())['status'] ==
                          'PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE')
        passed = (result.returncode == 0 and report['status'] == 'PASS' and
                  (not args.verify_restore or restore_passed))
        summary = {'status': 'PASS' if passed else 'FAIL',
                   'goal': args.goal,
                   'output': str(output), 'screenshot': str(output/'desktop.png'),
                   'receipt': str(report_path),
                   'restoreVerified': restore_passed,
                   'restoreReceipt': str(restore_path) if args.verify_restore else None,
                   'vncUsed': report['vncUsed'],
                   'networkUsed': report['networkUsed']}
        print(json.dumps(summary, ensure_ascii=False))
        if not passed:
            return 1
        return 0
    return result.returncode or 1


if __name__ == '__main__':
    sys.exit(main())
