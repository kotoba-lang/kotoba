# Shared client runtime: recovery provenance

Tracking: [JUN-14](https://linear.app/kotobalabs/issue/JUN-14).

This recovery is a draft targeting main. The legacy-CI retirement
[PR #25](https://github.com/kotoba-lang/wasm-webcomponent/pull/25) merged as
`1d36f9936e0e5af61d3f3064815bb46f6c4d4143` after the owner's explicit approval
to remove the five old jobs while native replacement gates remain unqualified.
That dependency is resolved. The recovery's integration and qualification
requirements below remain open; #25's approval does not qualify this module.

## Provenance

The canonical `src/kotoba-client-runtime.js` was absent from main at
`8ae8c5b412c9a37238b4a4330e5b57e0f27fa8c4`. Previous work on
`codex/client-first-runtime-host-20261016` and
`codex/client-runtime-v1-20261018` had left it uncommitted. The old worktree
registrations and branches were preserved.

The recovered file is the final source recorded by task
`01a14237-be01-73e0-b3cf-4febdf461bf1`: source snapshots followed by its final
two source patches, without executing any archived command. The recovered version was 29,517
bytes / 677 lines, SHA-256
`9b1c7984ca18b596b30e1c2b8f1ee3d0c3d82e1f0dd698483bc1ca934665e40a`.
That digest matches the task's final recorded source digest. The recovery commit retained
the implementation exactly, including its comments and API names. No old
test harness or generated app bundle was recovered in that commit.

This module is browser host code, permitted by the shared end-user app
architecture contract. It does not provide a Node, Clojure, JVM or C execution
path for Amu selfhost, compiler builds or CDCI.

## Recovered surface (historical API inventory)

| Export | Purpose |
| --- | --- |
| `clientRuntimeProblems` | Validate the descriptor, local state, Workers, service operations and requested capabilities |
| `clientEndpointAllowsRequest` | Match concrete HTTPS method, path and query scope |
| `effectiveClientOperations` | Intersect declared operations, local host eligibility and host-supported selectors; empty by default |
| `createClientOperationBroker` | Snapshot requests, request confirmation for each invocation and dispatch a declared service adapter |
| `clientRuntimeConnectSrc` | Derive `connect-src` from declared service and redirect origins |
| `applyOfflineClientPolicy` | Add a restricting document policy for a local session |
| `CLIENT_INFERENCE_PROTOCOL` | Name `kotoba.inference.v1` |
| `clientInferenceRequestProblems`, `clientInferenceEventProblems` | Validate inference Worker messages |
| `createClientInferenceRequest`, `createClientInferenceEvent` | Construct schema-checked inference messages |

The recovered `approvedOperations` input is a host eligibility filter. It
cannot replace fresh consent for an invocation. A `load` inference message
carrying that field also grants no external request or inference authority.

## Follow-up implementation and qualification

The current candidate extends that recovery. It replaces caller-supplied
confirmation / HTTP adapters with a canonical trusted consent host and
browser fetch, adds browser-native operation declarations, artifact digest
and Ed25519 descriptor admission, and a restricted self-contained HTML guest
fixture. The original recovery digest above is provenance, not the digest of
the current source. Current source / fixture hashes are in the browser receipt.

See [the current integration contract](client-runtime.md) for API changes,
trust boundaries and remaining qualification work, and the
[2026-10-23 browser receipt](evidence/client-runtime-browser-20261023.json).
Recovery alone qualified no runtime behavior; subsequent browser fixtures
are explicitly distinguished from product integration and native CDCI.

No production route change or stopping of an existing service is authorized.
