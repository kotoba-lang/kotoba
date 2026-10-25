(ns authentication.adapters.email
  "Provider-neutral email verification, OTP and magic-link records. The host
  supplies random tokens/digests and sends mail through SES/Resend/Postmark."
  (:require [authentication.identity :as identity]
            [authentication.model :as model]))

(defn challenge
  [{:keys [id subject purpose email token-digest attempts max-attempts
           expires-at created-at used?]}]
  (let [email (identity/normalize-email email)]
    (when-not (and (some? id) (some? subject) email
                   (#{:verify-email :login :reset-password} purpose)
                   (string? token-digest) (<= 32 (count token-digest)))
      (throw (ex-info "invalid email challenge" {:purpose purpose})))
    {:identity.email-challenge/id id
     :identity.email-challenge/subject subject
     :identity.email-challenge/purpose purpose
     :identity.email-challenge/email email
     :identity.email-challenge/token-digest token-digest
     :identity.email-challenge/attempts (or attempts 0)
     :identity.email-challenge/max-attempts (or max-attempts 5)
     :identity.email-challenge/created-at created-at
     :identity.email-challenge/expires-at expires-at
     :identity.email-challenge/used? (boolean used?)}))

(defn challenge-usable? [record now]
  (and (not (:identity.email-challenge/used? record))
       (< (:identity.email-challenge/attempts record)
          (:identity.email-challenge/max-attempts record))
       (neg? (compare now (:identity.email-challenge/expires-at record)))))

(defn verify
  "Turn a usable email challenge into an authentication factor.

  `digest-matches?` is supplied by the host so JVM, WebCrypto, and a remote HSM
  may each perform the comparison appropriate to their digest representation.
  The raw token is deliberately outside this contract."
  [record presented-digest now digest-matches?]
  (let [ok? (and (challenge-usable? record now)
                 (boolean
                  (digest-matches?
                   (:identity.email-challenge/token-digest record)
                   presented-digest)))]
    (model/factor
     (:identity.email-challenge/id record)
     :email ok?
     {:subject (:identity.email-challenge/subject record)
      :evidence-ref (:identity.email-challenge/id record)
      :assurance :address-possession
      :at now})))

(defn consume [record now]
  (assoc record
         :identity.email-challenge/used? true
         :identity.email-challenge/used-at now))

(defn supersede [record now]
  (assoc record
         :identity.email-challenge/used? true
         :identity.email-challenge/used-at now
         :identity.email-challenge/terminal-reason :superseded))

(defn consume-tx [challenge-id now]
  [{:db/id challenge-id
    :identity.email-challenge/used? true
    :identity.email-challenge/used-at now}])
