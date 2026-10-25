# AGENTS.md — org-oci-distribution

The workspace rules in com-junkawasaki/root `AGENTS.md` apply: CDCI is
stopped, and when it restarts it runs Amu selfhost and Kotoba native gates only.

## CI/CD: no JVM, no nbb

Owner decision 2026-10-22: the JVM and nbb (Node.js) are not used, so they are
not part of CI/CD (Linear JUN-290). `.github/workflows/ci.yml` (nbb tests on Node with a
kotobase checkout) was removed.

- Do not add `setup-java`, `setup-clojure`, `clojure`, nbb, babashka or
  GraalVM steps to a workflow, and do not keep them as a fallback. A check that
  needs something the native route cannot do yet is a blocker to record in
  Linear, not permission to bring a host runtime back.
- A native gate is an Amu selfhost build: the pinned root compiler
  (kotoba-lang/amu `seed/bootstrap/aarch64-linux-static-root.elf`) compiles a
  Kotoba module in the seed subset into a loaderless static image whose result
  is checked, together with a negative control that must fail.
- `kotoba/oci/itonami_artifact.kotoba` has a native gate: the README
  "Kotoba decisions" block (`:result 31`, negative control `23`; receipt
  `docs/evidence/itonami-artifact-selfhost-gate-20261022.edn`).
  `kotoba/oci/reference.kotoba` does not build with the pinned root compiler
  yet (`E2104`, amu `f5b11a08`, 2026-10-22).

### What CI no longer covers

The `.cljk` server tests (`bin/run_tests.cljk`) ran only on nbb. They are
migration inventory (JUN-290) and are not run by CI.
