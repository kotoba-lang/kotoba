# `sys_adr_corpus_persist` cell

Elevates the `kotoba` content-addressed monorepo projection to Phase R2.
Reads the static NDJSON quad stream generated in Phase R1 (`kotoba-quads.ndjson`) and persists it into the live kotoba EAVT datom log.

Executes using `kotoba-wasm` node bindings and `kotodama` orchestration, running exclusively on the Murakumo fleet.

**References**:
- ADR-2606071800 (Phase R2 ADR corpus persistence)
- ADR-2605281700 (R0 schema)
- ADR-2605281800 (R1 ingest tool)
