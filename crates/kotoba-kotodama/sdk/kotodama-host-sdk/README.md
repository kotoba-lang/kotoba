# @etzhayyim/kotoba-kotodama-host-sdk

Kotodama host runtime SDK for Worker-hosted apps.

## XRPC Error Control (OCEL v2)

`App.handleXRPC()` now applies explicit error control and OCEL logging for **all** `/xrpc/*` requests.

- Every XRPC call emits OCEL v2 lifecycle events:
  - `phase: "start"`
  - `phase: "success"` on completion
  - `phase: "error"` on failure (including unknown NSID)
- Default event type for XRPC is:
  - `xrpc.{nsid}`
- If a command has `withOCELEvent("...")`, that event type is used for the command lifecycle.

### Error Response Shape

XRPC failures return structured JSON:

```json
{
  "error": "human-readable message",
  "errorCode": "MACHINE_CODE",
  "retryable": true
}
```

Current standard cases:

- Unknown XRPC method:
  - `status: 404`
  - `errorCode: "XRPC_UNKNOWN_METHOD"`
  - `retryable: false`
- Handler/runtime failure:
  - `status`: derived from thrown error if provided; otherwise `500`
  - `errorCode`: derived from thrown error `.code` if provided; otherwise fallback (`APP_COMMAND_FAILED` / `XRPC_HANDLER_FAILED`)
  - `retryable`: derived from thrown error `.retryable` if provided; otherwise `status >= 500`

## OCEL Dispatch Path

Host audit/OCEL emit APIs dispatch through write-buffer type:

- `anomaly-emit-event`

This avoids unknown write-buffer event types for OCEL emission.

## Legacy NSID Migration

Write-dispatch mappings were updated to reduce legacy PDS errors:

- `cypher-query`:
  - from `com.etzhayyim.graph.query`
  - to `com.etzhayyim.kagami.graph.query`
- `cypher-write`:
  - from `com.etzhayyim.graph.write` (legacy, removed)
  - to `com.etzhayyim.kagami.graph.query` (authenticated write, unified)
- `anomaly-emit-event`:
  - legacy `com.etzhayyim.audit.emitEvent` dispatch removed (best-effort no-op)
