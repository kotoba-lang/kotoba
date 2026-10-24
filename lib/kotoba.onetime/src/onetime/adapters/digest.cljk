(ns onetime.adapters.digest
  (:require [onetime.model :as m]
            [onetime.ports :as p]))

(defprotocol IDigestVerifier
  (verify-digest! [verifier payload opts]))

(defn- payload [challenge response]
  {:challenge-id (:onetime/id challenge)
   :kind (:onetime/kind challenge)
   :subject (:onetime/subject challenge)
   :purpose (:onetime/purpose challenge)
   :digest-ref (:onetime/digest-ref challenge)
   :response response})

(defn verifier-port [verifier opts]
  (reify p/IOneTime
    (verify! [_ challenge response]
      (let [result (verify-digest! verifier (payload challenge response) opts)]
        (m/result challenge (not (:error result))
                  {:verified-at (:verified-at result)})))))
