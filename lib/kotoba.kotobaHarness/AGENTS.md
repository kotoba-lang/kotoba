# Native-only execution

- Compiler and harness domain code are canonical `.kotoba`, built by pinned
  Amu selfhost. Never restore JVM/Clojure, NBB/KBB, Node compiler hosts, legacy
  launchers, PATH discovery or a C compiler/loader/runtime fallback.
- `src/kotoba_harness/{data,catalog,ast,search,decision,ledger,verification,main,bench,gate}.kotoba`
  own project parsing, candidate legality, DFS holes, paging, rewinds, sibling
  freezing, admission/retries, source generation, verdicts, receipts and budgets.
  `bin/native-transport.py` supplies only explicit byte staging/hashing,
  process/browser launch, framed I/O and fixed-endpoint opaque HTTP transport.
  Do not move domain behavior or verdicts into Python/JavaScript.
- `test/native/toolchain.json` pins the compiler image, runner source and
  official browser driver/host. Explicitly select the matching Amu checkout.
  The full route is ARM64 Linux, including native ARM64 Podman on macOS.
  The payload target name does not qualify Mach-O/public macOS CLI execution.
  Whole-harness x86 f64 code generation remains unqualified; do not fall back.
- `bin/check-native` builds the ordered Kotoba gate. It restores the original
  six search/catalog tests / 25 assertions, adds boundary controls, and runs
  actual selfhost check + browser Wasm known/wrong/scripted search for all
  three projects, stop/exhaustion and budget refusals. Native CI is in
  `.github/workflows/native-harness.yml`. CI makes no model API calls.
- The earlier `bin/native-controls.py` / `control_verdict.kotoba` fixed-corpus
  route remains a separate control via `--all`; it does not qualify search/Jev.
- Live Jev needs an explicit credential and budget. No automatic credential
  discovery, redirects, remote model/compiler fallback or transport retries.
  A caller's authorization does not carry to another caller/session. Never
  write keys to disk or pass them to native guests, compilers or the browser.
  Unknown charges stop the session and remain unknown; do not substitute zero.
  Record current model/rate assumptions and exact native build identity.
- Known/wrong/source acceptance and actual model coding outcomes are distinct.
  A stopped/rejected model run is not verified code. Preserve every refusal.
- Former hosted sources/tests remain non-executable `.txt` migration records
  in `docs/retired/hosted-harness-20261027`; their original source pins are
  immutable. Maintain `local-changes.json` hashes for all active changes.
- Hash mismatches, missing binaries, unsupported hosts and execution failures
  stop with `blocked`. Preserve unrelated WIP. Public CLI/target parity,
  generic EDN outside the declared input subset, whole-catalog/runtime-value
  oracle coverage and the old 60-run benchmark are not qualified by this gate.
