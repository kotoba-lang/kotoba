# Kotoba native migration

## Product and measurement language

Introduce Kotoba as the language at the heart of a modern Lisp machine in
development, inspired by Lisp's programs-as-data and composable forms. Amu
owns native compilation; Kototama owns the execution contract and AIUEOS the
OS direction. Do not describe the full machine or live development as shipped
without evidence for that capability and host.

The 2026-10-15 M4 observation measured translated Kotoba ports at 0.80× C
execution time across 19 Embench workloads, using one compiler snapshot and
one sample per workload. The measured path includes audited algorithm
substitutions. This is not a released-toolchain result, certified score, or
universal speed or safety ranking. Keep that boundary next to the comparison:
https://kotoba-lang.org/blog/embench-c-parity-20261015/.

Use the Kotoba Labs Linear workspace. This migration is tracked by AWAI-24,
AWAI-43, AWAI-48 and JUN-290. Workspace architecture and authority rules apply.

## CDCI

Use Amu selfhost and canonical Kotoba only. Do not restore CLJK/CLJC, NBB,
KBB, Clojure, JVM/Java, GraalVM, Node or a C compiler/loader as a CI prerequisite
or fallback. Python scripts may stage/hash bytes and observe native processes;
they must not implement language resolution, compilation or verdicts.

The 2026-10-24 replacement removes the JVM/Node launcher job and the macOS C
loader toolchain. Original definitions/scripts are byte-preserved as inert
text under `docs/retired/native-ci-20261024/` with their hashes. Do not execute
these archives. The static documentation Pages workflow remains separate.

Current native CI checks the pinned loaderless Amu root, combined selfhost,
all12 CLI request parsing with all declared flags/aliases and refusals, and
the Amu/Kotoba native controller on an actual x86 Linux runner. The controller
qualifies its declared complete24 Kotoba corpus, not this product's whole CLI.
All native guests run without a hosted language executable in their PATH.

The public launcher still contains retired host routes. Do not run them.
All12 command execution, package/signature admission, general FS fault/race
parity, public target parity and the old library/runtime-value oracle corpus
remain open until ported and qualified. A green request-parser or controller
job must not mark these acceptance criteria Done. Legacy JVM/JS lint, Q9,
runtime-values, SDK packaging, library and package admission jobs no longer
run in CI; preserve their fixtures while porting their checks to native code.

## Local reference oracle (owner decisions 2026-10-29 to 2026-11-07, JUN-579 / JUN-588)

The CDCI rule above is unchanged for prerequisites and fallbacks. A reference
oracle is a separate thing: it produces reference values (KIR, Definition
CIDs, outputs) when porting a construct or checking cljk/edn-sugar against pure
`.kotoba`. It is not proof that the native result is correct; a mismatch is
reported, not forced to agree.

- Oracle languages: nbb, JVM, C, Python, Basilisp, jank and Fennel, plus every
  language that supports `.cljc` (Clojure, ClojureScript, ClojureCLR, Babashka,
  Squint, Cherry, ClojureDart, Clojerl, Lokke, Phel and others). Hy was replaced
  by Basilisp on 2026-11-07. The candidate table is unverified; see
  `docs/oracle-cljc-dialects-20261107.md` in kotoba-lang/kotoba-lang, and
  confirm tool version, feature key and `.cljc` handling at first use.
- Record the exact command, tool versions, inputs and outputs as dated data.
- CI exception (owner decision 2026-11-07): JVM, nbb, Babashka and every other
  `.cljc`-capable language above may run in CI as separate oracle jobs, named and
  reported as oracle. Native build, gates, packaging and runtime do not depend on
  them, nothing falls back to them, and an oracle job is not a required check
  until the owner decides. Any other CI use of JVM, nbb, Babashka and GraalVM
  stays banned (JUN-290). The oracle languages that do not read `.cljc` (C,
  Python, Fennel) run on a developer machine, one-off.
- CLJK stays as a reference oracle source and is treated as CLJC-equivalent
  for oracle runs: `#?(:kotoba …)` selects the Kotoba branch, `#?@` is not
  read, and an oracle is handed the source as `.cljc`. The route stays
  `.kotoba`; native input rules are unchanged and native `.cljc` acceptance is
  not pursued. Where the code disagrees, the code is the state and the
  disagreement is reported.
- Policy and plan: ADR `adr-2611071200-cljk-oracle-cljc-standard` (com-junkawasaki/root `90-docs/adr/`), tracked in
  Linear JUN-579 and JUN-967 to JUN-973. cljk sources follow standard cljc; cljc itself is not customised. Moving
  the `:kotoba/*` namespace attribute-map keys to a quoted spelling (JUN-967 to JUN-969) is a plan, not yet
  implemented; until then a JVM run stops on `{:kotoba/export [...]}`.
- Before a selfhost refactor of a cljk component, take its reference values
  first from the JVM and node (nbb) oracles.

## AIUEOS UEFI image gate (JUN-709)

Owner decision 2026-11-01: the AIUEOS image CI job lives in this repository.
kotoba-lang/aiueos dropped its image CI in #491 and has had no `os/` tree since
#536, so the `aiueos-uefi` job in `native-shared.yml` is the only CI that builds
and boots `lib/kotoba.aiueos`. It runs on push to main, the nightly schedule and
workflow_dispatch, not on pull requests (PR tiering is JUN-629), on
`ubuntu-24.04-arm`: `scripts/fetch-native-amu.sh`, Zig 0.15.2 from ziglang.org
checked against its sha256, apt `qemu-system-x86` and `ovmf`, `build-uefi.sh`,
`smoke-qemu-uefi.sh` (default profile, `AIUEOS_UEFI_SMOKE_OK`), `smoke-qemu-multiboot.sh`
(the `build-multiboot.sh` link and a QEMU multiboot boot), and a negative
control (`AIUEOS_CORRUPT_KERNEL=1`: the loader must refuse with
`AIUEOS_LOADER_FAIL kernel-sha256` and the success marker must be absent).
The native generators run with seccomp enforced (`AIUEOS_NATIVE_SECCOMP` unset).
The image sha256 lines, the plain-build images, timings and the host record are
uploaded as `aiueos-uefi-linux-arm64`.

The image bytes depend on the Zig build: the official ziglang.org 0.15.2 gives
the same KERNEL.ELF/BOOTX64.EFI on the runner, linux/arm64 podman and macOS
arm64, while Homebrew's zig 0.15.2 gives different bytes. Compare hashes only
against the official build. Not covered: the `AIUEOS_PLC_RT_SMOKE=1` profile
(its program builder `build-plc-native-program.sh` needs the macOS Amu root),
the GRUB multiboot smoke, the x86_64 Linux host build, release media and
physical hardware.

## JUN-93 shared native text

The canonical text owner is lib/kotoba.text; kotoba-lang/text is archived.
Maintain the immutable imports and explicit local-changes source/addition
hashes. Extend the existing loaderless native CI; retain its CLI request and
controller gates. Shared component goldens do not qualify the whole library
catalog, public CLI execution or the P4 desktop.

Native text keeps Unicode whitespace excluding U+00A0/U+2007/U+202F, ASCII
lower preserving non-ASCII, and an empty needle matching every string.
Do not alias the differently named ASCII whitespace/UTF-8 byte-index kernels
to full text APIs. Native index-of retains UTF-16/option semantics and both arities; join takes
typed string lists and preserves empty fields. CSSOM capture regex and full
Unicode case remain distinct qualification requirements. Preserve all graph declarations.

The native-shared workflow now executes the current owner fixture on both native
ARM and x86 Linux using an immutable Amu commit and pinned shared dependencies.
It hashes the actual compiler image, locks all discovered source bytes and
preserves Kotoba verdicts/refusals as artifacts. Its bounded result does not
restore the uncovered legacy full host suite or qualify the P4 desktop.

## Repository guide (merged from CLAUDE.md, which is no longer used)

This repository is the **installable Kotoba CLI and host implementation**: the
`kotoba` launcher, capability host, host adapters, package/release admission,
and the security-assurance ("Grade A") gates. Kotoba source is compiled through
[`kotoba-lang/amu`](https://github.com/kotoba-lang/amu) (frontend/KIR, Wasm and
native backends), pinned in `deps.edn`. The language and public CLI contract
(`lang/cli.edn`, conformance fixtures) is owned by
[`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang); this
repo implements it.

User-facing overview, install paths and the command tour are in `README.md`.
Repository split policy: `docs/ADR-repository-boundaries.md`.

### History (short)

- The Rust workspace (`crates/*`: `kotoba-core`, `kotoba-query`/KQE,
  `kotoba-vault`/KSE, `kotoba-runtime`, `kotoba-clj`, `kotoba-server`, …) was
  removed in `60489617` (#259, 2026-07-01). None of its `cargo` commands,
  crate paths or benchmarks exist here any more, and neither do its WIT host
  files. The remaining Python SDK/WIT packaging assets were retired in
  JUN-198 because their Python implementation and tests were already absent.
  The Rust
  design vocabulary is kept in `docs/HISTORICAL-RUST-ARCHITECTURE.md`; the previous,
  Rust-era version of this file is in git history (`git show 5505040e:CLAUDE.md`).
- KQE (Kotoba Query Engine) is called **`kgraph`** in the current
  implementation (an EAVT graph store with assert/retract, not only queries);
  the canonical datom model lives in `kotoba-lang/datom`, the persistent
  distributed database in `kotoba-lang/kotobase`.
- All Clojure-family sources were renamed to `.cljk` on 2026-09-11
  (ADR-2609111500). `cljk-origin.edn` records each file's pre-rename extension.

### Layout

| path | contents |
|---|---|
| `bin/kotoba` | public launcher; `adl`/`doctor` are routed to JVM-free kbb drivers (`bin/kotoba_adl.cljk`, `bin/kotoba_doctor.cljk`), everything else execs `bin/kotoba-clj` |
| `bin/kotoba-clj` | explicit JVM launcher: `clojure -M -i tools/cljk_loader.cljk -m kotoba.launcher` |
| `bin/kbb`, `bin/kbb_*.cljk` | kbb — deny-by-default script runner (amu-compiled `.kotoba` guests, or `--backend sci` for `.cljk`; `-M:<alias>` resolves `deps.edn` aliases) |
| `src/kotoba/*.cljk` | host implementation: `launcher` (dispatch), `runtime` (step-bounded interpreter), `kbb_native` (host-native KEXE compile and measured-loader execution, also behind `compile --run` for the host native target), `wasm_exec` (Chicory Wasm execution, fuel-bounded; Wasm is one target), `cap_table`, `host_providers`, adapters (`git_`, `rad_`, `graph_`, `did_`, `deploy_adapter`), `kami_host`, `sensing_host`, `kagi_boundary`, codebase (`codebase_*`, `semantic_codebase`), identity/custody (`principal_*`, `operator_identity`, `passkey_pqc`), security gates (`grade_a`, `key_hierarchy`, `control_adoption`, `crypto_qualification`, `sealed_egress`, `cold_tier_admission`, `anchor_relayer`, `origin_assertion`, …) |
| `src/*.kotoba` + `src/*_policy.edn` | demo / gate programs and their capability policies |
| `cores/` | decision cores moved from host code into Kotoba source (see `cores/README.md`) |
| `lib/catalog.edn`, `lib/kotoba.*`, `src/kotoba/library_source.cljk` | bundled dotted-ID sources, language-owned alias resolution, explicit SCI source imports |
| `lib/kbb/`, `examples/kbb/` | kbb standard library and example scripts (`.kotoba` + policy) |
| `providers/` | host provider consumers/transports (HTTP, DB, Postgres) and their policies |
| `test/kotoba/*_test.cljk` | test namespaces; `test/kotoba/test_runner.cljk` is the aggregate runner; `test/fixtures/` |
| `run-tests.cljk` | the portable (JVM-free) test slice for the kbb/SCI host; see its docstring |
| `qualification/`, `spec/`, `security-adoption.edn` | qualification evidence and policies (EDN) read by the security/qualification gates |
| `resources/` | `kotoba/lang` resources and `repository-rules.edn` (repo role + production git deps) |
| `tools/` | `cljk_loader.cljk` (byte-identical copy from kotoba-lang/kotoba-lang; see `tools/CLJK-COMPATIBILITY.md`), `raw_memory_audit.cljk` |
| `scripts/` | native build/release (`build-native.sh`, `package-native-release.sh`, `verify-release-binary.mjs`), CI runtime setup, `prepare-jvm-analysis.mjs` |
| `vendor/grammar` | committed overlay of kotoba-lang/grammar (`:local/root`) |
| `lexicons/`, `kotoba.words.json`, `kotoba.lock.edn` | ATProto lexicons and word/root registry artifacts |
| `docs/` | ADRs, docs site (`.github/workflows/pages.yml`), `docs/lang/` language profile and gates, `docs/issues/` + `.issues/` issue sources |
| `Formula/`, `install.sh` | Homebrew formula and shell installer |

### Build and test

The required native gate builds three compiler generations and executes the
19-module runtime fixture with hosted language executables denied. Its scope
and remaining public CLI/build migration are explicit in
[`docs/native-cli-migration.md`](docs/native-cli-migration.md). The CLJ commands
below remain bootstrap/compatibility diagnostics; their passing result is not
native/selfhost qualification.

```bash
# public CLI from a source checkout (same as the installed `kotoba`)
bin/kotoba check --kind cli-contract --json

# JVM aggregate suite via kotoba.test-runner (CI "Test CLJ launcher")
clojure -M:test

# portable kbb/SCI slice (incl. kotoba.kbb-deps-test, which is SCI-only)
kbb --backend sci --classpath src:test run-tests.cljk

# Q9 backend-qualification report
clojure -M:qualification

# shared security adoption + lint (both read the generated .jvm-analysis copy)
node scripts/prepare-jvm-analysis.mjs
clojure -M -i tools/cljk_loader.cljk -e "(require 'kotoba.security.adoption) (kotoba.security.adoption/verify! \".jvm-analysis\")"
clojure -M:lint

# package admission smoke (positive lock must pass)
bin/kotoba-clj package verify --lock test/fixtures/package/positive-lock.edn --trust test/fixtures/package/trust.edn --json
```

Other `deps.edn` aliases: `:dev` (sibling `:local/root` overrides, e.g.
`../../kotoba-lang/amu`), `:build` (`build.cljk` uberjar, `-T` tool alias), `:release-tag`,
`:reproducible-emit`, `:raw-memory-audit`, and the security checks
`:grade-a-check`, `:grade-a-attest`, `:crypto-check`, `:threat-model-check`,
`:supply-chain-check`, `:key-hierarchy-check`, `:control-adoption-check`,
`:vulnerability-response-check`. Native binary: `scripts/build-native.sh`
(needs GraalVM `native-image`). **Known broken since the `.cljk` rename:** its
`kbb -T:build uber` step cannot run tools.build (kbb's engine loads no Maven
jars), `clojure -T:build uber` cannot find the `build` namespace in
`build.cljk`, and tools.build's `compile-clj` cannot AOT-load `.cljk` sources.
The last native release (`native-release.yml`) is v0.7.2 (2026-08-17).

Some tests resolve evidence paths in sibling checkouts; CI sets
`KOTOBA_LANG_AUTHORITY_ROOT`, `KOTOBA_COMPILER_EVIDENCE_ROOT` and
`KOTOTAMA_EVIDENCE_ROOT` and clones the siblings (see `.github/workflows/ci.yml`).
`kbb` needs the `kotoba-lang/org-babashka-nbb` engine as a sibling checkout or
via `KBB_ENGINE`.

### Rules

#### Repository boundary

- New public command shape belongs in `kotoba-lang/kotoba-lang`. Host
  launchers delegate to that CLJC contract; do not add independent command
  semantics here.
- Domain actors/cells live in their own repositories (see
  `docs/ADR-repository-boundaries.md`); AT Protocol actors,
  PDS/AppView and XRPC application surfaces in `network-awai/app-aozora`; hosting,
  placement, fleet and gateway operations in `kotoba-lang/murakumo`; the
  persistent database in `kotoba-lang/kotobase`; the OS product in
  `kotoba-lang/aiueos`. The standard-library pilot (`coll/spec/json`) lives
  under `lib/kotoba.*` here; see
  `docs/ADR-kotoba-library-monorepo-and-lexicon-events.md`. Other libraries
  are grouped or separated by maintenance/release boundaries. A definition's
  content identity does not require its own physical repository.
- Do not reintroduce a Rust workspace or `crates/` tree.
- No central master node in distributed designs.

#### Security posture

- Fail closed: a compiled program has only the authority it was granted (no
  implicit filesystem, network, process, clock, model or secrets); unsupported
  or unverifiable behaviour is refused, never silently downgraded or routed to
  another backend.
- New cryptographic boundaries require the post-quantum floor (hybrid
  X25519 + ML-KEM-768 for confidentiality; ML-DSA-65 alongside the classical
  proof for publication/package admission). No classical-only downgrade.
- Every execution path — native, interpreter and Wasm — is fuel- or
  step-bounded; never add an unbounded execution path. Examples: native KEXE
  artifacts carry a declared `:fuel` in their fuel ABI and run under the
  measured loader; the interpreter is bounded by
  `kotoba.runtime/default-interpreter-step-limit` or
  `:kotoba.policy/interpreter-step-limit`; Wasm execution is fuel-bounded by
  `kotoba.wasm-exec/default-fuel-limit` or `:kotoba.policy/fuel`.
- Chain integration is read + verify only. Transaction signing, broadcast,
  on-chain settlement and AT-MST origination belong to the operating entity
  (operating-entity boundary) and are not implemented here. One exception:
  the hosted session's Torihiki app signs devnet / demo orders with a
  throwaway session key and sends them only after per-operation approval
  (ADR-0284, `lib/kotoba.aiueos`); real-money settlement and custody stay out
  of scope.
- Do not put non-spec bodies under `com.atproto.*` NSIDs; Kotoba surfaces use
  the namespace declared in `lexicons/`.

#### Code and tests

- New Clojure-family source is `.cljk`. Keep `tools/cljk_loader.cljk`
  byte-identical to its kotoba-lang/kotoba-lang origin.
- Every test namespace must be listed in `test/kotoba/test_runner.cljk` —
  in both the `:require` and the `run-tests` call — otherwise it never runs
  (`kotoba.test-runner-completeness-test` enforces this). SCI-only namespaces
  (currently `kotoba.kbb-deps-test`) are exempted there and run only from
  `run-tests.cljk`; other portable tests also go in `run-tests.cljk`.
- Dependencies are immutable `:git/sha` pins. `nbb.edn` copies its `:paths`
  and shas from `deps.edn`; change both together. Production git deps must
  match `resources/repository-rules.edn` `:depends-on`.
- `bin/kotoba-clj wasm emit|run … --json` lines in `docs/lang/README.md` and
  `docs/lang/gates.md` are executed by `kotoba.doc-examples-test`; keep them
  runnable.

### worktree cleanup(定例指示, 2026-06-12)

ユーザーが「worktree cleanup」と指示したら、以下の定例手順として実行する:

1. `git fetch --all --prune` → 全 remote/local ブランチと PR 状態(`gh pr list --state all`)を突き合わせる
2. **PR が無いブランチ**(ローカル main の未 push commit も branch 化して含める)→ 一時 worktree で `origin/main` を merge し衝突解決 → 影響範囲の test/check を実行 → PR 作成 → review → main へ squash merge
3. **PR が MERGED/CLOSED 済みのブランチ → 削除**。ただし tip が PR merge 時刻より後に push されている場合(タイムゾーン正規化して比較)は `git merge-tree --write-tree origin/main <branch>` の結果 tree を `origin/main^{tree}` と比較し、新規内容ゼロ(または main からの回帰のみ = superseded)を確認してから削除。真の新規内容があれば 2 に回す
4. ローカル main を `origin/main` に reset(取り込み済み commit のみ破棄)、一時 worktree を `git worktree remove`、削除済みブランチを `git fetch --prune`

注意: squash-merge 運用のためコミット ID では merge 判定できない — 必ず PR 状態 + content diff で判定する。他エージェントが並行作業中の checkout の dirty tree には触れない(committed 分のみ branch 化して回収)。
