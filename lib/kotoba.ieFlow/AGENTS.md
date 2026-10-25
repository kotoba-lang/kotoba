# IE-flow shared-library rules

- `library.edn` is canonical repository metadata.
- Keep metrics, gates, lifecycle, ledger, and control actor-neutral and deterministic.
- `etzhayyim.ie-flow.scoreboard` is deliberately excluded: it imports concrete actors and belongs
  to a cross-repository governance/runtime application.
- `kotoba.datom` is a SHA-pinned dependency. Do not restore root classpaths.
- Run `./run_tests.sh` from a standalone checkout.
