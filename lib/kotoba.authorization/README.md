# authorization

Authorization request/decision facade. Policy evaluation can be delegated to
`kotoba-lang/policy`; CACAO capability verification can be delegated to
`kotoba-lang/cacao`.

## Where decisions are kept

`authorization.schema` declares every attribute once, in Datomic's
installation tx-data dialect. A real Datomic connection transacts it as-is;
`langchain.db/schema-from-tx-data` converts it for the in-memory store. Each
entity carries its identity as a `:db.unique/identity` attribute — a string
`:db/id` is a tempid scoped to one transaction, so a request and the decision
answering it only looked like one entity because both were written under the
same string in the same write. They are two entities joined by
`:authz.decision/request`, which says so.

`authorization.adapters.journal-ledger` is the durable `IDecisionLedger`:
[`langchain.db`](https://github.com/kotoba-lang/langchain) holds the index and
answers the Datalog, [`journal`](https://github.com/kotoba-lang/journal) holds
the append-only history, and the connection replays that history on open — so a
restarted process answers the same queries the previous one did, and the replay
invariant (one decision per request id) is a query rather than a set maintained
by hand.

```clojure
(def ledger (jl/journal-decision-ledger {:path "authz.journal.edn"}))
(ledger/persist-decision! ledger request decision {:request-id "r1"})
(jl/decision ledger "r1")   ;; the decision, with what was asked
(jl/history io)             ;; what happened, in order
```

Nested EDN — a request's context, a decision's effect trace and its
obligations — is stored as a `pr-str` blob, because no Datomic value type holds
a vector of maps; the ledger reads them back on the way out. Attributes with no
value are dropped rather than asserted as nil, which a real transactor rejects.

## Test

```bash
kbb -M:test
```
