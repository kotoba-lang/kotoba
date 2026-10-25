(ns hpke.core
  "[RFC 9180](https://www.rfc-editor.org/rfc/rfc9180) HPKE — Hybrid Public Key
  Encryption — in portable `.cljc`.

  **DHKEM(X25519, HKDF-SHA256)** and **HKDF-SHA256**, with any of the three
  AEADs — AES-128-GCM, AES-256-GCM, ChaCha20Poly1305 — in **all four modes**:
  base, PSK, Auth and AuthPSK.

  ## What is a parameter and what is not

  The **AEAD is a value** (`aes-128-gcm`, `aes-256-gcm`,
  `chacha20-poly1305`), passed as an optional leading argument to every
  `setup-*`. Omitted, it is `default-suite` — ChaCha20Poly1305, what this
  library had before, so an existing call site means what it used to.

  The **KEM and the KDF are still constants**, and the reason is evidence
  rather than effort. `org-nist-sha2` has SHA-384 and SHA-512 and their MACs,
  so HKDF-SHA384 and HKDF-SHA512 would run — but RFC 9180 publishes no vector
  for **this KEM** with either, so they would run against nothing. The NIST
  curves and X448 have no portable implementation in this workspace at all.

  A suite table listing identifiers nothing can execute is the kind of
  completeness that reads as capability, so `suites` lists three.

  ## Why there are four modes

  RFC 9180 Appendix **A.2 is exactly this KEM and KDF with ChaCha20Poly1305**
  and **A.1 is the same with AES-128-GCM**, and both publish all four modes.
  The earlier argument for shipping base alone — that the other three would
  be untested code paths — was an argument about evidence, and the evidence
  was in the specification the whole time.

  Running both appendices is also the cheapest check that the AEAD is a
  parameter: they differ in one identifier, that identifier is inside
  `suite_id`, and `suite_id` is inside every derivation in the key schedule.

  ## Use

      (def kp (dhkem/derive-key-pair ikm))          ; recipient
      (def s (setup-base-sender (:public kp) info eph))
      (seal (:context s) aad plaintext)             ; -> ciphertext
      (def r (setup-base-recipient (:enc s) kp info))
      (open (:context r) aad ciphertext)

  A context is a value and `seal`/`open` return a NEW one alongside the
  bytes, because the sequence number advances and a mutable counter shared by
  two callers is how a nonce gets reused.

  ## The rule the construction depends on

  **A fresh ephemeral key pair per `setup-base-sender`.** Reusing one gives
  two encapsulations the same key and base nonce, and the AEAD underneath is
  a stream cipher. Randomness is a capability, so this library takes the
  ephemeral rather than making it — which also means a caller who reuses one
  is doing so visibly."
  (:require [aes.gcm :as gcm]
            [chacha20.aead :as aead]
            [hpke.dhkem :as dhkem]
            [hpke.kdf :as kdf]))

(def mode-base 0x00)
(def mode-psk 0x01)
(def mode-auth 0x02)
(def mode-auth-psk 0x03)

(def default-psk
  "RFC 9180 §5.1 `default_psk` — the empty string.

  It is still hashed into `psk_id_hash` and still salts `secret`, so a
  base-mode context and a PSK-mode context with an empty PSK are *not* the
  same: the mode byte leads the key schedule context and separates them."
  [])

(def default-psk-id [])

;; ── the AEADs ────────────────────────────────────────────────────────────────

(def aes-128-gcm {:aead-id 0x0001 :nk 16 :nn 12 :nt 16 :seal gcm/seal :open gcm/open})
(def aes-256-gcm {:aead-id 0x0002 :nk 32 :nn 12 :nt 16 :seal gcm/seal :open gcm/open})
(def chacha20-poly1305 {:aead-id 0x0003 :nk 32 :nn 12 :nt 16 :seal aead/seal :open aead/open})

(defn- export-only-error [& _]
  {:status :error :reason :export-only-aead})

(def export-only
  "RFC 9180 §7.3, identifier `0xFFFF`.

  A suite that cannot encrypt. `Nk` and `Nn` are zero, no key or base nonce is
  derived, and `seal` and `open` refuse. It exists for callers that want HPKE
  only as a key agreement — `export` gives them independent secrets and they
  bring their own record layer.

  The refusal is a value, not an omission. A missing `:seal` would give a
  caller a null-pointer at the moment they tried to send something; this gives
  them `:export-only-aead`."
  {:aead-id 0xFFFF :nk 0 :nn 0 :nt 0 :seal export-only-error :open export-only-error})

(def aeads
  {0x0001 aes-128-gcm 0x0002 aes-256-gcm 0x0003 chacha20-poly1305 0xFFFF export-only})

;; ── a suite ──────────────────────────────────────────────────────────────────

(defn suite
  "`{:kem … :kdf … :aead …}` plus the `suite_id` the three of them determine."
  [kem the-kdf aead]
  (let [ids [(:kem-id kem) (:kdf-id the-kdf) (:aead-id aead)]]
    {:kem kem :kdf the-kdf :aead aead
     :kem-id (:kem-id kem) :kdf-id (:kdf-id the-kdf) :aead-id (:aead-id aead)
     :nk (:nk aead) :nn (:nn aead) :nt (:nt aead) :nh (:nh the-kdf)
     :suite-id (vec (concat (kdf/ascii "HPKE")
                            (mapcat (fn [i] [(quot i 256) (mod i 256)]) ids)))}))

(def default-suite
  "DHKEM(X25519, HKDF-SHA256) / HKDF-SHA256 / ChaCha20Poly1305 — what this
  library had when it had one suite, kept as the default so every existing
  call site means what it used to."
  (suite dhkem/x25519-hkdf-sha256 kdf/hkdf-sha256 chacha20-poly1305))

(def suite-id
  "The default suite's `suite_id`. Use `(:suite-id s)` for any other."
  (:suite-id default-suite))

(def nk 32)   ; the default suite's key length, kept for callers that read it
(def nn 12)
(def nt 16)
(def nh 32)

;; ── the key schedule ─────────────────────────────────────────────────────────

(defn psk-inputs-error
  "RFC 9180 §5.1 `VerifyPSKInputs`. Returns `nil` when the inputs are
  consistent with `mode`, and an error map otherwise.

  Three separate mistakes, and the RFC is right to name them apart:

  - a PSK with no id, or an id with no PSK — the pair is what gets bound, and
    half of it is a caller who thinks they configured something
  - a PSK supplied in a mode that ignores it — it would be silently dropped,
    and a secret that is silently dropped is worse than one that was never
    there, because the caller believes it is in force
  - a mode that requires a PSK and did not get one — the key schedule would
    still produce a key, just not the one the peer computes"
  [mode psk psk-id]
  (let [got-psk (boolean (seq psk))
        got-id (boolean (seq psk-id))
        needs (contains? #{mode-psk mode-auth-psk} mode)]
    (cond
      (not= got-psk got-id)
      {:status :error :reason :inconsistent-psk-inputs :psk? got-psk :psk-id? got-id}

      (and got-psk (not needs))
      {:status :error :reason :psk-not-needed-in-mode :mode mode}

      (and (not got-psk) needs)
      {:status :error :reason :psk-required-in-mode :mode mode})))

(defn key-schedule
  "RFC 9180 §5.1.

  The two- and five-argument forms are the default suite. The six-argument
  form takes any. There is no branch on the mode below, which is the point: a
  mode is a value that leads `key_schedule_context`, so the four modes cannot
  drift from one another.

  For an export-only suite (`Nk = 0`) no key and no base nonce are derived —
  the RFC does not define them there, and deriving something unused would put
  two more `LabeledExpand` calls between a caller and a specification they can
  check against.

  `:key-schedule-context` is kept in the returned context. It is not secret —
  it is the mode byte and two hashes, and RFC 9180 publishes it as a test
  vector — and keeping it is what lets a test assert the value the modes
  actually differ in, rather than only the keys derived from it.

  Throws on inconsistent PSK inputs rather than returning an error map. The
  `setup-*` functions below return one; the difference is deliberate. `psk`
  comes from local configuration, not from a peer, so a bad pair here is a
  programming error and not a message to reject — the same reasoning that
  makes `hpke.kdf/expand!` throw."
  ([shared-secret info]
   (key-schedule mode-base shared-secret info default-psk default-psk-id))
  ([mode shared-secret info psk psk-id]
   (key-schedule default-suite mode shared-secret info psk psk-id))
  ([s mode shared-secret info psk psk-id]
   (when-let [e (psk-inputs-error mode psk psk-id)]
     (throw (ex-info (str "hpke: " (name (:reason e))) e)))
   (let [k (:kdf s) sid (:suite-id s)
         psk-id-hash (kdf/labeled-extract k sid [] "psk_id_hash" psk-id)
         info-hash (kdf/labeled-extract k sid [] "info_hash" info)
         ks-context (vec (concat [mode] psk-id-hash info-hash))
         secret (kdf/labeled-extract k sid shared-secret "secret" psk)]
     (cond-> {:exporter-secret (kdf/labeled-expand k sid secret "exp" ks-context (:nh s))
              :key-schedule-context ks-context
              :suite s
              :seq 0}
       (pos? (:nk s))
       (assoc :key (kdf/labeled-expand k sid secret "key" ks-context (:nk s))
              :base-nonce (kdf/labeled-expand k sid secret "base_nonce" ks-context (:nn s)))))))

(defn- compute-nonce
  "RFC 9180 §5.2: `base_nonce XOR I2OSP(seq, Nn)`.

  The big-endian bytes are produced by repeated division rather than by
  multiplying `seq` against powers of 256. `256^11` is 2^88, which overflows a
  JVM long the moment it is formed and is not an exact integer under
  ClojureScript — so writing the obvious `(* seq (expt 256 k))` throws at
  namespace load, before any nonce is computed."
  [base-nonce n]
  (let [be (loop [v n out () k 0]
             (if (= k (count base-nonce))
               (vec out)
               (recur (quot v 256) (conj out (bit-and v 0xFF)) (inc k))))]
    (mapv bit-xor base-nonce be)))

(def ^:private max-seq
  "The largest sequence number this can count to.

  RFC 9180 §5.2 puts the limit at 2^(8*Nn) - 1, which for Nn = 12 is 2^96 -
  and neither runtime can hold that: a JVM long stops at 2^63 and a
  ClojureScript number stops being an exact integer at 2^53. So the real limit
  is the smaller of those, and it is stated as such rather than as a constant
  that cannot be formed.

  This is not a shortcut. At one message per nanosecond, 2^53 takes over two
  hundred years; the RFC's bound was never the binding one."
  9007199254740990)

(defn seal
  "Encrypt with `ctx`. Returns `{:status :ok :bytes ct :context ctx'}` — the
  new context carries the advanced sequence number."
  [ctx aad pt]
  (let [s (:suite ctx default-suite)]
    (cond
      (zero? (:nk s)) {:status :error :reason :export-only-aead}
      (>= (:seq ctx) max-seq) {:status :error :reason :message-limit-reached :seq (:seq ctx)}
      :else
      (let [r ((:seal (:aead s)) (:key ctx) (compute-nonce (:base-nonce ctx) (:seq ctx)) aad pt)]
        (if (= :ok (:status r))
          {:status :ok :bytes (:bytes r) :context (update ctx :seq inc)}
          r)))))

(defn open
  "Decrypt with `ctx`. Returns `{:status :ok :bytes pt :context ctx'}`.

  The sequence number advances **only on success**: a rejected message must
  not consume a nonce, or an attacker could desynchronise the two sides by
  injecting garbage."
  [ctx aad ct]
  (let [s (:suite ctx default-suite)]
    (cond
      (zero? (:nk s)) {:status :error :reason :export-only-aead}
      (>= (:seq ctx) max-seq) {:status :error :reason :message-limit-reached :seq (:seq ctx)}
      :else
      (let [r ((:open (:aead s)) (:key ctx) (compute-nonce (:base-nonce ctx) (:seq ctx)) aad ct)]
        (if (= :ok (:status r))
          {:status :ok :bytes (:bytes r) :context (update ctx :seq inc)}
          r)))))

(defn export
  "RFC 9180 §5.3 — derive an independent secret from the context.

  Does not touch the sequence number: exporting is not sending, and a caller
  that exports between messages must not shift the nonce. Available in every
  suite including the export-only one, which is what that suite is for."
  [ctx exporter-context length]
  (let [s (:suite ctx default-suite)]
    (kdf/labeled-expand (:kdf s) (:suite-id s) (:exporter-secret ctx)
                        "sec" exporter-context length)))

;; ── setup ────────────────────────────────────────────────────────────────────
;;
;; Eight functions, four pairs, RFC 9180 §5.1.1-5.1.4. Each is the same two
;; steps -- encapsulate, then run the key schedule -- and they are written out
;; rather than collapsed behind a `mode` argument because the *arguments*
;; differ, not the body: a PSK setup needs a psk and an id, an Auth setup
;; needs a static key pair, and a signature that took all of them and ignored
;; most would let a caller pass a PSK to a mode that drops it.
;;
;; That check exists anyway (`psk-inputs-error`), but a wrong call that does
;; not typecheck is better than a wrong call that returns an error map.

(defn- schedule-from
  [s kem-result mode info psk psk-id]
  (if (not= :ok (:status kem-result))
    kem-result
    (if-let [e (psk-inputs-error mode psk psk-id)]
      e
      (cond-> {:status :ok
               :context (key-schedule s mode (:shared-secret kem-result) info psk psk-id)}
        (:enc kem-result) (assoc :enc (:enc kem-result))))))

(defn setup-base-sender
  "RFC 9180 §5.1.1. `eph` is the ephemeral key pair — see this namespace's
  docstring on why it is a parameter."
  ([pk-r info eph] (setup-base-sender default-suite pk-r info eph))
  ([s pk-r info eph]
   (schedule-from s (dhkem/encap (:kem s) pk-r eph) mode-base info default-psk default-psk-id)))

(defn setup-base-recipient
  "RFC 9180 §5.1.1, the receiving half."
  ([enc kp-r info] (setup-base-recipient default-suite enc kp-r info))
  ([s enc kp-r info]
   (schedule-from s (dhkem/decap (:kem s) enc kp-r) mode-base info default-psk default-psk-id)))

(defn setup-psk-sender
  "RFC 9180 §5.1.2. The PSK authenticates the *recipient* to the sender: only
  a holder of the same pre-shared key can derive the same context, so a
  message that opens is a message the intended party received.

  `psk-id` is sent in the clear by whatever protocol carries `enc`, and it is
  hashed into the context here. It identifies which PSK, and identifying it is
  not the same as proving possession of it."
  ([pk-r info psk psk-id eph] (setup-psk-sender default-suite pk-r info psk psk-id eph))
  ([s pk-r info psk psk-id eph]
   (schedule-from s (dhkem/encap (:kem s) pk-r eph) mode-psk info psk psk-id)))

(defn setup-psk-recipient
  "RFC 9180 §5.1.2, the receiving half."
  ([enc kp-r info psk psk-id] (setup-psk-recipient default-suite enc kp-r info psk psk-id))
  ([s enc kp-r info psk psk-id]
   (schedule-from s (dhkem/decap (:kem s) enc kp-r) mode-psk info psk psk-id)))

(defn setup-auth-sender
  "RFC 9180 §5.1.3. `kp-s` is the sender's static key pair.

  This is where the KEM changes rather than the key schedule: `auth-encap`
  mixes a second DH and a third public key into the shared secret. The mode
  byte still separates the context, so the two changes are independent and
  both are needed."
  ([pk-r info eph kp-s] (setup-auth-sender default-suite pk-r info eph kp-s))
  ([s pk-r info eph kp-s]
   (schedule-from s (dhkem/auth-encap (:kem s) pk-r eph kp-s)
                  mode-auth info default-psk default-psk-id)))

(defn setup-auth-recipient
  "RFC 9180 §5.1.3, the receiving half. `pk-s` is the sender's static public
  key.

  A wrong `pk-s` produces a context, not an error — see `dhkem/auth-decap`.
  The first `open` is what rejects."
  ([enc kp-r info pk-s] (setup-auth-recipient default-suite enc kp-r info pk-s))
  ([s enc kp-r info pk-s]
   (schedule-from s (dhkem/auth-decap (:kem s) enc kp-r pk-s)
                  mode-auth info default-psk default-psk-id)))

(defn setup-auth-psk-sender
  "RFC 9180 §5.1.4 — both at once."
  ([pk-r info psk psk-id eph kp-s]
   (setup-auth-psk-sender default-suite pk-r info psk psk-id eph kp-s))
  ([s pk-r info psk psk-id eph kp-s]
   (schedule-from s (dhkem/auth-encap (:kem s) pk-r eph kp-s) mode-auth-psk info psk psk-id)))

(defn setup-auth-psk-recipient
  "RFC 9180 §5.1.4, the receiving half."
  ([enc kp-r info psk psk-id pk-s]
   (setup-auth-psk-recipient default-suite enc kp-r info psk psk-id pk-s))
  ([s enc kp-r info psk psk-id pk-s]
   (schedule-from s (dhkem/auth-decap (:kem s) enc kp-r pk-s) mode-auth-psk info psk psk-id)))

;; ── single-shot ──────────────────────────────────────────────────────────────

(defn- seal-once [setup aad pt]
  (if (not= :ok (:status setup))
    setup
    (let [r (seal (:context setup) aad pt)]
      (if (= :ok (:status r))
        {:status :ok :enc (:enc setup) :bytes (:bytes r)}
        r))))

(defn- open-once [setup aad ct]
  (if (not= :ok (:status setup)) setup (open (:context setup) aad ct)))

(defn seal-base
  ([pk-r info aad pt eph] (seal-base default-suite pk-r info aad pt eph))
  ([s pk-r info aad pt eph] (seal-once (setup-base-sender s pk-r info eph) aad pt)))

(defn open-base
  ([enc kp-r info aad ct] (open-base default-suite enc kp-r info aad ct))
  ([s enc kp-r info aad ct] (open-once (setup-base-recipient s enc kp-r info) aad ct)))

(defn seal-psk
  ([pk-r info aad pt psk psk-id eph] (seal-psk default-suite pk-r info aad pt psk psk-id eph))
  ([s pk-r info aad pt psk psk-id eph]
   (seal-once (setup-psk-sender s pk-r info psk psk-id eph) aad pt)))

(defn open-psk
  ([enc kp-r info aad ct psk psk-id] (open-psk default-suite enc kp-r info aad ct psk psk-id))
  ([s enc kp-r info aad ct psk psk-id]
   (open-once (setup-psk-recipient s enc kp-r info psk psk-id) aad ct)))

(defn seal-auth
  ([pk-r info aad pt eph kp-s] (seal-auth default-suite pk-r info aad pt eph kp-s))
  ([s pk-r info aad pt eph kp-s] (seal-once (setup-auth-sender s pk-r info eph kp-s) aad pt)))

(defn open-auth
  ([enc kp-r info aad ct pk-s] (open-auth default-suite enc kp-r info aad ct pk-s))
  ([s enc kp-r info aad ct pk-s] (open-once (setup-auth-recipient s enc kp-r info pk-s) aad ct)))

(defn seal-auth-psk
  ([pk-r info aad pt psk psk-id eph kp-s]
   (seal-auth-psk default-suite pk-r info aad pt psk psk-id eph kp-s))
  ([s pk-r info aad pt psk psk-id eph kp-s]
   (seal-once (setup-auth-psk-sender s pk-r info psk psk-id eph kp-s) aad pt)))

(defn open-auth-psk
  ([enc kp-r info aad ct psk psk-id pk-s]
   (open-auth-psk default-suite enc kp-r info aad ct psk psk-id pk-s))
  ([s enc kp-r info aad ct psk psk-id pk-s]
   (open-once (setup-auth-psk-recipient s enc kp-r info psk psk-id pk-s) aad ct)))

(defn hex [bs] (aead/hex bs))
(defn unhex [s] (aead/unhex s))
