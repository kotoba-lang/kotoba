# ADR 0009: Route clock-v1 through the typed provider callback

## Status

Accepted.

## Decision

`:clock-v1` uses the existing typed capability callback at context offset 128.
Its request remains one pair-handle word, so its target argument register is
the same typed-value register used by string and tagged-i64 calls. Authority is
still checked from the capability bitmap before the indirect call.
