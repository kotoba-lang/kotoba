;; ayatori.disclosure-open — the `:open!` port of `ayatori.disclosure`,
;; built on a qualified hybrid provider instead of a fixture.
;;
;; `ayatori.disclosure` deliberately leaves `:open!` to the host: it is the
;; one place where a real secret key touches a real ciphertext, and a query
;; plane is the wrong owner for either. What was missing was not the port
;; but anything to put in it — every test so far handed it a closure that
;; already held the content key, which proves the delivery protocol and
;; proves nothing about key delivery.
;;
;; This is the smallest thing that is not that. It still owns no keys and no
;; ciphertext framing; both stay ports. What it owns is the step between
;; them, and the refusals along it.
(ns ayatori.disclosure-open
  (:require [envelope.sealed-key :as sealed-key]))

(defn- reject! [reason data]
  (throw (ex-info "ayatori recipient key opening rejected"
                  (merge {:ayatori.disclosure-open/reason reason} data))))

(defn- wipe!
  "Overwrite the recovered data key once the content is out.

  Best effort, and said so: a JavaScript runtime may have copied the bytes
  during any of the operations above and nothing here can reach those
  copies. It costs one loop and removes the longest-lived of them."
  [^js key-bytes]
  (when (instance? js/Uint8Array key-bytes)
    (.fill key-bytes 0))
  nil)

(defn recipient-opener
  "Build the `:open!` port for `ayatori.disclosure/recipient-decryptor-async`.

  Two ports, because two things here are genuinely somebody else's:

    :keys!          fingerprint -> {:recipient-key :pub :priv :pq-priv}, or a
                    Promise of one. THE CUSTODY SEAM. Where a recipient's
                    X25519 and ML-KEM secret keys live -- a device keystore,
                    a passkey-wrapped identity key, an HSM -- is a deployment
                    decision, and a query plane that answered it would be
                    wrong in every deployment but one. It must return a map
                    whose :recipient-key is the fingerprint it was asked for;
                    a custody store that hands back a different key is
                    refused here, by name, rather than four steps later as an
                    indistinguishable AEAD failure.

    :open-content!  {:ciphertext :key} -> Arrangement's encoded bytes, or a
                    Promise. How the object itself is framed under its
                    content key is the writer's choice and travels with the
                    ciphertext, not with the grant.

  What this owns is the step between them: the wrapped key arrives as the
  octet vector `:sealed/ciphertext`, is opened with `binding(grant)` as the
  authenticated context, and the recovered key reaches `:open-content!` and
  nothing else. It is never returned, never logged, and is overwritten once
  the content is out.

  `binding` is required to be a non-empty string. An absent AAD is not a
  weaker binding, it is no binding: the wrap would open under any grant that
  produced the same envelope, which is the transplant the whole protocol is
  arranged to prevent, and it would do so silently."
  [{:keys [keys! open-content!] :as ports}]
  (when-not (= #{:keys! :open-content!} (set (keys ports)))
    (reject! :invalid-options {:got (sort (keys ports))}))
  (doseq [k [:keys! :open-content!]]
    (when-not (fn? (get ports k)) (reject! :missing-port {:port k})))
  (fn [{:keys [ciphertext key-envelope binding recipient-key]}]
    (-> (js/Promise.resolve nil)
        (.then
         (fn [_]
           (when-not (and (string? binding) (seq binding))
             (reject! :missing-binding {}))
           (when-not (and (string? recipient-key) (seq recipient-key))
             (reject! :missing-recipient-key {}))
           (let [sealed (:sealed/ciphertext key-envelope)]
             (when-not (and (vector? sealed) (seq sealed)
                            (every? #(and (integer? %) (<= 0 % 255)) sealed))
               (reject! :invalid-sealed-key {}))
             (js/Promise.resolve (keys! recipient-key)))))
        (.then
         (fn [held]
           (when-not (map? held)
             (reject! :no-key-for-recipient {:recipient-key recipient-key}))
           (when-not (= recipient-key (:recipient-key held))
             (reject! :custody-returned-another-key {:asked recipient-key}))
           (when-not (and (:pub held) (:priv held) (:pq-priv held))
             (reject! :incomplete-key-material {:recipient-key recipient-key}))
           (sealed-key/open-key
            (sealed-key/from-octets (:sealed/ciphertext key-envelope))
            held
            binding)))
        (.then
         (fn [data-key]
           (-> (js/Promise.resolve (open-content! {:ciphertext ciphertext :key data-key}))
               (.then (fn [plaintext] (wipe! data-key) plaintext))
               (.catch (fn [e] (wipe! data-key) (throw e)))))))))
