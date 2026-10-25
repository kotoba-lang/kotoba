(ns wise.transfers
  "Wise transfer listing/status lookup (read-only). REST v1, JVM-only."
  (:require [wise.client :as client]))

#?(:clj
(defn list-transfers
  "List transfers for `profile-id`, optionally filtered by `status`
  (e.g. \"incoming_payment_waiting\", \"processing\", \"funds_converted\",
  \"outgoing_payment_sent\", \"cancelled\", \"funds_refunded\" -- see Wise's
  transfer status docs for the full set)."
  ([profile-id] (list-transfers profile-id {}))
  ([profile-id {:keys [status] :as http-opts}]
   (client/request! "/v1/transfers"
                    (assoc (dissoc http-opts :status)
                           :query (cond-> {:profile profile-id}
                                    status (assoc :status status)))))))

#?(:clj
(defn get-transfer
  ([transfer-id] (get-transfer transfer-id {}))
  ([transfer-id http-opts]
   (client/request! (str "/v1/transfers/" transfer-id) http-opts))))
