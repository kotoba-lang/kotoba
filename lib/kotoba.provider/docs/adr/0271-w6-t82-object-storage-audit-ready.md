# ADR 0271: T8.2 object/storage audit :ready (on-call + mem-transport)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0153 kit ready checklist; ADR 0269 ops audit ready

## Context

T8.2 residual after 0269 was object/storage still scoring `audit :partial`.
Both kits already had optional `:on-call` hooks on production transports
(object-transport / storage-transport), but lacked a testable in-memory
audit surface and readiness evidence.

## Decision

1. Ship **`mem-transport`** on `provider.storage-transport` and
   `provider.object-transport` with optional `:on-call` (same shape as
   production-transport; exceptions swallowed).
2. Kit-readiness: object + storage **`:audit :ready`** with mem + production
   on-call evidence.
3. Does **not** claim signed-wasm or flip deny-fixtures for object
   (still `:partial`).

## Evidence

- Unit tests: storage put/get and object put-block/get-stream fire on-call

## Related

- Closes T8.2 non-ops audit residual for object/storage
