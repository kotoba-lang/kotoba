# ADR 0034: T4.2 `string-split-count` typed host import

- Status: Accepted
- Date: 2026-07-29
- WBS: T4.2

## Decision

Emit `string-split-count` as `kotoba:typed` import
`typed-string-split-count` (descriptor + haystack + sep → i32, extend to i64),
mirroring `string-contains`.

## Evidence

- Dual-backend pilot via compiler browser-host
