(ns onetime.model)

(def kinds #{:totp :hotp :email-code :sms-code :recovery-code :transaction-code})

(defn challenge [id kind opts]
  {:onetime/id id
   :onetime/kind kind
   :onetime/subject (:subject opts)
   :onetime/purpose (:purpose opts)
   :onetime/digest-ref (:digest-ref opts)
   :onetime/created-at (:created-at opts)
   :onetime/expires-at (:expires-at opts)})

(defn result [challenge ok? opts]
  {:onetime/id (:onetime/id challenge)
   :onetime/kind (:onetime/kind challenge)
   :onetime/ok? (boolean ok?)
   :onetime/attempts (:attempts opts)
   :onetime/verified-at (:verified-at opts)})
