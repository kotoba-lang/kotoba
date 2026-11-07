#!/usr/bin/env python3
"""Write a Git revision's `.cljk` sources outside the repository as `.cljc`.

This is an oracle and Otehon input, not part of the native route (network-awai-apex
ADR 0026 D2 and D18). It reads Git objects only, so working-tree changes and a
sparse checkout do not affect the result. It stays in Python so that no language
resolution, compilation or verdict moves here.

These rewrites are needed because hosted Clojure rejects what the Kotoba reader and
SCI accept. They apply to the output only, and the manifest counts them per file:

- `:kotoba/export [a b]` becomes `:kotoba/export '[a b]`. Clojure evaluates `ns`
  metadata, so the unquoted names fail with "Unable to resolve symbol".
- `(catch :default e)` becomes `(catch #?(:clj Throwable :default :default) e)`.
  Clojure reads `:default` as a class name.
- `(catch err/ExceptionInfo e)`, and the same class in `thrown?`, becomes `(catch #?(:clj clojure.lang.ExceptionInfo
  :default :default) e)`. `kotoba.lang.error/ExceptionInfo` is a var, and a catch
  position needs a class. On a JS host this also catches other throwables.

`--host lpy` also removes JVM type hints such as `^String`, because Basilisp resolves
them as symbols, and turns `(catch Exception e)` into `(catch python/Exception e)`.
`clojure.string` and its siblings become `basilisp.string` and so on. A conditional with no `:lpy` clause reads its `:clj` clause. It adds a root of `.lpy` shims and requires them under the names `Math`, `Long` and so on
in each source that calls those classes.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
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
HOST_CLASS = re.compile(r"(?<![\w./*+!?<>=-])(Math|Long|Integer|Double|Character|System)/[A-Za-z_]")
HOST_NAMESPACE = re.compile(r"(?<![\w.-])(clojure|cljs)\.(core|string|set|walk|edn|test|pprint)(?=[\s/\]\)])")
HOST_HINT = re.compile(r"\^(?:bytes|longs|ints|doubles|floats|booleans|objects|long|int|double|float|boolean|byte|char|short|[A-Z][\w.]*)(?=[\s\[(])\s*")
HOST_CATCH = re.compile(r"\(catch\s+(?:#\?\(:clj\s+[^\s()]+\s+:cljs\s+[^\s()]+\)|(?:java\.[\w.]+\.|clojure\.lang\.)?[A-Z]\w*)(?=\s)")
CONDITIONAL = re.compile(r"#\?@?\(")
HOST_CORE = re.compile(r"(?<![\w.*+!?<>=/-])(unsigned-bit-shift-right|byte-array|aset-byte|char-array|num|array-map|bound\?|sorted-map|sorted-set)(?=[\s)])")
CATCH_DEFAULT = re.compile(r"\(catch\s+:default(?=\s)")


def after_ns_form(text):
    """The offset just past the first `(ns ...)` form, or None."""
    start = NS_FORM.search(text)
    if not start:
        return None
    depth = 0
    index = start.start() + len(start.group(0)) - len(start.group(0).lstrip())
    in_string = False
    while index < len(text):
        c = text[index]
        if in_string:
            if c == "\\":
                index += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == ";":
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
        elif c == "\\":
            index += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def conditional_clauses(text, open_at):
    """Scan the `#?(` opening at `open_at`. Return its end and its depth-1 keyword offsets."""
    index = open_at
    depth = 0
    keys = []
    in_string = False
    while index < len(text):
        c = text[index]
        if in_string:
            if c == "\\":
                index += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == ";":
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
        elif c == "\\":
            index += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return index + 1, keys
        elif c == ":" and depth == 1 and text[index - 1] in " \t\n(":
            keys.append(index)
        index += 1
    return len(text), keys


def retarget_conditionals(text):
    """Read a conditional's `:clj` clause on Basilisp when it has no `:lpy` clause.

    Without this such a form disappears and its surroundings fail far from the cause. A clause
    that only imports JVM classes keeps its key, so it stays dropped.
    """
    out = []
    position = 0
    count = 0
    for match in CONDITIONAL.finditer(text):
        _, keys = conditional_clauses(text, match.end() - 1)
        names = {text[k:].split(None, 1)[0].rstrip(")") for k in keys}
        if ":lpy" in names or ":clj" not in names:
            continue
        key = next(k for k in keys if text.startswith(":clj", k) and not text[k + 4].isalnum() and text[k + 4] != "-")
        if text[key + 4:].lstrip().startswith("(:import"):
            continue
        out.append(text[position:key])
        out.append(":lpy")
        position = key + 4
        count += 1
    out.append(text[position:])
    return "".join(out), count


def host_core_refers(text):
    """Refer the `.lpy` definitions of the core vars that Basilisp lacks."""
    names = sorted(set(HOST_CORE.findall(text)))
    end = after_ns_form(text)
    if not names or end is None:
        return text, 0
    line = f"\n(require '[kotoba-lpy-host.core :refer [{' '.join(names)}]])"
    return text[:end] + line + text[end:], len(names)


def host_aliases(text):
    """Require the `.lpy` shims under the JVM class names that this source calls."""
    names = sorted(set(HOST_CLASS.findall(text)))
    end = after_ns_form(text)
    if not names or end is None:
        return text, 0
    lines = "".join(f"\n(require '[kotoba-lpy-host.{name.lower()} :as {name}])" for name in names)
    return text[:end] + lines + text[end:], len(names)


def rewrite(text, host="clj"):
    """Return the hosted Clojure reading of a source, and what changed."""
    text, conditional = EXPORT_CONDITIONAL.subn(r":kotoba/export\1'#?", text)
    text, vector = EXPORT_VECTOR.subn(r":kotoba/export\1'[", text)
    text, catches = CATCH_DEFAULT.subn("(catch #?(:clj Throwable :lpy python/Exception :default :default)", text)
    text, aliased = CATCH_ALIASED.subn(r"(\1 #?(:clj clojure.lang.ExceptionInfo :lpy python/Exception :default :default)", text)
    counts = {"export": conditional + vector, "catch-default": catches, "catch-aliased": aliased, "host-hint": 0, "host-alias": 0, "host-ns": 0, "host-conditional": 0, "host-core": 0}
    if host == "lpy":
        text, counts["host-hint"] = HOST_HINT.subn("", text)
        text, classes = HOST_CATCH.subn("(catch python/Exception", text)
        counts["catch-aliased"] += classes
        text, counts["host-conditional"] = retarget_conditionals(text)
        text, counts["host-ns"] = HOST_NAMESPACE.subn(lambda m: "basilisp." + m.group(2), text)
        text, counts["host-alias"] = host_aliases(text)
        text, counts["host-core"] = host_core_refers(text)
    return text, counts


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


def materialize(repo, rev, out, libraries=(), apply_rewrites=True, include_tests=False, host="clj"):
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
    totals = {"export": 0, "catch-default": 0, "catch-aliased": 0, "host-hint": 0, "host-alias": 0, "host-ns": 0, "host-conditional": 0, "host-core": 0}
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
            text, counts = rewrite(raw.decode("utf-8", "surrogateescape"), host) if apply_rewrites else (
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

    if host == "lpy":
        shims = out / "lpy_host"
        shutil.copytree(Path(__file__).resolve().parent / "lpy_host", shims)
        paths.insert(0, str(shims))
    (out / "classpath.txt").write_text(":".join(paths) + "\n")
    (out / "deps.edn").write_text(
        "{:paths [" + " ".join(json.dumps(p) for p in paths) + "]}\n")
    manifest = {
        "schema": SCHEMA,
        "source-commit": commit,
        "libraries": sorted(selected),
        "host": host,
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
    parser.add_argument("--host", choices=("clj", "lpy"), default="clj",
                        help="lpy also removes JVM type hints, which Basilisp resolves as symbols")
    parser.add_argument("--with-tests", action="store_true", help="also write test roots and their fixtures")
    parser.add_argument("--no-rewrite", action="store_true", help="negative control: copy the bytes unchanged")
    args = parser.parse_args()
    try:
        manifest = materialize(args.repo, args.rev, args.out, args.lib, not args.no_rewrite, args.with_tests, args.host)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({key: manifest[key] for key in ("source-commit", "roots", "rewrites")}
                     | {"files": len(manifest["files"]),
                        "duplicate-namespaces": len(manifest["duplicate-namespaces"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
