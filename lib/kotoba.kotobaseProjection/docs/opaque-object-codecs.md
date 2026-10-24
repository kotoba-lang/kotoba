# Opaque object CID migration

New concatenated projection packs and encrypted stored blocks use raw CIDv1
(`0x55`). Independently encoded logical row blocks and query bundles remain
DAG-CBOR (`0x71`). The pack is a concatenation with bundle-provided offsets and
lengths; it is not a CAR archive. CAR framing belongs to `io-ipld-car`.

This changes newly produced pack CIDs, encrypted stored CIDs, and bundle CIDs
that link to them. Logical plaintext row-block identities remain unchanged.
The query-bundle field grammar stays at version 1: links already carry their
codec, and readers locate the named object and verify logical blocks. Existing
objects and bundles are not rewritten. The in-memory reader remains compatible
with historical DAG-CBOR-labelled pack addresses. External stores must treat
pack links as opaque object addresses rather than decode them as metadata.
## Consumer audit (completed 2026-09-06)

An earlier revision of this note said the inspected `kotobase-peer`
object-store paths use CID as an opaque key. That was measured and is wrong,
and the way it was wrong is worth keeping: the paths that build keys
(`block-key`, `object-key`) do treat the CID as opaque, and those are the ones
inspection reached. The paths that *verify* do not. Both reachability walkers
recomputed `ipld/cid`, which is DAG-CBOR unconditionally, so a raw block's
*correct* bytes recompute to a different string -- same digest, `bafkrei...`
against `bafyrei...` -- and a correct store read as a corrupt one.

`reachable-cids!` already declined to *decode* packs as DAG-CBOR and said so in
its docstring. It still *addressed* them that way. Reading it confirms packs
are handled as opaque; only running it against a raw CID shows which half of
"opaque" was implemented. The existing opaque-leaf test addressed its fixture
with `ipld/cid`, so the suite that passed could not have caught this.

Fixed in [kotobase-peer #111](https://github.com/kotoba-lang/kotobase-peer/pull/111),
which advances the pin to this codec change in the same commit: either alone
leaves the store readable only by accident. The rule it produced -- verify
against the codec the CID declares, via `ipld/cid-codec`, as
`ipld/get-verified-block` already does. A raw block verifies against
`mf/cidv1-raw` and contributes no links, since raw is bytes and bytes have no
IPLD links, so it is verified and traversed no further rather than skipped
(which would drop it from a reachable set) or failed.

`kotobase-worker-shell` and `gftdcojp/tia` consume this repository by source
path rather than by SHA, so they follow the west pin, which advanced with it.
Remaining deployable consumers must still verify their resolved pins and
object handling during rollout. Merge is not evidence of live deployment.

`stored-cid` identifies ciphertext, while `cid` identifies plaintext. This patch
corrects writing their identities; it does not add ciphertext-CID verification
to decryption callbacks. Plaintext verification remains in `decode-range`.

Arrow IPC integration is follow-up work: define a versioned physical-layout
descriptor and decoder negotiation before writing Arrow blocks. Keep IPC bytes
raw and preserve column buffers through execution. Existing Bloom, min/max,
offset/length, coalescing, and delta-chain semantics must retain their behavior.
Current range upper bounds are inclusive; an OrderedMap half-open API needs an
explicit adapter.

See [the accepted cross-repository ADR](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2609060000-ipld-adl-selector-car-boundaries.edn).
