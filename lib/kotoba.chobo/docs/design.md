# chobo — design

Layer-by-layer API for `chobo` (services-EC foundation). For the *why* see
`docs/adr/0001-chobo-services-ec.md`.

## chobo.ledger (EAVT audit-ledger)

```
Activity  {:id :lane :kind :title :state :source :source-id :repo :tenant :actor :artifacts :parent :created-at :due-at}
Artifact  {:id :type :title :source :source-id :content-cid :props}
Relation  {:id :type :from :to :source :props}
Decision  {:id :activity :policy :status :decider :decided-at :note}
Effect    {:id :activity :kind :risk :status :tool :payload :repo}
Ledger    {:activities [] :artifacts [] :relations [] :decisions [] :effects []}
```
- `(ledger)`, `(append-activity l a)`, `(append-artifact ...)`, `(append-relation ...)`, `(append-decision ...)`, `(append-effect ...)`.
- Activity states `:open → :done | :cancelled`: `(activity m)`, `(can-transition? from to)`, `(transition-activity a to)`.
- Effect lifecycle `:proposed → :approved → :applied | :rejected`: `(effect m)`, `(approve-effect e)`, `(apply-effect e)`, `(reject-effect e)`.
- Queries: `activities-by-lane/-repo/-tenant`, `effects-for-activity`, `decisions-for-activity`, `open-activities`.
- `ILedgerStore` port (`put-record! [r]` / `get-activity [id]` / `list-activities` / `list-effects`); `(mock-ledger-store)`.

## chobo.subscription

```
Plan  {:id :name :tier :price :currency :entitlements {} :quotas {} :overage-rates {}}
Usage  {:tenant :consumed {key → used}}
```
- `(plan m)`, `(entitled? plan key)`, `(quota-for plan key)`, `(consumed-for usage key)`, `(within-quota? plan usage key amount?)`, `(record-usage usage key amount)`, `(overage plan usage key)`, `(total-overage plan usage)`.
- `(metering-event tenant key amount opts)` → a ledger activity.
- Sample tiers: `free-tier`, `pro-tier`.

## chobo.invoice

```
Invoice  {:id :tenant :lines [] :status :totals :issued-at :due-at}
Line     {:description :amount :currency}
```
- `(line desc amount currency?)`, `(invoice tenant opts?)`, `(add-line inv l)`, `(totals inv)` → `{:amount :currency}`.
- Status `:draft → :issued → :paid | :overdue | :cancelled`: `(can-transition? from to)`, `(transition inv to)`, `(mark-issued/paid/overdue inv)`, `(cancel inv)`, `(dunning? inv now)`.
- `(billing-activity inv opts)` → a ledger activity (lane :billing, kind :invoice).
- `IInvoiceStore` port (`put-invoice! [inv]` / `get-invoice [id]` / `list-invoices` / `overdue-invoices [now]`); `(mock-invoice-store)`.

## chobo.tenant

```
Tenant  {:id :name :plan-id :capabilities #{} :operator-level}
```
- `operator-levels` = `[:contributor :self-host :certified :managed :core]`.
- `(tenant id opts?)`, `(has-cap? t cap)`, `(grant t cap)`, `(revoke t cap)`, `(at-least-level? t target)`.

## chobo.events (re-frame, portable subset)

`(register!)` against `shitsuke.re-frame.core`. app-db `{:ledger :plan :usage :invoices :tenant}`.
- events: `:ledger/append-activity`, `:plan/loaded`, `:meter/record`, `:invoice/added`, `:invoice/transition`, `:tenant/loaded`.
- subs: `:ledger/ledger`, `:ledger/open-activities`, `:plan/plan`, `:plan/entitled?`, `:meter/usage`, `:meter/overage`, `:invoice/invoices`, `:tenant/tenant`.

## chobo.views (pure hiccup on shitsuke.components)

`chobo__*` classes via `shitsuke.style/class-name`.
- `(tenant-badge t)`, `(ledger-entry a)`, `(meter-gauge plan usage key)`, `(plan-status plan usage)`, `(invoice-line l)`, `(invoice-card inv)`, `(root db)`.

## chobo.ssr

`(sample-db)`, `(root-html db?)` → HTML string with shitsuke `:root` token vars.
