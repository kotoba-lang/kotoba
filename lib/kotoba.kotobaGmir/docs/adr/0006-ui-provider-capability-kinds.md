# ADR 0006: Reserve ui-commit-v1 and ui-event-v1 native capability kinds

## Status

Accepted.

## Decision

The closed native capability-kind table assigns code `6` to `:ui-commit-v1`
and code `7` to `:ui-event-v1`. The numeric capability ids (9 and 10) still
control authority. The kinds control only the value codecs: commit's request
and result records are not the same shape as event's request and
`[:option event]` result, so they cannot share one kind.

`checked_typed_cap_call` requires `request_kind == result_kind`, so each
capability keeps one kind covering both sides of its sealed pair.
