#!/usr/bin/env python3
"""Re-measure the :browser-component floor: how far the Browser/CSSOM graph gets through the kernel target of a given amu.

  python3 os/aiueos/scripts/measure-browser-component.py --amu <amu checkout with node_modules> --root <org dir, e.g. ~/github/kotoba-lang>
                                                         --work <scratch dir> [--entry browser/surface.cljk] [--target x86_64-aiueos-kernel-v1]

It builds a scratch source root by COPYING (the module linker refuses symlinks that escape the source path) the sources of browser, cssom,
text and dom-gpu, replaces the host-regex `kotoba.lang.text` and `kotoba.string` with their guest twins from kotoba-lang/lang/compat (the
twins exist for this route), adds each module the linker reports missing from the compat trees, locks the graph, and compiles it for the
target. It prints the first wall and a count of host regex literals in the modules that remain. Nothing in the source repos is touched.
"""
import argparse, glob, os, re, shutil, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("--amu", required=True)
ap.add_argument("--root", required=True)
ap.add_argument("--work", required=True)
ap.add_argument("--entry", default="browser/surface.cljk")
ap.add_argument("--target", default="x86_64-aiueos-kernel-v1")
a = ap.parse_args()
amu = os.path.join(a.amu, "bin", "amu")
src, blocks = os.path.join(a.work, "src"), os.path.join(a.work, "blocks")
shutil.rmtree(a.work, ignore_errors=True)
os.makedirs(src)
for r in ("browser", "cssom", "text", "dom-gpu"):
    shutil.copytree(os.path.join(a.root, r, "src"), src, dirs_exist_ok=True)
compat = os.path.join(a.root, "kotoba-lang", "lang", "compat")
for rel, drop in (("kotoba/lang/text.kotoba", "kotoba/lang/text.cljk"), ("kotoba/string.kotoba", "kotoba/string.cljk")):
    if os.path.exists(os.path.join(src, drop)): os.remove(os.path.join(src, drop))
    shutil.copy(os.path.join(compat, rel), os.path.join(src, rel))

def find(mod):
    rel = mod.replace(".", "/")
    for r in (compat, os.path.join(a.root, "kotoba-lang", "lang")) + tuple(glob.glob(os.path.join(a.root, "*", "src"))):
        for ext in (".kotoba", ".cljk", ".cljc"):
            p = os.path.join(r, rel + ext)
            if os.path.exists(p): return p, rel + ext
    return None, None

entry = os.path.join(src, a.entry)
for _ in range(80):
    shutil.rmtree(blocks, ignore_errors=True); os.makedirs(blocks)
    r = subprocess.run([amu, "module-lock", entry, "--source-path", src, "--blocks", blocks], capture_output=True, text=True)
    out = r.stdout + r.stderr
    if r.returncode == 0: break
    m = re.search(r"required module (\S+) is missing", out)
    if not m: print("LOCK-WALL", out[:600]); sys.exit(2)
    p, rel = find(m.group(1))
    if not p: print("LOCK-WALL module not found:", m.group(1)); sys.exit(3)
    os.makedirs(os.path.dirname(os.path.join(src, rel)), exist_ok=True)
    shutil.copy(p, os.path.join(src, rel)); print("added", m.group(1), "<-", os.path.relpath(p, a.root))
lock = os.path.join(os.path.dirname(entry), "kotoba.modules.edn")
mods = re.findall(r"([a-z][\w.\-]*) \"bafk", open(lock).read())
print("graph:", ", ".join(mods))
r = subprocess.run([amu, "compile", "--module-lock", lock, "--blocks", blocks, "--target", a.target, "--output", os.path.join(a.work, "out.o")],
                   capture_output=True, text=True)
print("COMPILE rc=%d" % r.returncode)
print((r.stdout + r.stderr)[-700:])
for m in mods:
    for ext in (".cljk", ".cljc", ".kotoba"):
        p = os.path.join(src, m.replace(".", "/").replace("-", "_") + ext)
        if os.path.exists(p):
            print("host regex literals in %-22s %d" % (m, open(p).read().count('#"'))); break
