# Native-only execution

- Compiler and replacement harness code must be canonical `.kotoba`, built by
  Amu selfhost. Do not restore JVM/Clojure, NBB/KBB, Node compiler hosts, legacy
  launchers, PATH compiler discovery, or a C compiler/loader/runtime fallback.
- Current `bin/native-controls.py` is test orchestration only: stage pinned
  fixtures, launch the pinned native compiler, run the official browser test
  host, and collect observations and the selfhost-built control verdict. Do not implement search, source assembly,
  project semantics, model policy or a replacement compiler in Python.
- The native controls cover check, Wasm generation and browser execution of
  fixed positive/negative acceptance fixtures. They are not the full native
  harness, the full ordered search/Jev controller or live Jev qualification.
  `src/kotoba_harness/control_verdict.kotoba` owns fixed-corpus acceptance;
  its native selftest includes corrupt results and runtime-failure refusals.
- NBB launcher/dependency/test entries and old CLI/Wasm runners were removed.
  All original sources/tests are non-executable `.txt` migration records in
  `docs/retired/hosted-harness-20261027`, with original hashes. Never execute
  them as a fallback. Keep the source corpus and historical evidence intact.
- Former search/catalog tests (six tests/25 assertions), arbitrary project
  validation, model decisions, backtracking and benchmarks are no longer covered
  by the active gate. They remain blocked until the whole native implementation
  preserves their behavior and passes its native positive/negative gate.
- No library-specific native CDCI gate exists. The root native workflows remain
  separate. Do not add JVM/NBB/hosted workflow steps. A required whole-harness
  native CDCI gate is missing and remains blocked.
- Hash mismatches, missing binaries, unsupported hosts and execution failures
  must stop with `blocked`; never count infrastructure failure as wrong-model
  behavior or quietly broaden compiler selection. Preserve unrelated WIP.
