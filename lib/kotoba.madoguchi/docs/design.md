# madoguchi — design

Customer support / CRM domain library on chobo.ledger (lane `:support`) + shitsuke.

## madoguchi.ticket
`Ticket{:id :customer :subject :status :priority :assignee :messages :sla-due :created-at}`. Status statechart: `:new → :open → :pending → :resolved → :closed` (reopen `:resolved/:closed → :open`). `(ticket m)`, `(open/pending/resolve-ticket/close/reopen t)`, `(add-message t msg)`, `(sla-breached? t now)`, `(support-activity t opts)` → chobo.ledger activity (lane :support).

## madoguchi.customer
`Customer{:id :name :email :tags :order-refs :lifetime-value :contacts}`. `Contact{:id :customer :channel :direction :subject :timestamp}`. `(customer m)`, `(tag/untag c t)`, `(add-contact c contact)`, `(contacts-by-channel c ch)`, `(add-order-ref c id)`, `(add-lifetime-value c amt)`.

## madoguchi.events / views / ssr
re-frame portable 7-fn subset. app-db `{:tickets [] :customers {}}`. events: `:madoguchi/init`, `:ticket/add`, `:ticket/transition`, `:ticket/message`, `:customer/loaded`, `:customer/tag`. subs: `:madoguchi/tickets`, `:madoguchi/open-tickets`, `:madoguchi/customers`, `:madoguchi/customer`. Views: `ticket-row`, `customer-card`, `root`. SSR: `sample-db`, `root-html`.
