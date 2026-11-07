# `.cljk` as `.cljc`

Hosted Clojure dialects read `.cljc` and not `.cljk`. [`materialize.py`](materialize.py)
writes a Git revision's `.cljk` sources outside the repository as `.cljc`, with a manifest
that binds every output to its source commit and SHA-256.

It has two uses:

- **Oracle measurements** (workspace `AGENTS.md`, JUN-579): reference values from JVM, nbb
  and other `.cljc` dialects, recorded with a date.
- **Awai Otehon input** (network-awai-apex ADR 0026 D18): an Otehon repository can depend on
  Kotoba libraries through the generated `deps.edn` or `classpath.txt`.

This is not part of the Kotoba or Amu native route. No native gate, build, package or
runtime path may depend on it, and native results must never fall back to it (ADR 0026 D2).
The `.cljc` output is never committed here, and the tool refuses an output path inside the
repository.

## Use

```bash
python3 oracle/cljc/materialize.py --rev origin/main --out "$OUT"
```

Add `--lib kotoba.coll` (repeatable) to limit the libraries, and `--with-tests` to include
test roots. `--no-rewrite` is the negative control.

```bash
java -cp "$(cat "$OUT/classpath.txt"):$CLOJURE_JAR_PATHS" clojure.main \
  oracle/cljc/load_census.clj namespaces.txt
```

## What it rewrites

Three source forms are valid for the Kotoba reader or nbb but not for hosted Clojure. The
rewrites apply to the output only, and the manifest counts them per file.

| Source | Output | Why |
|---|---|---|
| `:kotoba/export [a b]` | `:kotoba/export '[a b]` | The JVM `ns` macro evaluates its metadata |
| `(catch :default e)` | `(catch #?(:clj Throwable :default :default) e)` | The JVM reads `:default` as a class |
| `(catch err/ExceptionInfo e)`, `(thrown? err/ExceptionInfo …)` | The class on the JVM, `:default` elsewhere | `kotoba.lang.error/ExceptionInfo` is a var |

The last one is wider than its source on a JS host, where it also catches other throwables.

## Limits

- Loading a namespace does not show that it behaves correctly. Run its tests as well.
- `.kotoba` files with no `.cljk` twin are not written, so those namespaces do not exist on
  a hosted dialect.
- When two roots define one namespace, the first on the classpath wins. The manifest lists
  these under `duplicate-namespaces`.
- `:lpy` (Basilisp) has not been measured. It has no `Throwable`, so the `catch` output would
  need its own branch.

[Measurements](evidence-2026-11-07.md).

## Test

```bash
python3 oracle/cljc/test_materialize.py
```

Set `CLOJURE_CP` to the Clojure jars to run the JVM case with its negative control.
