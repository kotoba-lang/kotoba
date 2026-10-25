(ns wise.balances
  "Wise multi-currency balance listing (read-only). REST v4, JVM-only."
  (:require [wise.client :as client]))

#?(:clj
(defn list-balances
  ([profile-id] (list-balances profile-id {}))
  ([profile-id http-opts]
   (client/request! (str "/v4/profiles/" profile-id "/balances")
                    (assoc http-opts :query {:types "STANDARD"})))))
