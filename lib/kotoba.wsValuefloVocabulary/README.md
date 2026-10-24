# ws-valueflo-vocabulary

**[Valueflows](https://www.valueflo.ws/) — the REA (Resource–Event–Agent)
vocabulary for distributed economic networks — as pinned EDN and portable
`.cljc`.** A `kotoba-lang` origin-plane mirror: `valueflo.ws` reversed gives
`ws-valueflo`, the same derivation as `org-ietf-x509` and `io-libp2p`
(ADR-2608040100).

Upstream is `https://w3id.org/valueflows/ont/vf`, pinned by sha256 in
[`resources/valueflows/upstream.edn`](resources/valueflows/upstream.edn).
Sibling repository: [`ws-valueflo-algorithms`](https://github.com/kotoba-lang/ws-valueflo-algorithms)
implements the network-based algorithms on top of this.

## Why this exists

This workspace reached most of REA independently and under other names — MRP
explosion in `kotoba-lang/plm`, mutual credit in `cloud-itonami/credits`,
content-addressed receipts everywhere. What it lacked was a **shared economic
vocabulary**, so an event in one actor could not be joined to a resource in
another. Valueflows is that vocabulary, and as of ADR-2608153000 it is the
one the 営み OS uses.

## The operative part is the action behaviour table

Valueflows has 19 actions. Each one carries eleven cells saying what it does
to an inventoried resource — and that table, not the class diagram, is what
makes the vocabulary executable:

| action | inputOutput | accountingEffect | onhandEffect |
|---|---|---|---|
| `produce` | output | increment | increment |
| `consume` | input | decrement | decrement |
| `work` | input | notApplicable | notApplicable |
| `use` | input | notApplicable | notApplicable |
| `transfer` | notApplicable | decrementIncrement | decrementIncrement |
| `transferAllRights` | notApplicable | decrementIncrement | **notApplicable** |
| `transferCustody` | notApplicable | **notApplicable** | decrementIncrement |

The last two rows are the reason to mirror the spec rather than paraphrase it:
moving *rights* and moving *the thing* are separate registers, and most
inventory models collapse them.

**The table is published upstream as a PNG.** It is machine-readable only in
the TTL, which is why `bin/ingest.cljk` reads the RDF and not the website — a
mirror built from the rendered docs would have had to transcribe an image by
eye.

## Use

```clojure
(require '[valueflows.vocabulary :as vocab]
         '[valueflows.event :as ev])

(vocab/effect :transferCustody :accounting-effect)   ;=> :notApplicable
(vocab/effort-based? :work)                          ;=> true

;; REA accounting as a pure function; the arithmetic comes from the table
(ev/apply-event {"grain" {:onhand-quantity {:has-numerical-value 100 :has-unit :kg}
                          :accounting-quantity {:has-numerical-value 100 :has-unit :kg}}}
                {:action :transfer :provider :farm :receiver :mill
                 :resource-inventoried-as "grain"
                 :to-resource-inventoried-as "grain-at-mill"
                 :resource-quantity {:has-numerical-value 30 :has-unit :kg}
                 :to-location :mill-yard})
;=> {:ok? true :action :transfer :inventory {"grain" {...70...} "grain-at-mill" {...30...}}}
```

| namespace | what it is |
|---|---|
| `valueflows.data` | the vocabulary, generated. Not hand-edited |
| `valueflows.vocabulary` | read access; the only place that knows the shape |
| `valueflows.event` | apply events to an inventory, driven by the table |
| `valueflows.commitment` | promises and their settlement: `vf:fulfills`, `vf:satisfies` |
| `valueflows.proposal` | offers, requests, and reciprocity: `vf:Proposal`, `vf:Agreement` |
| `valueflows.unit` | which spellings mean one unit, and what may be added at all |
| `valueflows.conform` | structural conformance of events / commitments / intents |
| `valueflows.datom` | projection onto this workspace's datom plane |
| `valueflows.mapping` | where each VF term already lives here, and where it does not |

## Promises, and whether they were kept

```clojure
(require '[valueflows.commitment :as cm])

(cm/fulfilment {:id "po-1" :action :transfer :resource-quantity {:has-numerical-value 100 :has-unit :kg} :due 10}
               [{:action :transfer :fulfills "po-1" :resource-quantity {:has-numerical-value 60 :has-unit :kg}}]
               {:as-of 11})
;=> {:ok? true :state :partially-fulfilled :ratio 3/5
;;   :outstanding {:has-numerical-value 40 :has-unit :kg} :overdue true}
```

Three distinctions this keeps that a percentage alone loses:

- **`finished` is not `fulfilled`.** Upstream defines `vf:finished` as "no more
  will be done … irrespective of if the original goal has been met", so a
  commitment closed at 60% is `:closed-short` — an ordinary outcome, neither a
  success nor an error, and still reported as 40 kg short.
- **Overdue needs an `:as-of`.** Without one, and for a promise with no due
  date, the answer is `:unknown` rather than `false`.
- **An orphan `:fulfills`** — an event settling a commitment nobody has —
  is listed, because every other commitment in the batch looks correctly
  settled.

Deadlines may be caller-defined period numbers **or** ISO-8601 strings (which
sort chronologically, so no date library is needed). The two are never compared
to each other.

## Reciprocity

An offer is not much use without what is expected back, and an agreement's whole
job is to say whether both sides delivered.

```clojure
(require '[valueflows.proposal :as p])

;; a price-list line multiplies into commitments -- BOTH sides scale
(p/commitments-from price-list-line 3 {:agreement "agr-1" :due 12})
;=> {:ok? true :commitments [{... 3 loaves}] :reciprocal-commitments [{... 1500 JPY}]}

(p/commitments-from one-off-offer 3 {})
;=> {:ok? false :insufficient :not-unit-based}
```

`vf:unitBased` gates that multiplication, exactly as upstream describes it
("can be multiplied to create commitments; commonly seen in a price list").
Three of *this specific used bicycle* is a category error, not a bigger order.
Scaling the goods without the payment is how a price list becomes a loss, so
both sides scale together.

For agreements, `agreement-balance` answers **which party is exposed** —
delivered while the other still owes:

```clojure
(p/agreement-balance loan events {:as-of 7})
;=> {:ok? true :one-sided-exposure :reciprocal-outstanding
;;   :both-fulfilled? false :both-closed? false}
```

Two distinctions kept deliberately:

- **A one-sided deal is described, not rejected.** Upstream's "*sometimes* with
  what is expected in return" is load-bearing: a gift, a grant and a mutual-aid
  contribution have nothing reciprocal, and rejecting them would make this
  unable to express most of what a commons does.
- **Repaid and written off are both `:both-closed?`, but only one is
  `:both-fulfilled?`.** A lender whose loan was written off is no longer
  waiting, so there is no exposure — but they did lose the money, and
  `:closed-short` names which commitments. One `:settled?` flag would have
  destroyed that, and the first draft of this namespace did exactly that until a
  test caught it.

This is also the shape a loan takes in Valueflows terms: the principal is a
primary commitment, the repayments are reciprocal ones. `valueflows.mapping`
records that next to the `cloud-itonami-commitment-ledger` false friend, whose
"commitment" still means something else.

## Units

Refusing to add hours to kilograms is only worth having if two callers spell a
unit the same way. `valueflows.unit` is the small registry that makes that true:

```clojure
(require '[valueflows.unit :as u])

(u/same? :kg :kilogram)        ;=> true
(u/compatible? :kg :g)         ;=> true   (same quantity kind)
(u/compatible? :en :jpy)       ;=> false  (mutual credit is not currency)
(u/resolve-unit :kilo)         ;=> {:unit :kilo :source :unregistered}
(u/om-2-iri :second)           ;=> ".../om-2/second-Time"
```

`vf:Unit` is `rdfs:subClassOf om:Unit`, so [om-2](http://www.ontology-of-units-of-measure.org/)
is the authority for physical units; currencies carry an ISO 4217 code as well.
Three things the registry exists to hold, each measured against the om-2 RDF
distribution rather than assumed:

- **om-2 has no `each`.** A count of things is `piece`; `one` is the
  dimensionless ratio, a different quantity kind.
- **om-2 has no bare `second` or `minute`** — they are `second-Time` and
  `minute-Time`, because `second-Angle` also exists.
- **om-2 capitalises `JapaneseYen` but not `euro`.** Copied as-is; an
  identifier is not ours to tidy.

ENGI's `EN` is `:authority :none` and `:quantity-kind :mutual-credit`, not
`:currency` — it has no issuer and pays no interest, and calling it money would
make it addable to yen.

**An unregistered spelling is reported, never guessed.** `:kilo` does not
become kilograms by resembling them. The registry is small on purpose: measured
2026-08-15, `kotoba-lang/plm` declares `:plm.item/uom` and populates it
nowhere, so there is no divergent corpus to reconcile — this is the convention
written down before divergence.

```sh
kbb --backend sci bin/units.cljk --check                    # generated data matches the registry
kbb --backend sci bin/units.cljk --verify-om2 om-2.0.rdf     # every om-2 name really exists
```

`--verify-om2` takes a path rather than fetching, because the om-2 website
returned 500 on 2026-08-15 and every `/resource/om-2/<name>` 404'd — a network
check would fail for reasons unrelated to the registry. Without a readable file
it exits **2**, not 0.

## Regenerate and verify

```sh
kbb --backend sci bin/ingest.cljk           # TTL -> vocabulary.edn + src/valueflows/data.cljk
kbb --backend sci bin/ingest.cljk --check    # 0 identical / 1 stale / 2 could not answer
kbb --backend sci bin/units.cljk             # units.edn -> src/valueflows/unit_data.cljk
kbb -M:test                # 101 tests, 664 assertions
```

`--check` is three-valued on purpose. A missing TTL, a sha256 that does not
match the pin, or a parse that falls below the measured evidence floor (19
actions, 67 classes, 111 properties, 19 enum members) exits **2** — not 0.
A mirror that cannot read its upstream must not report a pass
(ADR-2608136000).

## What this does not do

- **No calendar arithmetic.** Time in the algorithms repo is a number the
  caller defines.
- **No RDF or GraphQL surface.** The vocabulary lands on the workspace's datom
  plane; `vf-graphql` is not implemented.
- **No claim of coverage.** `valueflows.mapping/summary` reports how many
  classes were examined against how many exist, because the difference is
  *unexamined*, not *absent*.
- **It cannot verify its own mapping.** The repositories it cites are west
  projects outside this tree. Each claim therefore carries an `:evidence`
  citation with the date it was read, labelled as a citation rather than a
  measurement.

## Naming

`ws-valueflo-vocabulary`, not `valueflows-clj` and not `org-valueflows`: the
origin plane reverses the authority's registrable domain, `valueflo.ws`
(NS-delegated, checked 2026-08-15). Language is not package identity, and
`-clj` suffixes are prohibited workspace-wide.

## Licence

Apache-2.0 for this repository. The mirrored ontology is upstream's, released
by the Valueflows project under Creative Commons Attribution 4.0; see
`resources/valueflows/upstream.edn` and NOTICE.
