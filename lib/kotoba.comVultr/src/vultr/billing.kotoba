(ns vultr.billing
  "Vultr billing history/invoice listing (read-only). Pairs with
  vultr.account for the \"what is this account actually being charged, and
  for what\" audit that today only exists as ad hoc dashboard clicking or
  trusting an invoice email's prose."
  (:require [vultr.client :as client]))

#?(:clj
(defn list-history
  "Paginated billing history (charges, payments, refunds, credits).
  `opts` may include :cursor and :per-page (max 500, Vultr default 100)."
  ([] (list-history {}))
  ([{:keys [cursor per-page] :as http-opts}]
   (:billing_history
    (client/request! "/billing/history"
                     (assoc (dissoc http-opts :cursor :per-page)
                            :query (cond-> {}
                                     cursor (assoc :cursor cursor)
                                     per-page (assoc :per_page per-page))))))))

#?(:clj
(defn list-invoices
  "Paginated invoice listing. `opts` may include :cursor and :per-page."
  ([] (list-invoices {}))
  ([{:keys [cursor per-page] :as http-opts}]
   (:billing_invoices
    (client/request! "/billing/invoices"
                     (assoc (dissoc http-opts :cursor :per-page)
                            :query (cond-> {}
                                     cursor (assoc :cursor cursor)
                                     per-page (assoc :per_page per-page))))))))

#?(:clj
(defn get-invoice
  ([invoice-id] (get-invoice invoice-id {}))
  ([invoice-id http-opts]
   (:billing_invoice (client/request! (str "/billing/invoices/" invoice-id) http-opts)))))

#?(:clj
(defn invoice-items
  "Line items for one invoice -- what specifically was billed, not just the total."
  ([invoice-id] (invoice-items invoice-id {}))
  ([invoice-id http-opts]
   (:invoice_items (client/request! (str "/billing/invoices/" invoice-id "/items") http-opts)))))
