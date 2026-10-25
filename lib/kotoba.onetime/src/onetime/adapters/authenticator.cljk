(ns onetime.adapters.authenticator
  (:require [onetime.ports :as p]))

(defprotocol IAuthenticator
  (verify-one-time! [authenticator payload opts]))

(defn authenticator-port
  ([authenticator] (authenticator-port authenticator {}))
  ([authenticator opts]
   (reify p/IOneTime
     (verify! [_ challenge response]
       (let [out (verify-one-time! authenticator
                                   {:challenge challenge :response response}
                                   opts)]
         {:onetime/id (:onetime/id challenge)
          :onetime/kind (:onetime/kind challenge)
          :onetime/ok? (true? (:ok? out))
          :onetime/evidence-ref (:evidence-ref out)
          :onetime/verified-at (:verified-at out)})))))

(defn static-authenticator [result]
  (reify IAuthenticator
    (verify-one-time! [_ _payload _opts] result)))
