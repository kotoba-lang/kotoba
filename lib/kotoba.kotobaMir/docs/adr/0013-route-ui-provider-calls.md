# ADR 0013: Route ui-commit-v1 and ui-event-v1 through the typed provider callback

## Status

Accepted.

## Decision

`:ui-commit-v1` and `:ui-event-v1` use the existing typed capability callback
at context offset 128. Each request remains one pair-handle word, so the
target argument register is the same typed-value register used by dataspace
(`:x86-64/r8`, `:aarch64/x4`). Authority is still checked from the capability
bitmap before the indirect call.
