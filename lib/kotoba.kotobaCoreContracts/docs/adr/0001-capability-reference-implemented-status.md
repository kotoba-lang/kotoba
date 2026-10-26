# ADR-0001: `:reference-implemented` provider status for atomic capability repos

- Status: accepted
- Date: 2026-07-28

## Decision

Allow atomic capability package manifests to use:

| status | meaning |
|---|---|
| `:contract-only` | definition CID + discovery only (default scaffold) |
| `:reference-implemented` | pure/ambient-free provider published with wasm sha256 + exports |

`:reference-implemented` is allowlisted (`math/sin`, `math/cos`, `hash/sha256`,
`data/cbor`, `data/json`, `clock/monotonic`, `random/bytes`, `time/now-days`).

Artifact fields required when implemented: `:path` (`artifacts/*.wasm`),
`:sha256` (64 hex), `:exports`, `:signature` (`:reference-unsigned` or map).

Semantic definition CID is unchanged by implementation digests.

## Consequences

- First landing: `capability-math-sin` / `capability-math-cos` with core wasm +
  JVM `Math/*` reference host helper.
- Production signed components can replace `:reference-unsigned` later without
  renaming repos.
