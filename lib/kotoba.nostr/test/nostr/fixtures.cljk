(ns nostr.fixtures
  "TEST-ONLY signer. Builds genuinely BIP-340-signed NIP-01 events (and
  NIP-98 auth events) for this repo's test suite, using
  nostr.crypto/schnorr-sign (itself test-fixture-only — see its docstring).
  Nothing under src/ requires this namespace; nostr.relay and nostr.blossom
  only ever VERIFY, never sign — signing is exclusively a client concern in
  real Nostr, so this is the one place in the whole repo a private key
  exists at all, and it exists only to make the test suite's fixtures real
  signed data instead of hand-typed (and therefore possibly-wrong-shaped)
  hex strings."
  (:require [nostr.crypto :as crypto]
            [nostr.event :as event]))

;; A handful of fixed (INSECURE — test-only, never use for anything real)
;; private key scalars, so fixtures are reproducible across runs.
(def alice-sk (crypto/big 3))
(def bob-sk (crypto/big 7))

(def zero-aux (vec (repeat 32 0)))

(defn pubkey [sk] (crypto/pubkey-for sk))

(defn sign-event
  "sk: private key bigint. draft: {\"kind\" \"created_at\" \"tags\" \"content\"}
  (string keys, matching the wire shape) — pubkey/id/sig are computed and
  merged in. Returns a full, genuinely-valid signed event map."
  [sk draft]
  (let [pub (pubkey sk)
        unsigned (assoc draft "pubkey" pub)
        id (event/compute-id unsigned)
        sig (crypto/schnorr-sign sk (crypto/hex->bytes id) zero-aux)]
    (assoc unsigned "id" id "sig" sig)))

(defn text-note
  ([sk content] (text-note sk content {}))
  ([sk content {:keys [created_at tags]}]
   (sign-event sk {"kind" 1
                    "created_at" (or created_at 1700000000)
                    "tags" (or tags [])
                    "content" content})))

(defn nip98-auth-event
  "A kind:27235 HTTP Auth event (NIP-98) for `method` + `url`."
  [sk method url {:keys [created_at]}]
  (sign-event sk {"kind" 27235
                  "created_at" (or created_at 1700000000)
                  "tags" [["u" url] ["method" method]]
                  "content" ""}))
