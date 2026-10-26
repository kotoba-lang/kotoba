#!/usr/bin/env python3
"""check-image-route-node-free.py -- measure the Python ports of the two nbb
image-route tools against the nbb originals.

WHAT THIS PROVES. `k16-pure-native-gate.py` and `image-freshness.py` are
ports of `k16-pure-native-gate.cljk` and `image-freshness.cljk`, made so the
accepted build path carries no NBB/Node (JUN-31 acceptance: no C, NBB/Node,
JVM or GraalVM path in the accepted build; Python is orchestration only).
A port nobody measured is a guess, so this harness runs BOTH implementations
over the same fixtures and compares:

  * every scenario's exit code and every marker line (REFUSED / SCANNED /
    AIUEOS_K16_* / UNANSWERED / COULD-NOT-RUN / IMAGE-RECEIPT / IMAGE-FRESH);
  * the gate receipt as an EDN VALUE (receipt text is not byte-comparable --
    cljs pr-str iterates hash maps in hash order, the port in insertion
    order -- but every reader sees the same value);
  * receipts read across implementations: nbb reads the port's receipts
    (clojure.edn / the original tool's `show` and `assert`) and the port
    reads nbb's receipts;
  * that the port completes with `node`/`nbb` absent from PATH.

The nbb side is a dev-time ORACLE only: it is not on the build path. A
machine without nbb records those scenarios as `oracle-absent` -- not a pass.

Usage:  python3 check-image-route-node-free.py --out <receipt.json>
Exit 0 = every measured pair agrees. Exit 1 = a pair disagrees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "os", "aiueos", "scripts")
KOTOBA_DIR = os.path.join(REPO, "os", "aiueos", "kotoba")

GATE_CLJK = os.path.join(SCRIPTS, "k16-pure-native-gate.cljk")
GATE_PY = os.path.join(SCRIPTS, "k16-pure-native-gate.py")
FRESH_CLJK = os.path.join(SCRIPTS, "image-freshness.cljk")
FRESH_PY = os.path.join(SCRIPTS, "image-freshness.py")

AMU_SHA = "9cf3a0ac07a1fb0d735a460230a7e5e9c97bc6a7"  # any hex40; the gate checks shape
TARGET = "x86_64-aiueos-kernel-v1"

MARKER = re.compile(
    r"^(REFUSED|SCANNED|AIUEOS_K16|UNANSWERED|COULD-NOT-RUN|IMAGE-RECEIPT|IMAGE-FRESH)")

SOURCE_OVERRIDES = {
    "ecdsa-p256-public.o": "ecdsa-p256-sign.kotoba",
    "sha256.o": "aiueos/sha256.kotoba",
    "digest-equal.o": "aiueos/digest_equal.kotoba",
}


sys.path.insert(0, SCRIPTS)
from edn_lite import Kw  # noqa: E402


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run(cmd, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    return r.returncode, r.stdout + r.stderr


def markers(text: str, normalize=()) -> list:
    out = []
    for line in text.splitlines():
        if MARKER.match(line):
            for old, new in normalize:
                line = line.replace(old, new)
            out.append(line)
    return out


def edn_quote(s: str) -> str:
    return json.dumps(s)  # EDN strings share JSON's escapes closely enough here


# ------------------------------------------------------------- fixtures ----


def manifest_sources() -> dict:
    """object basename -> its recorded `:source` from the committed
    provenance manifest. Not every object's source is named after it (some
    receipts point at a module under a different basename), so the fixture
    synthesizer needs the recorded names, not a guess."""
    import edn_lite
    v = edn_lite.read_edn(open(os.path.join(KOTOBA_DIR, "provenance.edn")).read())
    objs = v.get(edn_lite.Kw("objects"), v)
    out = {}
    for k, r in objs.items():
        if isinstance(r, dict):
            out[k] = r.get(edn_lite.Kw("source"))
    return out


SOURCES = manifest_sources()


def synthesized_receipt(name: str) -> dict:
    stem = name[:-2]
    if name in SOURCE_OVERRIDES:
        src_rel = "os/aiueos/kotoba/" + SOURCE_OVERRIDES[name]
    elif SOURCES.get(name):
        src_rel = SOURCES[name]
    else:
        src_rel = "os/aiueos/kotoba/" + stem + ".kotoba"
    src = os.path.join(REPO, src_rel)
    obj = os.path.join(KOTOBA_DIR, name)
    sys.path.insert(0, SCRIPTS)
    from edn_lite import Kw
    return {
        Kw("source"): src_rel,
        Kw("source-sha256"): sha256_file(src),
        Kw("object-sha256"): sha256_file(obj),
        Kw("target"): TARGET,
        Kw("compiler"): {Kw("repo"): "kotoba-lang/amu", Kw("sha"): AMU_SHA},
    }


def manifest_text(objects: dict) -> str:
    import edn_lite
    sys.path.insert(0, SCRIPTS)
    body = edn_lite.pr_str({
        edn_lite.Kw("format"): edn_lite.Kw("aiueos.kotoba-object-provenance/v1"),
        edn_lite.Kw("target"): TARGET,
        edn_lite.Kw("objects"): objects,
    })
    return body + "\n"


def write(path: str, text: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def section_table(buf: bytes):
    (shoff,) = struct.unpack_from("<Q", buf, 40)
    (shnum,) = struct.unpack_from("<H", buf, 60)
    out = []
    for i in range(shnum):
        o = shoff + i * 64
        (name_off, stype) = struct.unpack_from("<II", buf, o)
        (offset, size) = struct.unpack_from("<QQ", buf, o + 24)
        (entsize,) = struct.unpack_from("<Q", buf, o + 56)
        out.append({"index": i, "name-off": name_off, "type": stype,
                    "offset": offset, "size": size, "entsize": entsize})
    return out


def shstrtab_offset(buf: bytes) -> int:
    (idx,) = struct.unpack_from("<H", buf, 62)
    return section_table(buf)[idx]["offset"]


def section_named(buf: bytes, nm: str):
    base = shstrtab_offset(buf)
    for s in section_table(buf):
        start = base + s["name-off"]
        end = buf.index(b"\x00", start)
        if buf[start:end].decode("US-ASCII") == nm:
            return s
    raise AssertionError("no section " + nm)


def rename_data_section(buf: bytes) -> bytes:
    copy = bytearray(buf)
    s = section_named(buf, ".data")
    at = shstrtab_offset(buf) + s["name-off"]
    copy[at + 1] = ord("x")  # ".data" -> ".xata"
    return bytes(copy)


def patch_export_to_undef(buf: bytes) -> bytes:
    copy = bytearray(buf)
    symtab = next(s for s in section_table(buf) if s["type"] == 2)
    n = symtab["size"] // 24
    for i in range(n):
        if copy[symtab["offset"] + i * 24 + 4] & 0xFF == 0x12:
            struct.pack_into("<H", copy, symtab["offset"] + i * 24 + 6, 0)
            return bytes(copy)
    raise AssertionError("no GLOBAL FUNC symbol to undefine")


# ------------------------------------------------------------ scenarios ----


class Harness:
    def __init__(self, tmp: str, nbb: str):
        self.tmp = tmp
        self.nbb = nbb
        self.scenarios = []

    def gate_argv(self, tool: str, list_file: str, manifest: str, receipt_out=None):
        argv = [tool, "--link-list", list_file, "--provenance", manifest, "--root", REPO]
        if receipt_out:
            argv += ["--receipt-out", receipt_out]
        return argv

    def both_gate(self, name: str, argv_tail: list, normalize=()) -> dict:
        """Run the same argv through nbb(.cljk) and python3(.py)."""
        res = {"name": name}
        if self.nbb:
            code, text = run([self.nbb, GATE_CLJK] + argv_tail)
            res["oracle"] = {"exit": code, "markers": markers(text, normalize)}
        else:
            res["oracle"] = {"status": "oracle-absent"}
        code, text = run([sys.executable, GATE_PY] + argv_tail)
        res["port"] = {"exit": code, "markers": markers(text, normalize)}
        if self.nbb:
            res["agree"] = (res["oracle"]["exit"] == res["port"]["exit"]
                            and res["oracle"]["markers"] == res["port"]["markers"])
        else:
            res["agree"] = None
        self.scenarios.append(res)
        return res

    def both_fresh(self, name: str, argv_tail_by_tool: dict, normalize=()) -> dict:
        res = {"name": name}
        if self.nbb:
            code, text = run([self.nbb, FRESH_CLJK] + argv_tail_by_tool["cljk"])
            res["oracle"] = {"exit": code, "markers": markers(text, normalize)}
        else:
            res["oracle"] = {"status": "oracle-absent"}
        code, text = run([sys.executable, FRESH_PY] + argv_tail_by_tool["py"])
        res["port"] = {"exit": code, "markers": markers(text, normalize)}
        if self.nbb:
            res["agree"] = (res["oracle"]["exit"] == res["port"]["exit"]
                            and res["oracle"]["markers"] == res["port"]["markers"])
        else:
            res["agree"] = None
        self.scenarios.append(res)
        return res


def gate_scenarios(h: Harness) -> None:
    committed = sorted(f for f in os.listdir(KOTOBA_DIR) if f.endswith(".o"))
    assert committed, "no committed objects"
    d = os.path.join(h.tmp, "gate")
    os.makedirs(d)

    # G1: every committed object with a correct synthesized receipt -> admitted.
    synth = {name: synthesized_receipt(name) for name in committed}
    list_file = write(os.path.join(d, "all.txt"),
                      "\n".join("os/aiueos/kotoba/" + n for n in committed))
    man_ok = write(os.path.join(d, "manifest-ok.edn"), manifest_text(synth))
    h.both_gate("G1-all-committed-admitted",
                ["--link-list", list_file, "--provenance", man_ok, "--root", REPO])

    # G2: empty link list -> UNANSWERED, exit 2.
    empty = write(os.path.join(d, "empty.txt"), "")
    man_empty = write(os.path.join(d, "manifest-empty.edn"), manifest_text({}))
    h.both_gate("G2-empty-link-list-unanswered",
                ["--link-list", empty, "--provenance", man_empty, "--root", REPO])

    # G3: an input that is not on disk -> UNANSWERED, exit 2.
    absent = write(os.path.join(d, "absent.txt"), "os/aiueos/kotoba/there-is-no-such.o\n")
    h.both_gate("G3-link-input-absent",
                ["--link-list", absent, "--provenance", man_empty, "--root", REPO])

    first = committed[0]
    one = write(os.path.join(d, "one.txt"), "os/aiueos/kotoba/" + first + "\n")

    # G4: no receipt for the object -> REFUSED receipt-missing.
    h.both_gate("G4-receipt-missing",
                ["--link-list", one, "--provenance", man_empty, "--root", REPO])

    # G5: receipt digest does not match the bytes -> object-sha256-mismatch.
    bad = synthesized_receipt(first)
    bad[Kw("object-sha256")] = "0" * 64
    man_bad = write(os.path.join(d, "manifest-bad.edn"), manifest_text({first: bad}))
    h.both_gate("G5-object-sha256-mismatch",
                ["--link-list", one, "--provenance", man_bad, "--root", REPO])

    # G6: one st_shndx set to SHN_UNDEF -> undefined-symbol.
    probe = "kernel-probe.o"
    patched = patch_export_to_undef(open(os.path.join(KOTOBA_DIR, probe), "rb").read())
    p6 = os.path.join(d, probe)
    with open(p6, "wb") as f:
        f.write(patched)
    rec6 = synthesized_receipt(probe)
    rec6[Kw("object-sha256")] = hashlib.sha256(patched).hexdigest()
    list6 = write(os.path.join(d, "g6.txt"), p6 + "\n")
    man6 = write(os.path.join(d, "g6.edn"), manifest_text({probe: rec6}))
    h.both_gate("G6-undefined-symbol",
                ["--link-list", list6, "--provenance", man6, "--root", REPO])

    # G7: section set wrong (.data renamed) -> sections.
    patched7 = rename_data_section(open(os.path.join(KOTOBA_DIR, probe), "rb").read())
    p7 = os.path.join(d, "g7", probe)
    os.makedirs(os.path.dirname(p7))
    with open(p7, "wb") as f:
        f.write(patched7)
    rec7 = synthesized_receipt(probe)
    rec7[Kw("object-sha256")] = hashlib.sha256(patched7).hexdigest()
    list7 = write(os.path.join(d, "g7.txt"), p7 + "\n")
    man7 = write(os.path.join(d, "g7.edn"), manifest_text({probe: rec7}))
    h.both_gate("G7-section-set-wrong",
                ["--link-list", list7, "--provenance", man7, "--root", REPO])

    # G8/G9: a real C object (zig cc), first with a receipt that names the .c
    # (c-source), then with a receipt that LIES and claims a .kotoba source
    # (caught by the section set).
    if shutil.which("zig"):
        csrc = os.path.join(REPO, "os", "aiueos", "kernel", "framebuffer.c")
        obj = os.path.join(d, "framebuffer.o")
        zc, zt = run(["zig", "cc", "-target", "x86_64-freestanding-none", "-std=c11",
                      "-O2", "-ffreestanding", "-fno-stack-protector", "-mno-red-zone",
                      "-c", "-o", obj, csrc])
        if zc == 0:
            sha = sha256_file(obj)
            list8 = write(os.path.join(d, "g8.txt"), obj + "\n")
            rec8 = {Kw("source"): "os/aiueos/kernel/framebuffer.c",
                    Kw("source-sha256"): sha256_file(csrc), Kw("object-sha256"): sha,
                    Kw("target"): TARGET,
                    Kw("compiler"): {Kw("repo"): "kotoba-lang/amu", Kw("sha"): AMU_SHA}}
            man8 = write(os.path.join(d, "g8.edn"), manifest_text({"framebuffer.o": rec8}))
            h.both_gate("G8-c-source-named",
                        ["--link-list", list8, "--provenance", man8, "--root", REPO])
            rec9 = {Kw("source"): "os/aiueos/kotoba/kernel-probe.kotoba",
                    Kw("source-sha256"): sha256_file(os.path.join(KOTOBA_DIR, "kernel-probe.kotoba")),
                    Kw("object-sha256"): sha, Kw("target"): TARGET,
                    Kw("compiler"): {Kw("repo"): "kotoba-lang/amu", Kw("sha"): AMU_SHA}}
            man9 = write(os.path.join(d, "g9.edn"), manifest_text({"framebuffer.o": rec9}))
            h.both_gate("G9-lying-receipt-sections",
                        ["--link-list", list8, "--provenance", man9, "--root", REPO])
        else:
            h.scenarios.append({"name": "G8/G9-c-object", "agree": None,
                                "status": "zig-cc-failed", "detail": zt[-400:]})
    else:
        h.scenarios.append({"name": "G8/G9-c-object", "agree": None,
                            "status": "zig-absent"})

    # G10: the committed manifest over the committed objects, with receipts.
    man_real = os.path.join(KOTOBA_DIR, "provenance.edn")
    out_cljk = os.path.join(d, "receipt-cljk.edn")
    out_py = os.path.join(d, "receipt-py.edn")
    tail = ["--link-list", list_file, "--provenance", man_real, "--root", REPO]
    res = {"name": "G10-committed-manifest-receipt-value"}
    if h.nbb:
        code_c, text_c = run([h.nbb, GATE_CLJK] + tail + ["--receipt-out", out_cljk])
        res["oracle"] = {"exit": code_c, "markers": markers(text_c)}
    else:
        res["oracle"] = {"status": "oracle-absent"}
    code_p, text_p = run([sys.executable, GATE_PY] + tail + ["--receipt-out", out_py])
    res["port"] = {"exit": code_p, "markers": markers(text_p)}
    if h.nbb:
        sys.path.insert(0, SCRIPTS)
        import edn_lite
        v_c = edn_lite.read_edn(open(out_cljk).read())
        v_p = edn_lite.read_edn(open(out_py).read())
        res["receipt-value-equal"] = v_c == v_p
        res["agree"] = (res["oracle"]["exit"] == res["port"]["exit"]
                        and res["oracle"]["markers"] == res["port"]["markers"]
                        and v_c == v_p)
    else:
        res["agree"] = None
    h.scenarios.append(res)

    # G11: nbb (clojure.edn) reads the PORT's gate receipt.
    if h.nbb:
        expr = ("(require '[clojure.edn :as edn] '[\"node:fs\" :as fs]) "
                "(let [r (edn/read-string (.readFileSync fs " + edn_quote(out_py) + " \"utf8\"))] "
                "(println (if (and (= :aiueos.k16-pure-native-receipt/v1 (:format r)) "
                "(= " + str(len(committed)) + " (:scanned r)) "
                "(= " + str(len(committed)) + " (:kotoba r)) "
                "(= 0 (:stubs r)) (= 0 (:foreign r)) (= 0 (:unattested r)) "
                "(= {:c-sources [] :foreign-objects [] :imports [] :dynamic-dependencies []} "
                "(:foreign-code-receipt r))) \"G11-MATCH\" \"G11-MISMATCH\")))")
        code, text = run([h.nbb, "-e", expr])
        h.scenarios.append({
            "name": "G11-nbb-reads-port-gate-receipt",
            "oracle": {"exit": code, "markers": [text.strip()]},
            "port": {"expected": ["G11-MATCH"]},
            "agree": code == 0 and "G11-MATCH" in text and "G11-MISMATCH" not in text,
        })


def fresh_scenarios(h: Harness) -> None:
    # A scratch git repo, so the tree half is measured against a controlled
    # state instead of the (differently dirty) working tree of this checkout.
    root = os.path.join(h.tmp, "fresh-repo")
    os.makedirs(os.path.join(root, "src"))
    write(os.path.join(root, "src", "kernel.txt"), "kernel-one\n")
    write(os.path.join(root, "src", "loader.txt"), "loader-two\n")
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(["git", "-C", root, "add", "."], check=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=probe@example.invalid",
                    "-c", "user.name=probe", "commit", "-q", "-m", "fixture"],
                   check=True)
    artifacts = [os.path.join(root, "BOOTX64.EFI"), os.path.join(root, "KERNEL.ELF")]
    write(artifacts[0], "MZ-one")
    write(artifacts[1], "ELF-two")

    def runs(cljk_tail, py_tail, name, normalize=()):
        return h.both_fresh(name, {"cljk": cljk_tail, "py": py_tail}, normalize)

    # F1: record, then assert on the same receipt -> fresh.
    r_py = os.path.join(h.tmp, "img-py.edn")
    r_cljk = os.path.join(h.tmp, "img-cljk.edn")
    runs(["record", "--out", r_cljk, "--root", root, "--scope", "src"] + artifacts,
         ["record", "--out", r_py, "--root", root, "--scope", "src"] + artifacts,
         "F1-record",
         normalize=[(r_cljk, "<RECEIPT>"), (r_py, "<RECEIPT>")])
    runs(["assert", "--receipt", r_cljk, "--root", root],
         ["assert", "--receipt", r_py, "--root", root],
         "F2-assert-own-receipt")

    # F3: cross-read -- each implementation asserts the OTHER's receipt.
    runs(["assert", "--receipt", r_py, "--root", root],
         ["assert", "--receipt", r_cljk, "--root", root],
         "F3-cross-assert")

    # F4: record with no artifacts -> COULD-NOT-RUN, exit 3.
    runs(["record", "--out", os.path.join(h.tmp, "none.edn"), "--root", root],
         ["record", "--out", os.path.join(h.tmp, "none.edn"), "--root", root],
         "F4-record-no-artifacts")

    # F5: assert with no receipt at all -> COULD-NOT-RUN receipt-missing.
    runs(["assert", "--receipt", os.path.join(h.tmp, "absent.edn"), "--root", root],
         ["assert", "--receipt", os.path.join(h.tmp, "absent.edn"), "--root", root],
         "F5-assert-receipt-missing")

    # F6: a tampered artifact -> REFUSED stale-image.
    write(artifacts[0], "MZ-one-tampered")
    runs(["assert", "--receipt", r_cljk, "--root", root],
         ["assert", "--receipt", r_py, "--root", root],
         "F6-assert-tampered-artifact")

    # F7: the tree moved (an untracked file under scope) -> REFUSED stale-image.
    write(artifacts[0], "MZ-one")  # artifact back in sync; only the tree moves
    probe = os.path.join(root, "src", "probe.tmp")
    write(probe, "tree moved\n")
    runs(["assert", "--receipt", r_cljk, "--root", root],
         ["assert", "--receipt", r_py, "--root", root],
         "F7-assert-tree-moved")
    os.remove(probe)

    # F8: show prints the receipt; the port must parse nbb's and vice versa.
    if h.nbb:
        code_c, text_c = run([h.nbb, FRESH_CLJK, "show", "--receipt", r_py])
        code_p, text_p = run([sys.executable, FRESH_PY, "show", "--receipt", r_cljk])
        h.scenarios.append({
            "name": "F8-cross-show",
            "oracle": {"exit": code_c, "markers": markers(text_c)},
            "port": {"exit": code_p, "markers": markers(text_p)},
            "agree": code_c == 0 and code_p == 0 and ":aiueos.image-freshness/v1" in text_c
                     and ":aiueos.image-freshness/v1" in text_p,
        })

    # F9: the real checkout, real git plumbing: record + assert over os/aiueos.
    real_out = os.path.join(h.tmp, "real.edn")
    real_artifact = os.path.join(REPO, "os", "aiueos", "VERSION")
    code_r, text_r = run([sys.executable, FRESH_PY, "record", "--out", real_out,
                          "--root", REPO, "--scope", "os/aiueos", real_artifact])
    code_a, text_a = run([sys.executable, FRESH_PY, "assert", "--receipt", real_out,
                          "--root", REPO])
    h.scenarios.append({
        "name": "F9-real-tree-record-assert",
        "port": {"exit": code_r, "markers": markers(text_r)}
                | {"assert-exit": code_a, "assert-markers": markers(text_a)},
        "agree": code_r == 0 and code_a == 0,
    })


def node_free_check(h: Harness) -> None:
    """The port must complete with node/nbb absent from PATH."""
    py_dir = os.path.dirname(os.path.abspath(sys.executable))
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([py_dir, "/usr/bin", "/bin"])
    node = shutil.which("node", path=env["PATH"])
    nbb = shutil.which("nbb", path=env["PATH"])
    d = os.path.join(h.tmp, "node-free")
    os.makedirs(d, exist_ok=True)
    committed = sorted(f for f in os.listdir(KOTOBA_DIR) if f.endswith(".o"))
    list_file = write(os.path.join(d, "all.txt"),
                      "\n".join("os/aiueos/kotoba/" + n for n in committed))
    man = write(os.path.join(d, "man.edn"),
                manifest_text({n: synthesized_receipt(n) for n in committed}))
    r = subprocess.run([sys.executable, GATE_PY, "--link-list", list_file,
                        "--provenance", man, "--root", REPO],
                       capture_output=True, text=True, env=env, check=False)
    r2 = subprocess.run([sys.executable, FRESH_PY, "record",
                         "--out", os.path.join(d, "r.edn"), "--root", REPO,
                         "--scope", "os/aiueos",
                         os.path.join(REPO, "os", "aiueos", "VERSION")],
                        capture_output=True, text=True, env=env, check=False)
    h.scenarios.append({
        "name": "N1-node-free-path",
        "port": {"node-on-path": node, "nbb-on-path": nbb,
                 "gate-exit": r.returncode, "gate-markers": markers(r.stdout + r.stderr),
                 "fresh-exit": r2.returncode, "fresh-markers": markers(r2.stdout + r2.stderr)},
        "agree": node is None and nbb is None and r.returncode == 0 and r2.returncode == 0,
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sys.path.insert(0, SCRIPTS)
    nbb = shutil.which("nbb")
    with tempfile.TemporaryDirectory(prefix="aiueos-node-free-") as tmp:
        h = Harness(tmp, nbb)
        gate_scenarios(h)
        fresh_scenarios(h)
        node_free_check(h)

    bad = [s for s in h.scenarios if s.get("agree") is False]
    receipt = {
        "format": "aiueos.image-route-node-free/v1",
        "recorded-at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repo-head": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                                    capture_output=True, text=True, check=True).stdout.strip(),
        "oracle": "nbb " + GATE_CLJK if nbb else "absent",
        "port": [GATE_PY, FRESH_PY],
        "scenarios": h.scenarios,
        "measured": len(h.scenarios),
        "disagreements": len(bad),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
        f.write("\n")
    for s in h.scenarios:
        state = "AGREE" if s.get("agree") else ("DISAGREE" if s.get("agree") is False
                                                else "NOT-MEASURED")
        print(f"{state}\t{s['name']}")
    print(f"SCANNED {len(h.scenarios)} disagreements {len(bad)} out={args.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
