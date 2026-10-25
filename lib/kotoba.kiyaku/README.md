# kiyaku

`kiyaku`（客）— kotoba-lang shared **customer accounts + returns/RMA** domain
library. The end-customer counterpart to chobo.tenant (which is the operator).
Portable .cljc on [`chobo.ledger`](../chobo) (lanes `:customer` + `:returns`) +
[`shitsuke`](../shitsuke). Zero host effects.

| layer | role |
|---|---|
| `kiyaku.account` | CustomerAccount + address book + payment-method refs + wallet + ledger projection (lane :customer) |
| `kiyaku.returns` | ReturnRequest/RMA + status statechart (requested→approved→shipped→received→refunded|rejected) + refund + ledger projection (lane :returns) |
| `kiyaku.events` | re-frame events/subs (portable 7-fn subset) |
| `kiyaku.views` | pure-hiccup: account-card, return-row |
| `kiyaku.ssr` | SSR parity |

| `kotoba/returns_core.kotoba` | the same returns statechart + refund arithmetic **in Kotoba** — a port, not yet a cutover |

## The Kotoba port of `kiyaku.returns`

`kotoba/returns_core.kotoba` is the decision content of `kiyaku.returns`: what
a return may become, what it is worth, and which of its lines go back on the
shelf. It compiles with an **empty `requiredCapabilities`**.

Two differences from the `.cljc` are intended, and the parity test asserts them
rather than smoothing them over:

* a refused transition is `nil` in the `.cljc` and `[:result :document :keyword]`
  in the port. Kotoba has no nil, and the two arms are what make a caller handle
  the refusal — the `.cljc` idiom for the same thing is `(or (transition r to) r)`,
  which is in `kiyaku.events` today and silently keeps the old status.
* money is `:i64`. Only integer cases are compared; a decimal price is a
  value-shape question for the whole ledger, not one this port decides.

**Nothing has been cut over.** `kiyaku.returns` is still what every consumer
gets, and it stays the oracle until a soak says otherwise
(`lang/q9-migration.edn` rollback policy). `return-activity` is not ported: it
projects onto `chobo.ledger` in another repository, which is a module boundary
rather than a language one.

```bash
kbb -M:test       # published deps
kbb -M:local:test # local ../shitsuke ../chobo

# the port, on :jvm-kir :js and :wasm (ABSOLUTE path: a relative one is
# "input must be a regular file")
kotoba -M test "$PWD/kotoba/returns_core.kotoba"

# differential parity: the .cljc that ships against the ESM amu emitted.
# Both sides RUN -- the oracle is the namespace, not a table of remembered
# answers, and the port is the artifact, not the source.
kbb --backend sci --classpath "src:../chobo/src:../text/src" test/kotoba/returns_parity.cljk
```

See `docs/design.md` and `docs/adr/0001-kiyaku-customer-returns.md`.
