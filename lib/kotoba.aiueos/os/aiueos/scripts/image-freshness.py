#!/usr/bin/env python3
"""image-freshness.py -- the receipt that makes a boot say WHICH kernel it
ran. The Node-free port of `image-freshness.cljk` (the nbb original stays in
the tree as the oracle `check-image-route-node-free.py` measures against).

Why the original exists (ADR-0155), unchanged: every acceptance claim in the
K16 programme is a string read off a serial log, and until this receipt
existed NOTHING connected the strings to the bytes QEMU opened -- a boot
consumed whatever happened to be in the output directory. `record` is run by
the builder right after it produced the artifacts; `assert` is run by the
boot harness right before QEMU and refuses if either half moved.

Why the port exists: the original runs under nbb, a Node host, and
`build-uefi.sh` REFUSED to build without it -- NBB/Node sat inside the
accepted build path, which the JUN-31 acceptance criteria exclude (no C,
NBB/Node, JVM or GraalVM path; Python is orchestration only).

Exit codes are three, deliberately, and the same three everywhere:

  0  fresh          -- the artifacts and the tree are what the receipt says
  3  could-not-run  -- no receipt, no artifact, no git. NOT a pass, and not
                       a boot failure either: the question was not answered
  4  refused        -- the artifacts or the tree moved. `REFUSED stale-image`

Usage:
  python3 image-freshness.py record --out <receipt> [--root <repo>]
                                    [--scope <path>] <artifact>...
  python3 image-freshness.py assert --receipt <receipt> [--root <repo>]
                                    [--scope <path>] <artifact>...
  python3 image-freshness.py show   --receipt <receipt>
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import NoReturn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edn_lite import EdnError, Kw, pr_str, read_edn  # noqa: E402

EXIT_FRESH = 0
EXIT_COULD_NOT_RUN = 3
EXIT_REFUSED = 4


def out(*parts) -> None:
    print(" ".join(str(p) for p in parts))


def could_not_run(reason, *detail) -> NoReturn:
    """Neither 0 nor the refusal code. A machine without git, or a receipt
    that was never written, has not shown the image to be stale -- it has
    failed to look."""
    print(" ".join(["COULD-NOT-RUN", reason] + [str(d) for d in detail]), file=sys.stderr)
    sys.exit(EXIT_COULD_NOT_RUN)


def refuse(*detail) -> NoReturn:
    """The pinned literal. Callers grep for `REFUSED stale-image`; the tail
    names which of the two comparisons disagreed and with what."""
    print(" ".join(["REFUSED", "stale-image"] + [str(d) for d in detail]), file=sys.stderr)
    sys.exit(EXIT_REFUSED)


# --- primitives ------------------------------------------------------------


def sha256_hex(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def sha256_string(s: str) -> str:
    return sha256_hex(s.encode("utf-8"))


def sha256_file(p: str):
    try:
        with open(p, "rb") as f:
            return sha256_hex(f.read())
    except OSError:
        return None


def file_bytes(p: str):
    try:
        return os.stat(p).st_size
    except OSError:
        return None


def git(root: str, *args):
    """None when git could not answer. Callers turn that into `could-not-run`,
    never into an empty result -- an unreadable tree must not look like a
    clean one."""
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", root, *args],
            capture_output=True, text=True, check=False)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 and r.stdout is not None else None


# --- the tree half of the receipt -----------------------------------------


def porcelain_path(line: str) -> str:
    """A porcelain v1 line is `XY<space>PATH`, and a rename is `PATH -> PATH`.
    The destination is the one whose bytes are on disk."""
    p = line[3:]
    arrow = p.find(" -> ")
    return p[arrow + 4:] if arrow >= 0 else p


def tree_state(root: str, scope: str):
    """What the image was built FROM, as one digest.

    Three inputs, in this order and no other: the commit, the index of the
    scoped subtree (blob SHAs -- free, git already has them), and the
    working-tree bytes of everything git reports as changed or untracked
    under the scope. The third is what makes an uncommitted edit count."""
    head = git(root, "rev-parse", "HEAD")
    index = git(root, "ls-files", "-s", "--", scope)
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all", "--", scope)
    if head is None or index is None or status is None:
        could_not_run("git-unavailable", "root=" + root)
    head = head.strip()

    entries = []
    for line in status.splitlines():
        if not line.strip():
            continue
        rel = porcelain_path(line)
        abs_ = os.path.join(root, rel)
        entries.append((rel, line[:2], sha256_file(abs_) or "absent"))
    entries.sort(key=lambda e: e[0])

    canonical = ("head " + head + "\n"
                 + "scope " + scope + "\n"
                 + "index " + sha256_string(index) + "\n"
                 + "dirty " + str(len(entries)) + "\n"
                 + "\n".join(xy + " " + sha + " " + rel for rel, xy, sha in entries)
                 + "\n")
    return {"head": head, "dirty": len(entries), "digest": sha256_string(canonical)}


# --- the artifact half -----------------------------------------------------


def artifact_entry(root: str, p: str):
    abs_ = p if os.path.isabs(p) else os.path.join(root, p)
    sha = sha256_file(abs_)
    if sha is None:
        could_not_run("artifact-missing", abs_)
    return {Kw("path"): os.path.relpath(abs_, root),
            Kw("sha256"): sha,
            Kw("bytes"): file_bytes(abs_)}


# --- argv ------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))


def parse_args(argv):
    opts = {"root": DEFAULT_ROOT, "scope": "os/aiueos"}
    positional = []
    a = list(argv)
    while a:
        x = a.pop(0)
        if x == "--root":
            opts["root"] = os.path.abspath(a.pop(0) if a else ".")
        elif x == "--scope":
            opts["scope"] = a.pop(0) if a else None
        elif x == "--out":
            opts["out"] = a.pop(0) if a else None
        elif x == "--receipt":
            opts["receipt"] = a.pop(0) if a else None
        else:
            positional.append(x)
    return opts, positional


# --- commands --------------------------------------------------------------


def do_record(opts, artifacts) -> None:
    root, scope = opts["root"], opts["scope"]
    if not opts.get("out"):
        could_not_run("usage", "record requires --out <receipt>")
    if not artifacts:
        # Evidence floor. A receipt over zero artifacts would let every later
        # `assert` pass while covering nothing.
        could_not_run("no-artifacts", "record was given no artifact paths")
    tree = tree_state(root, scope)
    entries = [artifact_entry(root, p) for p in artifacts]
    receipt = {
        Kw("receipt/format"): Kw("aiueos.image-freshness/v1"),
        Kw("receipt/recorded-at"): datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        Kw("tree/head"): tree["head"],
        Kw("tree/scope"): scope,
        Kw("tree/dirty-entries"): tree["dirty"],
        Kw("tree/digest"): tree["digest"],
        Kw("artifacts"): entries,
    }
    out_path = opts["out"]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pr_str(receipt) + "\n")
    out("IMAGE-RECEIPT", "artifacts=" + str(len(entries)),
        "head=" + tree["head"][:7],
        "dirty=" + str(tree["dirty"]),
        "tree=" + tree["digest"][:12],
        "out=" + out_path)
    out("SCANNED", len(entries))
    sys.exit(EXIT_FRESH)


def read_receipt(p: str):
    if not os.path.exists(p):
        could_not_run("receipt-missing", p)
    try:
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        could_not_run("receipt-unreadable", p)
    try:
        value = read_edn(text)
    except EdnError as e:
        could_not_run("receipt-unreadable", p, str(e))
    if not (isinstance(value, dict)
            and value.get(Kw("receipt/format")) == Kw("aiueos.image-freshness/v1")):
        could_not_run("receipt-unreadable", p,
                      "format=" + pr_str(value.get(Kw("receipt/format"))
                                         if isinstance(value, dict) else value))
    return value


def do_assert(opts, artifacts) -> None:
    root = opts["root"]
    if not opts.get("receipt"):
        could_not_run("usage", "assert requires --receipt <receipt>")
    r = read_receipt(opts["receipt"])
    recorded = r.get(Kw("artifacts")) or []
    if not recorded:
        could_not_run("no-artifacts", opts["receipt"] + " records no artifact")
    by_path = {a[Kw("path")]: a for a in recorded}
    # The caller may name the artifacts it is about to boot; naming none
    # means "everything the receipt covers".
    if artifacts:
        wanted = [os.path.relpath(p if os.path.isabs(p) else os.path.join(root, p), root)
                  for p in artifacts]
    else:
        wanted = [a[Kw("path")] for a in recorded]
    for rel in wanted:
        expected = by_path.get(rel)
        if expected is None:
            could_not_run("artifact-not-in-receipt", rel, "receipt=" + opts["receipt"])
        abs_ = os.path.join(root, rel)
        found = sha256_file(abs_)
        if found is None:
            refuse("artifact=" + rel, "expected=" + expected[Kw("sha256")], "found=absent")
        if found != expected[Kw("sha256")]:
            refuse("artifact=" + rel, "expected=" + expected[Kw("sha256")], "found=" + found)
    # The tree half. An artifact can be byte-identical to the receipt and
    # still be stale: the receipt was written three commits ago and nobody
    # rebuilt. This is the comparison that catches the boot-only harnesses.
    scope = r.get(Kw("tree/scope")) or opts["scope"]
    now = tree_state(root, scope)
    if now["digest"] != r.get(Kw("tree/digest")):
        refuse("tree=" + scope,
               "expected=" + str(r.get(Kw("tree/digest"))),
               "found=" + now["digest"],
               "receipt-head=" + str(r.get(Kw("tree/head"))),
               "head=" + now["head"])
    out("IMAGE-FRESH", "artifacts=" + str(len(wanted)),
        "head=" + str(r.get(Kw("tree/head")))[:7],
        "tree=" + str(r.get(Kw("tree/digest")))[:12])
    out("SCANNED", len(wanted))
    sys.exit(EXIT_FRESH)


def do_show(opts) -> None:
    if not opts.get("receipt"):
        could_not_run("usage", "show requires --receipt <receipt>")
    print(pr_str(read_receipt(opts["receipt"])))
    sys.exit(EXIT_FRESH)


def main(argv) -> None:
    if not argv:
        could_not_run("usage", "expected one of: record | assert | show")
    command, rest = argv[0], argv[1:]
    opts, positional = parse_args(rest)
    if command == "record":
        do_record(opts, positional)
    elif command == "assert":
        do_assert(opts, positional)
    elif command == "show":
        do_show(opts)
    else:
        could_not_run("usage", "expected one of: record | assert | show")


if __name__ == "__main__":
    main(sys.argv[1:])
