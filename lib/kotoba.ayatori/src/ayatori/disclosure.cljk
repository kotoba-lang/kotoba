(ns ayatori.disclosure
  "Recipient key delivery at the existing Arrangement decrypt-fn seam.
  Verified ciphertext caching remains in ayatori.remote. Authority and key
  delivery are deliberately NOT memoised with immutable ciphertext bytes."
  (:require [kotobase.disclosure-grant :as disclosure]))

(defn- reject! [reason]
  (throw (ex-info "ayatori recipient decryption rejected"
                  {:ayatori.disclosure/reason reason})))

(defn- sync-bind [value f]
  #?(:cljs (when (and (some? value) (fn? (unchecked-get value "then")))
             (reject! :use-async-decryptor)))
  (f value))

(defn- decryptor [bind options]
  (when-not (= #{:context! :request! :deliver! :verify! :open! :crypto-policy}
               (set (keys options)))
    (reject! :invalid-options))
  (doseq [k [:context! :request! :deliver! :verify! :open!]]
    (when-not (fn? (get options k)) (reject! :missing-port)))
  (fn [ciphertext]
    (let [resource (disclosure/ciphertext-cid ciphertext)]
      (bind ((:context! options) resource)
            (fn [context]
              (when-not (= resource (:resource context)) (reject! :resource-mismatch))
              (bind ((:request! options) context)
                    (fn [request]
                      (when-not (= resource (:resource request)) (reject! :resource-mismatch))
                      (bind ((:deliver! options) request)
                            (fn [delivery]
                              ;; Refresh local epoch/time after a potentially slow network call.
                              (bind ((:context! options) resource)
                                    (fn [current]
                                      (when-not (= (dissoc context :now) (dissoc current :now))
                                        (reject! :authority-changed))
                                      (let [check (disclosure/delivery-verification
                                                   current request delivery (:crypto-policy options))]
                                        (bind ((:verify! options) check)
                                              (fn [valid?]
                                                (when-not (true? valid?) (reject! :signature-rejected))
                                                (bind ((:open! options)
                                                       {:ciphertext ciphertext
                                                        :key-envelope (:key-envelope delivery)
                                                        :binding (:binding delivery)
                                                        :recipient-key (:recipient-key current)})
                                                      identity)))))))))))))))

(defn recipient-decryptor
  "Build remote/open-snapshot's synchronous decrypt-fn. OPEN! is the qualified
  crypto provider: unwrap for the named local key using binding as authenticated
  context, authenticate/decrypt ciphertext, return Arrangement's encoded bytes.
  Request signing and the delivery network transport remain host effects."
  [options]
  (decryptor sync-bind options))

#?(:cljs
   (defn recipient-decryptor-async
     "Build remote/open-snapshot-async's decrypt-fn. All ports may be Promises."
     [options]
     (let [f (decryptor (fn [value k] (.then (js/Promise.resolve value) k)) options)]
       (fn [ciphertext]
         (try (js/Promise.resolve (f ciphertext))
              (catch :default error (js/Promise.reject error)))))))
