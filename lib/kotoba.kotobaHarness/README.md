# kotoba-harness

Catalog, typed AST assembly, ordered search/backtracking, Jev admission,
source generation, verification verdicts, receipts and benchmark ordering now
run in canonical `.kotoba`, built by the pinned Amu selfhost. The original six
tests / 25 assertions run natively. JVM, NBB, Node compiler hosts, PATH-selected
`kotoba`, the old `-M` CLI and old Wasm runner remain retired.

## Run locally

Check out Amu at the exact revision in `test/native/toolchain.json`. Pass that
checkout explicitly; binary, runner and browser-host hashes must match.

```sh
export KOTOBA_AMU_ROOT=/path/to/amu-at-29352f9182cba9dc0e523df3265b0965aced26f7
bin/kotoba-harness projects/kotoba.edn validate
bin/kotoba-harness projects/kotoba.edn known runs/local
bin/kotoba-harness projects/kotoba.edn wrong runs/local  # exits 1: actual rejection
python3 -B bin/check-native --amu "$KOTOBA_AMU_ROOT" --output runs/ordered-gate
python3 -B -m unittest discover -s test -p 'test_*.py'
```

The full route requires **native ARM64 Linux**. On Apple Silicon it uses an
already-running ARM64 Podman VM, directly executing the pinned static ARM64
compiler and runner. It does not use x86 emulation. An already-present
`docker.io/library/alpine:3` image supplies container metadata only: no image
shell, loader or libraries execute, no image is pulled, and the container has
no network. On native ARM64 Linux the same pinned binaries run directly.
Native compiler/guest PATH contains no hosted tools.
The packed `aarch64-macos` payload target is the Amu/KX64 runner payload format;
it does not mean this is a Mach-O macOS executable. No public macOS CLI or
whole-harness x86 qualification is claimed. The x86 backend currently refuses
the floating-point operations used for probability admission.

Google Chrome/Chromium is required (`KOTOBA_BROWSER` selects its executable).
The pinned official Amu browser driver runs `wasm32-browser` in a real browser
Worker through its static host, with a temporary profile and DevTools pipe.
The Python transport stages declared source bytes and a KSL source lock,
launches the exact compiler/runner/browser, and relays opaque HTTP bodies and
raw observations. It does not parse project EDN, select candidates, generate
Kotoba, admit answers, manage search or create semantic receipts. Those are
owned by the native modules. The controller receives only stdin/stdout, hash
and clock grants; filesystem/process/HTTP mechanisms remain outside it.

The ordered Kotoba gate runs input/catalog/search/boundary tests, then each
project's known → wrong → scripted search, stop/exhaustion and budget refusals,
and a zero-request benchmark budget control. It checks actual native results,
not test output strings alone. CI runs this gate on ARM64 Linux and uploads
source locks, native build identities, raw observations and native receipts.
It makes no paid API requests. `--all` retains the separate pinned fixed-corpus
control gate from JUN-454; it is not a substitute for the ordered gate.

## Decisions and budgets

```sh
# Supply the credential explicitly in the invoking environment.
# The launcher does not discover credentials or read Keychain / Hermes files.
bin/kotoba-harness projects/kotoba.edn jev runs/live --budget-usd 0.01
bin/kotoba-harness projects/itonami.edn scripted runs/scripted --script choices.json
bin/bench 5 runs/bench --budget-usd 0.05
```

`OPENROUTER_API_KEY` is required for paid runs and removed from child process
execution environments. It is never sent to a compiler, native guest, browser
or receipt. The only paid endpoint is the fixed HTTPS OpenRouter Decisions
endpoint; redirects and transport retries are refused. The model remains
`typesafe/jev-1.13`. See the [official model page](https://openrouter.ai/typesafe/jev-1.13).

A positive explicit budget (at most USD 0.05 per invocation) is mandatory.
Before each request the native ledger reserves 32,768 input tokens at the
2026-10-27 verified USD 0.042/M input, zero output price: USD 0.001376256.
It then accounts the actual reported cost, rounding upward to picodollars.
An unknown charge stops execution with `api-usd: null`; it is never treated as
free. Recheck this price assumption before changing the model/price pin.
The benchmark shares one total budget across guided/plain projects,
escalation on/off and rounds (1–32), preserving individual native receipts.
Budget exhaustion stops further requests. A model refusal is a measured
outcome; it does not make a benchmark successful coding run.

Project input is data, not evaluated source. The native reader admits the
project's map/vector/string/keyword/decimal-number/bool/nil subset of EDN and
strict JSON, rejects duplicate keys, malformed escapes, trailing JSON and
i64 overflow, and bounds input to 1 MiB / depth 64. Project bounds retain
16 functions/stages, 32 literals, 256 audit entries, depth 16 and candidate
pages of 4–16. AST arenas and audit/attempt/exclusion lists are independent
of the bounded document constructor ABI; candidate pools can exceed 32.
Only the offered candidate ID is accepted from the model. Invalid distributions
retry once, with both charged decisions retained in the audit. Function bodies
are frozen after individual verification; sibling failures are isolated.

Receipts retain `kotoba-harness.receipt/v1` with source, verification, decisions,
attempts, usage and hashes, plus native build/toolchain identities. Program hashes
cover this native reader's canonical EDN serialization. `verified` requires a
successful check, Wasm compile, clean browser exit and a nonnegative integer
failure count of zero. Compiler/runtime/protocol failures are `blocked`, never
wrong-model evidence. Unresolved ASTs are not emitted as final source on refusal.
The obsolete `NBB`, `KOTOBA_BIN` and `KOTOBA_BROWSER_HOST` settings are refused.

## Evidence and preserved sources

[evidence/native-harness-2026-10-27.json](evidence/native-harness-2026-10-27.json)
records the new route's actual deterministic and live results. Two projects
verified in the first live round; Murakumo reached its six-attempt limit and
refused. These are development qualification runs, not a new 60-run benchmark.

Original implementations/tests/launchers/dependencies remain inert `.txt`
migration records under [docs/retired/hosted-harness-20261027](docs/retired/hosted-harness-20261027),
with immutable source pins and destination change hashes. Never execute them.
Project EDN and [the 2026-10-07 benchmark](evidence/bench-2026-10-07.json) remain
unchanged; that historical benchmark qualifies its retired route only.
