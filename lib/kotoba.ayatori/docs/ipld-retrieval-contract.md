# IPLD retrieval contract

Status: Accepted boundary contract; Selector-engine implementation remains open. See [Kotobase ADR-2609060000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2609060000-ipld-adl-selector-car-boundaries.edn).

## Existing implementation

`ayatori.pack/open-pack` reads a CARv2 header and index through a caller-owned
range function. `read-block` delegates frame validation to `io-ipld-car` and
checks that the returned CID equals the requested CID. `pack-fetcher` adapts
this to `ayatori.remote/provider-block-getter`. Discovery locates providers;
the CAR index locates candidate frames. Neither establishes graph truth.

The current index-derived `:frame-length` is a read bound, not universally an
exact frame size. It is exact only when every frame boundary is represented
once and frames are contiguous. Sparse indexes (including omitted identity
sections) can over-fetch. Repeated offsets now share the next distinct boundary.
Header arithmetic and index offsets are checked before block reads. Candidate
lookup matches both hash code and digest; `read-block` tries distinct candidate
offsets until the full CID matches, preserving verification of each parsed frame.
Even an overlong provider response cannot extend a frame past its read bound.

This does not claim arbitrary-CAR support: the codec remains CIDv1 and
MultihashIndexSorted only, with its existing supported hash algorithms. Sparse
reads remain bounds rather than exact lengths.

## Index and header limits (landed 2026-09-06)

Index size/work limits and header qualification are no longer separate work.

The index read is bounded rather than open-ended. It was `bytes=N-` -- the rest
of the object, whatever that was -- so the reader learned the size by already
holding it, and a large tail or a store that ignores `Range` was an unbounded
read nothing downstream could undo. `max-index-bytes` (8 MiB, about 200k
records at 40 bytes each) is a ceiling the reader chooses; a caller packing
larger passes its own. Because asking for a window is not the same as being
given one, an oversized response is refused as well as bounded.

The whole header is qualified, not only the parts this reader uses. CARv2 gives
an archive a 128-bit characteristics bitfield to say it is not an ordinary one,
and this reader implements no characteristic. Parsed and discarded, saying so
and saying nothing produced the same read; a declared characteristic is now
refused on the header read, before the index is fetched.

Truncation is refused by the codec rather than here. `io-ipld-car` checks each
declared count against the bytes remaining and takes a `:max-records` ceiling,
because a large *well-formed* index is still an unbounded allocation for a
reader that cannot see its size until it holds it. Its failures are typed apart
so a short buffer cannot decode as an empty index -- nothing here can tell that
apart from a pack that genuinely indexes no blocks.

That refusal replaced a non-termination, not a mis-parse: measured on nbb, an
index header claiming one code group and carrying none of it spun without
yielding, because an out-of-range read returned `NaN` and `NaN` compares false
against every guard. In a Worker that is the isolate, not a slow request.

## Selective hydration

Input: immutable root CID, standard Selector, explicitly supported ADL versions,
and budgets for bytes, blocks, depth, and traversal work. Output: independently
verified loaded blocks, selected values, and explicit completion/failure state.
CAR export consumes loaded traversal dependencies, including the root path and
ADL substrate blocks. Merely listing Matcher results is insufficient.

Replay traversal locally; reject missing dependencies and unsupported forms.
Deduplicate fetched bytes by CID while retaining traversal state by path and
Selector state. Reaching a work limit is incomplete retrieval, not success.

Replay landed 2026-09-06 as `ipld.car.trustless/replay-selection`, the verifier
counterpart to `selection-car`. It is not that function read backwards: a
producer may trust its own store, a verifier may trust nothing it was handed.
Three things it must not believe, each silent by default.

`car/decode` does not verify. It keys blocks by the CID the frame *declares*
and never rehashes them, so an archive whose frame claims one CID while
carrying another block's bytes decodes without complaint. CARv2's `read-frame`
*does* verify, which is the trap -- the habit does not carry from v2 to v1.
Replay inherits verification from `select-blocks`, which rehashes every block
it fetches.

A CAR's roots header is a claim by whoever wrote the archive. Replaying from it
shows the sender's archive is self-consistent, which is not the question; the
caller's root is what binds the graph.

An archive missing a block the traversal needs is no answer, not a shorter one.

Every failure is thrown and typed apart -- `:ipld/car-root-mismatch`,
`:ipld/invalid-selector`, `:ipld/missing-block`, `:ipld/cid-mismatch`,
`:ipld/resource-limit` -- because a completion flag in a returned map is a
value a caller can drop on the floor. The selector is taken as canonical
DAG-CBOR rather than an executable form, so it is something a verifier can
hash and agree with a producer about, and decoding it is where a form outside
the supported subset is refused instead of quietly matching less. Blocks the
archive carried but the traversal never reached are reported as `:unused`
rather than rejected -- logical selection legitimately loads shared blocks
holding other rows -- but they are unverified, since only touched blocks were
rehashed.

Ayatori does not yet expose replay through its own retrieval surface; it is
available from `io-ipld-car` and this contract now describes real behaviour
rather than a proposal.
Selectors do not choose Datalog indexes or express ordered-map key intervals:
`ExploreRange` is a list-position interval. Initially, database range cursors
can record visited CIDs as a custom artifact with no standard-Selector claim.

CAR roots bind the starting graph only when checked against the caller's root.
Hash verification and Selector replay do not establish database-query completeness
or authorize access. Logical selection may load shared blocks containing other
rows. Apply authorization before serving bytes, and define authenticated range
proofs separately if needed.

## Transport and rollout

Retain `io-ipld-car` as the only encoder/parser. CARv1 is a streaming option;
indexed CARv2 is an object/cache option. Arbitrary Selector-over-HTTP needs a
custom negotiated protocol and must not be advertised as standard gateway
support merely because the response is a CAR.

Keep existing write-local packs. Evaluate traversal-order exports separately
with request-count, byte-count, memory, and latency evidence. Coalescing must
preserve per-frame full-CID verification. `pack-bounds-test` covers
sparse/duplicate indexes, hash-code candidate filtering, codec aliases, padded
payload/index offsets, truncated/corrupt frames, and payload-end bounds;
`pack-limits-test` covers the bounded index request, a caller-set ceiling, an
oversized response, a truncated index, and a declared characteristic. These
tests do not add support for new hash algorithms. Selector work then
needs missing-block, shared-DAG, unsupported-ADL, and budget-exhaustion fixtures.

References: [CARv2](https://ipld.io/specs/transport/car/carv2/) and
[Selectors](https://ipld.io/specs/selectors/).
