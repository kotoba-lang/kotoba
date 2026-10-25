# Maturity

**Level: R2 live transport**

Implemented:
- CTF request and attributed result models.
- Default route order: `:malak` then `:yabai`.
- Host port for route-specific screening.
- Route, case-ref, level, and non-adjudicating result validation.
- Aggregate status preserving case-ref and route set.
- Audit datom emitters for route results and screening summaries.
- Etzhayyim XRPC adapter boundary:
  - `:malak` -> `ai.gftd.apps.malak.queryRiskChain`
  - `:yabai` -> `ai.gftd.apps.yabai.getRisk`
- Java HttpClient XRPC transport with pluggable codecs.
- XRPC auth wrapper for bearer, service JWT, and API-key headers.
- Retry wrapper for retryable XRPC/transport failures with injectable exponential backoff.
- Identity evidence ledger bridge for CTF screening evidence and attestations.
- Schema conformance validator for upstream lexicon drift.
- Contract tests for route order, invalid boundary inputs, datom shape, XRPC payload/result mapping, local-server transport, auth header propagation, backoff/retry behavior, and evidence ledger persistence.

Not yet R2:
- None.
