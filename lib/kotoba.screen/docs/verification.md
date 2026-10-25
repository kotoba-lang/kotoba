# screen verification evidence (2026-09-03, M4 aarch64 / macOS 26.4)

## Toolchain

- amu worktree at pin `kotoba-lang/main` = `5bc77ef3` (Merge #766) with
  `kotoba-sema` advanced to `219f14f7` (adds `:screen/observe` 31 and
  `:screen/act` 32) and `resources/kotoba/lang/{guest-grammar,capability-catalog}.edn`
  re-synced from `kotoba-lang/kotoba-lang` main.
- Loader + runtime measurement from `amu measure-runtime`
  (`runtime-sha256 3e33c6f1…`, loader at `/tmp/kotoba-loader`).

## Checks (all measured, not asserted)

1. `amu check --jvm-free` per module: **rect / tree / diff / intent / guest
   all `{:ok true}`**. `guest` carries `(:capabilities #{:screen/observe})`
   and compiles only with a policy allowing `[:cap/call 31]` — the
   deny-by-default policy gate works.
2. Project route: `amu check` on an entry requiring all five modules with
   `--source-path src` — `{:ok true}`; also `amu compile --target aarch64`
   → `screen.kexe` emitted with provenance + publication EDN.
3. **Golden vectors 17/17** (`:status :ok :result 17 :verify :pass`):
   closed graph compiled with `kotoba.compiler/compile-project`, signed with
   a fresh Ed25519 keypair, executed through
   `kototama.native.executor/execute` (aarch64, measured loader,
   `:trusted-runtime-sha256` pinned). Driver: `host/verify.cljk`.

## Known upstream gap (not screen-specific)

`amu extract-native` on amu main rejects the artifact with
`:kotoba/verification-failed "native export table rejected"` — bisected by
upstream ADR 0288 to a `kotoba-mir` pin, and the same failure reproduces on
a minimal recursive-pair program with no screen code at all. The signed
execution path through `kototama-native` verifies fine, so the library is
not blocked; flagging the extract path for the owner.

## Language constraints the library encodes (measured)

- Native ABI caps a function at 5 parameters → rects are a 4-field record
  passed as one argument.
- `mod` has no lowering in this profile → written as
  `(- x (* m (quot x m)))` (division is `quot`; `/` is float-only).
- `(= xs 0)`-terminated legacy i64 pair chain is the walkable sequence;
  `[:list T]` has no accessors and `[:vector T]` is the bounded literal.
- Docstrings are not yet admitted in defn position → kept as `;;` comments.
- A namespace may not export a plain `def`; exports are functions only.
- Declared-but-unused capabilities are refused — declare what you use.
