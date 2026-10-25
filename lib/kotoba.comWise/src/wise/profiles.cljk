(ns wise.profiles
  "Wise profile listing (personal + business profiles on the token's
  account). REST v1, JVM-only."
  (:require [wise.client :as client]))

#?(:clj
(defn list-profiles
  ([] (list-profiles {}))
  ([http-opts] (client/request! "/v1/profiles" http-opts))))

#?(:clj
(defn business-profile
  "The first business-type profile, or nil if the account has none."
  ([] (business-profile {}))
  ([http-opts]
   (first (filter #(= "business" (:type %)) (list-profiles http-opts))))))
