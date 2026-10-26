(ns browser.account
  "Minimal account identity model for kotoba-only browser profiles.")

(defn new-account
  [{:keys [id handle display-name trust keys] :as opts}]
  {:account/id (or id handle "local")
   :account/handle handle
   :account/display-name (or display-name handle "Local User")
   :account/trust (or trust :local)
   :account/keys (vec keys)
   :account/meta (dissoc opts :id :handle :display-name :trust :keys)})

(defn verified?
  [account]
  (contains? #{:verified :trusted} (:account/trust account)))
