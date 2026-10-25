# Kotoba runner loading mechanics — why a repo reads measurement-impossible

Topic: how kotoba-lang repos' test runners actually load source files and dep coords, and what genuinely unblocks one. Consult when a report says `Ran 0 tests` / `ENOENT`/engine death, but the runner files exist.

## Loader gap rules

- After the `.clj/.cljs → .cljk` rename, a host loads `.cljk` only if THAT host's loader knows the extension.
  - cognitect `test-runner` (v0.5.1) does not scan `.cljk` → `clojure -M:test` prints “Ran 0 tests containing 0 assertions” while the files exist; **`0 tests` is not a pass**.
  - babashka/nbb (`run-tests.cljk`, `run_portable.cljk`, kernel verifier) does not load `.cljk` → `ENOENT`.
- That gap is deliberately not mirrored; the fix lives on the loader/host side (the `nbb-run-tests.cljs` entry `IS the nbb runtime` and moves with the test-host migration; an engine-side nbb-compat shim owns `clojure.java.io` resolve failures). Nothing repo-side alone clears it; do not treat “swap the launch string” as a fix.
- **JVM runner is effectively dead under the rename**: `clojure -M:test` cannot scan `.cljk` at all.

## Engine/coord loading rules (kbb)

- kbb's nbb engine reads `nbb.edn` and NOT `deps.edn`; a `:local/root` coordinate declared only in `deps.edn` is not resolvable → death before the runner: `kbb: N dep(s) … NOT on the classpath`, `Could not find namespace: <own src namespace>`.
- `kbb` prints its own substitution banner (“running N namespace(s) with cljs.test”) because alias-named JVM runners (test-runner/kaocha/eftest) are replaced with its cljs.test scan.
- Symbol-level failures follow coords: a JVM-only core fn (e.g. `byte-array`) is `Unable to resolve symbol` on a cljs-side runner.
- Count shrinkage after a host swap is a REAL difference to cause-identify (kbb runs fewer than the old JVM count: JVM-only tests legitimately fall out), not a false pass.
    - No `deps.edn` at all → `kbb: no deps.edn … aliases :test cannot be resolved here` (EXIT 66) = honest N/A, not failure.

## The unblock recipe that worked

Copy the repo's `deps.edn` coordinates for superproject libs + `test-runner` coordinate into the repo's own `nbb.edn`. The first repo to do this then ran `kbb -M:test` identically to its prior JVM baseline counts. Repeat this per repo (its OWN src namespace + `text` + sibling codec libs), one repo per attempt.

`nbb.edn` example shape/note: “kbb reads nbb.edn, not deps.edn — copy coords here” so the engine resolves `:local/root`.

Verify-command forms: `(cd <abs-repo> && kbb -M:test)` under subshell cd only; kernel host via `kbb --backend sci --classpath scripts scripts/verify-<…>.cljk --amu <dir>`.

---
# 补齐蒸馏: 此ファイルは診断表 + 復活レシピ、勿 paste transcript.

结局凡例整合:
- 0 tests / ENOENT = 測不能 ≠ pass.
- 単一根 = repo 側 nbb.edn 不在 (coords 未解決), not harness loader.
- 実測基準: preserve prior real JVM baseline.
