# kotoba-harness

The hosted harness execution route was retired on 2026-10-27. JVM, NBB,
Node compiler hosts, PATH-selected `kotoba`, the old `-M` CLI and the old
`instantiateKotoba` runner are unavailable. Missing native functionality fails
closed; there is no hosted fallback.

The active entry runs **fixed native verification controls only**. A pinned
Amu selfhost compiler checks canonical `.kotoba` fixtures and compiles them to
`wasm32-browser`; the current official Amu static Worker host runs them in real
Chrome/Chromium. The selfhost-built `src/kotoba_harness/control_verdict.kotoba` owns the
control verdict and its 16-case positive/refusal selftest. Python only stages
bytes, launches these processes and records the native verdict. It does not implement the search, EDN evaluator, model policy
or Kotoba function behavior.

## Run the native controls

Use a checkout of `kotoba-lang/amu` with the native artifact and its matching
pin descriptor. Select it explicitly with `KOTOBA_AMU_ROOT`; a sibling `../amu`
is the default for standalone checkouts. In the monorepo, set the path explicitly. There is no search for an installed compiler. On Apple Silicon,
the existing Podman VM must be running native ARM64 Linux. The compiler is
`seed/bootstrap/aarch64-linux-static-root.elf`, executed directly without x86
emulation. The existing local container image defaults to `docker.io/library/alpine:3`
(`KOTOBA_PODMAN_IMAGE` may select another already-present image). Its entrypoint
is replaced with the static native compiler; no image shell or libraries run.
No image is pulled and the container has no network. The compiler mount is
read-only and file capability access is limited to the per-run directory.

Native ARM64 Linux uses the same root directly. Native Linux x86_64 selects
`bin/amu` with `native-product.json`. This change was exercised on Apple Silicon
via the ARM64 VM; it does not qualify the public macOS CLI or the Linux x86 route.

Google Chrome/Chromium is required (`KOTOBA_BROWSER` may select its executable).
The official browser test host uses a temporary isolated profile and a DevTools
pipe. No Node or previous browser ABI runner is used.

```sh
export KOTOBA_AMU_ROOT=/path/to/kotoba-lang/amu
bin/kotoba-harness --all                         # all six positive/negative controls
bin/kotoba-harness projects/kotoba.edn known      # exit 0 on zero failures
bin/kotoba-harness projects/kotoba.edn wrong      # exit 1 on nonzero failures
python3 -B -m unittest discover -s test -p 'test_*.py'
```

`--all` exits 0 only when every known control returns 0 and every wrong control
returns its exact expected failure count (Kotoba 120, Itonami 400, Murakumo 702).
Infrastructure failures exit 78 and are recorded as `blocked`, not model
rejections. Receipts under `runs/` include compiler/source/Wasm hashes, browser
version, fuel, compiler diagnostics and actual browser reports. The fixtures and
accepted project bytes are pinned in `test/native/manifest.json`; arbitrary or
modified project files are refused rather than silently using a stale fixture.

## Migration status

`validate`, arbitrary projects, typed candidate search, decision generation,
backtracking, Jev and `bin/bench` are **blocked pending the whole native port**.
These features are not reimplemented in Python or replaced with fixed controls.
The active gate tests the fixed acceptance corpus and its native verdict, not catalog/search semantics,
model generation or live API behavior. The former six NBB tests/25 assertions
are preserved but no longer run. No model requests or credential lookups occur.
The obsolete `NBB`, `KOTOBA_BIN` and `KOTOBA_BROWSER_HOST` settings are refused.

Original implementations, tests, launchers, dependency files and README are
preserved byte-for-byte as non-executable `.txt` migration records under
[docs/retired/hosted-harness-20261027](docs/retired/hosted-harness-20261027).
Their manifest records the original paths, revision and SHA-256 values. They
are not dependencies or fallback tools. Project EDN and
[evidence/bench-2026-10-07.json](evidence/bench-2026-10-07.json) remain unchanged.
The 2026-10-07 60-run Jev benchmark is historical evidence of the retired route;
it does not qualify the current native search/Jev route.
