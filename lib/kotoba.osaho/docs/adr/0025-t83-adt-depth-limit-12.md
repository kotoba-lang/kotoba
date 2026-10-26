# ADR 0025: T8.3/W4 raise parametric ADT value depth 8 → 12

- Status: Accepted
- Date: 2026-08-01
- Depends: recursive EDN atom|pair (provider 0246/0247)

## Context

Ops W4 packages build request/result maps as pair spines of map entries.
Structured entries `pair(atom key, atom value)` nested as header maps
`pair(entry, entry)` exceed the historical **depth 8** budget during
`bounded-typed-value!`. Preformatted entry-atom strings (0247) worked around
this; structured kv is the residual for kit identity honesty.

## Decision

1. `adt-depth-limit` **8 → 12** (value trees only).
2. `document-depth-limit` stays **8**.
3. Node budget 64 unchanged.
4. Consumers (compiler manifest, browser-host runtime assert) must match.

## Evidence

- value_test depth rejection uses depth-13 type
- Enables structured kv EDN packages under provider ADR 0248

## Related

- T8.3 / W4; provider 0246–0248; compiler parametric-adt-depth pin
