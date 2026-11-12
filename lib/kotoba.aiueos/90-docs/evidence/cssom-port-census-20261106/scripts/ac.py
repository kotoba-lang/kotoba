#!/usr/bin/env python3
"""Run the native Amu seed compiler with DIR as FD3 file root: ac.py DIR ARGS...  (same driver shape as JUN-855 compiler/ac.py)"""
import os, subprocess, sys
C = os.environ.get('AMU_FULL_ROOT', '/Users/junkawasaki/github/wt/claude/amu-merged/seed/bootstrap/aarch64-macos/amu-full-root.macho')
d = sys.argv[1]
fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
if fd != 3:
    os.dup2(fd, 3)
env = {"PATH": "/usr/bin:/bin", "LANG": "C", "TMPDIR": d, "TMP": d, "TEMP": d}
r = subprocess.run([C, *sys.argv[2:]], cwd=d, env=env, pass_fds=(3,), capture_output=True)
sys.stdout.write(r.stdout.decode(errors="replace")); sys.stderr.write(r.stderr.decode(errors="replace"))
print("exit=%d" % r.returncode)
