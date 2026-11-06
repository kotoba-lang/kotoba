#!/usr/bin/env python3
"""Compile every probes/*.kotoba and prototype/*_user.kotoba with the pinned Amu seed compiler for the AIUEOS targets, and
`amu check` them on the host, and write probe-results.tsv. usage: run_probes.py OUT.tsv
Needs: AMU_FULL_ROOT (amu-full-root.macho) and AMU_CLI (amu-cli.macho); defaults are the amu-merged checkout used for the census."""
import os, subprocess, sys, tempfile, shutil, hashlib, csv
HERE = os.path.dirname(os.path.abspath(__file__)); EV = os.path.dirname(HERE)
C = os.environ.get('AMU_FULL_ROOT', '/Users/junkawasaki/github/wt/claude/amu-merged/seed/bootstrap/aarch64-macos/amu-full-root.macho')
CLI = os.environ.get('AMU_CLI', '/Users/junkawasaki/github/wt/claude/amu-merged/seed/bootstrap/aarch64-macos/amu-cli.macho')
TARGETS = ['x86_64-aiueos-user-v1', 'x86_64-aiueos-user-v2', 'x86_64-aiueos-user-v5', 'x86_64-aiueos-kernel-v1']
def compile_one(d, name, target):
    out = 'o_%s_%s' % (name.replace('.kotoba', ''), target)
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    if fd != 3: os.dup2(fd, 3)
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'TMPDIR': d, 'TMP': d, 'TEMP': d}
    r = subprocess.run([C, 'compile', name, '--target', target, '--output', out], cwd=d, env=env, pass_fds=(3,), capture_output=True, timeout=300)
    txt = (r.stdout + r.stderr).decode(errors='replace').strip().replace('\n', ' | ')
    os.close(fd) if fd != 3 else None
    return r.returncode, txt
rows = []
tmp = tempfile.mkdtemp(prefix='probe-')
files = sorted(os.path.join(EV, 'probes', f) for f in os.listdir(os.path.join(EV, 'probes')) if f.endswith('.kotoba'))
files += [os.path.join(EV, 'prototype', f) for f in ('block_width_q6_user.kotoba', 'px_parse_q6_user.kotoba')]
for p in files:
    name = os.path.basename(p); shutil.copy(p, os.path.join(tmp, name))
    ck = subprocess.run([CLI, 'check', os.path.join(tmp, name)], capture_output=True, timeout=120)
    host = (ck.stdout + ck.stderr).decode(errors='replace').strip().split('\n')[0][:120]
    for t in TARGETS:
        rc, txt = compile_one(tmp, name, t)
        rows.append((os.path.relpath(p, EV), t, 'ok' if rc == 0 else 'refused', txt[:200], host))
with open(sys.argv[1], 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t'); w.writerow(['source', 'target', 'verdict', 'compiler_output', 'amu_check_host_first_line'])
    w.writerows(rows)
print(len(rows), 'rows')
