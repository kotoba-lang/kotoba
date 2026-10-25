# langgraph-store

Two small storage primitives every JVM `langgraph-clj` app needed
identically:

- `langgraph-store.blob` — a content-addressed blob store (protocol +
  in-memory/filesystem impls) for offloading generated images/media out of
  the datom store (a datom holds a short content key, not megabytes of
  base64).
- `langgraph-store.checkpoint` — a latest-only `langgraph.checkpoint/
  Checkpointer` over a `langchain.db` conn. `langgraph.checkpoint`'s own
  `datomic-checkpointer` keeps every superstep forever (O(T²) storage for a
  T-turn conversation that holds cumulative message state); this one keys
  by thread alone and upserts, bounding storage to O(threads × current
  state) — the shape every consumer that only resumes (never time-travels)
  actually wants.

Extracted from `mangaka.{blob,checkpoint}` / `animeka.{blob,checkpoint}`
(`orgs/gftdcojp/ai-gftd-mangaka`, `orgs/gftdcojp/ai-gftd-animeka`), which
were byte-identical copies of each other. `comfyui.gateway` (in
`kotoba-lang/comfyui`) and `langchain.jvm` (in `kotoba-lang/langchain`) are
this extraction's siblings — the app-scaffolding that *was* bundled
alongside these two in a short-lived `kotoba-lang/genapp-clj`, split out to
their natural homes next to the pure engines they wire. See
`90-docs/adr/2607011816-ghosthacker-shiropico-standalone-repo.md` and
`90-docs/adr/2607011900-genapp-clj-mangaka-animeka-commons.md` in the
`com-junkawasaki/root` superproject for the full history.

## Test

```bash
kbb -M:dev:test
```
