# Agent rules

## Kotoba migration is whole-component and JVM-free

The repository authority is `qualification/q9-whole-component-build.edn` and
the accepted decision is `docs/adr/0012-whole-component-kotoba-migration.md`.

- `kototama.leash` and `kototama.unspsc.life` migrate as complete components,
  including every public var/function and the transitive source closure. Do
  not create `*_decision.cljk` or count a predicate-only port as migration.
- Native mechanisms cross only declared capability/provider imports. A
  missing JVM-free backend feature blocks the component; it does not reduce
  the migration unit.
- Every target must pass the verified native Kotoba CLI and Amu
  `check`/`compile --jvm-free`, with equivalent payload/definition CIDs,
  exports, imports, effects and resource bounds.
- Q9 tests and parity use nbb/CLJS, native, Wasm or content-addressed golden
  vectors. They must not require `java`, `javac`, `clojure` or `clj`.
- The JVM/Chicory tender remains an explicit compatibility/diagnostic surface
  only. It cannot authorize cutover, source deletion, soak or deployment.


## Claude 向け追記（旧 CLAUDE.md より統合）

Kototama Q9 work moves complete components and must build
without a JVM through native `kotoba` and Amu `--jvm-free`. Decision-only
`.cljk` files and JVM-backed acceptance are forbidden; block on missing
tooling instead of falling back.
