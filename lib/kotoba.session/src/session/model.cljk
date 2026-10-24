(ns session.model)

(def statuses #{:active :expired :revoked})

(defn session [id subject opts]
  {:session/id id
   :session/subject subject
   :session/status (get opts :status :active)
   :session/authn-ref (:authn-ref opts)
   :session/device-id (:device-id opts)
   :session/ip (:ip opts)
   :session/token-binding (:token-binding opts)
   :session/cookie-binding (:cookie-binding opts)
   :session/header-binding (:header-binding opts)
   :session/created-at (:created-at opts)
   :session/last-seen-at (:last-seen-at opts)
   :session/rotated-from (:rotated-from opts)
   :session/expires-at (:expires-at opts)})

(defn event [session type opts]
  {:session.event/session-id (:session/id session)
   :session.event/type type
   :session.event/at (:at opts)
   :session.event/reason (:reason opts)})
