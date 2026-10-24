# Prolly metadata/coordinate index v1

The Prolly engine cannot remove eager history hydration by merely replacing
the linked metadata log with another container. Its current Arrangement leaf
value carries `[a b o]`, while the engine returns Datoms with the transaction
coordinate `t`; normal scans reconstruct that coordinate from the entire
history vector.

Manifest format v3 therefore commits a second persistent Prolly root
with four key spaces:

| Prefix | Key | Value | Access |
|---|---|---|---|
| `r/` | keyed token of canonical request ID | sealed request receipt | point |
| `h/` | zero-padded epoch | sealed transaction Datoms | prefix scan only for history |
| `e/` | zero-padded epoch | public snapshot/manifest links | point |
| `t/` | keyed token of canonical logical Datom key | sealed latest assertion epoch | point/batch |

`r/` and `t/` keys must cross a caller-supplied keyed function. An unkeyed CID
or digest is not acceptable because low-entropy request IDs and Datoms admit a
dictionary attack. Sensitive values must cross the existing seal/open boundary.

One transaction computes the Arrangement snapshot root and metadata root
before publishing a manifest that commits both. Assertions upsert their `t/`
coordinate; retractions remove it. A cursor batches coordinate lookups only for
rows returned by the selected covering-index range. A normal point read must
never scan `h/`; explicit history is allowed to do so.

Migration reads format v1/v2, replays historical coordinate roots on the next
write, and publishes format v3. Qualification gates implemented by this repo:

- 32-epoch cold restore with fewer than 10 metadata block reads;
- replay of the oldest request with fewer than 10 metadata block reads;
- point scans returning the same `t` values as the memory oracle;
- retract/reassert transitions updating `t/` without stale coordinates;
- root manifest and hot request/snapshot maps remaining bounded.
