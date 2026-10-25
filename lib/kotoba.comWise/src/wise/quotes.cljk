(ns wise.quotes
  "Wise quote creation (source/target currency + amount -> a quote with
  fees/rate, the first step before creating a transfer). REST v3, JVM-only."
  (:require [wise.client :as client]))

#?(:clj
(defn create-quote!
  "Create a quote under `profile-id`. `params` is the Wise quote request
  body, e.g. {:sourceCurrency \"GBP\" :targetCurrency \"JPY\"
  :sourceAmount 1000 :payOut \"BANK_TRANSFER\"} -- see Wise's quotes API
  docs for the full field set. This only creates a quote (no funds move);
  executing a transfer from it is a separate, deliberately unimplemented
  operation -- see this library's README/ADR for why."
  ([profile-id params] (create-quote! profile-id params {}))
  ([profile-id params http-opts]
   (client/request! (str "/v3/profiles/" profile-id "/quotes")
                    (assoc http-opts :method :post :body params)))))
