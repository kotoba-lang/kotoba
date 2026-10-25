# kotoba-procedure

A multi-step external procedure -- KYC resubmission, corporate-account
setup, contract renewal -- as pure state transitions over an injectable
store. Zero-dep `.cljc`.

## Why this exists

`kotoba-lang/kotoba-issue-clj` already models issue → proposal(PR) → review
→ merge → audit: a single agent action that gets approved or rejected once.
That shape doesn't fit a "log in within 7 days to finish corporate account
setup or the transfer gets refunded"-style email: several ordered steps,
each one someone else's turn to move (you, the counterparty, or an agent),
and a deadline the whole thing can blow past without anyone approving or
rejecting anything. That gap was real, not hypothetical -- tracking exactly
this kind of Wise email had nowhere to live except a hand-written ledger
line before this library existed.

## Design

```text
kotoba.procedure.store -- IProcedureStore(get/put/list-entities, append-audit!) + mem-store
kotoba.procedure.gate  -- open!/advance-step!/block!/cancel!/expire!/note!, pure: expired?/next-action
```

Same `IProcedureStore` 4-fn contract shape as `kotoba-issue-clj`'s
`IssueStore` (`kind` is a caller-chosen partition keyword; a real deployment
adapts its own Datomic/kotobase backend) -- no code dependency between the
two libraries, since the state machines themselves are different shapes.

## Quickstart

```clojure
(require '[kotoba.procedure.store :as store]
         '[kotoba.procedure.gate :as gate])

(def s (store/mem-store))

(gate/open! s {:id "proc-1" :kind :wise/corporate-account-setup
              :title "Wise法人アカウント開設"
              :source "gmail" :source-id "19f31061f743c669"
              :deadline "2026-07-13T00:00:00Z"
              :steps [{:key :login :label "wise.comにログインして開設を完了する" :owner :self}
                      {:key :wise-confirms :label "Wiseが送金保留を解除する" :owner :counterparty}]})

(gate/next-action (store/get-entity s :procedure "proc-1") "2026-07-06T00:00:00Z")
;; => {:step {:kotoba.procedure.step/key :login ...} :overdue? false}

(gate/advance-step! s "proc-1" :login)   ; you logged in and finished setup
;; state stays :open -- one step left, owned by :counterparty

(gate/advance-step! s "proc-1" :wise-confirms)
;; => {:kotoba.procedure/state :done ...}
```

If nobody moves before the deadline, a runner tick calls:

```clojure
(when (gate/expired? proc (now-as-iso-string)) (gate/expire! s (:kotoba.procedure/id proc)))
```

## Relationship to `kotoba-ledger-clj`

A procedure's audit trail (`kotoba.procedure.gate/audit`) uses the same
event shape convention (`:id`/`:type`/`:at`/...) as `kotoba-issue-clj`'s, so
it can be projected through `kotoba-ledger-clj`'s JSONL codec the same way
-- but this library has no code dependency on either, matching the
"gate and ledger have different consumers/lifetimes" split established for
`kotoba-issue-clj`/`kotoba-ledger-clj`.

## Tests

```sh
kbb -M:test
```
