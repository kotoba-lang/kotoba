# ekyc-native-provider

The composing `ekyc.adapters.provider/IEkycProviderClient` implementation
for kotoba-lang/ekyc. The one repo that knows ekyc's payload shapes and
dispatches each check to the real, standalone engine repos:

- `:document-ocr` → `kotoba-lang/mrz` (real ICAO 9303 decode/checksum)
- `:liveness` → `kotoba-lang/face-liveness` (real EAR/MAR/yaw challenge scoring)
- `:face-match` → `kotoba-lang/face-match` (deliberate stub — always `:review`)

Every other check kind (`:document-authenticity`, `:address`, `:pep`,
`:sanctions`, `:adverse-media`, `:manual-review`) is honestly unsupported
and maps to `:review` — `:pep`/`:sanctions` belong to the separate
`kotoba-lang/watchlist-screen` + `kotoba-lang/aml` path, not this provider.

## Why one composing provider, not three shims

Each engine repo (`mrz`, `face-liveness`, `face-match`) stays completely
ekyc-agnostic — a plain library with its own API, reusable outside eKYC
entirely. This repo is the only place that knows `ekyc.adapters.provider`'s
exact payload shapes and `ekyc.model/statuses`' closed vocabulary
(`#{:created :submitted :verified :rejected :expired :review}`) — every
engine's own status keywords (`face-liveness`'s `:failed`, `face-match`'s
`:flagged`) get mapped into that vocabulary in exactly one place
(`ekyc-native-provider.core/score-check`), so a future fourth engine only
needs a new `case` branch here, not a new ekyc integration each.

## The evidence-fetch gap (read before using this)

`ekyc.adapters.provider`'s payload shapes carry only a `:evidence-ref`/
`:custody-ref` — a REFERENCE to where evidence was stored, never the raw
bytes. There is no read-back protocol anywhere in `ekyc` for resolving
that reference back to content a check engine can actually score. This
repo defines its own seam,
`ekyc-native-provider.ports/IEvidenceFetcher`, mirroring every sibling
engine's host-injection pattern — **no implementation ships here**. A real
integration must supply one (e.g. backed by
`ekyc.adapters.kagi-custody`'s store), resolving each check kind's
evidence-ref into:

```clojure
:document-ocr {:mrz-lines ["P<..." "L898902C36..."]}
:liveness     {:challenge <face-liveness.model/challenge> :frames [...]}
:face-match   {:selfie ... :document-photo ...}
```

## Usage

```clojure
(require '[ekyc.adapters.provider :as ekyc-provider]
         '[ekyc-native-provider.core :as native])

(def client (native/provider-client my-fetcher)) ; my-fetcher: an IEvidenceFetcher

;; client satisfies ekyc.adapters.provider/IEkycProviderClient directly --
;; wrap it with ekyc.adapters.provider/provider-port for the full
;; ekyc.ports/IEkyc surface ekyc.core/start|submit|result expects.
(ekyc-provider/create-session! client {:id "sess-1" ...} {})
```

See `MATURITY.md` and `90-docs/adr/*-kotoba-lang-ekyc-native-provider.edn`
(in the `com-junkawasaki/root` superproject) for the design rationale.
