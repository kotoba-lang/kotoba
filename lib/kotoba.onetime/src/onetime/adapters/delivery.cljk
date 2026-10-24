(ns onetime.adapters.delivery)

(defprotocol IDeliveryClient
  (deliver! [client payload opts]))

(defn delivery-payload [challenge code opts]
  {:challenge-id (:onetime/id challenge)
   :kind (:onetime/kind challenge)
   :subject (:onetime/subject challenge)
   :purpose (:onetime/purpose challenge)
   :channel (:channel opts)
   :destination (:destination opts)
   :template-ref (:template-ref opts)
   :code code
   :expires-at (:onetime/expires-at challenge)})

(defn send-code! [client challenge code opts]
  (let [payload (delivery-payload challenge code opts)]
    (deliver! client payload opts)))

(defn email-client [send-email!]
  (reify IDeliveryClient
    (deliver! [_ payload opts]
      (send-email! (assoc payload :channel :email) opts))))

(defn sms-client [send-sms!]
  (reify IDeliveryClient
    (deliver! [_ payload opts]
      (send-sms! (assoc payload :channel :sms) opts))))
