(ns wise.recipients
  "Wise recipient account listing (read-only). REST v1, JVM-only."
  (:require [wise.client :as client]))

#?(:clj
(defn list-recipients
  ([profile-id] (list-recipients profile-id {}))
  ([profile-id http-opts]
   (client/request! "/v1/accounts" (assoc http-opts :query {:profile profile-id})))))
