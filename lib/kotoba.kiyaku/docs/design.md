# kiyaku — design

Customer accounts + returns/RMA domain library on chobo.ledger (lanes `:customer` + `:returns`) + shitsuke. The end-customer counterpart to chobo.tenant (operator).

## kiyaku.account
`Account{:id :email :name :addresses :payment-method-refs :wallet-balance :created-at}`. `Address{:id :label :line1 :line2 :city :postal :country :default?}`. `(account m)`, `(add-address acc addr)`, `(default-address acc)`, `(set-default-address acc id)`, `(add-payment-method acc ref)`, `(adjust-wallet acc amt)`, `(customer-activity acc opts)` → chobo.ledger activity (lane :customer).

## kiyaku.returns
`ReturnRequest{:id :order-id :account-id :items :reason :status :refund-amount}`. Status statechart: `:requested → :approved → :shipped → :received → :refunded` (`:rejected` from `:requested/:approved`). `(return-request m)`, `(approve/reject/mark-shipped/mark-received/refund r)`, `(set-refund r)`, `(total-return-qty r)`, `(return-activity r opts)` → chobo.ledger activity (lane :returns, kind :rma).

## kiyaku.events / views / ssr
re-frame portable 7-fn subset. app-db `{:accounts {} :returns []}`. events: `:kiyaku/init`, `:account/loaded`, `:account/add-address`, `:return/add`, `:return/transition`. subs: `:kiyaku/accounts`, `:kiyaku/account`, `:kiyaku/returns`, `:kiyaku/open-returns`. Views: `account-card`, `return-row`, `root`. SSR: `sample-db`, `root-html`.
