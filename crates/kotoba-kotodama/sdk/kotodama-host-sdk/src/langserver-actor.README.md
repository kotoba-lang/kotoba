# langserver-actor

Kotodama actor wrapper around a per-taxonomy LangGraph Pregel langserver,
per **ADR-2605180900** Phase 6.

The actor is a thin HTTP client targeting an in-cluster Service DNS. Each
method maps 1:1 to a lexicon under `00-contracts/lexicons/com/etzhayyim/apps/{taxonomy}/`,
so the same input/output shapes are reused across HTTP / XRPC / MCP /
in-process actor callers.

## Usage

```typescript
import {
  createUnispscActor,
  createIsicActor,
  createLangserverActor,
} from "@etzhayyim/kotoba-kotodama-host-sdk";

// Explicit endpoint (dev / external):
const unispsc = createUnispscActor({ endpoint: "https://lg-open-unispsc.etzhayyim.com" });

// In-cluster default (production CF Worker / K8s pod):
const isic = createLangserverActor("isic");

// Methods match the lexicons:
const { candidates } = await unispsc.classify({ description: "live cattle", topK: 3 });
const result = await unispsc.invokeAgent({
  code: "10101501",
  payload: { animal_id: "cow-001", health_status: "pending", quarantine_verified: false, transport_logs: [] },
});

const { path } = await isic.hierarchicalClassify({ description: "wheat farm", stopAt: "class" });
const isicLeaf = await isic.invokeAgent({ classCode: "0111", payload: { crop_id: "wheat-2026" } });

// Health + listing:
const health = await unispsc.health();
const page = await unispsc.listAgents({ prefix: "101", limit: 50 });
```

## Endpoints used (NSIDs)

| Method                                  | NSID                                           |
|-----------------------------------------|------------------------------------------------|
| `unispsc.classify`                      | `com.etzhayyim.apps.unispsc.classify`                |
| `unispsc.invokeAgent`                   | `com.etzhayyim.apps.unispsc.invokeAgent`             |
| `unispsc.listAgents`                    | `com.etzhayyim.apps.unispsc.listAgents`              |
| `unispsc.health`                        | `com.etzhayyim.apps.unispsc.health`                  |
| `isic.classify`                         | `com.etzhayyim.apps.isic.classify`                   |
| `isic.hierarchicalClassify`             | `com.etzhayyim.apps.isic.hierarchicalClassify`       |
| `isic.invokeAgent`                      | `com.etzhayyim.apps.isic.invokeAgent`                |
| `isic.listAgents`                       | `com.etzhayyim.apps.isic.listAgents`                 |
| `isic.health`                           | `com.etzhayyim.apps.isic.health`                     |

## Default Service DNS

```
unispsc  →  http://lg-open-unispsc.lg-open-unispsc.svc:80
isic     →  http://lg-open-isic.lg-open-isic.svc:80
```

Pass `endpoint` explicitly to override (e.g. for local dev with port-forward,
or to call the public XRPC AppView in Phase 7).

## Custom fetcher

Pass `fetcher: { fetch: customFetch }` to:

- inject a CF Worker Service binding (in-mesh call without DNS),
- intercept calls in tests (see `test/langserver-actor.test.ts`),
- add cross-cutting concerns like distributed tracing.

```typescript
const actor = createUnispscActor({
  endpoint: "http://lg",
  fetcher: { fetch: tracedFetch },
  timeoutMs: 12_000,
});
```

## Errors

Non-2xx responses throw `LangserverActorError`:

```typescript
try {
  await actor.invokeAgent({ code: "00000000", payload: {} });
} catch (e) {
  if (e instanceof LangserverActorError) {
    console.error(e.status, e.message, e.detail); // 404 AgentNotFound { detail: "AgentNotFound" }
  }
}
```

## Tests

```
$ vitest run 20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk/test/langserver-actor.test.ts
Test Files  1 passed (1)
     Tests  12 passed (12)
```

## See also

- `00-contracts/lexicons/com/etzhayyim/apps/unispsc/*.json` — lexicon contracts
- `00-contracts/lexicons/com/etzhayyim/apps/isic/*.json` — lexicon contracts
- `50-infra/k8s/lg-open-unispsc/` — UNSPSC langserver pod
- `50-infra/k8s/lg-open-isic/` — ISIC langserver pod
- ADR-2605180900 (`90-docs/adr/`) — full architecture
