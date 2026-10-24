(ns saml.adapters.conditions
  (:require [saml.adapters.xml :as xml])
  #?(:clj (:import [java.time Instant]
                   [java.time.temporal ChronoUnit])))

(defn- before? [a b]
  (neg? (compare (str a) (str b))))

(defn- after-or-equal? [a b]
  (not (before? a b)))

(defn- plus-seconds [t seconds]
  #?(:clj (str (.plus (Instant/parse (str t)) (long seconds) ChronoUnit/SECONDS))
     :cljs t))

(defn- minus-seconds [t seconds]
  #?(:clj (str (.minus (Instant/parse (str t)) (long seconds) ChronoUnit/SECONDS))
     :cljs t))

(defn- condition-error [claims now skew-seconds]
  (cond
    (and (:not-before claims)
         (before? now (minus-seconds (:not-before claims) skew-seconds))) :not-before
    (and (:not-on-or-after claims)
         (after-or-equal? now (plus-seconds (:not-on-or-after claims) skew-seconds))) :not-on-or-after
    :else nil))

(defn condition-verifier [delegate opts]
  (reify xml/IXmlSignatureVerifier
    (verify-saml! [_ assertion-ref call-opts]
      (let [claims (xml/verify-saml! delegate assertion-ref call-opts)
            now (or (:now call-opts) (:now opts))
            skew-seconds (or (:clock-skew-seconds call-opts)
                             (:clock-skew-seconds opts)
                             0)
            err (when now (condition-error claims now skew-seconds))]
        (if err
          (assoc claims :error err)
          claims)))))
