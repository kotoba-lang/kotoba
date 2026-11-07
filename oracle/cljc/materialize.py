#!/usr/bin/env python3
"""Write a Git revision's `.cljk` sources outside the repository as `.cljc`.

This is an oracle and Otehon input, not part of the native route (network-awai-apex
ADR 0026 D2 and D18). It reads Git objects only, so working-tree changes and a
sparse checkout do not affect the result. It stays in Python so that no language
resolution, compilation or verdict moves here.

Three rewrites are needed because hosted Clojure rejects what the Kotoba reader and
SCI accept. They apply to the output only, and the manifest counts them per file:

- `:kotoba/export [a b]` becomes `:kotoba/export '[a b]`. Clojure evaluates `ns`
  metadata, so the unquoted names fail with "Unable to resolve symbol".
- `(catch :default e)` becomes `(catch #?(:clj Throwable :default :default) e)`.
  Clojure reads `:default` as a class name.
- `(catch err/ExceptionInfo e)`, and the same class in `thrown?`, becomes `(catch #?(:clj clojure.lang.ExceptionInfo
  :default :default) e)`. `kotoba.lang.error/ExceptionInfo` is a var, and a catch
  position needs a class. On a JS host this also catches other throwables.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


SCHEMA = "kotoba.oracle.cljc-materialization.v1"
NS_FORM = re.compile(r"^\s*\(ns\s+(?:\^\S+\s+)*([^\s()]+)", re.MULTILINE)
DUAL_NAME = re.compile(r"^(.*)\.(clj|cljs|cljc)\.cljk$")
EXCLUDED_SEGMENTS = {"test", "tests", "fixtures", "examples", "docs", "scripts", "tools", "bin", "provenance"}
RESOURCE_SUFFIXES = (".edn", ".json", ".js", ".mjs", ".txt")
EXPORT_CONDITIONAL = re.compile(r":kotoba/export(\s+)#\?")
EXPORT_VECTOR = re.compile(r":kotoba/export(\s+)\[")
CATCH_ALIASED = re.compile(r"\((catch|thrown\?|thrown-with-msg\?)\s+[\w.-]+/ExceptionInfo(?=\s)")
CATCH_DEFAULT = re.compile(r"\(catch\s+:default(?=\s)")


def rewrite(text):
    """Return the hosted Clojure reading of a source, and what changed."""
    text, conditional = EXPORT_CONDITIONAL.subn(r":kotoba/export\1'#?", text)
    text, vector = EXPORT_VECTOR.subn(r":kotoba/export\1'[", text)
    text, catches = CATCH_DEFAULT.subn("(catch #?(:clj Throwable :default :default)", text)
    text, aliased = CATCH_ALIASED.subn(r"(\1 #?(:clj clojure.lang.ExceptionInfo :default :default)", text)
    return text, {"export": conditional + vector, "catch-default": catches, "catch-aliased": aliased}


def output_name(path):
    """`a.cljs.cljk` keeps its platform extension and `a.cljk` becomes `a.cljc`."""
    dual = DUAL_NAME.match(path)
    return f"{dual.group(1)}.{dual.group(2)}" if dual else path[: -len(".cljk")] + ".cljc"


def source_root(path, namespace):
    """The classpath root of a file, or None when the path does not match its ns."""
    stem = DUAL_NAME.sub(r"\1.cljk", path)[: -len(".cljk")]
    expected = namespace.replace(".", "/").replace("-", "_")
    if stem == expected:
        return ""
    if stem.endswith("/" + expected):
        return stem[: -len(expected) - 1]
    return None


def library_id(path):
    parts = path.split("/")
    return parts[1] if parts[0] == "lib" and len(parts) > 2 else ""


def git(repo, *args, stdin=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=stdin, stdout=subprocess.PIPE, check=True).stdout


def read_blobs(repo, ids):
    """Read many blobs through one `git cat-file --batch`, in the order given."""
    raw = git(repo, "cat-file", "--batch", stdin="".join(f"{i}\n" for i in ids).encode())
    blobs = {}
    offset = 0
    for _ in ids:
        end = raw.index(b"\n", offset)
        object_id, kind, size = raw[offset:end].decode().split(" ")
        if kind != "blob":
            raise ValueError(f"{object_id} is a {kind}, not a blob")
        start = end + 1
        blobs[object_id] = raw[start : start + int(size)]
        offset = start + int(size) + 1
    return blobs


def list_tree(repo, rev):
    entries = []
    for row in git(repo, "ls-tree", "-r", "-z", rev).decode().split("\0"):
        if row:
            meta, path = row.split("\t", 1)
            mode, kind, object_id = meta.split(" ")
            if kind == "blob" and mode in ("100644", "100755"):
                entries.append((path, object_id))
    return entries


def materialize(repo, rev, out, libraries=(), apply_rewrites=True, include_tests=False):
    excluded = EXCLUDED_SEGMENTS - ({"test", "tests", "fixtures"} if include_tests else set())
    repo = Path(repo).resolve(strict=True)
    out = Path(out).resolve()
    if out == repo or repo in out.parents:
        raise ValueError("the output must be outside the repository: .cljc is not committed source")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"the output directory is not empty: {out}")

    commit = git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()
    entries = list_tree(repo, commit)
    selected = set(libraries)
    if selected and not selected <= {library_id(path) for path, _ in entries}:
        missing = sorted(selected - {library_id(path) for path, _ in entries})
        raise ValueError(f"unknown libraries: {', '.join(missing)}")

    sources = [(p, i) for p, i in entries if p.endswith(".cljk") and (not selected or library_id(p) in selected)]
    blobs = read_blobs(repo, sorted({i for _, i in sources}))

    roots = {}
    namespaces = {}
    duplicates = {}
    skipped = []
    for path, object_id in sources:
        form = NS_FORM.search(blobs[object_id].decode("utf-8", "replace"))
        root = source_root(path, form.group(1)) if form else None
        if root is None or excluded & set(root.split("/")):
            skipped.append(path)
            continue
        roots.setdefault(root, []).append((path, object_id, form.group(1)))

    resources = {}
    resource_rows = [(p, i) for p, i in entries if p.endswith(RESOURCE_SUFFIXES)]
    names = [root + "/" if root else "" for root in roots]
    for path, object_id in resource_rows:
        for root, prefix in zip(roots, names):
            if prefix and path.startswith(prefix):
                resources.setdefault(root, []).append((path, object_id))
    if resources:
        blobs.update(read_blobs(repo, sorted({i for rows in resources.values() for _, i in rows})))

    files = []
    paths = []
    totals = {"export": 0, "catch-default": 0, "catch-aliased": 0}
    for index, root in enumerate(sorted(roots)):
        directory = out / "roots" / f"{index:04d}"
        paths.append(str(directory))
        prefix = root + "/" if root else ""
        for path, object_id, namespace in sorted(roots[root]):
            if namespace in namespaces:
                duplicates.setdefault(namespace, [namespaces[namespace]]).append(path)
            else:
                namespaces[namespace] = path
            raw = blobs[object_id]
            text, counts = rewrite(raw.decode("utf-8", "surrogateescape")) if apply_rewrites else (
                raw.decode("utf-8", "surrogateescape"), {"export": 0, "catch-default": 0})
            data = text.encode("utf-8", "surrogateescape")
            target = directory / output_name(path[len(prefix):])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            for key, value in counts.items():
                totals[key] += value
            files.append({
                "source": path,
                "output": str(target.relative_to(out)),
                "namespace": namespace,
                "source-sha256": hashlib.sha256(raw).hexdigest(),
                "output-sha256": hashlib.sha256(data).hexdigest(),
                "rewrites": counts,
            })
        for path, object_id in resources.get(root, ()):
            target = directory / path[len(prefix):]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blobs[object_id])

    (out / "classpath.txt").write_text(":".join(paths) + "\n")
    (out / "deps.edn").write_text(
        "{:paths [" + " ".join(json.dumps(p) for p in paths) + "]}\n")
    manifest = {
        "schema": SCHEMA,
        "source-commit": commit,
        "libraries": sorted(selected),
        "rewrites-applied": apply_rewrites,
        "rewrites": totals,
        "roots": len(paths),
        "files": files,
        "skipped-no-matching-ns-or-excluded": len(skipped),
        "duplicate-namespaces": duplicates,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--rev", default="HEAD")
    parser.add_argument("--out", required=True)
    parser.add_argument("--lib", action="append", default=[], help="a lib/ directory name; repeat. Default: all")
    parser.add_argument("--with-tests", action="store_true", help="also write test roots and their fixtures")
    parser.add_argument("--no-rewrite", action="store_true", help="negative control: copy the bytes unchanged")
    args = parser.parse_args()
    try:
        manifest = materialize(args.repo, args.rev, args.out, args.lib, not args.no_rewrite, args.with_tests)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({key: manifest[key] for key in ("source-commit", "roots", "rewrites")}
                     | {"files": len(manifest["files"]),
                        "duplicate-namespaces": len(manifest["duplicate-namespaces"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
