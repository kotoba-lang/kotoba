# kotobase-client-query

**Does the query run in the client, with the server holding only bytes?**

This is the acceptance for that claim, and it answers it the only way that
can: by recording every HTTP request the process makes and looking at what
they are.

```bash
cd ~/github/kotoba-lang/kotobase-client-query
npm install
KOTOBASE_LIVE_BLOCKS=1 npm run acceptance
```

Measured 2026-09-06 against the real `https://kotobase.net`:

```
phase A — writing 5 facts through the client engine
  commit bafyreiazg6b5vredwkxabiq4t7a3blk3m3e5h42am6q57avtygoudbop7y
  3 requests to write
phase B — cold read: new engine, empty ref store, only the CID carried over
  ok   query answered from blocks fetched in this process: #{["alice" "works-at" "acme"]}
  3 requests to read, 3 of them GET /ipld/<cid>
PASS: every one of the 3 requests was GET /ipld/<cid>. The query, the index
walk and the materialisation ran here.
```

## What is being asserted

Not "did we get the right answer" — a server-side query gets the right answer
too. The assertion is:

> every request this process made was `GET /ipld/<cid>`

If any part of the read were still happening on the server, this run would
have to POST something: a query, a `datoms` index read, an `xrpc/…` method.
One request outside that shape fails the run, and the run says which one.

**The control was run.** Slipping a single
`POST /xrpc/ai.gftd.apps.kotobase.datomic.q` into the read phase produces:

```
  4 requests to read, 3 of them GET /ipld/<cid>
FAIL: 1 request(s) were not a block read — the server did more than store bytes
    POST https://kotobase.net/xrpc/ai.gftd.apps.kotobase.datomic.q
```

An acceptance that has never failed asserts nothing (root AGENTS.md), and the
same is true of one whose only negative case is "the answer was wrong".

## Why phase B is cold

Phase A writes through the client engine, which already exercises the client
side — encoding, block splitting and CID derivation all happen locally. It is
not evidence about reads, though, because the engine still holds what it just
built.

So phase B builds a *new* engine over a *new* transport with an empty ref
store, pins it to phase A's commit with `at-cid`, and queries. The only thing
that crosses between the phases is a 59-character address. Every block the
query touches has to come back over the wire, which is what makes the request
log mean anything.

## The pieces, and who owns which

| | |
|---|---|
| `kotobase.blocks` (`kotoba-lang/kotobase-client`) | CID-verified `GET/PUT /ipld/<cid>`. Re-derives the address from the bytes that arrived. |
| `kotobase.storage.ipfs` (`kotoba-lang/kotobase-storage-ipfs`) | turns an injected `{:get-block :put-block!}` into an `IBlockStore`. |
| `kotobase.storage.core/compose` | blocks from one provider, refs from another. Refs here are in-memory: a pinned read needs no ref service at all. |
| `kotobase.engine` (`kotoba-lang/kotobase-engine`) | the engine. Portable `.cljc`/`.cljs`; nothing about it is server-only. |

None of that is new. What was missing was a transport that reads blocks and
proves they are the blocks it asked for, and something that put the four
together and looked at the wire.

## Two things this does not claim

- **It is not a benchmark.** It counts round trips, not milliseconds. This
  workstation runs dozens of concurrent agents at a load average in the tens,
  so wall clock here measures the workstation — the discipline
  `kotobase-peer`'s dag-shape bench established (ADR-2608021000).
- **The graph is tiny.** Three GETs is a property of five facts in one
  commit, not a scaling result. What scales, and what it costs, is
  `kotoba-lang/kotobase-shard-index`'s question, not this one's.

## Paths

`deps.edn` reaches `kotobase-client` and `org-nist-sha2` as sibling
checkouts (`../kotobase-client/src`, `../org-nist-sha2/src` — i.e.
`kotoba-lang/<repo>` side by side in the github forest), because
`kotobase-client` has no `deps.edn` by design — its consumers add its `src` to
their own source paths. So this runs from a checkout with those two repos
cloned next to it, not from a bare clone of this repo alone.

Source paths live in `deps.edn`, not `shadow-cljs.edn`: shadow-cljs ignores
the latter when `:deps` is set. It does say so, but the namespace it then
cannot find reads like a missing library.
