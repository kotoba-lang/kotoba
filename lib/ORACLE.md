# Official path and oracles for `lib/` packages

Owner decision, 2026-10-25.

- **Official CD/CI path:** Amu selfhost and Kotoba native. A package is qualified by that path only.
- **Oracle:** every other runner — JVM (`clojure`, Maven artifacts), Node (`nbb`, `kbb --backend sci`), cross-check implementations such as hashlib or OpenSSL. An oracle compares behaviour; its result is evidence, never the gate, and nothing in a package may depend on it.
- **Sources:** `.cljk` and `.cljc` stay. JVM-only sources are not carried into new imports.
- **Dependencies:** `deps.edn` of a package names no Maven coordinates and no JVM-only alias (`clj-kondo`, `cognitect test-runner`, `cloverage`, `shadow-cljs`, …). The `:kotoba` alias (Amu compiler) stays. Each removal is recorded in the package's `local-changes.json`.
- **Registry:** suites registered as `jvm-only` in `test-suites.json` are oracle suites. They are kept as files and as registry rows so the provenance check keeps passing, but they are not run by the official path; retiring them is a separate change together with `scripts/run-library-jvm-tests.cljk` and the Node checks.
- **Not changed here:** the repository's root `deps.edn` and launcher (`bin/kotoba-clj`), CI workflow definitions, and the Node check scripts.
