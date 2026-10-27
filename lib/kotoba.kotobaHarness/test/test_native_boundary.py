import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('controls', ROOT / 'bin/native-controls.py')
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


class NativeBoundary(unittest.TestCase):
    def invoke(self, args, extra=None):
        env = {k: v for k, v in os.environ.items() if k not in ('NBB', 'KOTOBA_BIN', 'KOTOBA_BROWSER_HOST')}
        env.update(extra or {})
        return subprocess.run([str(ROOT / 'bin/kotoba-harness'), *args], capture_output=True, text=True, env=env)

    def test_unported_jev_refuses_before_credential_or_compiler_access(self):
        with tempfile.TemporaryDirectory() as directory:
            trap = Path(directory) / 'called'
            for name in ('java', 'clojure', 'nbb', 'node', 'kotoba', 'kotoba-clj', 'security'):
                path = Path(directory) / name
                path.write_text(f'#!/bin/sh\ntouch "{trap}"\nexit 99\n')
                path.chmod(0o755)
            r = self.invoke([str(ROOT / 'projects/kotoba.edn'), 'jev'],
                            dict(PATH=directory + os.pathsep + os.environ['PATH'],
                                 KOTOBA_HARNESS_KEYCHAIN_SERVICE='should-not-be-read'))
            self.assertEqual(r.returncode, 78, r.stderr)
            self.assertFalse(trap.exists(), 'retired executable or credential lookup invoked')

    def test_missing_native_root_never_tries_path_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            trap = Path(directory) / 'called'
            for name in ('kotoba', 'nbb', 'java', 'node'):
                path = Path(directory) / name
                path.write_text(f'#!/bin/sh\ntouch "{trap}"\nexit 99\n')
                path.chmod(0o755)
            r = self.invoke([str(ROOT / 'projects/kotoba.edn'), 'known'],
                            dict(PATH=directory + os.pathsep + os.environ['PATH'], KOTOBA_AMU_ROOT=directory))
            self.assertEqual(r.returncode, 78, r.stderr)
            self.assertFalse(trap.exists(), 'missing native compiler triggered fallback')

    def test_obsolete_configuration_is_refused(self):
        for key in ('NBB', 'KOTOBA_BIN', 'KOTOBA_BROWSER_HOST'):
            r = self.invoke([str(ROOT / 'projects/kotoba.edn'), 'known'], {key: '/not/an/allowed/entry'})
            self.assertEqual(r.returncode, 78)
            self.assertIn('retired configuration', r.stderr)

    def test_modified_project_does_not_select_stale_control(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project.edn'
            project.write_text((ROOT / 'projects/kotoba.edn').read_text() + '\n; changed\n')
            r = self.invoke([str(project), 'known'])
            self.assertEqual(r.returncode, 78)
            self.assertIn('not a pinned control', r.stderr)

    def test_corrupt_compiler_pin_stops_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            compiler = Path(directory) / 'compiler'
            compiler.write_bytes(b'corrupted')
            with patch.object(controls.subprocess, 'run') as run:
                with self.assertRaises(controls.Blocked):
                    controls.pinned(compiler, dict(bytes=9, sha256='0' * 64))
                run.assert_not_called()

    def test_compiler_failure_is_blocked_instead_of_model_rejection(self):
        entry = json.loads(controls.MANIFEST.read_text())['cases']['kotoba']['controls']['known']
        cfg = dict(container=False, compiler=Path('/native/compiler'), pin={}, target='aarch64-linux')
        with tempfile.TemporaryDirectory() as directory:
            failed = subprocess.CompletedProcess([], 1, '', 'resource limit setup failed')
            with patch.object(controls.subprocess, 'run', return_value=failed) as run:
                receipt = controls.run_control(cfg, 'kotoba', 'known', entry, Path(directory))
            self.assertEqual(run.call_count, 1, 'failure must not trigger another compiler')
            self.assertEqual(receipt['status'], 'blocked')
            self.assertNotIn('failures', receipt)

    def test_verdict_signal_after_success_output_is_blocked(self):
        entry = json.loads(controls.MANIFEST.read_text())['cases']['kotoba']['controls']['known']
        host = SimpleNamespace(
            run_modules=lambda *args, **kwargs: ({'product': 'test'}, {'kotoba': {'wasmTrap': None}}),
            observe=lambda line: {'status': 'ok', 'exit': 0, 'result': 0})
        cfg = dict(container=False, compiler=Path('/native/compiler'), pin={},
                   target='aarch64-linux', host=host, browser='test', host_sha256='test')
        def process(argv, **kwargs):
            if argv[0] == '/native/compiler':
                if '--output' in argv:
                    Path(argv[argv.index('--output') + 1]).write_bytes(b'test artifact')
                return subprocess.CompletedProcess(argv, 0, '', '')
            if argv[1:] == ['selftest']:
                return subprocess.CompletedProcess(argv, 0, 'selftest-verified', '')
            return subprocess.CompletedProcess(argv, -9, 'verified', 'killed after write')
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(controls.subprocess, 'run', side_effect=process):
                receipt = controls.run_control(cfg, 'kotoba', 'known', entry, Path(directory))
            self.assertEqual(receipt['status'], 'blocked')
            self.assertFalse(receipt['control_passed'])
            self.assertEqual(receipt['verdict']['exit'], -9)
            self.assertEqual(receipt['verdict']['stdout'], 'verified')

    def test_single_control_requires_successful_native_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            interrupted = {'status': 'verified', 'control_passed': False}
            with patch.object(controls, 'environment', return_value={}), \
                 patch.object(controls, 'run_control', return_value=interrupted):
                status = controls.main([str(ROOT / 'projects/kotoba.edn'), 'known', directory])
            self.assertEqual(status, 1)

    def test_retired_corpus_is_preserved_and_has_no_active_launch_files(self):
        archive = ROOT / 'docs/retired/hosted-harness-20261027'
        ledger = json.loads((archive / 'manifest.json').read_text())
        for path, digest in ledger['sha256'].items():
            preserved = archive / (path + '.txt')
            self.assertEqual(hashlib.sha256(preserved.read_bytes()).hexdigest(), digest, path)
            self.assertEqual(preserved.stat().st_mode & 0o111, 0)
        for path in ('package.json', 'bin/run-wasm.mjs'):
            self.assertFalse((ROOT / path).exists(), path)
        self.assertFalse(list(ROOT.rglob('*.cljs')))
        self.assertFalse(list((ROOT / 'src').rglob('*.cljk')))
        self.assertEqual((ROOT / 'deps.edn').read_text(), '{:paths ["src"]}\n')

    def test_import_source_pins_survive_destination_relocations(self):
        archive = ROOT / 'docs/retired/hosted-harness-20261027'
        before = json.loads((archive / 'imports.json.txt').read_text())
        after = json.loads((ROOT / 'imports.json').read_text())
        changes = json.loads((ROOT / 'local-changes.json').read_text())
        for old_origin, new_origin in zip(before['imports'], after['imports'], strict=True):
            self.assertEqual({k:v for k,v in old_origin.items() if k != 'files'},
                             {k:v for k,v in new_origin.items() if k != 'files'})
            for old, new in zip(old_origin['files'], new_origin['files'], strict=True):
                self.assertEqual({k:v for k,v in old.items() if k != 'path'},
                                 {k:v for k,v in new.items() if k != 'path'})
                record = changes['files'].get(new['path'])
                if record:
                    self.assertEqual(record['imported-sha256'], old['sha256'])
                expected = record['sha256'] if record else old['sha256']
                self.assertEqual(hashlib.sha256((ROOT / new['path']).read_bytes()).hexdigest(), expected)
        for path, record in changes['added'].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), record['sha256'], path)


if __name__ == '__main__':
    unittest.main()
