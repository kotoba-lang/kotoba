# kotoba-lang/kotoba — agent guide

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

## History (short)

- The Rust workspace (`crates/*`: `kotoba-core`, `kotoba-query`/KQE,
  `kotoba-vault`/KSE, `kotoba-runtime`, `kotoba-clj`, `kotoba-server`, …) was
  removed in `60489617` (#259, 2026-07-01). None of its `cargo` commands,
  crate paths or benchmarks exist here any more, and neither do its WIT host
  files — with one exception: the `kotoba:kais` WIT package the Python SDK
  uses to build py→wasm guests survives as `sdk/kotoba-modal/wit/world.wit`
  and its identical packaged copy `sdk/kotoba-modal/kotoba_modal/wit/world.wit`
  (shipped via `pyproject.toml`; CI asserts it is in the wheel). The Rust
  design vocabulary is kept in `docs/HISTORICAL-RUST-ARCHITECTURE.md`; the previous,
  Rust-era version of this file is in git history (`git show 5505040e:CLAUDE.md`).
- KQE (Kotoba Query Engine) is called **`kgraph`** in the current
  implementation (an EAVT graph store with assert/retract, not only queries);
  the canonical datom model lives in `kotoba-lang/datom`, the persistent
  distributed database in `kotoba-lang/kotobase`.
- All Clojure-family sources were renamed to `.cljk` on 2026-09-11
  (ADR-2609111500). `cljk-origin.edn` records each file's pre-rename extension.

## Layout

| path | contents |
|---|---|
| `bin/kotoba` | public launcher; `adl`/`doctor` are routed to JVM-free kbb drivers (`bin/kotoba_adl.cljk`, `bin/kotoba_doctor.cljk`), everything else execs `bin/kotoba-clj` |
| `bin/kotoba-clj` | explicit JVM launcher: `clojure -M -i tools/cljk_loader.cljk -m kotoba.launcher` |
| `bin/kbb`, `bin/kbb_*.cljk` | kbb — deny-by-default script runner (amu-compiled `.kotoba` guests, or `--backend sci` for `.cljk`; `-M:<alias>` resolves `deps.edn` aliases) |
| `src/kotoba/*.cljk` | host implementation: `launcher` (dispatch), `runtime`, `wasm_exec` (Chicory Wasm execution, fuel-bounded), `cap_table`, `host_providers`, adapters (`git_`, `rad_`, `graph_`, `did_`, `deploy_adapter`), `kami_host`, `sensing_host`, `kagi_boundary`, codebase (`codebase_*`, `semantic_codebase`), identity/custody (`principal_*`, `operator_identity`, `passkey_pqc`), security gates (`grade_a`, `key_hierarchy`, `control_adoption`, `crypto_qualification`, `sealed_egress`, `cold_tier_admission`, `anchor_relayer`, `origin_assertion`, …) |
| `src/*.kotoba` + `src/*_policy.edn` | demo / gate programs and their capability policies |
| `cores/` | decision cores moved from host code into Kotoba source (see `cores/README.md`) |
| `lib/kbb/`, `examples/kbb/` | kbb standard library and example scripts (`.kotoba` + policy) |
| `providers/` | host provider consumers/transports (HTTP, DB, Postgres) and their policies |
| `test/kotoba/*_test.cljk` | test namespaces; `test/kotoba/test_runner.cljk` is the aggregate runner; `test/fixtures/` |
| `run-tests.cljk` | the portable (JVM-free) test slice for the kbb/SCI host; see its docstring |
| `qualification/`, `spec/`, `security-adoption.edn` | qualification evidence and policies (EDN) read by the security/qualification gates |
| `resources/` | `kotoba/lang` resources and `repository-rules.edn` (repo role + production git deps) |
| `tools/` | `cljk_loader.cljk` (byte-identical copy from kotoba-lang/kotoba-lang; see `tools/CLJK-COMPATIBILITY.md`), `raw_memory_audit.cljk` |
| `scripts/` | native build/release (`build-native.sh`, `package-native-release.sh`, `verify-release-binary.mjs`), CI runtime setup, `prepare-jvm-analysis.mjs` |
| `vendor/grammar` | committed overlay of kotoba-lang/grammar (`:local/root`) |
| `sdk/kotoba-modal`, `py/` | Python SDK and packages |
| `lexicons/`, `kotoba.words.json`, `kotoba.lock.edn` | ATProto lexicons and word/root registry artifacts |
| `docs/` | ADRs, docs site (`.github/workflows/pages.yml`), `docs/lang/` language profile and gates, `docs/issues/` + `.issues/` issue sources |
| `Formula/`, `install.sh` | Homebrew formula and shell installer |

## Build and test

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

## Rules

### Repository boundary

- New public command shape belongs in `kotoba-lang/kotoba-lang`. Host
  launchers delegate to that CLJC contract; do not add independent command
  semantics here.
- Domain actors/cells live in `etzhayyim/com-etzhayyim-*`; AT Protocol actors,
  PDS/AppView and XRPC application surfaces in `network-awai/app-aozora`; hosting,
  placement, fleet and gateway operations in `kotoba-lang/murakumo`; the
  persistent database in `kotoba-lang/kotobase`; the OS product in
  `kotoba-lang/aiueos`. Reusable libraries get their own `kotoba-lang/<lib>` repo.
- Do not reintroduce a Rust workspace or `crates/` tree.
- No central master node in distributed designs.

### Security posture

- Fail closed: a compiled program has only the authority it was granted (no
  implicit filesystem, network, process, clock, model or secrets); unsupported
  or unverifiable behaviour is refused, never silently downgraded or routed to
  another backend.
- New cryptographic boundaries require the post-quantum floor (hybrid
  X25519 + ML-KEM-768 for confidentiality; ML-DSA-65 alongside the classical
  proof for publication/package admission). No classical-only downgrade.
- Wasm execution is always fuel-bounded (`kotoba.wasm-exec/default-fuel-limit`
  or `:kotoba.policy/fuel`); never add an unbounded execution path.
- Chain integration is read + verify only. Transaction signing, broadcast,
  on-chain settlement and AT-MST origination are **etzhayyim-exclusive**
  (operating-entity boundary) and are not implemented here.
- Do not put non-spec bodies under `com.atproto.*` NSIDs; Kotoba surfaces use
  the `com.etzhayyim.apps.kotoba.*` namespace (`lexicons/`).

### Code and tests

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

## worktree cleanup(定例指示, 2026-06-12)

ユーザーが「worktree cleanup」と指示したら、以下の定例手順として実行する:

1. `git fetch --all --prune` → 全 remote/local ブランチと PR 状態(`gh pr list --state all`)を突き合わせる
2. **PR が無いブランチ**(ローカル main の未 push commit も branch 化して含める)→ 一時 worktree で `origin/main` を merge し衝突解決 → 影響範囲の test/check を実行 → PR 作成 → review → main へ squash merge
3. **PR が MERGED/CLOSED 済みのブランチ → 削除**。ただし tip が PR merge 時刻より後に push されている場合(タイムゾーン正規化して比較)は `git merge-tree --write-tree origin/main <branch>` の結果 tree を `origin/main^{tree}` と比較し、新規内容ゼロ(または main からの回帰のみ = superseded)を確認してから削除。真の新規内容があれば 2 に回す
4. ローカル main を `origin/main` に reset(取り込み済み commit のみ破棄)、一時 worktree を `git worktree remove`、削除済みブランチを `git fetch --prune`

注意: squash-merge 運用のためコミット ID では merge 判定できない — 必ず PR 状態 + content diff で判定する。他エージェントが並行作業中の checkout の dirty tree には触れない(committed 分のみ branch 化して回収)。
