# ADR — kbb `--backend js`: a JVM-free JS host as the second oracle, plus the kbb library

- Date: 2026-09-06
- Status: Accepted (owner instruction 2026-09-06「nbb を kbb に refactor, kotoba compile で js も対応, lib も 設計実装」)
- Superproject record: ADR-2609062200; roadmap ADR-2607181900; native design ADR-2609051100

## Context

`bin/kbb` is a `clojure -M -m kotoba.kbb` bootstrap (~10 s cold). ADR-2609051100
chose the native KEXE + `kexe_loader` as the JVM-free distribution artifact and
rejected "kbb を nbb で書き直すだけ" as the *final* form, because a JS-engine
guest is not the Node/browser-independent artifact ADR-2607198300 requires.
Nothing there argues against a JS backend as an **oracle**: Q9 asks every public
surface to be checked across nbb/CLJS, native and Wasm, and until 2026-09-06
the JS route itself needed a JDK (`kotoba-script` was `.clj`).

## Decision

1. `bin/kbb_js.cljk` (nbb) hosts `.kotoba` + kbb-v1 policy through
   `amu compile --target js --jvm-free` and Node `instantiateKotoba(grants)`.
   Grants are built from the policy, keyed by compiler wire id (35/33/34/20),
   re-check scope on every call, and journal receipts. Capabilities without a
   wire id (`:data/json` `:data/edn` `:http/fetch`) are refused by name with the
   reason. Output is the kbb v1 receipt shape; exit 0/1.
2. `lib/kbb/{fs,env,browse,proc}.kotoba` is the script library: typed wrappers
   over `typed-cap-call`, one per capability, consumed via `--source-path lib`.
   Scripts never spell a wire id. Fs was read-only on purpose while native's
   wire-35 provider was read-only; since 2026-09-07 both hosts implement the
   WRITE form (`78458db1`, mirroring amu `6cca3852`) and the library also
   carries the pure modules `kbb.str` (`a96dae55`) and `kbb.edn` (`c29163985`).
   The full index is `docs/DEMONSTRATIONS.md` § kbb.
3. Parity is the acceptance: `demo_kbb_fs_read_native.kotoba` answers 84 on
   `--backend js` and on `--backend native` (kbb_native_test) for the same
   policy. `test/kotoba/kbb_js_test.cljk` measures the js side; a missing `nbb`
   or amu runtime SKIPS with a printed line, never a silent green.
4. This is not the shipped artifact. `--backend native` remains the
   distribution form; the shim that routes `bin/kbb` is a separate,
   concurrent slice (`bin/kbb_shim.cljk`) and is free to add `--backend js`
   delegation to this file.

## Measured (2026-09-06)

- Gate item ② first port: `examples/kbb/no_bb_scan.kotoba` (compile route,
  kbb.fs + kbb.browse) and `src/no_bb_scan.kotoba` (interpreter) both answer
  3 over the same fixtures and policy; asserted together in
  `kbb_js_test/the-gate-script-port-agrees-with-the-interpreter`.
- Second port: `examples/kbb/shebang_scan.kotoba` packs the interpreter's
  `[1 2 2]` as 122; measured against the interpreter in the same test file.

- js backend cold run of demo_kbb_fs_read_native: 1.7 s (JVM kbb: ~10 s).
- Two emitter defects found by the library and fixed upstream
  (kotoba-script `8a55311b`): `string-index-of` returned a JS Number of code
  points (contract: i64 byte offset), and `string-split-count` was not lowered.
- Wire ids exist only for `:fs/app-data` 35, `:env/read` 33, `:fs/browse` 34,
  `:process/spawn` 20 (kotoba-lang capability-catalog). The other three kbb v1
  capabilities are interpreter-only until they get one.

## Measured (2026-09-07)

Read from the merge commits on `main` (`git log --format=%B <sha>`); test
counts are quoted as the commit bodies state them.

- Provider-boundary tests (`c5393d04`, branch commit `79f1542d`): one group
  per provider of `bin/kbb_js.cljk`, asserting every refusal leaves exit 1,
  `:kbb-js/guest-failed`, `:kotoba.kbb/capability` naming the provider and a
  LAST receipt with `:outcome :denied`. Probes
  `examples/kbb/probe_{fs,browse,proc}_via_env.kotoba` and the three env
  probes. Three host defects found and fixed (over-limit / not-a-regular-file
  / not-a-directory threw without a receipt). Body states:
  `kotoba.kbb-js-providers-test  Ran 4 tests containing 97 assertions. 0 failures, 0 errors.`
  and `kotoba.kbb-js-test            Ran 5 tests containing 33 assertions. 0 failures, 0 errors.`
- CLI surface tests for `bin/kbb_js.cljk` (`d3251c1d`): `--fuel` reaches the
  compiled module (`probe_fuel` → 100 by default, `fuel-exhausted` under
  `--fuel 8`), `--json`, argument refusals, two `--source-path`. Body states:
  `Ran 4 tests containing 54 assertions, 0 failures`.
- `kbb.str` + `env_scan` (`a96dae55`): five byte-addressed helpers, the ported
  scans walk their listings with them, third gate script `env_scan` reads its
  directory from `KBB_SCAN_DIR` (dirty_dir 3, clean_dir 0, unset → browse
  denied). Body states: `kbb-lib-test 3 tests/22 assertions, kbb-js-test 5/33,
  0 failures`.
- `kbb.edn` (`c29163985`, branch commit `de0880da2`): EDN values read with no
  capability; `examples/kbb/edn_value_read.kotoba` → 6272, not granted →
  `:kotoba/admission-denied`, out of scope → `:denied` receipt; measured
  JVM-free with `clojure`/`java`/`clj` stubbed to exit 127. Test count: not
  stated in the commit.
- fs WRITE form on the js host (`78458db1`): wire 35 request
  `<path>WRITE_SEP<content>`, mirrors amu `6cca3852`;
  `examples/kbb/fs_roundtrip.kotoba` → 20. Body states:
  `Ran 12 tests containing 213 assertions. 0 failures, 0 errors (kbb-js-write / kbb-js / kbb-js-providers).`
- Shim delegation (`39aab807`, dated 2026-09-06; branch commit `e43b4d68`):
  `bin/kbb --backend js` hands argv to `bin/kbb_js.cljk` with `KBB_HOME`
  derived from the shim's own location; delegation answers 84 with
  `:backend :js`, `--source-path` / `--json` pass through (`no_bb_scan` → 3),
  a js-host refusal keeps exit 1. The merge commit states no test count; the
  branch commit states: `kbb-shim-test + kbb-js-test 8 tests, 44 assertions,
  0 failures`.
