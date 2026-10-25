# kura-bugyo

蔵奉行 — the economics of the [kura](https://github.com/kotoba-lang/kura)
storage network: what a customer pays, what a node earns, what it must bond,
and a payout root anyone can check.

Design: [ADR-2607299200](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607299200-kura-erasure-coded-storage-network.edn).

## Permissionless, bonded, no token

ADR open question 1 asked "bonded invite-only **or** permissionless". That was
a false dichotomy — **bonding and open participation are orthogonal** (Filecoin
is both). What filters the node-loss rate is the collateral, not the invitation.

So: **anyone may run a node; the bond is the barrier, not a gatekeeper.**

And **no network token.** Priced in USD, settled in USDC on Base through
`kotoba-lang/pay` (which holds no keys). A token whose value derives from
network fees makes the security budget reflexive — collateral is worth least
exactly when the network is being doubted — and puts every customer through an
exchange to buy storage.

## Checked against the incumbent

Storj publishes what it pays storage-node operators. Read 2026-07-29:

| | Storj publishes | kura uses |
|---|---|---|
| node storage | $1.50 / TB-month | **$1.50** |
| node egress | $2.00 / TB | **$2.00** |
| node audit/repair bandwidth | $2.00 / TB | $2.00 (the bond's repair anchor) |

All three match, so those rates are `:benchmarked` rather than `:modelled` —
what the incumbent publicly pays, which is a much stronger footing than a
guess and still not a measurement of *our own* node economics.

**A caution that cost real time.** A search summary reported Storj's egress
payout as $20/TB and repair as $10/TB, which would have made the collateral
model's repair anchor five times larger and the operator bond prohibitive. The
official payout page says $2.00 for both. Rates that move the bond get read
from the source, not from a summary.

### Where kura is cheaper, and why

| | retail / TB-month | COGS | margin |
|---|---|---|---|
| Storj (2.76× expansion) | $7.00 | $4.14 | 41% |
| kura launch (2.0×) | **$4.62** — 34% less | $3.00 | 35% |
| kura target (1.625×) | **$3.75** — 46% less | $2.44 | 35% |

kura is cheaper **on a thinner margin**, paying node operators the identical
rate. The entire difference is the storage multiplier. That is worth stating
plainly because the alternative readings — undercutting operators, or running
a fatter margin — are both wrong and both are what a cheaper price usually
means.

## The identity that makes the code a business decision

```
customer pays for LOGICAL bytes
nodes are paid for PHYSICAL bytes
the storage multiplier is the coordinator's cost of goods
```

| | multiplier | storage | egress | 1 PB/month |
|---|---|---|---|---|
| **launch** k=16 n=32 | 2.000× | $4.62/TB-mo | $3.08/TB | $4,615 |
| **target** k=16 n=26 | 1.625× | $3.75/TB-mo | $3.08/TB | $3,750 |

Launch is conservative **on purpose**. At launch the node-loss rate is
unmeasured, and the costs are asymmetric: launching optimistic and finding the
rate is worse loses data irreversibly; launching conservative and finding it is
better is a price cut. The 18.7% reduction belongs to the customer — the
measurement that justifies it comes from running their data, and a coordinator
that pockets its own efficiency gain has nothing to say when asked why anyone
should help it measure.

**Egress is not multiplied by the code.** A systematic read reconstructs
nothing, so serving one logical TB moves one physical TB. Charging egress at
the storage multiplier would bill for work the network does not do.

## The bond has two anchors, and the larger wins

The usual derivation prices a bond above what a cheat *gains*. Run it here and
it comes out tiny, because the audit is strong: 688 challenges catch 1%
deletion at p=0.999, so a node that deletes everything is caught in about one
epoch and gains one epoch of storage cost — $15 for 10 TB.

But the network's loss is not the node's gain. Somebody has to **rebuild** what
the node held: `r/k` read from peers plus a write, so 1.25× the lost volume in
traffic. That anchor is larger, and it is the one that binds.

| capacity | bond | per TB | binding anchor |
|---|---|---|---|
| 10 TB | $75 | $7.50 | repair |
| 100 TB | $750 | $7.50 | repair |
| 1 PB | $7,500 | $7.50 | repair |

**Read `capital-cost`, not `payback-epochs`.** The payback figure is ~5 epochs
and sounds prohibitive; it is the wrong number, because the bond is
*collateral* and comes back. What an operator gives up is the return on locked
capital: **4.11% of revenue at a 10% opportunity cost.** Deciding on payback
would have had us cutting the safety factor to fix a problem that is not there.

## The payout root

Every epoch, node earnings (minus slashing) become `merkle-sum` leaves; the
root goes on chain; each node claims with an inclusion proof.

- Understate the total → contradicts some node's proof.
- Inflate a node's share → contradicts the published root.
- Shrink a sum → `merkle-sum` rejects it.

What is **not** covered: a coordinator that omits a node's orders entirely.
The node detects it immediately — it holds the signed orders — but detection is
not prevention, and the escalation is a dispute path. Saying so is the point;
this design keeps refusing to claim more than it has.

Slashing is applied **before** the tree is built. A deduction applied
afterwards would make the published root disagree with what was paid, and the
root is the only checkable thing there is. A slashed epoch also withholds
earnings up to the deduction — taking it from the bond alone would let a node
profit from an epoch it was caught cheating in.

`treasury-instruction` returns **data**, not a wallet call. The USDC transfer
goes through `pay`; signing happens where the keys are.

## Rates are parameters with stated provenance

Every default carries `:provenance :modelled` or `:chosen`. **None is
observed.** Phase 0 exists to replace them.

## The metadata plane, and the claim it exists to make true

ADR-2607299200 sections 3 and 4 rest on one question:

> node N is gone — which placement groups are now below threshold?

That is a join across `{PG → node set}`, `{node → liveness}`, `{PG → durability
class}` and `{PG → last audit}`. Section 4 forbids splitting those across refs,
because kura's query plane reaches exactly one ref and a sharded plane makes
the question **unanswerable**, not merely slow. Section 3 forbids storing
`shard → node` directly: at 64 MiB objects and n=32 that is 500 million rows
per petabyte.

So `kura.bugyo.plane` holds **placement groups, not shards** — one row per
group, and an object's group is a function of its id, never a stored row. That
turns a petabyte into ~10⁵ rows instead of ~10⁸, and the question into a scan.

Measured, in-memory, one assessment per touched group:

| groups | node-death query | groups touched |
|---|---|---|
| 1,000 | 36 ms | 160 |
| 10,000 | 126 ms | 1,600 |
| 100,000 (≈1 PB) | **1,227 ms** | 16,000 |

Linear in groups, as designed. A petabyte's worth is a query someone can wait
for; the shard-addressed version would have been a data-warehouse job, and the
scheduler would have been built around not asking.

### Single writer, and replay

Every mutation is an event through `apply-event`, a pure function from state
and event to state. Concurrency is handled by there **being one writer** — a
Durable Object in deployment — rather than by locking, because ADR-260726
points out that a shared ref with CAS serialisation is better solved by
removing the contention than by managing it.

`replay` rebuilds a plane from its log. The coordinator is a trusted point
(section 6f) and the only thing that makes a trusted point auditable is that
its decisions replay from a log someone else can read.

Two smaller decisions with teeth:

- **An unknown event is recorded as rejected, not ignored.** A plane that
  silently drops what it does not understand diverges from its own log, and the
  divergence is invisible until someone replays it.
- **A departed node is marked `:lost`, not deleted.** Forgetting it would make
  the groups that held it look healthy.
- **Shard state is derived from node liveness**, not stored beside it — so the
  bug where a node is marked dead and its shards are still marked live cannot
  occur.

## A spending ceiling that refuses, not one that warns

Phase 0 rents its storage, and renting loses money by construction *on the
wholesale basis*: B2 is $6.95/TB-month against a $1.50/TB-month node payout.
That is an acceptable price for learning how the system behaves under real cost
— **but only if the price is bounded, and an experiment without a ceiling is
not an experiment.** (Sold as a subscription rather than by the terabyte the
same bytes are profitable; see *Two bases* below. `report` is the wholesale
basis and labels itself as such.)

So `kura.bugyo.budget` puts the cap in the admission path. `admit-write?`
refuses once the projected bill passes it; a cap that only reports is a cap you
find out you exceeded.

| monthly cap | B2 alone (2.0×) | B2 + owned disk, mirrored |
|---|---|---|
| $10 | 0.72 TB | **1.44 TB** |
| $25 | 1.80 TB | **3.60 TB** |
| $100 | 7.19 TB | **14.39 TB** |

These fell by 14% on 2026-07-30, when B2's rate was corrected here from $6.00
to the published $6.95. The old figure was carried as `:published` and was not;
the rate that prices the entire rented fleet now cites the page it was read
from, the same way the node egress rate had to after a search summary put
Storj's at ten times its real value.

Three decisions in it, each closing a way a ceiling gets bypassed:

- **Cost is computed on physical bytes**, so the erasure multiplier is inside
  the number. A ceiling in logical TB silently doubles when the code's
  parameters change, which is the shape of every surprising cloud bill.
- **An unpriced provider is charged the most expensive known rate**, not zero.
  Defaulting an uncosted backend to free is how a cap gets bypassed by adding a
  backend nobody costed.
- **Owned disk is zero *marginal* cost and says so** — `:provenance :marginal`,
  with the ~$0.26/TB-month replacement figure in the note, so free-marginal is
  never read as free.

### The finding this produced

With **one** provider the erasure code buys nothing. 1 logical TB at 2.0× is
2 physical TB on B2 — $13.90/month — and the failure-domain audit correctly
says one domain. You pay twice for B2's durability.

| | cost / logical TB-month | survives |
|---|---|---|
| B2 alone, 2.0× coded | **$13.90** | B2-internal faults only |
| B2 + owned disk, mirrored | **$6.95** | **losing B2 entirely, or the disk entirely** |

Half the bill for the durability the code was charging double to not provide.

And a corollary worth stating because it contradicts this repo's own default:
**at two domains an LRC is the wrong code.** Surviving the loss of one of two
domains means tolerating n/2 erasures, which a non-MDS LRC only reaches at a
2.25–2.5× multiplier. At two domains, mirror. The local parity starts earning
its keep at the third site.

## Two bases, and why an unlabelled margin is unreadable

Everything above prices a terabyte. `kura.bugyo.pricing`'s retail plane sells a
quota at a subscription price instead, the shape `kotobase.net` already uses —
and a subscription is not anchored to $/TB at all, so the storage multiplier
that dominates the wholesale card stops mattering.

Tier prices are **adopted** from that service, not derived here; this library
only computes what serving them costs.

At the Phase 0 mix (everything on B2 at $6.95, launch layout 2.0×), priced at
the *worst case each quota permits*:

| plan | price | quota | storage cost/mo | storage gross margin | implied $/logical TB | ×Storj retail |
|---|---|---|---|---|---|---|
| Free | ¥0 | 512 MiB / 50 | $0.0078 | — | — | — |
| Developer Standard | ¥2,980 | 50 GiB / 1,000 | $0.75 | **96.2%** | $370 | 52.9× |
| Team Pro | ¥19,800 | 500 GiB / 10,000 | $7.54 | **94.3%** | $246 | 35.1× |
| Regulated | ¥100,000+ | — | `:uncomputable` | — | — | — |

**That margin covers the provider storage bill and nothing else** — not egress,
the coordinator, repair, audit, support or development. It was called
`:margin-at-full-quota` until the first attempt to publish it, which made
obvious that a 96% figure with no scope on the name reads as a business margin.
`:cost-excludes` now travels with it.

Four things this made explicit that a spreadsheet would have hidden:

- **The same bytes are loss-making and profitable at the same instant.** Three
  Standard subscriptions at full quota is 0.33 physical TB and a $2.26 bill.
  Wholesale: $0.75 of revenue, **−$1.51**. Retail: $59.60, **+$57.34**. Both
  reports now carry `:basis`, because `:loss-making?` without one reads as a
  verdict on the business.
- **The object quota is what bounds the small-object multiplier.** Sub-mebibyte
  objects are replicated 3× rather than coded, which looks like it breaks the
  price — but filling 50 GiB with them needs 51,200 objects against a cap of
  1,000. The worst reachable arrangement costs **0.98%** more than the flat
  coded figure. A pin cap that exists for metadata reasons turns out to bound
  the replication exposure too.
- **Egress is the risk, not storage.** Storage headroom is enormous; a Standard
  subscriber's gross profit is gone after reading their whole quota **~42
  times** in a month (Pro: ~29). B2's free allowance is a multiple of what it
  *holds*, so the code's multiplier enlarges the allowance without enlarging
  the bill, and its Class B calls are free — a systematic read touching k
  shards costs the same in transactions as touching one.
- **A plan with no quota has no computable cost.** `:regulated` returns
  `:uncomputable` rather than an estimate, and a free tier's margin is `nil`
  rather than 0 or −∞. Both would have been claims about quantities that do not
  exist.

`tier-economics` requires a cost basis rather than defaulting one, for the same
reason `storj.store` requires a clock: the physical rate depends on which
providers hold the shards, and the pricing namespace cannot know the fleet mix.
`budget/cost-basis` builds one from real usage.

## Tests

```bash
kbb -M:test
kbb -M:cljs -m cljs.main --target node -m kura.bugyo.cljs-runner
kbb -M:lint
```

## License

MIT.
