# sumitsubo actor instructions

Canonical gates, integrations, cells, and dependency pins live in `manifest.edn`
and `repository-contracts.edn`. Do not make Markdown authoritative.

- Preserve the cleanroom boundary: no vendor SDK headers, decompilation, vendored
  samples, or claims of native DWG output.
- Keep the actor's `OP-SCHEMA` aligned with the fixed revision of
  `etzhayyim/com-etzhayyim-sumitsubo-cad` declared in EDN.
- Drawing state is `:dwg.*` Datoms; do not introduce a SQL/vector-store authority.
- Any generative runtime is Murakumo-only and no-server-key.
- Update the SDK repository first when changing the shared ModelOp vocabulary,
  then pin its resulting commit in both canonical EDN files here.

Run the actor suite with `kbb run_tests.cljk`.
