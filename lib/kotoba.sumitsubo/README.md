# sumitsubo 墨壺

Cleanroom CAD modeling and drafting actor. Canonical actor identity, gates, cells,
and SDK pin are defined in [`manifest.edn`](manifest.edn). Repository boundaries
are defined in [`repository-contracts.edn`](repository-contracts.edn).

The reusable TypeScript geometry and format-interoperability surface lives in the
independent [`com-etzhayyim-sumitsubo-cad`](https://github.com/etzhayyim/com-etzhayyim-sumitsubo-cad)
library. This repository owns the actor-specific ModelOp planning, Datom emission,
cell definitions, lexicons, schema, and seed data.

```bash
kbb run_tests.cljk
```

Deployment is operator-gated and described canonically by
[`kotoba/deploy.edn`](kotoba/deploy.edn); it is not an executable shell script.
