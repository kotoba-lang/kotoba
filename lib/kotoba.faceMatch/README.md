# face-match

Face-match comparison contract for kotoba-lang eKYC/AML. **This repo has no
embedding model and no comparison algorithm.** It exists to define an
honest boundary: `face-match.core/match` always routes to human review
(`:review`/`:not-implemented`) unless a real
`face-match.ports/IFaceMatcher` is injected — and none exists anywhere in
this org today.

## Why ship a repo that does nothing?

Comparing a selfie against a document photo needs a real face-embedding
model with a real, measured false-accept/false-reject rate. Building or
porting one without real benchmark data would produce a component that
*looks* like it verifies identity while actually offering no real
assurance — worse than not having the check at all, because it creates
false confidence. See `MATURITY.md` for the full reasoning and the
conditions under which this would be revisited.

This repo is the "seam", matching `mrz.ports/IZoneOcr` and
`face-liveness.ports/ILandmarkTracker`'s own host-injection shape, so a
real implementation has somewhere to plug in later without changing any
caller's contract.

## Usage

```clojure
(require '[face-match.core :as core])

(core/match selfie-bytes document-photo-bytes)
;;=> {:face-match/status :review
;;    :face-match/confidence nil
;;    :face-match/reason :not-implemented
;;    :face-match/non-adjudicating true}
```

See `90-docs/adr/*-kotoba-lang-face-match.edn` (in the
`com-junkawasaki/root` superproject) for the design rationale.

## Kotoba bounded profile

`src/face_match/bounded_no_matcher.kotoba` is a capability-free Kotoba
profile that covers exactly the path above — the only way any caller in
this org invokes `match` today (no `IFaceMatcher` injected). It is a
verifiable, sovereign-source guarantee that this system never
auto-verifies or auto-flags a face-match check on that path; every check
routes to human review. The `IFaceMatcher` injection seam and any future
real comparison algorithm stay in `core.cljc`/`ports.cljc` as the general
oracle. See [migration/bounded-no-matcher-v1.edn](migration/bounded-no-matcher-v1.edn)
for the full record, including two compiler gaps hit while implementing
it (an Option-payload type-check gap and a bare `:option-i64` Wasm
lowering gap — routed around by modeling confidence as a plain bool
rather than an Option, since this path never has a confidence value to
represent in the first place).
