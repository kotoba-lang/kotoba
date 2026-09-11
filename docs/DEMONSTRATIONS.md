# Demonstrations — real programs built with `.kotoba`

A curated index of **actually-running artifacts** written in the `.kotoba`
language (or, where noted, in the same compiler's kotoba-clj subset): what
each one is, where it lives, and which real host executes it. Everything
listed here is checked in and exercised end-to-end — compiled by
`kotoba wasm emit` (not interpreted, not hand-written WAT) and run on a real
WebAssembly engine: [Chicory](https://github.com/dylibso/chicory) on the JVM
(`kotoba.wasm-exec`), the browser's own native `WebAssembly`
([`kotoba-lang/wasm-webcomponent`](https://github.com/kotoba-lang/wasm-webcomponent)),
or [`kotoba-lang/kototama`](https://github.com/kotoba-lang/kototama)'s
`actor:host` tender.

Run any in-repo demo directly:

```bash
kotoba wasm run src/demo_kgraph.kotoba --policy src/demo_kgraph_policy.edn \
    --package-lock kotoba.lock.edn
```

or run the test suites that execute them on Chicory:

```bash
clojure -M:dev:test   # wasm_exec_test, real_host_providers_test, actor_host_test, …
```

## Applications (this repo, `src/`)

The first *applications* — as opposed to capability demos — ported to
`.kotoba`:

| program | what it is | executed by |
|---|---|---|
| [`mesh/examples/mesh_drama_profile.kotoba`](https://github.com/kotoba-lang/mesh/blob/main/examples/mesh_drama_profile.kotoba) | **First real mesh app in `.kotoba`** (ADR-2607082400): now owned and tested by the dedicated `kotoba-lang/mesh` runtime. | `kotoba-lang/mesh` compiles, executes, and serves the route over real HTTP |
| [`mesh/examples/mesh_no_answer.kotoba`](https://github.com/kotoba-lang/mesh/blob/main/examples/mesh_no_answer.kotoba) | Assert-only mesh guest covering the HTTP 204 branch. | `kotoba-lang/mesh` owner tests |
| [`src/mesh_bad_route.kotoba`](../src/mesh_bad_route.kotoba) | Deliberately non-compiling mesh guest — proves `compile-route` treats an unservable route as a startup-time configuration error. | `mesh_node_test.clj` |
| [`src/demo_kgraph.kotoba`](../src/demo_kgraph.kotoba) | Minimal datom tool: `kgraph-assert!` an EAVT fact, `kgraph-query` it back with a Datalog-style query — the language's in-memory `[e a v]` graph exercised from inside WASM. | `wasm_exec_test.clj` (Chicory); browser port in wasm-webcomponent's `examples/kgraph` |

## Capability & ABI demos (this repo, `src/`)

58 `.kotoba` programs live under `src/`, 37 with a `*_policy.edn`
capability policy alongside (the rest are pure-compute and need no
capability grant; the 58th program is the **kami-survivors game**, listed
under [Games](#games) below rather than here). Each family proves one
slice of the capability-confined execution model, and each is executed —
not just compiled — by the named test suite.

| family | programs | what it demonstrates | executing tests |
|---|---|---|---|
| **core language / ABI** | `demo`, `demo_call`, `demo_indirect`, `demo_i64`, `demo_i64_params`, `demo_i64_if`, `demo_f32`, `demo_f32_ops`, `demo_f32_if`, `demo_f32_result`, `demo_result_record`, `demo_string_abi`, `demo_buffer_abi`, `demo_alloc`, `demo_alloc_checked`, `demo_memory`, `demo_memory_write`, `demo_memory_grow`, `demo_loop_forever` | arithmetic, i64/f32 numerics, direct & indirect calls, string/buffer ABI, linear-memory alloc/grow, non-termination guard | `wasm_exec_test.clj` |
| **capability system** | `demo_cap`, `demo_cap_passing`, `demo_cap_threading`, `demo_notify`, `demo_providers`, `demo_provider_result`, `demo_i64_host` | `has-capability?` runtime checks, passing/threading capability values (incl. affine-reuse provenance tracking), host-provider dispatch | `cap_typed_test.clj`, `cap_passing_test.clj`, `cap_affine_test.clj`, `host_providers_test.clj` |
| **real host providers** (`demo_real_*`) | `clock`, `random`, `log`, `fs`, `clipboard`, `keychain`, `http_fetch`, `http_post`, `topic_publish` / `topic_poll` / `topic_take` / `topic_count` | the same guest binaries running against **real side-effectful providers** — wall clock, OS RNG, filesystem, clipboard, keychain, live HTTP, pub/sub topics — each gated by its policy EDN (e.g. `#{:http/fetch}`) | `real_host_providers_test.clj` |
| **`actor:host` ABI** (`demo_actor_host_*`) | `sha256`, `sign`, `verify`, `keypair`, `http_post`, `log_read` | the kototama `actor:host` vocabulary (crypto / http / log — ADR-2607062330) called from `.kotoba`: hashing, Ed25519 keypair/sign/verify, HTTP POST, append-only log reads | `actor_host_test.clj` |
| **aiueOS kernel caps** (`demo_aiueos_*`) | `clock`, `random`, `log`, `irq`, `dma`, `mmio`, `pci`, `topic_publish`, `topic_poll` | OS-kernel-level capability surface (interrupts, DMA, MMIO, PCI, …) confined behind the same policy mechanism | `aiueos_kernel_caps_test.clj` |

## kbb — operational scripts on the JVM-free hosts (`examples/kbb/`, `lib/kbb/`)

`bin/kbb` runs one `.kotoba` script under an explicit deny-by-default policy
on a **JVM-free** backend: `--backend native` (amu `kexe_loader`, wire 35
only) or `--backend js` (`bin/kbb_js.cljk`: `amu compile --target js
--jvm-free` + Node `instantiateKotoba`; wire ids 35/33/34/20/22). Scripts are
written against the `lib/kbb/` library through the project route
(`--source-path lib`) and never spell a wire id. Every script answers ONE
i64, so a packed number is the parity evidence between hosts and against the
nbb original it ports (ADR-2607181900; `docs/ADR-kbb-js-backend-oracle.md`,
`docs/ADR-kbb-jvm-free-front-door.md`).

Run one:

```bash
bin/kbb examples/kbb/fs_report.kotoba --policy examples/kbb/fs_report_policy.edn --backend js --source-path lib
nbb bin/kbb_js.cljk examples/kbb/fs_report.kotoba --policy examples/kbb/fs_report_policy.edn --source-path lib --json
```

(`bin/kbb <script> --policy <p> [--backend native|js|interpreter] [--source-path <dir>]... [--fuel <n>] [--json]`
is the shim's usage line; with `--backend` absent it routes to a JVM-free
backend or refuses by name with exit 3.)

### Scripts

| program | what it demonstrates | measured answer | executed by |
|---|---|---|---|
| [`examples/kbb/fs_report.kotoba`](../examples/kbb/fs_report.kotoba) | the `demo_kbb_fs_report` pattern written against the library: read one policy-scoped file through `kbb.fs`, answer its byte count. Compiles on js and native through `--source-path lib`. | **84** | `kbb_js_test.clj` |
| [`examples/kbb/env_browse_proc.kotoba`](../examples/kbb/env_browse_proc.kotoba) | the three non-fs modules in one script: entry count of one directory (`kbb.browse`), whether `HOME` is set (`kbb.env`), exit status of the policy's invocation 0 (`kbb.proc`, `echo`). | `entries * 1000 + (HOME set? 100 : 0) + exit`; the test recomputes `entries` from the fixture dir at run time and asserts required capabilities `[20 33 34]` | `kbb_js_test.clj` |
| [`examples/kbb/no_bb_scan.kotoba`](../examples/kbb/no_bb_scan.kotoba) | **gate item ② first port**: the interpreter gate script `src/no_bb_scan.kotoba` (verify-no-babashka residue scan — name ends `.bb`, name is `bb.edn`, content starts `#!/usr/bin/env bb`) on the compile route; listing walked with `kbb.str/line-count` + `nth-line`. | **3** — same as the interpreter twin, asserted together | `kbb_js_test.clj` |
| [`examples/kbb/shebang_scan.kotoba`](../examples/kbb/shebang_scan.kotoba) | second gate port: `src/shebang_scan.kotoba`'s per-file class (bb-shebang / other-shebang / no-shebang), the interpreter's 3-vector packed as `bb*100 + other*10 + none`. | **122** (↔ `[1 2 2]`) | `kbb_js_test.clj` |
| [`examples/kbb/env_scan.kotoba`](../examples/kbb/env_scan.kotoba) | third gate port: no_bb_scan's three checks over ONE directory named by the env var `KBB_SCAN_DIR` read through `kbb.env` — four library modules in one script (env + browse + fs + str). | **3** for `dirty_dir`, **0** for `clean_dir`; unset → `kbb.env/read` answers `""`, the `""` directory is outside the `:fs/browse` scope, host denies → `:kbb-js/guest-failed` with a `:denied` receipt | `kbb_lib_test.clj` |
| [`examples/kbb/fs_roundtrip.kotoba`](../examples/kbb/fs_roundtrip.kotoba) | the wire-35 WRITE form: write one policy-scoped file through `kbb.fs/write-ok?`, read it back through `kbb.fs/read-bytes-count`, answer the length read back (−1 if the host did not hand back exactly what was written). Scope `test/fixtures/kbb_js_write/out`. | **20** | `kbb_js_write_test.clj` |
| [`examples/kbb/edn_value_read.kotoba`](../examples/kbb/edn_value_read.kotoba) | reading VALUES out of a real EDN file with **no `:data/edn` capability** — bytes via `:fs/app-data`, parsing is computation in `kbb.edn` (a `}` inside a string, a `{` inside a comment and `\{` / `\;` char literals must not move the entry count). | **6272** = `6000` (6 entries) `+ 42` (`:count`) `+ 200` (`:pins` present) `+ 0` (`:missing` absent) `+ 30` (well-formed); not granted → `:kotoba/admission-denied`; granted but out of scope → `:denied` receipt | `scripts/verify-kbb-ports.cljk`; commit `de0880da2` |
| [`examples/kbb/edn_depth_scan.kotoba`](../examples/kbb/edn_depth_scan.kotoba) | superproject `scripts/docs-edn-depth-profile.cljs` ported: end depth of an EDN document honouring escapes, char literals and `;` comments, summed over two fixtures. `:fs/app-data` only, so it runs on **both** JVM-free backends. | **3** on native AND js (nbb original prints end depth `0` + `3`) | `scripts/verify-kbb-ports.cljk`; commit `91c12dc64` |
| [`examples/kbb/store_adoption_scan.kotoba`](../examples/kbb/store_adoption_scan.kotoba) | superproject `scripts/langchain-store-adoption-scan.cljs` ported: buckets `store.cljc` files as adopted / hand-rolled / other, packed `adopted*100 + hand-rolled*10 + other`. Scans ONE flat directory because `:fs/browse` answers names with no is-directory (a stated capability gap). | **121** (nbb original: adopted 1, hand-rolled 2, other 1) | `scripts/verify-kbb-ports.cljk`; commit `91c12dc64` |
| [`examples/kbb/checkout_holds_probe.kotoba`](../examples/kbb/checkout_holds_probe.kotoba) | superproject `scripts/checkout-holds.cljs` ported — the NO_GIT arm (a directory without `.git` must be answered from a listing, not a git call), packed `verdict*100 + git-exit*10 + home?`. The five per-path counts are NOT ported: `:proc/exec` answers an exit status, never stdout. | **201** (nbb original exits 2, `git --version` exits 0, `HOME` set) | `scripts/verify-kbb-ports.cljk`; commit `91c12dc64` |
| [`examples/kbb/git_status_report.kotoba`](../examples/kbb/git_status_report.kotoba) | the capability that had a wire id in the catalog and nothing behind it — `kbb.git` (:git/run, wire 22) runs ONE allowlisted git invocation by grant INDEX and answers `<exit>\n<stdout>`; the write half rides the shipped wire-35 WRITE_SEP form (`kbb.fs/write-file`), and the read-back through the same provider proves the bytes reached the disk. | **112837** = `100000` (ls-files 1 line) `+ 0` (exit 0) `+ 12800` (cat-file exit 128 — a non-zero git exit is information) `+ 15` (15 bytes written) `+ 15` (15 bytes read back) `+ 7` (round-trip equal); not granted → `:kbb-js/compile-failed`; cwd outside the `:git/run` scope or index outside the table → refused at the provider | `scripts/verify-kbb-ports.cljk` |

### Probes (`examples/kbb/probe_*.kotoba`)

Each probe measures one host rule from outside; a guest has no argv, so the
value under test arrives through a granted env name the test sets at run time.

| probe | rule measured | measured answer | executed by |
|---|---|---|---|
| `probe_fuel` | does `kbb --fuel N` reach the compiled module? Self-recursive countdown, empty capability set. | **100** under the host default (amu's 512); under `--fuel 8` the guest traps `fuel-exhausted`. Countdown is 100 not 200 because kotoba-kir's `lower` oracle executes an effect-free entry once at compile time under its own budget (200 failed there as `:kotoba/lowering-failed "fuel-exhausted"`, measured 2026-09-06 on amu ffd9adfa) | `kbb_js_cli_test.clj` |
| `probe_str` | `kbb.str` with NO capability; eight checks, one bit each. | **255** (all eight hold; a zero bit names the failing check) | `kbb_lib_test.clj` |
| `probe_str_oracle` | a PURE module reaching `kbb.str/nth-line` **does not compile** on the amu pin: `ir/lower` constant-folds `main` through the KIR reference interpreter, which has no `string-index-of` case. | refused with `unknown-function`, asserted by its literal so the test goes red the day the interpreter learns the op (would answer 1) | `kbb_lib_test.clj` |
| `probe_env_unset` | `:env/read` of a granted-but-unset name | `""` → `present?` false → **0** | `kbb_js_providers_test.clj` |
| `probe_env_equals` | `:env/read` of a name containing `=`, even when the policy grants that exact string | host refuses (`:denied`) | `kbb_js_providers_test.clj` |
| `probe_env_outside` | `:env/read` of a name the policy does not grant | refused before `getenv` runs; `main` never returns | `kbb_js_providers_test.clj` |
| `probe_fs_via_env` | `:fs/app-data` READ of a path from `KBB_PROBE_PATH` | byte count, or `:denied` for over-limit (65537 bytes → receipt `:bytes 65537 :limit 65536`), a directory, a symlink escaping the scope | `kbb_js_providers_test.clj` |
| `probe_fs_write_via_env` | `:fs/app-data` WRITE of `KBB_PROBE_CONTENT` to `KBB_PROBE_PATH` | bytes written back, or `:denied` for outside-scope, a second `WRITE_SEP`, over 65536 bytes, a directory, a missing parent, a symlink | `kbb_js_write_test.clj` |
| `probe_browse_via_env` | `:fs/browse` of a directory from `KBB_PROBE_DIR` | entry count (5-entry temp dir → 5), or `:denied` for a file or a directory outside the scope | `kbb_js_providers_test.clj` |
| `probe_proc_via_env` | `:proc/exec` by grant index from `KBB_PROBE_INDEX` | exit status, or `:denied` for index out of range / command outside the scope set; `sleep 5` under `:timeout-seconds 1` → `:failed` `ETIMEDOUT` | `kbb_js_providers_test.clj` |

### Library (`lib/kbb/`)

One module per capability; each owns its wire id and typed request/result
shape once, so a script never spells a `typed-cap-call`. Backend column is
what each module's own header states.

| module | wraps | wire id | runs today on |
|---|---|---|---|
| [`kbb.fs`](../lib/kbb/fs.kotoba) | `:fs/app-data` — `read-file` / `read-bytes-count`, and the WRITE form `write-file` / `write-ok?` / `write-bytes-count` (request `<path>WRITE_SEP<content>`, result = content written back; a second `WRITE_SEP` is refused; path + 9 + content must fit the 65536-byte string limit) | 35 | js (`kbb_js_write_test.clj`) and native (amu `kexe_loader.c` `fs_app_data_write_provider`, commit 6cca3852 — per that commit, not run here) |
| [`kbb.env`](../lib/kbb/env.kotoba) | `:env/read` — `read` / `present?`; host narrows by NAME against the policy scope; a granted unset name answers `""` (same contract as the native loader's `env_read_provider`); a name outside the scope is refused before `getenv` | 33 | js (the shim routes only `{:fs/app-data}` surfaces to native — commit 91c12dc64) |
| [`kbb.browse`](../lib/kbb/browse.kotoba) | `:fs/browse` — `entries` (sorted names of one directory, `"\n"`-joined) / `entry-count` | 34 | js; the native loader's wire-34 provider is still the identity stub (ADR-2609051100 task 5) |
| [`kbb.proc`](../lib/kbb/proc.kotoba) | `:process/spawn` — `exec` / `ok?`: ONE allowlisted invocation by grant INDEX (argv, cwd, timeout are policy literals; result is the exit status) | 20 | js; the native loader's wire-20 provider is still pending (ADR-2609051100 task 5) |
| [`kbb.str`](../lib/kbb/str.kotoba) | byte-addressed string helpers — `starts-with?` / `ends-with?` / `line-count` / `nth-line` / `count-matches` — no capability | — (pure) | js runs every export; `amu check lib/kbb/str.kotoba --jvm-free` answers `:ok true` with all five exports. Limit: a PURE module reaching `nth-line` fails to compile (`unknown-function`, see `probe_str_oracle`) |
| [`kbb.edn`](../lib/kbb/edn.kotoba) | reading the STRUCTURE of an EDN document — `entry-count` / `value-of` (source text) / `value-i64` / `has-key?` / `well-formed?` — no capability (parsing is computation, not authority; bytes come from `kbb.fs`) | — (pure) | native and js (asks for nothing the native loader does not already provide) |

## Cross-repo demonstrations

`.kotoba`-built artifacts hosted outside this repo:

| where | artifact | what it demonstrates |
|---|---|---|
| [`kotoba-lang/wasm-webcomponent`](https://github.com/kotoba-lang/wasm-webcomponent) `examples/` | `gcd/gcd.kotoba`, `cap/demo_cap.kotoba` (+ their committed `.wasm`), plus `hello`, `kgraph`, `actor-host` example pages | `kotoba wasm emit` output running on the **browser's native `WebAssembly` engine** as a WebComponent — no JVM, no Chicory, no wasmtime. `kgraph.js` / `actor-host.js` are browser ports of the same host ABIs this repo's tests exercise on Chicory. |
| [`kotoba-lang/kototama`](https://github.com/kotoba-lang/kototama) `test/kototama/fixtures/` | `kotoba-compiled-gen-keypair.kotoba`, `kotoba-compiled-sha256-hex.kotoba` (+ committed compiled `.wasm`) | the E2E proof for ADR-2607062330: real `kotoba wasm emit` binaries (not hand-written WAT) linking against kototama's closed `actor:host` import table and executing correctly under the JVM/Chicory tender (`tender_test.clj`). |
| [`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang) | `examples/hello.kotoba`, `lang/conformance/entry_extensions/main.kotoba` | the language profile's own hello-world and conformance fixtures — the `.kotoba` entry-point contract every launcher must honor. |
| [`kotoba-lang/lab`](https://github.com/kotoba-lang/lab) | `lab.kotoba` | a research-notebook site definition (replayable analysis runs, environment locks, CID artifacts) authored as `.kotoba` data — `.kotoba` as a declarative app-config surface rather than compiled logic. |

## Games

### Authored directly in `.kotoba` (this repo)

| game | source | running demonstration |
|---|---|---|
| **kami-survivors** (survivors-style: ghosts spawn on a ring, chase the player, a periodic nova burst clears the closest) | [`src/kami_survivors.kotoba`](../src/kami_survivors.kotoba) + [`src/kami_survivors_policy.edn`](../src/kami_survivors_policy.edn) (granting the one shared `:kami/engine` capability) | **The first game authored in a `.kotoba` file** — the "natural next demonstration" this page used to end on. Compiled by `kotoba wasm emit` against the `kami-*` host imports (kotoba-core-contracts `"kami/engine"`, id 233: the kami:engine vocabulary exposed through this repo's single `(module "kotoba")` ABI) and hosted by [`src/kotoba/kami_host.cljk`](../src/kotoba/kami_host.cljk) — a **portable** host-owned ECS (fixed-step integration, tick counter, input axes, 32-bit-pair seeded xorshift64, bit-identical on every runtime). Per the repo-wide runtime priority (kotoba wasm > clojurewasm > ClojureScript > nbb; JVM last resort) the canonical non-JVM host path is **ClojureScript**: `scripts/verify_kami_survivors_nbb.cljk` (run: `nbb --classpath src scripts/verify_kami_survivors_nbb.cljk`, no JVM) drives the checked-in `test/kotoba/fixtures/kami_survivors.wasm` for 300 ticks on Node's native WebAssembly engine; `test/kotoba/kami_game_test.cljk` keeps the same run green on Chicory (JVM = compat, not the premise). Both assert exact pinned entity counts (the parity-by-counts method wasm-webcomponent's netsurvivors verification uses) and that the host-owned input axis really steers the player. Every op is capability-guarded: the same binary under a policy without `:kami/engine` is denied on its very first host call. **Also playable in the browser**: wasm-webcomponent's [`examples/kami-survivors`](https://github.com/kotoba-lang/wasm-webcomponent/tree/main/examples/kami-survivors) ships this exact compiled `.wasm` driven per `requestAnimationFrame` on a canvas (arrow keys/WASD → the host-owned axes) via `src/kami-ecs.js` — a hand-JS port of `kotoba.kami-host` whose `verify-kami-survivors.mjs` replays the same 300-tick run on native WebAssembly and asserts the same pinned counts this repo's Chicory test does. |

### Authored in the kotoba-clj subset (kami lineage)

Game logic compiled by the same compiler family also runs today authored in
the **kotoba-clj subset** (`.clj` files restricted to the proven compiler
vocabulary — `defsystem`, `spawn-entity`, `set-velocity!`,
`nearest-tagged`, `tick-n`, …):

| game | source | running demonstration |
|---|---|---|
| **01-netsurvivors** (survivors-style: shiro-pico vs ghosts vs beat-sparks) | `gftdcojp/isekai-network` `games/01-netsurvivors/logic.clj` | compiled `.wasm` is checked into wasm-webcomponent's [`examples/kami-engine-host`](https://github.com/kotoba-lang/wasm-webcomponent/tree/main/examples/kami-engine-host) and ticks live in the browser via `kami-engine-host.js` (14 `kami:engine/*` host imports: scene / input / random / time) — a browser port of `kotoba-lang/kami-script-runtime-rs`. |
| **8 genre base systems** (horror, puzzle, rhythm, single-player, sports, stealth, strategy, superhero) | [`kotoba-lang/kami-genre-base-systems`](https://github.com/kotoba-lang/kami-genre-base-systems) `games/<genre>/logic.clj` (+ `author.clj`, `scene.edn`) | one minimal, honest core-loop archetype per genre, each verified end-to-end through the kami-clj compiler and the `kami-script-runtime-rs` WASM host. |

**kami-survivors runs in the browser too**: `kotoba.kami-host`'s ECS is
ported as wasm-webcomponent's `src/kami-ecs.js` (hand-JS, `kgraph.js` /
`actor-host.js` family), and its `test/verify-kami-survivors.mjs` proves
count-for-count parity between Chicory and the native WebAssembly engine
on the same compiled binary — the same closing-of-the-loop netsurvivors
got from `kami-engine-host.js`.
