#!/usr/bin/env python3
"""Write a Git revision's `.cljk` sources outside the repository as `.cljc`.

This is an oracle and Otehon input, not part of the native route (network-awai-apex
ADR 0026 D2 and D18). It reads Git objects only, so working-tree changes and a
sparse checkout do not affect the result. It stays in Python so that no language
resolution, compilation or verdict moves here.

Four rewrites are needed because hosted Clojure rejects what the Kotoba reader and
SCI accept. They apply to the output only, and the manifest counts them per file:

- `:kotoba/export [a b]` becomes `:kotoba/export '[a b]`. Clojure evaluates `ns`
  metadata, so the unquoted names fail with "Unable to resolve symbol".
- `(catch :default e)` becomes `(catch #?(:clj Throwable :default :default) e)`.
  Clojure reads `:default` as a class name.
- `(catch err/ExceptionInfo e)`, and the same class in `thrown?`, becomes `(catch #?(:clj clojure.lang.ExceptionInfo
  :default :default) e)`. `kotoba.lang.error/ExceptionInfo` is a var, and a catch
  position needs a class. On a JS host this also catches other throwables.
- A top-level `#?(:kotoba A :default (do B C))` becomes `B C`, because nbb's SCI analyzes a
  top-level `do` as one form and C cannot see a var that B defines.
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
# A root ending in `kotoba` is a library's native twin of its `src`, not a host source.
EXCLUDED_SEGMENTS = {"test", "tests", "fixtures", "examples", "docs", "scripts", "tools", "bin", "provenance",
                     "kotoba", "testdata", "conformance", "script"}
RESOURCE_SUFFIXES = (".edn", ".json", ".js", ".mjs", ".txt")
EXPORT_CONDITIONAL = re.compile(r":kotoba/export(\s+)#\?")
EXPORT_VECTOR = re.compile(r":kotoba/export(\s+)\[")
CATCH_ALIASED = re.compile(r"\((catch|thrown\?|thrown-with-msg\?)\s+[\w.-]+/ExceptionInfo(?=\s)")
TOP_LEVEL_KOTOBA = re.compile(r"^#\?\(:kotoba\b", re.MULTILINE)
DEFAULT_DO = re.compile(r"\s*:default\s+\(do\b")
CATCH_DEFAULT = re.compile(r"\(catch\s+:default(?=\s)")


def form_end(text, opening):
    """The offset just past the balanced form that opens at `opening`."""
    depth = 0
    index = opening
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
    raise ValueError("unbalanced form")


def unwrap_default_do(text):
    """Turn a top-level `#?(:kotoba A :default (do B C))` into the forms `B C`.

    SCI analyzes a top-level `do` as one form, so C cannot see a var that B defines. nbb then
    refuses the namespace. The output is never read by Kotoba, so the `:kotoba` clause can go.
    """
    out = []
    position = 0
    count = 0
    for match in TOP_LEVEL_KOTOBA.finditer(text):
        if match.start() < position:
            continue
        opening = match.start() + 2
        try:
            end = form_end(text, opening)
            clause = text.index(":kotoba", opening) + len(":kotoba")
            # Skip the :kotoba clause's form, which is a balanced form or a single token.
            start = clause + len(text[clause:]) - len(text[clause:].lstrip())
            after = form_end(text, start) if text[start] in "([{" else start + len(text[start:].split(None, 1)[0])
        except (ValueError, IndexError):
            continue
        default = DEFAULT_DO.match(text, after)
        if not default:
            continue
        body_end = form_end(text, default.end() - 3)
        if text[body_end:end].strip() != ")":
            continue
        out.append(text[position:match.start()])
        out.append(text[default.end():body_end - 1])
        position = end
        count += 1
    out.append(text[position:])
    return "".join(out), count


def rewrite(text):
    """Return the hosted Clojure reading of a source, and what changed."""
    text, conditional = EXPORT_CONDITIONAL.subn(r":kotoba/export\1'#?", text)
    text, vector = EXPORT_VECTOR.subn(r":kotoba/export\1'[", text)
    text, catches = CATCH_DEFAULT.subn("(catch #?(:clj Throwable :default :default)", text)
    text, aliased = CATCH_ALIASED.subn(r"(\1 #?(:clj clojure.lang.ExceptionInfo :default :default)", text)
    text, unwrapped = unwrap_default_do(text)
    return text, {"export": conditional + vector, "catch-default": catches, "catch-aliased": aliased,
                  "default-do": unwrapped}


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


def collect(repo, rev, libraries, excluded):
    """Read one repository's revision. Return its commit, root table and blobs."""
    commit = git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()
    entries = list_tree(repo, commit)
    selected = set(libraries)
    if selected and not selected <= {library_id(path) for path, _ in entries}:
        missing = sorted(selected - {library_id(path) for path, _ in entries})
        raise ValueError(f"unknown libraries: {', '.join(missing)}")

    sources = [(p, i) for p, i in entries if p.endswith(".cljk") and (not selected or library_id(p) in selected)]
    blobs = read_blobs(repo, sorted({i for _, i in sources}))

    roots = {}
    skipped = 0
    for path, object_id in sources:
        form = NS_FORM.search(blobs[object_id].decode("utf-8", "replace"))
        root = source_root(path, form.group(1)) if form else None
        if root is None or excluded & set(root.split("/")):
            skipped += 1
            continue
        roots.setdefault(root, []).append((path, object_id, form.group(1)))

    resources = {}
    for path, object_id in entries:
        if path.endswith(RESOURCE_SUFFIXES):
            for root in roots:
                if root and path.startswith(root + "/"):
                    resources.setdefault(root, []).append((path, object_id))
    if resources:
        blobs.update(read_blobs(repo, sorted({i for rows in resources.values() for _, i in rows})))
    return commit, roots, resources, blobs, skipped


def materialize(repo, rev, out, libraries=(), apply_rewrites=True, include_tests=False, also=()):
    """`also` names other repositories as `path` or `path@rev`, in classpath order after `repo`."""
    excluded = EXCLUDED_SEGMENTS - ({"test", "tests", "fixtures"} if include_tests else set())
    repo = Path(repo).resolve(strict=True)
    out = Path(out).resolve()
    if out == repo or repo in out.parents:
        raise ValueError("the output must be outside the repository: .cljc is not committed source")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"the output directory is not empty: {out}")

    inputs = [(repo, rev, libraries)]
    for item in also:
        path, _, other_rev = item.partition("@")
        inputs.append((Path(path).resolve(strict=True), other_rev or "HEAD", ()))

    namespaces = {}
    duplicates = {}
    files = []
    paths = []
    origins = []
    skipped = 0
    totals = {"export": 0, "catch-default": 0, "catch-aliased": 0, "default-do": 0}
    for repo_index, (source_repo, source_rev, selected) in enumerate(inputs):
        commit, roots, resources, blobs, repo_skipped = collect(source_repo, source_rev, selected, excluded)
        skipped += repo_skipped
        origins.append({"name": source_repo.name, "commit": commit})
        for index, root in enumerate(sorted(roots)):
            directory = out / "roots" / f"{repo_index:02d}-{index:04d}"
            paths.append(str(directory))
            prefix = root + "/" if root else ""
            for path, object_id, namespace in sorted(roots[root]):
                label = f"{source_repo.name}:{path}"
                if namespace in namespaces:
                    duplicates.setdefault(namespace, [namespaces[namespace]]).append(label)
                else:
                    namespaces[namespace] = label
                raw = blobs[object_id]
                text = raw.decode("utf-8", "surrogateescape")
                text, counts = rewrite(text) if apply_rewrites else (text, dict.fromkeys(totals, 0))
                data = text.encode("utf-8", "surrogateescape")
                target = directory / output_name(path[len(prefix):])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                for key, value in counts.items():
                    totals[key] += value
                files.append({
                    "origin": source_repo.name,
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
        "source-commit": origins[0]["commit"],
        "origins": origins,
        "libraries": sorted(libraries),
        "rewrites-applied": apply_rewrites,
        "rewrites": totals,
        "roots": len(paths),
        "files": files,
        "skipped-no-matching-ns-or-excluded": skipped,
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
    parser.add_argument("--also", action="append", default=[],
                        help="another repository as PATH or PATH@REV; earlier inputs win a namespace. Repeat")
    parser.add_argument("--with-tests", action="store_true", help="also write test roots and their fixtures")
    parser.add_argument("--no-rewrite", action="store_true", help="negative control: copy the bytes unchanged")
    args = parser.parse_args()
    try:
        manifest = materialize(args.repo, args.rev, args.out, args.lib, not args.no_rewrite, args.with_tests, args.also)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({key: manifest[key] for key in ("source-commit", "roots", "rewrites")}
                     | {"files": len(manifest["files"]),
                        "duplicate-namespaces": len(manifest["duplicate-namespaces"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
