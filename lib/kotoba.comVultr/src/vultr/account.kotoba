(ns vultr.account
  "Vultr account info lookup (read-only): balance, pending charges, ACLs."
  (:require [vultr.client :as client]))

#?(:clj
(defn get-account
  "Current account balance/pending-charges/last-payment snapshot. This is
  the cheapest single call to answer \"is this account about to be
  surprised by a charge\" without opening the dashboard."
  ([] (get-account {}))
  ([http-opts]
   (:account (client/request! "/account" http-opts)))))
