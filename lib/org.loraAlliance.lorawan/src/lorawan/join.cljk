(ns lorawan.join
  "LoRaWAN L2 1.0.4 §6.2 \"Over-the-Air Activation\" — Join-Request (§6.2.5,
  Table 53), Join-Accept (§6.2.6, Table 54), and session-key derivation
  (§6.2.6). Ties together `lorawan.phy` (framing), `lorawan.mic` (MIC) and
  `lorawan.crypt` (Join-Accept decryption).

  Join-Request is symmetric — both `encode-join-request` and
  `decode-join-request` are here, it is never encrypted (§6.2.5: \"The
  Join-Request frame is not encrypted\"). **Join-Accept is decode-only** —
  `decode-join-accept` (the end-device's role) is here; encoding one (a
  join server's role) needs the AES-128 *inverse* cipher, which this
  workspace does not have — see `lorawan.crypt`'s docstring for the exact
  boundary and why."
  (:require [aes.core]
            [lorawan.bytes :as b]
            [lorawan.crypt :as crypt]
            [lorawan.mic :as mic]
            [lorawan.phy :as phy]))

;; ── Join-Request — §6.2.5, Table 53: JoinEUI(8) | DevEUI(8) | DevNonce(2) ──

(defn encode-join-request
  "Both EUIs and `dev-nonce` little-endian on the wire (`lorawan.bytes`).
  MIC is `aes128_cmac(AppKey, MHDR | JoinEUI | DevEUI | DevNonce)`
  (§6.2.5) — computed here, not passed in, since a Join-Request's MIC has
  no keystream/counter state a caller could get wrong independently of
  the fields already given."
  [app-key join-eui dev-eui dev-nonce]
  (let [mhdr (phy/encode-mhdr :join-request)
        body (into (b/le-n join-eui 8) (into (b/le-n dev-eui 8) (b/le-n dev-nonce 2)))
        mic-r (mic/join-request-mic app-key (:byte mhdr) join-eui dev-eui dev-nonce)]
    (if (= :error (:status mic-r)) mic-r
        (phy/encode-phypayload (:byte mhdr) body (:mic mic-r)))))

(defn decode-join-request
  "Returns `{:status :ok :join-eui :dev-eui :dev-nonce :mic-valid?}` (MIC
  checked if `app-key` is given, `nil` in `:mic-valid?` if not — a passive
  observer without the key can still read the cleartext fields, just not
  authenticate them). `:lorawan/wrong-ftype` if the MHDR is not
  `:join-request` — decoding a `transfer`-shaped frame as if it were a
  join is exactly the confusion `lorawan.performative`-style dispatch
  discipline (mirroring `amqp.performative`'s `:amqp/not-a-performative`)
  exists to catch."
  ([bs] (decode-join-request bs nil))
  ([bs app-key]
   (let [phy-r (phy/decode-phypayload bs)]
     (if (= :error (:status phy-r))
       phy-r
       (if (not= :join-request (get-in phy-r [:mhdr :ftype]))
         {:status :error :reason :lorawan/wrong-ftype :got (get-in phy-r [:mhdr :ftype])}
         (if (not= 18 (count (:body phy-r)))
           {:status :error :reason :lorawan/bad-join-request-length :length (count (:body phy-r))}
           (let [body (:body phy-r)
                 join-eui (b/le->int (subvec body 0 8))
                 dev-eui (b/le->int (subvec body 8 16))
                 dev-nonce (b/le->int (subvec body 16 18))
                 mic-valid? (when app-key
                              (let [exp (mic/join-request-mic app-key (nth bs 0) join-eui dev-eui dev-nonce)]
                                (and (= :ok (:status exp)) (= (:mic exp) (vec (:mic phy-r))))))]
             {:status :ok :join-eui join-eui :dev-eui dev-eui :dev-nonce dev-nonce
              :mic-valid? mic-valid?})))))))

;; ── Join-Accept — §6.2.6, Table 54 ───────────────────────────────────────────

(defn decode-join-accept
  "Decrypts the body with `app-key` (`lorawan.crypt/decrypt-join-accept`),
  then parses the recovered plaintext into `{:status :ok :join-nonce
  :net-id :dev-addr :dl-settings :rx-delay :cf-list :mic-valid?}`.
  `cf-list` is `[]` when the frame is the 16-byte (no-CFList) form, else
  the trailing 16 opaque bytes. The MIC is always checked here (unlike
  Join-Request's optional `app-key`) since decrypting *requires* the key
  already."
  [bs app-key]
  (let [phy-r (phy/decode-phypayload bs)]
    (if (= :error (:status phy-r))
      phy-r
      (if (not= :join-accept (get-in phy-r [:mhdr :ftype]))
        {:status :error :reason :lorawan/wrong-ftype :got (get-in phy-r [:mhdr :ftype])}
        (let [ciphertext (into (:body phy-r) (:mic phy-r))
              dec-r (crypt/decrypt-join-accept app-key ciphertext)]
          (if (= :error (:status dec-r))
            dec-r
            (let [pt (:bytes dec-r)
                  n (count pt)]
              (if (not (#{16 32} n))
                {:status :error :reason :lorawan/bad-join-accept-length :length n}
                (let [join-nonce (b/le->int (subvec pt 0 3))
                      net-id (b/le->int (subvec pt 3 6))
                      dev-addr (b/le->int (subvec pt 6 10))
                      dl-settings (nth pt 10)
                      rx-delay (nth pt 11)
                      cf-list (if (= n 32) (subvec pt 12 28) [])
                      recv-mic (subvec pt (- n 4) n)
                      mhdr-byte (nth bs 0)
                      exp-mic (mic/join-accept-mic app-key mhdr-byte join-nonce net-id dev-addr
                                                    dl-settings rx-delay cf-list)
                      mic-valid? (and (= :ok (:status exp-mic)) (= (:mic exp-mic) (vec recv-mic)))]
                  {:status :ok
                   :join-nonce join-nonce :net-id net-id :dev-addr dev-addr
                   :dl-settings dl-settings :rx-delay rx-delay :cf-list cf-list
                   :mic-valid? mic-valid?})))))))))

;; ── Session-key derivation — §6.2.6 ──────────────────────────────────────────
;; Both keys are exactly one AES block encrypted forward — no inverse
;; cipher needed, unlike decrypting the frame that carries the nonces used
;; here.

(defn- session-key [app-key selector join-nonce net-id dev-nonce]
  (let [sched (aes.core/expand-key app-key)]
    (if (= :error (:status sched))
      sched
      (let [block (b/zero-pad (-> [selector] (into (b/le-n join-nonce 3)) (into (b/le-n net-id 3))
                                   (into (b/le-n dev-nonce 2)))
                               16)]
        {:status :ok :bytes (aes.core/encrypt-block sched block)}))))

(defn nwk-s-key [app-key join-nonce net-id dev-nonce]
  (session-key app-key 0x01 join-nonce net-id dev-nonce))

(defn app-s-key [app-key join-nonce net-id dev-nonce]
  (session-key app-key 0x02 join-nonce net-id dev-nonce))
