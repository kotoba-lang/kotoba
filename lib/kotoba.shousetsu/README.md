# shousetsu

Work-agnostic serialized web-fiction (小説) domain vocabulary — the craft
library split out of gftdcojp's private `ai-gftd-syosetsuka` actor
(ADR-2607023000: コードは kotoba-lang、職能は cloud-itonami-isco、商売は
gftdcojp). Completes the creative -ka craft-lib family:
`anime` / `ongaku` / `douga` / `kami-genko`+`kami-mangaka-*` / **`shousetsu`**.

`shousetsu.serialization` provides:

- **Entity vocabulary** — author / work / episode / worldview / character /
  review, with the `:au/ :nv/ :ep/ :wd/ :ch/ :rv/` attribute-prefix scheme
  and plain-string entity ids (`work:<slug>`, `episode:<slug>:<index>`, …)
  plus parsers (`work-slug-of`, `episode-index-of`)
- **Datom tx helpers** — `tx-add`, `encode`, `chunk-tx-data` (byte-capped
  transaction chunking for store request-size ceilings)
- **Record → ops builders** — `author->ops`, `work->ops`,
  `episode-meta->ops`, encoding the invariant that **long-form text never
  becomes a datom**: episode bodies are content-addressed blobs referenced
  by `:ep/bodyBlobKey`
- `slug` — ASCII slug derivation with a stable hash fallback for
  non-ASCII pen names / titles

Nothing here knows about a specific site, DID authority, store endpoint, or
LLM — that wiring stays in the consuming actor.

## Occupation

ISCO-08 `2641` (Authors and Related Writers) —
[cloud-itonami-isco-2641](https://github.com/cloud-itonami/cloud-itonami-isco-2641).

## Test

```bash
kbb -M:test
```

## License

Apache-2.0.
