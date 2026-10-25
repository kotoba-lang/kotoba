# Maturity

**Level: R1 experimental (real integration, no bundled evidence fetcher)**

Implemented:
- `ekyc-native-provider.ports/IEvidenceFetcher` — the evidence-resolution
  seam (see README.md's "evidence-fetch gap" section for why this had to
  be invented; no equivalent exists anywhere in `ekyc`).
- `ekyc-native-provider.core/score-check` — dispatches `:document-ocr` to
  `mrz.core/parse`+`valid?` (real), `:liveness` to
  `face-liveness.core/score-response` (real), `:face-match` to
  `face-match.core/match` (deliberate stub, always `:review`); every
  unsupported check kind and every unresolvable evidence-ref both map to
  `:review` — "cannot score this" and "not implemented" are deliberately
  the same safe answer.
- `ekyc-native-provider.core/provider-client` — a full, real
  `ekyc.adapters.provider/IEkycProviderClient` implementation
  (`create-session!`/`upload-evidence!`/`retrieve-result!`), with a
  process-lifetime in-memory session→evidence map so `retrieve-result!` is
  actually answerable (documented as non-durable — a real deployment's
  durable ledger is whatever `ekyc.core`'s own caller already uses).
- Every engine's own status vocabulary correctly mapped into EXACTLY
  `ekyc.model/statuses` (`ekyc.core/valid!` rejects anything else) in one
  place, not leaked through.
- Contract tests: `score-check`'s three engines against real fixture data
  (the same ICAO Doc 9303 TD3 worked example `kotoba-lang/mrz` itself uses,
  a real blink-frame sequence, the face-match stub), the fail-closed paths
  (nil content, unsupported check), `create-session!`/`upload-evidence!`/
  `retrieve-result!` end-to-end through a fixed in-memory fetcher including
  custody-ref-wins-over-evidence-ref and worst-status-wins aggregation. 11
  tests, 17 assertions, 0 failures. `clj-kondo`: 0 errors, 0 warnings.

Not yet R1 (i.e., explicitly absent, not a rounding-down):
- **No `IEvidenceFetcher` implementation ships anywhere.** A real
  deployment must supply one, e.g. backed by
  `ekyc.adapters.kagi-custody`'s store — this repo only defines the seam.
- **In-memory session state is not durable** — restarting the process
  loses `retrieve-result!`'s answer for any in-flight session. A real
  deployment persists via whatever ledger `ekyc.core`'s caller already
  uses (e.g. `ekyc.adapters.identity-bridge`), not this map.
- **Inherits every upstream engine's own honest gaps** — `mrz`'s optical
  step is R1-experimental with no bundled OCR-B templates,
  `face-liveness` has no bundled `ILandmarkTracker`, `face-match` has no
  comparison algorithm at all (R0, by design). This provider correctly
  wires these gaps through rather than hiding them; it does not close
  any of them.
- **No `:document-authenticity` / `:address` / `:adverse-media` engine**
  — these `ekyc.model/checks` members have no implementation anywhere in
  this org; this provider maps them (and `:pep`/`:sanctions`, which belong
  to a different subsystem entirely) to `:review`.

## Downstream consumers

None yet in production. Designed as the engine layer behind a future
`cloud-itonami-isic-649` verification actor (Phase F of the eKYC/AML
vendor plan, ADR-2607198200's roadmap).
