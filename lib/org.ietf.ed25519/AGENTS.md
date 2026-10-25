# AGENTS.md — org-ietf-ed25519

The workspace rules in com-junkawasaki/root `AGENTS.md` apply. CDCI is
stopped. When it restarts, it runs only Amu selfhost and Kotoba native gates.

## CI/CD: no JVM, no nbb

Owner decision 2026-10-22: the JVM and nbb (Node.js) are not used, so they are
not part of CI/CD (Linear JUN-290).

- **Removed:** `.github/workflows/ci.yml` (`clojure -M:test` on JDK 17 and 21)
  was removed on 2026-10-23.
- **Native gate:** the README section "Selfhost (amu, no host crypto)" holds
  it. The pinned amu root compiler builds `kotoba/ed25519/selfhost.kotoba`
  (SHA-512 and Ed25519 in the seed subset) into a loaderless static image.
  The FIPS 180-4 and RFC 8032 vectors must pass, and two negative controls
  must fail. The receipt is `docs/evidence/selfhost-gate-20261023.edn`.
- **Not covered by CI any more:**
  - the `.cljk` library (`src/ed25519/*.cljk`) and its tests
    (`test/ed25519/*_test.cljk`, `test/nbb_smoke.cljk`);
  - the full-dialect guests `kotoba/ed25519/field.kotoba` and `scalar.kotoba`.
  These are migration inventory.
- Do not add `setup-java`, `setup-clojure`, `clojure`, nbb, babashka or
  GraalVM steps to a workflow, and do not keep them as a fallback.
