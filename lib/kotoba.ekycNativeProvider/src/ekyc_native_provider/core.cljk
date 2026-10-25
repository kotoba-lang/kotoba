(ns ekyc-native-provider.core
  "The composing ekyc.adapters.provider/IEkycProviderClient implementation:
   the ONE repo that knows ekyc's payload shapes, dispatching each
   :document-ocr / :liveness / :face-match check to the real, standalone,
   ekyc-agnostic engine repos (kotoba-lang/mrz, kotoba-lang/face-liveness,
   kotoba-lang/face-match) — per ADR-2607198200's architecture decision:
   one composing provider, not N per-engine shims, keeping every engine
   repo reusable outside the ekyc substrate too.

   Every engine's own status vocabulary is mapped into EXACTLY
   ekyc.model/statuses (#{:created :submitted :verified :rejected :expired
   :review}) here, in ONE place — ekyc.core/valid! rejects anything else,
   and leaking an engine-internal keyword (mrz has none, face-liveness has
   :verified/:failed/:expired, face-match has :review/:verified/:flagged)
   straight through would silently break every ekyc.core caller.

   Checks this provider does NOT implement (:document-authenticity,
   :address, :pep, :sanctions, :adverse-media, :manual-review) map to
   :review, honestly -- :pep/:sanctions belong to the separate
   kotoba-lang/watchlist-screen + kotoba-lang/aml path, not this
   IEkycProviderClient at all; the others have no engine anywhere in this
   org."
  (:require [ekyc.adapters.provider :as ekyc-provider]
            [ekyc-native-provider.ports :as ports]
            [face-liveness.core :as liveness]
            [face-match.core :as face-match]
            [mrz.core :as mrz]))

(def supported-checks #{:document-ocr :liveness :face-match})

;; --- per-check scoring, mapped into ekyc.model/statuses -------------------

(defn- score-document-ocr [content]
  (let [parsed (mrz/parse (:mrz-lines content))
        valid? (mrz/valid? parsed)]
    {:status (if valid? :verified :rejected)
     :confidence (if valid? 1.0 0.0)
     :evidence {:mrz/parsed parsed}}))

(defn- score-liveness [content now-ms]
  (let [{:keys [challenge frames]} content
        result (liveness/score-response challenge frames now-ms)]
    {:status (case (:result/status result)
               :verified :verified
               :expired :expired
               :rejected) ; :failed, or anything else -- fail closed to :rejected, not :review
     :confidence (:result/confidence result)
     :evidence (:result/evidence result)}))

(defn- score-face-match [content]
  (let [{:keys [selfie document-photo]} content
        result (face-match/match selfie document-photo)]
    {:status (case (:face-match/status result)
               :verified :verified
               :flagged :rejected
               :review) ; :review, or anything else -- honest default
     :confidence (:face-match/confidence result)
     :evidence {:face-match/reason (:face-match/reason result)}}))

(defn score-check
  "Dispatch `check` against already-fetched `content` (see
   ekyc-native-provider.ports/IEvidenceFetcher). Returns
   {:status <ekyc.model/statuses member> :confidence :evidence}. `content`
   nil (evidence-ref could not be resolved) and an unsupported check both
   map to :review -- 'cannot score this' and 'not implemented' are
   deliberately the same safe answer, never a guessed pass/fail."
  [check content now-ms]
  (cond
    (nil? content) {:status :review :confidence nil :evidence {:reason :evidence-unfetchable}}
    (not (contains? supported-checks check)) {:status :review :confidence nil :evidence {:reason :unsupported-check}}
    :else (case check
            :document-ocr (score-document-ocr content)
            :liveness (score-liveness content now-ms)
            :face-match (score-face-match content))))

;; --- IEkycProviderClient ----------------------------------------------------

(defn- default-now-ms [] #?(:clj (System/currentTimeMillis) :cljs (.getTime (js/Date.))))

(defn provider-client
  "`fetcher` is an ekyc-native-provider.ports/IEvidenceFetcher (no
   implementation ships in this repo, see that ns's module doc).
   `now-ms-fn` defaults to the system clock; pass a fixed fn in tests.

   Keeps a small in-memory session->evidence map so retrieve-result! can
   answer honestly within one process's lifetime -- this is NOT a durable
   store (a real deployment's durable session/evidence ledger is whatever
   ekyc.core's own caller already uses, e.g. ekyc.adapters.identity-bridge
   into orgs/kotoba-lang/identity; this map exists only because
   IEkycProviderClient's own contract expects retrieve-result! to be
   answerable, and this provider has nowhere else to keep that)."
  ([fetcher] (provider-client fetcher default-now-ms))
  ([fetcher now-ms-fn]
   (let [state (atom {})]
     (reify ekyc-provider/IEkycProviderClient
       (create-session! [_ payload _opts]
         (swap! state assoc (:id payload) {})
         {:status :submitted
          :session-ref (str "ekyc-native://" (:id payload))
          :provider :ekyc-native-provider
          :expires-at (:expires-at payload)})

       (upload-evidence! [_ payload _opts]
         (let [check (:check payload)
               evidence-ref (or (:custody-ref payload) (:evidence-ref payload))
               content (when evidence-ref (ports/fetch-evidence fetcher check evidence-ref))
               now (now-ms-fn)
               outcome (score-check check content now)
               response {:status (:status outcome)
                         :evidence-ref evidence-ref
                         :confidence (:confidence outcome)
                         :observed-at now}]
           (swap! state assoc-in [(:session-id payload) check]
                  (assoc response :check check :source :ekyc-native-provider))
           response))

       (retrieve-result! [_ payload _opts]
         (let [evidence (vals (get @state (:session-id payload) {}))
               statuses (set (map :status evidence))]
           {:status (cond
                      (empty? evidence) :review
                      (contains? statuses :rejected) :rejected
                      (contains? statuses :review) :review
                      (contains? statuses :expired) :expired
                      :else :verified)
            :evidence (vec evidence)}))))))
