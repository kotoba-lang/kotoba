# ADR 0022: T4.2 `string-split-count` runtime op

- Status: Accepted
- Date: 2026-07-29
- WBS: T4.2

## Decision

Add KIR op `string-split-count` (haystack, separator) → i64:

- Empty separator traps (`:empty-string-split-separator`)
- Non-overlapping segment count (JS `String#split` length for non-regex seps)
- Full split-to-collection remains deferred

## Evidence

- Unit tests + compiler dual-backend pilot (pin this SHA)
