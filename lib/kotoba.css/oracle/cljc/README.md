# oracle/cljc — generated .cljc mirror

`../../src/**/*.cljk` copied byte-for-byte to `src/**/*.cljc` by
`scripts/oracle-cljc-mirror.sh` (repository root), for hosts that do not read
the `.cljk` extension: ClojureScript, JVM Clojure, nbb.

- The `.cljk` sources stay canonical. Never edit this tree; rerun the script
  after changing `src/`, and `scripts/oracle-cljc-mirror.sh --check` fails on a
  stale or extra file.
- It sits under `oracle/` because native Kotoba rejects `.clj`/`.cljc`/`.cljs`
  anywhere else (JUN-579). It is not on any native gate, build, CI or runtime
  path, and nothing falls back to it (AGENTS.md "CDCI").
- Consumer: Awai Otehon builds (network-awai ADR 0026 D18), first the
  awai.network studio bundle (AWAI-215), as a git dep with
  `:deps/root "lib/<library>/oracle/cljc"`.
