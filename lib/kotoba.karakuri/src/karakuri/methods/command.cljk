(ns karakuri.methods.command
  "karakuri (絡繰) ServiceOp parser/planner — web-service-to-CLI, stdlib only (ADR-2606039200).

  1:1 Clojure port of `methods/command.py`.

  The uniform vocabulary is a normalized ServiceOp: `service` · `noun` · `verb` ·
  classified `safety` (read/create/update/delete) + a `destructive` flag + the
  selected adapter `tier`. A CLI string

      karakuri <service> <noun>.<verb> [--flag value ...]

  parses into exactly one ServiceOp. This module does the offline-safe parts
  purely and deterministically: command parsing, service resolution against a
  :representative registry, safety classification, adapter-tier selection
  (official-API-first), the ToS gate (the T2 browser-use adapter is refused on a
  browser-automation-prohibited service — G2; Google + Facebook route to their
  official API and refuse browser automation), the browser-use engine selection
  for a permitted T2 op, and the mutate gate (mutating ops require member
  authorization — G5). It emits a dry-run plan and never touches the network
  (G6). The T2 browser action plan is built by `t2_browser.py`.

  G1 own-account · G2 official-API-first / ToS-honest · G5 read-default/mutate-gated
  · G6 outward-gated · G8 :representative registry (unknown service degrades
  honestly).

  Pure Clojure (clojure.core + clojure.string only), portable .cljc."
  (:require [kotoba.lang.text :as str]))

;; ═════════════════════════════════════════════════════════════════════════════
;; Constants
;; ═════════════════════════════════════════════════════════════════════════════

;; The T2 (headless-browser) engine: browser-use, a LangGraph-driven browser
;; agent over Playwright. It is selected ONLY for a T2 op whose service t2
;; stance permits automation (G2).
(def T2-ENGINE "browser-use")

;; Safety classification (G5). The verb determines whether an op reads or mutates.
(def SAFETY-READ "read")
(def SAFETY-CREATE "create")
(def SAFETY-UPDATE "update")
(def SAFETY-DELETE "delete")

(def VERB-SAFETY
  {"list" SAFETY-READ, "get" SAFETY-READ, "search" SAFETY-READ,
   "query" SAFETY-READ, "show" SAFETY-READ, "export" SAFETY-READ,
   "create" SAFETY-CREATE, "add" SAFETY-CREATE, "new" SAFETY-CREATE,
   "update" SAFETY-UPDATE, "set" SAFETY-UPDATE, "edit" SAFETY-UPDATE,
   "publish" SAFETY-UPDATE,
   "delete" SAFETY-DELETE, "remove" SAFETY-DELETE, "destroy" SAFETY-DELETE})

;; Adapter tiers (G2; safest-first).
(def TIER-T1 "t1-official-api")
(def TIER-T2 "t2-headless-browser")
(def TIER-T3 "t3-structured-export")

;; ToS gate outcomes (G2).
(def TOS-OK "ok")
(def TOS-REFUSED "refused-automation-prohibited")

;; Mutate gate outcomes (G5).
(def MUTATE-READ-ALLOWED "read-allowed")
(def MUTATE-AWAIT-SIG "awaiting-member-sig")

;; Honest degradations (G8).
(def UNKNOWN-SERVICE "unknown-service")

;; ═════════════════════════════════════════════════════════════════════════════
;; :representative service capability + ToS registry (mirrors
;; data/service-registry.kotoba.edn; G8). Runtime source of truth is the EDN
;; registry; operator MUST verify a ToS stance before live use.
;;
;; TWO independent stance axes (a service can sanction its API yet forbid
;; browser automation):
;;   "tos" — the OFFICIAL-API stance (governs T1 selection).
;;   "t2"  — the BROWSER-AUTOMATION stance: "permitted" / "restricted" /
;;           "prohibited"; a "prohibited" t2 stance refuses the T2 browser-use
;;           adapter by construction (G2), EVEN when an official API exists. A
;;           missing "t2" defaults to "prohibited" (default-deny browser
;;           automation — safest). ("restricted" is treated as "permitted" at
;;           R0 — reserved for a future per-service throttle/scope limit.)
;; Google + Facebook are the canonical api-ok / t2-prohibited case: drive their
;; official API on the member's OWN account (T1), never browser-automate the
;; consumer surface (T2 refused).
;; ═════════════════════════════════════════════════════════════════════════════

(def SERVICE-REGISTRY
  {"squarespace" {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "wix"         {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "notion"      {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "shopify"     {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "stripe"      {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "github"      {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "airtable"    {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "wordpress"   {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   ;; api-ok yet browser-automation-prohibited → default path is the official API (T1); T2 refused.
   "google"      {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   "facebook"    {"official_api" true,  "tos" "api-ok", "t2" "prohibited"}
   ;; no usable official API + ToS permits automation → T2 browser-use is the sanctioned path.
   "legacy-portal" {"official_api" false, "tos" "automation-allowed", "t2" "permitted"}
   "noauto-saas"   {"official_api" false, "tos" "automation-prohibited", "t2" "prohibited"}})

;; ═════════════════════════════════════════════════════════════════════════════
;; Records
;; ═════════════════════════════════════════════════════════════════════════════

;; ServiceOp is a plain map in Clojure, preserving the Python dataclass field
;; names as kebab keywords.

(defn make-service-op
  [service noun verb safety destructive adapter-tier & {:keys [args service-known
                                                               dry-run tos-gate
                                                               mutate-gate t2-engine
                                                               note]
                                                        :or {args {}
                                                             service-known true
                                                             dry-run true
                                                             tos-gate TOS-OK
                                                             mutate-gate MUTATE-READ-ALLOWED
                                                             t2-engine ""
                                                             note ""}}]
  {:service service
   :noun noun
   :verb verb
   :safety safety
   :destructive destructive
   :adapter-tier adapter-tier
   :args args
   :service-known service-known
   :dry-run dry-run
   :tos-gate tos-gate
   :mutate-gate mutate-gate
   :t2-engine t2-engine
   :note note})

;; ═════════════════════════════════════════════════════════════════════════════
;; Public API
;; ═════════════════════════════════════════════════════════════════════════════

(defn classify-safety
  "Map a verb to its op safety. Unknown verbs are treated conservatively as :update (mutating)."
  [verb]
  (get VERB-SAFETY (str/trim (str/lower (or verb ""))) SAFETY-UPDATE))

(defn is-destructive
  "G5: delete is the only irreversible class; flagged for explicit member confirmation."
  [safety]
  (= safety SAFETY-DELETE))

(defn resolve-service
  "Look the service up in the :representative registry. nil → honest :unknown-service (G8)."
  [service-id]
  (get SERVICE-REGISTRY (str/trim (str/lower (or service-id "")))))

(defn t2-stance
  "The browser-automation stance for a service. Missing → 'prohibited' (default-deny; G2)."
  [rec]
  (get rec "t2" "prohibited"))

(defn select-tier
  "Safest-first (G2): official API > ToS-permitted browser-use > structured export."
  [rec]
  (cond
    (get rec "official_api") TIER-T1
    (#{"permitted" "restricted"} (t2-stance rec)) TIER-T2
    :else TIER-T3))

(defn tos-gate
  "G2: a T2 browser-use op on a service whose browser-automation stance is
  'prohibited' is refused by construction — even when an official API exists
  (e.g. Google, Facebook)."
  [rec tier]
  (if (and (= tier TIER-T2) (= (t2-stance rec) "prohibited"))
    TOS-REFUSED
    TOS-OK))

(defn t2-engine
  "The browser-automation engine (browser-use) for a permitted T2 op; '' otherwise (G2)."
  [rec tier gate]
  (if (and (= tier TIER-T2)
           (= gate TOS-OK)
           (#{"permitted" "restricted"} (t2-stance rec)))
    T2-ENGINE
    ""))

(defn mutate-gate
  "G5: reads are allowed at R0; any mutation awaits a member signature."
  [safety]
  (if (= safety SAFETY-READ)
    MUTATE-READ-ALLOWED
    MUTATE-AWAIT-SIG))

(defn parse-command
  "Parse `[karakuri] <service> <noun>.<verb> [--flag value ...]` → [service noun verb args].

  Raises ex-info on a malformed command (G8 — never guesses the shape)."
  [line]
  (let [tokens (str/split (str/trim (or line "")) #"\s+")
        tokens (if (and (seq tokens) (= (str/lower (first tokens)) "karakuri"))
                 (rest tokens)
                 tokens)]
    (when (< (count tokens) 2)
      (throw (ex-info (str "malformed command (need '<service> <noun>.<verb>'): " (pr-str line))
                      {:line line})))
    (let [service (first tokens)
          nv (second tokens)]
      (when-not (str/includes? nv ".")
        (throw (ex-info (str "malformed op (need '<noun>.<verb>'): " (pr-str nv))
                        {:line line :nv nv})))
      (let [[noun verb] (str/split nv #"\." 2)]
        (when (or (str/blank? noun) (str/blank? verb))
          (throw (ex-info (str "malformed op (empty noun or verb): " (pr-str nv))
                          {:line line :nv nv})))
        (let [args (loop [j 0
                          rest (drop 2 tokens)
                          acc {}]
                     (if (>= j (count rest))
                       acc
                       (let [tok (nth rest j)]
                         (if (str/starts-with? tok "--")
                           (let [key (subs tok 2)]
                             (if (and (< (inc j) (count rest))
                                      (not (str/starts-with? (nth rest (inc j)) "--")))
                               (recur (+ j 2) rest (assoc acc key (nth rest (inc j))))
                               (recur (inc j) rest (assoc acc key true))))
                           (recur (inc j) rest acc)))))]
          [service (str/lower noun) (str/lower verb) args])))))

(defn plan
  "Parse a command into a dry-run ServiceOp plan with the ToS + mutate gates applied (no network).

  `prefer-tier` lets a caller request a specific adapter (e.g. force T2) so the
  G2 ToS gate can be demonstrated; by default the safest tier is selected."
  [line & {:keys [prefer-tier]}]
  (when (and (some? prefer-tier)
             (not (#{TIER-T1 TIER-T2 TIER-T3} prefer-tier)))
    (throw (ex-info (str "unknown prefer_tier " (pr-str prefer-tier) " (expected one of T1/T2/T3 constants)")
                    {:prefer-tier prefer-tier})))

  (let [[service noun verb args] (parse-command line)
        safety (classify-safety verb)
        rec (resolve-service service)]
    (if (nil? rec)
      ;; G8: unknown service degrades honestly — no tier, no guess.
      (make-service-op
       service noun verb safety (is-destructive safety) ""
       :args args :service-known false :tos-gate TOS-OK
       :mutate-gate (mutate-gate safety) :note UNKNOWN-SERVICE)

      (let [tier (or prefer-tier (select-tier rec))
            gate (tos-gate rec tier)
            engine (t2-engine rec tier gate)
            note (if (= gate TOS-REFUSED)
                   "G2: ToS prohibits browser automation; T2 browser-use refused — use the official API (T1) or T3 export"
                   "")]
        (make-service-op
         service noun verb safety (is-destructive safety) tier
         :args args :service-known true :dry-run true
         :tos-gate gate :mutate-gate (mutate-gate safety)
         :t2-engine engine :note note)))))
