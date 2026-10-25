# AGENTS.md — org-ietf-jcs

The workspace rules in com-junkawasaki/root `AGENTS.md` apply. CDCI runs only
Amu selfhost / Kotoba native gates; the JVM and nbb are not used (Linear
JUN-290).

## CI removed (2026-10-23)

- `.github/workflows/ci.yml` was removed. It installed Java 21 (setup-java)
  and the Clojure CLI (setup-clojure) and ran `clojure -M:test` and
  `clojure -M:lint`. It is not kept as a fallback.
- **No longer covered by CI:** the `.cljk` canonicalizer's suite
  (`test/jcs/core_test.cljk`, `test/nbb_smoke.cljk`). It stays as corpus.
  Porting the canonicalizer to `.kotoba` remains open.
- **Native gate, run locally, not CDCI:** `kotoba/jcs/reader.kotoba`. The
  README section "Reading in a static image" describes it, and its receipt
  is `docs/evidence/reader-gate-20261023.edn`.
