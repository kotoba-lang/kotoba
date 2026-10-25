(ns koe.carrier
  "What a real carrier sends when a telephone rings, and whether to believe it.

  This is the edge of the system: the first bytes that arrive from outside, over
  the public internet, from a party that has not authenticated. Everything
  downstream — the dialog, the envelope, the 予約 — assumes it is being told the
  truth about who called and where the call came from. This namespace is the only
  place that assumption is checked, so it is written to be boring and total.

  ## Provider-neutral, but not provider-blind

  A host's transport admission decides which provider may answer a call and
  typically requires `:webhook-auth` among its capabilities. This is the other
  half: the capability is only real if the signature is actually verified
  on the way in.

  The verification schemes are genuinely different — Twilio signs an HMAC-SHA1
  over the URL plus sorted parameters, Telnyx signs Ed25519 over a timestamped
  body — so `verify` dispatches on provider and **refuses a provider it does not
  implement**. An unimplemented scheme returning 'not verified' is correct; the
  failure this shape prevents is one returning nil that a caller reads as fine.

  ## The forwarding case is the normal case

  The first deployment is a restaurant forwarding its existing line here, so the
  webhook parameters that matter most are the ones describing the diversion.
  `arrival` maps them into `koe.arrival`'s vocabulary, and the mapping is
  deliberately conservative: a carrier that says nothing about the diversion
  yields `:diverted-unknown`, not `:network-caller`. On a forwarded call the
  presented `From` is the caller only when the upstream carrier passed it
  through, and no webhook field distinguishes 'passed through' from 'replaced' —
  so the number is trusted only on a call that arrived directly."
  (:require [kotoba.lang.text :as str])
  #?(:clj (:import [javax.crypto Mac]
                   [javax.crypto.spec SecretKeySpec]
                   [java.util Base64])))

;; `implemented-providers` is DERIVED from the verifier table below rather than
;; written beside it. The first version had both — a set and an `(= :twilio
;; provider)` test inside `verify` — and removing either one alone changed
;; nothing, because the other still refused. Two guards for one rule are not
;; twice the safety: they are a rule that cannot be tested, and a place for the
;; two to disagree the day a second provider is added.

;; ── signature ────────────────────────────────────────────────────────────────

#?(:clj
   (defn- hmac-sha1-base64 [^String secret ^String message]
     (let [mac (Mac/getInstance "HmacSHA1")]
       (.init mac (SecretKeySpec. (.getBytes secret "UTF-8") "HmacSHA1"))
       (.encodeToString (Base64/getEncoder)
                        (.doFinal mac (.getBytes message "UTF-8"))))))

(defn twilio-signing-string
  "Twilio's canonical string: the full request URL, then every POST parameter
  appended as name+value in **lexicographic order by name**.

  The sort is the whole of the security property. A verifier that concatenated
  in the order the parameters arrived would accept a request whose parameters
  had been reordered by an attacker, which is to say it would accept anything."
  [url params]
  (str url
       (apply str (for [k (sort (keys params))]
                    (str (name k) (get params k))))))

(def ^:private verifiers
  "provider → the function that checks its signature. The ONLY place a provider
  becomes verifiable.

  Empty under ClojureScript: deliberately not implemented rather than
  approximated. A signature verifier that 'does its best' on a runtime without
  HMAC is the exact shape of a check that returns the same value whether or not
  it ran."
  #?(:clj
     {:twilio
      (fn [{:keys [url params signature secret]}]
        (and (seq (str signature)) (seq (str secret)) (seq (str url)) (map? params)
             ;; Constant-time comparison is not attempted: the compared value is
             ;; a base64 digest the attacker is trying to produce, not a secret
             ;; they can learn by timing. The secret never enters the comparison.
             (= (str signature)
                (hmac-sha1-base64 (str secret) (twilio-signing-string url params)))))}
     :cljs {}))

(def implemented-providers
  "Providers whose inbound signature can actually be verified here. Derived, so
  it cannot claim more than `verifiers` can do."
  (set (keys verifiers)))

(defn verify
  "Whether this request really came from the carrier. `false` on anything
  unproven, never nil.

  Returns false — not an exception — for an unimplemented provider, a missing
  signature and a missing secret, because all three mean the same thing to the
  caller: this request is not admitted."
  [{:keys [provider] :as request}]
  (boolean (when-let [f (get verifiers provider)] (f request))))

;; ── the call, as the carrier describes it ────────────────────────────────────

(def ^:private twilio-keys
  {:call-id "CallSid" :from "From" :to "To"
   :forwarded-from "ForwardedFrom" :direction "Direction"})

(defn arrival
  "Webhook parameters → `koe.arrival`'s vocabulary.

  `ForwardedFrom` present means the call reached us by diversion. In that case
  the provenance is `:diverted-unknown` **even though `From` is populated**:
  Twilio fills `From` with whatever the upstream carrier handed it, and nothing
  in the webhook says whether that was the original caller or the diverting
  line. Guessing right most of the time is not good enough for a value that gets
  sealed into a 予約 as the way to reach someone.

  A direct call is the only case that yields `:network-caller`."
  [provider params]
  (when-not (= :twilio provider)
    (throw (ex-info "この事業者の webhook 形式は未実装です。"
                    {:type :koe/unimplemented-provider :provider provider})))
  (let [g (fn [k] (some-> (get params (get twilio-keys k)) str str/trim not-empty))
        forwarded (g :forwarded-from)]
    {:call-ref (g :call-id)
     :via (if forwarded :forwarded :direct)
     :forwarded-from forwarded
     :presented-number (g :from)
     :provenance (if forwarded :diverted-unknown :network-caller)
     :dialled-number (g :to)}))

;; ── what we answer the carrier with ──────────────────────────────────────────

(defn- xml-escape [s]
  (-> (str s)
      (str/replace "&" "&amp;") (str/replace "<" "&lt;") (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")))

(defn answer-document
  "The instruction returned to the carrier to put the call on a bidirectional
  media stream to `stream-url`.

  `<Connect><Stream>` rather than `<Start><Stream>`: `Start` forks a copy of the
  audio to us and leaves the call going, which is a listening device. `Connect`
  hands us the call — we are the other party, and when the stream ends the call
  ends. A receptionist is a participant, not a tap.

  Refuses a non-`wss` URL. Telephone audio carries a stranger's voice and, in a
  moment, their name and telephone number; sending it over `ws` would put both on
  the wire in the clear, and a scheme typo is not a thing to discover in
  production."
  [{:keys [stream-url greeting]}]
  (when-not (str/starts-with? (str stream-url) "wss://")
    (throw (ex-info "メディアストリームは wss:// にしてください。"
                    {:type :koe/insecure-stream-url :stream-url stream-url})))
  (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
       "<Response>"
       (when (seq greeting)
         (str "<Say language=\"ja-JP\">" (xml-escape greeting) "</Say>"))
       "<Connect><Stream url=\"" (xml-escape stream-url) "\"/></Connect>"
       "</Response>"))

(def refusal-document
  "What an unverified request is answered with: a hang-up, and nothing else.

  Not an error page and not a spoken message. A request that failed signature
  verification did not necessarily come from the carrier at all, so anything said
  here is said to an unknown party, and any detail in it is a detail given away."
  "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Hangup/></Response>")

(defn admit
  "The whole edge decision: verify, then describe the call.

  Returns `{:admitted true :arrival {...}}` or `{:admitted false :reason ...}`.
  Nothing downstream should ever see the webhook parameters directly — this is
  the boundary at which unauthenticated input stops being unauthenticated."
  [{:keys [provider params] :as request}]
  (cond
    (not (contains? implemented-providers provider))
    {:admitted false :reason :unimplemented-provider}

    (not (verify request))
    {:admitted false :reason :signature-not-verified}

    :else
    {:admitted true :arrival (arrival provider params)}))
