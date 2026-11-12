#!/usr/bin/env python3
"""Compile + run a native test with a source-lock, like lib/kotoba.html/scripts/check-*-native-macos.py. usage: runnative.py OUTDIR ENTRY name=path ..."""
import hashlib, subprocess, sys, os
from pathlib import Path
AMU = Path(os.environ.get('AMU_CLI', '/Users/junkawasaki/github/wt/claude/amu-merged/seed/bootstrap/aarch64-macos/amu-cli.macho'))
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
entry = Path(sys.argv[2]).resolve()
mods = dict(a.split('=', 1) for a in sys.argv[3:])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
lock = out / (entry.stem + '.ksl')
import re
nsname = re.search(r'\(ns\s+([^\s\)]+)', entry.read_text()).group(1)
mods[nsname] = str(entry)
paths = {n: Path(p).resolve() for n, p in mods.items()}
lock.write_text('KSL2\nentry ' + str(entry) + '\n' + ''.join('module %s %s\n' % (n, p) for n, p in sorted(paths.items())) +
                ''.join('file %s %s\n' % (sha(p), p) for p in sorted(set(list(paths.values()) + [entry]))))
env = {'PATH': '/nonexistent', 'LANG': 'C'}
binary = out / entry.stem
b = subprocess.run([str(AMU), 'compile', str(entry), '--source-lock', str(lock), '-o', str(binary)], env=env, capture_output=True, timeout=300)
print('compile rc=%d stderr=%r' % (b.returncode, b.stderr[-300:]))
if b.returncode == 0:
    r = subprocess.run([str(binary)], env=env, capture_output=True, timeout=120)
    print('run rc=%d stdout=%r stderr=%r' % (r.returncode, r.stdout, r.stderr[-200:]))
