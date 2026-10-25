# Maturity

**Level: R2 live adapter**

Implemented:
- Append-only EDN line codec (`encode` / `decode`), newline-safe by `pr-str` escaping.
- Stream multiplexing and `:tx`-exclusive `since` filtering over one sink.
- Host event-log operation map (`:append` / `:read`) consumed by `langchain.persist/scoped`.
- Sink boundary validation.
- In-memory sink.
- JVM file sink: lock-serialized appends, parent directory creation.
- ClojureScript/Node file sink: `appendFileSync`, parent directory creation, `require` resolved on use.
- Contract tests for round-trip ordering, stream isolation, `since` exclusivity, append-never-rewrites, newline-in-value, blank-line tolerance, empty journal, sink rejection.
- JVM tests for restart recovery and 50-thread append contention.
- Integration tests against `langchain.db`: replay rebuild, upsert/retraction fidelity across replay, two conns over one sink, and the append-only secret-retention hazard.

Not yet R2:
- None.

Deliberately out of scope:
- Compaction, rotation, and truncation. A journal that rewrites is no longer a journal; a caller that needs bounded size should snapshot into a second store and start a new journal, which is a decision only the caller can make.
- Encryption at rest. See the append-only note in the README: the answer for secrets is not to journal them.
