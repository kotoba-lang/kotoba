(ns kototama.gates
  "kototama · gates — the unified CHARTER-GATE vocabulary for cells, atproto actors
  and artificial organisms (the merge of the former actor.gates + the organism
  membrane). Pure, deterministic, dependency-free — runs under bb/JVM today and
  (its scalar subset) under the kototama wasm runtime via the ACTOR_PRELUDE.

  Two membranes live here:

    (leashed? organism)          — is this organism leashed + not suspended? (the
                                   organism off-switch; pairs with kototama.leash)
    (may-draft? record)          — the charter membrane: may this record become a
                                   DRY-RUN post? (>=2 sources · cash≡0 · no-server-
                                   key · dry-run · sim-only · no-advice)
    (scan text)                  — the §2 catastrophe-veto content screen (CSAM /
                                   coercion / manipulation / targeting)
    (may-actuate? ctx)          — publication ≠ actuation: high-stakes actuation
                                   needs an explicit human/Council token

  种をまく doctrine (etzhayyim ADR-2606281500): autonomy is bounded by these rails,
  not by per-post operator prior restraint."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────── organism off-switch ─────────────────────────

(defn leashed?
  "An organism may DRAFT/POST iff it carries a leash and is not suspended (the
  leash's expiry/scope is checked separately by kototama.leash/valid?)."
  [{:keys [leash suspended?]}]
  (boolean (and leash (not suspended?))))

(defn may-actuate?
  "PUBLICATION ≠ ACTUATION. High-stakes real-world actuation (funds, permission
  grants, deletes, binding votes, live physical action, domain go-lives like a
  robotaxi launch) is NEVER autonomous — it always requires an explicit
  human/Council authorization token. Without one, refuse."
  [{:keys [actuation-authorization]}]
  (boolean actuation-authorization))

;; ───────────────────────── §2 catastrophe-veto content scan ─────────────────────────

(def ^:private catastrophe-markers
  #{"csam" "child sexual" "manipulat" "coerc" "blackmail" "doxx"
    "where is " "track this person" "kill " "weaponi" "bioweapon"})

(defn scan
  "Screen post text against the §2 catastrophe term. Returns {:ok? bool :flags [..]}.
  Empty/whitespace text is refused (an organism must have something to say)."
  [text]
  (let [t (str/lower (str text))
        flags (filterv #(str/includes? t %) catastrophe-markers)]
    {:ok? (and (seq (str/trim (str text))) (empty? flags))
     :flags flags}))

;; ───────────────────────── charter-gate vocabulary (from actor.gates) ─────────────────────────

(defn enough-sources?
  "G-sources: >=2 non-blank provenance citations (ADR / committed-ledger CID / DID)."
  [sources]
  (>= (count (filter #(and % (seq (str/trim (str %)))) (or sources []))) 2))

(defn cash-zero?
  "G-cash-zero: the consumer-facing cash amount is exactly 0 (commons, not a market)."
  [cash] (= 0 (or cash 0)))

(defn keyless?
  "G-keyless (no-server-key): the server holds no signing key for this act."
  [server-held-key?] (not (boolean server-held-key?)))

(defn dry-run?
  "G-dry-run: the act's status is :dry-run (the only producible status at R0)."
  [status] (= :dry-run status))

(defn sim-only?
  "G-sim-only: the act is flagged simulation/assessment, never an actuation."
  [sim?] (boolean sim?))

;; G-no-advice — an outward TEXT may state observations but never advice / valuation /
;; forecast / buy-sell. English on WORD BOUNDARIES ("ope-rating income" ≠ "rating");
;; Japanese has no boundaries → substring is correct.
(def advice-terms-en
  ["buy" "sell" "hold" "overweight" "underweight" "outperform" "underperform"
   "price target" "undervalued" "overvalued" "cheap" "expensive" "bullish" "bearish"
   "recommend" "rating" "ratings" "upgrade" "downgrade" "forecast" "guidance"])
(def advice-terms-ja
  ["投資判断" "買い推奨" "売り推奨" "推奨" "割安" "割高" "目標株価" "格付" "業績予想" "見通し"])

(def ^:private advice-en-re
  (re-pattern (str "(?i)\\b(?:" (str/join "|" (map #(str/replace % " " "\\s+") advice-terms-en)) ")\\b")))

(defn advice-hit
  "The first advice/valuation/forecast term `text` carries, or nil if clean."
  [text]
  (let [t (or text "")]
    (or (some #(when (str/includes? t %) %) advice-terms-ja)
        (re-find advice-en-re t))))

(defn no-advice?
  "G-no-advice: `text` carries no advice / valuation / forecast / buy-sell language."
  [text] (nil? (advice-hit text)))

(defn assert-no-advice
  "Throw if `text` carries advice language (G-no-advice); else return it unchanged.
  The guard every machine-composed outward string passes before publish."
  [text]
  (when-let [hit (advice-hit text)]
    (throw (ex-info (str "G-no-advice violation: outward text carries forbidden term " (pr-str hit))
                    {:term hit :text text})))
  text)

(defn may-draft?
  "The charter outward-membrane decision: may this record become a DRY-RUN post?
  Missing keys default to the safe value. True only when every applicable gate holds."
  [{:keys [status sources cash server-held-key sim-only text]
    :or {status :dry-run sources [] cash 0 server-held-key false sim-only true}}]
  (and (dry-run? status)
       (enough-sources? sources)
       (cash-zero? cash)
       (keyless? server-held-key)
       (sim-only? sim-only)
       (or (nil? text) (no-advice? text))))

(defn why-refused
  "Diagnostic: the ordered list of gate keywords that FAILED (empty = may-draft?)."
  [{:keys [status sources cash server-held-key sim-only text]
    :or {status :dry-run sources [] cash 0 server-held-key false sim-only true}}]
  (cond-> []
    (not (dry-run? status))             (conj :G-dry-run)
    (not (enough-sources? sources))     (conj :G-sources)
    (not (cash-zero? cash))             (conj :G-cash-zero)
    (not (keyless? server-held-key))    (conj :G-keyless)
    (not (sim-only? sim-only))          (conj :G-sim-only)
    (and (some? text) (not (no-advice? text))) (conj :G-no-advice)))
