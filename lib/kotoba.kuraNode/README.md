# kura-node

The mechanism layer of the [kura](https://github.com/kotoba-lang/kura) storage
network: hold shards, move bytes, answer audits, count what you are owed.

Design: [ADR-2607299200](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607299200-kura-erasure-coded-storage-network.edn).
`kura` decides; this executes. Placement, repair scheduling and payment
amounts are not here and must not migrate here.

## The thing to read first

**A backend must declare how independent its failures are, and there is no
default.**

```clojure
(store/descriptor {:node-id "b2-0"
                   :failure-domain {:provider "b2" :bucket "kura-0"}
                   :independence :shared-substrate})   ; required
```

ADR section 1 gets a 1.625× storage multiplier to ten nines by assuming shard
losses are independent. Phase 0 stands up pseudo-nodes on rented backends —
B2, R2, S3, Storj — because you cannot pick a multiplier without a measured
node-loss rate, and you cannot measure one without running the real planes
against something. But **twenty-six pseudo-nodes on one B2 account are one
node.** The code cannot tell; it sees twenty-six shards in twenty-six places
and reports a seven-erasure tolerance that does not exist. What you have is
B2's durability, and you paid 1.625× not to get the code's.

So `independence-profiles` is a closed set — `:independent`,
`:shared-provider`, `:shared-substrate` — the choice is mandatory, and
`store/audit` reports the consequence:

```clojure
(store/audit fleet 7)
;; {:backends 26 :effective-domains 1 :largest-domain 26 :survivable? false
;;  :note "one domain holds 26 shards but the code tolerates 7 —
;;         durability is that domain's, not the code's"}
```

That is not a flaw in Phase 0. It is the fact Phase 0 exists to make visible.
The conformance suite deliberately does **not** check the declaration — whether
two buckets share a control plane is a fact about the world, not about an API.
It is a claim its operator is accountable for.

## The fast path, and why it is allowed to exist

`erasure.gf/scale-add` is the definition: a vector of integers, one field
multiply per byte through log/exp lookups. It is the oracle and it is far too
slow to move a petabyte. `kura.node.gf` is what a node runs — one 256-byte
table per coefficient, so the inner loop is an indexed load and an xor:

```
acc[i] ^= mul_table_c[xs[i]]
```

ADR section 5 designates this as the **one** piece of mechanism a host provider
may replace, on condition it proves byte-equality against the definition.
`kura.node.gf-test` is that condition: the coefficient sweep is exhaustive over
all 256 field elements, the table check is exhaustive over all 65,536 products,
and the encode comparison runs the real k=16/r=4/g=6 layout shard for shard.

The tables are built from `erasure.gf/mul-def` — the table-free
Russian-peasant definition — not from `erasure.gf/mul`, which is itself
table-driven. A fast path derived from the slow path's own tables could share
its bugs and never know.

**Signed bytes are a real hazard here.** A JVM `byte[]` holds 200 as −56, and
−56 is not a table index. Every read masks with `0xff`; the suite runs on both
hosts precisely because `Uint8Array` does not have this problem and the JVM
does.

## What else is here

- **`kura.node.store`** — the backend protocol, the independence declaration,
  and the domain-collapse audit.
- **`kura.node.contract`** — the conformance suite, shipped in `src` (not
  `test`) so a third party writing a backend can actually run it.
- **`kura.node.memory`** — reference backend. Declares `:shared-substrate`,
  because that is what one heap is.
- **`kura.node.s3`** — B2 / R2 / S3 / Storj Gateway-MT. Zero I/O and zero
  crypto: `IHttp` and `ICrypto` are injected and signing comes from
  `kotoba-lang/sigv4`, so request shaping is a pure function testable without
  credentials. Range reads use a real `Range` header — a backend that reads
  4 MiB to return 1 KiB gives back the whole benefit of the systematic layout
  (ADR section 7). Listing re-filters client-side, because "S3-compatible" is
  a claim rather than a conformance result and a backend that accepts the
  `prefix` parameter and ignores it would have the audit tree commit to shards
  this node does not hold.
- **`kura.node.audit`** — commit to what is *on the store*, not to a manifest;
  a node that commits to what it was supposed to have passes its own audit
  while missing shards. Takes **two** hashers, because shard bodies are buffers
  and `merkle-sum`'s node preimage is text — conflating them fails loudly on
  the JVM and quietly elsewhere. `self-check` is a full local scrub: sampling
  is what the *coordinator* does instead of scrubbing, not what the node does.
- **`kura.node.accounting`** — the byte limit enforced per chunk rather than
  once, because a node that checks at the start and then streams has not
  checked. Refusal is a return value, not an exception: hitting the limit is
  the ordinary end of a transfer for a client that asked for more than it paid
  for, and a node that throws there has that path exercised by every over-eager
  client on the network.

## Live: the signature is proven against a real service

`kura.node.s3` is pure by design — request shaping is a function of its
inputs, testable without credentials. `kura.node.host-node` is the other half:
`node:crypto` and `fetch`, the one file in this repo that is host-specific.

`script/live_sigv4_check.cljk` closes the loop by signing a **read-only**
ListObjectsV2 against a real S3-compatible bucket. A wrong signature returns
403, so a 200 proves the whole SigV4 ladder — canonical request, credential
scope, the four-step key derivation, the authorization header — end to end.

```
$ B2_KEY_ID=... B2_APP_KEY=... B2_BUCKET=... kbb --backend sci --classpath "src:..." \
    script/live_sigv4_check.cljk
status: 200
SIGV4 OK — service accepted the signature
```

Verified against Backblaze B2 (`s3.us-west-004.backblazeb2.com`) on
2026-07-29. Read-only on purpose: the credential to hand is scoped to an
existing archive bucket, and writing conformance fixtures into somebody's
archive to test our own code is not a trade this repo makes. Full read/write
conformance needs a bucket of its own — see the gap below.

**The SigV4 hazard this file exists to contain:** the key-derivation ladder
feeds each HMAC's *raw* digest into the next. Hex-encoding between steps
produces a signature that is wrong in a way no unit test catches, because both
sides of a self-consistent test agree — you find out when a real service
returns 403. `-hmac-sha256` returns a Buffer and only `-hex` ever stringifies.

### Two bugs the unit suite could not have found

Both were found by running the real code against a real object store, and both
are the same shape: **a test that supplies its own world agrees with itself.**

**1. The synchronous protocol cannot survive an async transport.**
`kura.node.store/IShardStore` is synchronous. Every host a node actually runs
on — Node, a Worker — has async I/O. `s3/send!` returned whatever the injected
transport returned, `ok?` read `:status` off it, and a promise has no
`:status`, so it was falsy: **every read reported the shard absent, every
write reported success.** The suite passed because `FakeHttp` is synchronous.

Fixed by `kura.node.async/IAsyncShardStore` — a separate protocol, not a
promise-shaped patch on the sync one, because a contract that is sometimes
synchronous is a contract nobody can implement correctly.
(`kotobase.storage` split the same way, for the same reason.) The sync
protocol is **not** deprecated: it is right for in-memory and for genuinely
blocking I/O. What was wrong was pretending an async transport satisfied it.

**2. `:advanced` renames un-inferred property reads.** `(.-objects res)` on the
R2 list result became `.-Xa` and returned `undefined`, so listing came back
empty while eighteen other assertions passed. Method *calls* survive; property
*reads* do not. No unit test runs through `:advanced`, so none could catch it.
`^js` hints on every property read, and the reason is at the call site.

### Live conformance

`kura-conformance` runs `kura.node.async/verify>` inside a Worker against a
real R2 bucket and returns the result as JSON — a conformance run is a URL
anyone can fetch, not a claim in a README:

**https://kura-conformance.04-feasts-minded.workers.dev/conformance** — 19/19.

`/audit` reports what a fleet of 26 such backends is actually worth:
`{effective-domains: 1, largest-domain: 26, survivable?: false}`. One bucket
is one failure domain however many prefixes are carved out of it, and the
harness says so about itself.

### The multi-provider fleet, and what the audit says about it

`kura.node.r2` covers a single provider with no HTTP at all. But **one provider
is one failure domain**, and ADR-2607299200 section 1's entire model assumes
shard losses are independent — so reaching a second provider is not a nice-to-
have, it is the thing that makes the storage multiplier worth paying for.
Reaching another provider means HTTP, HTTP means async, and that is
`kura.node.s3-async`.

Crypto and transport are split (`kura.node.crypto-noble`,
`kura.node.http-fetch`) because the Worker build cannot resolve `node:crypto`,
and because `crypto.subtle` is **async** while `s3/sign` is a straight-line
derivation with no I/O in it. Making the signer async to accommodate the host's
crypto API would push promises through every caller of a pure function;
`@noble/hashes` is synchronous, audited, and already what
`kotobase-protocols-worker` uses for the same reason.

Live, both providers, 19/19 each:
**https://kura-conformance.04-feasts-minded.workers.dev/conformance**

And the audit that matters — `/audit` — currently says **no**:

| layout | shards | tolerates | domains | need | largest | survivable |
|---|---|---|---|---|---|---|
| launch | 32 | 13 | 2 | ≥3 | 16 | ✗ |
| target | 26 | 7 | 2 | ≥4 | 13 | ✗ |

Two providers spread 32 shards 16-and-16, and 16 is more than 13. The number
is not a judgement call: `ceil(shards / tolerated)` is the minimum count of
genuinely independent domains, and until the fleet has that many the code's
tolerance is decoration. That is what this harness is for — turning "spread it
across providers" into an integer that is either satisfied or not.

## Running a node

`kura.node.fs` made a self-hosted node possible. This makes it a command —
and the distance between those two is why the fleet is still short a failure
domain, because **a backend nobody can start is not a node.**

```bash
kbb --backend sci --classpath "src:script:../kura/src:../erasure/src:../merkle-sum/src:../sigv4/src" \
  script/run_node.cljk --root ~/kura-data --port 8080 \
  --node-id my-node --operator alice --site home
```

Serves the async shard-store contract over HTTP, so a coordinator probes a
self-hosted node exactly the way it probes a rented bucket — a self-hosted node
is not a special case anywhere in the system. `GET /self-check` runs the full
contract against the real disk; verified 19/19 on a live run, including a
ranged read.

`--operator` and `--site` are both required, and the assertions say why.

`--site` names **a place, not a machine.** Ten machines in one room are one
failure domain: one power feed, one uplink, one flood. Passing a hostname is
the obvious thing to reach for, and this project's own first deployment did
exactly that — `--site $(hostname -s)` — which would have made each box its own
domain and inflated the fleet's durability by however many boxes are in the
room. That is the same flaw the `fs` demo exposed in `domain-key`, reintroduced
one layer up within a day of fixing it. Now it is impossible to reach for by
accident: there is no default.

### Live on owned hardware

Deployed to a Mac mini on a tailnet, 2026-07-30: contract **19/19** against its
real disk, a real PUT/GET/ranged-GET/DELETE round trip, and with the two rented
backends the placement audits as **3 domains, largest 11, survivable** for the
launch layout. Zero purchase — the machine was already there.

The rented backends remain measurement scaffolding and cannot be the business:
B2 costs $6/TB-month and R2 $15/TB-month against a $1.50/TB-month node payout,
so every rented terabyte loses $4.50 a month. Owned disk is about
$0.26/TB-month (a 20 TB drive at ~$250 over five years, plus ~6 W of power),
which is why $1.50 works for an operator and renting never can.

### Three things it is not

- **Not authenticated.** Phase 0 holds no customer data and takes no bond, so
  there is nothing to steal. `--accept-customer-data` is refused by an
  assertion rather than left as a TODO, because a node quietly serving
  unauthenticated writes with real data on it is the failure this project
  keeps trying not to ship. Wire `kura.order/admit` and a coordinator public
  key first.
- **Not reachable.** Binding a port is not a public address. Behind NAT you
  need a tunnel or a forwarded port; the coordinator cannot probe what it
  cannot reach, and an unreachable node reads as a dead one.
- **Not redundant on its own.** One disk, no RAID. That is fine — absorbing a
  lost shard is exactly what the erasure code is for — but the operator should
  know that is the arrangement rather than assume the network protects their
  disk.

## Tests

```bash
kbb -M:test
kbb -M:cljs -m cljs.main --target node -m kura.node.cljs-runner
kbb -M:lint
```

## License

MIT.
