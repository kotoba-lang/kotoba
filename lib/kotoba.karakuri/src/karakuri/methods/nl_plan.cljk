(ns karakuri.methods.nl-plan
  "karakuri (絡繰) NL→ServiceOp planner — Murakumo-only (ADR-2606039200, G4).

  1:1 Clojure port of `methods/nl_plan.py`.

  Turns a member's natural-language brief into an ordered list of normalized ServiceOps (each
  gated by command/plan), Charter-Rider scanned (N6), as a dry-run plan (G6). The canonical NL
  parser is the Murakumo LLM (LiteLLM 127.0.0.1:4000, gemma3:4b — G4); a deterministic heuristic
  is the always-available, hermetic fallback. The live LLM call is a refused-by-default membrane
  (operator + flag gated), so this module is offline-safe and never reaches the network at R0.

  G4 Murakumo-only · G5 mutate-gated · G6 dry-run only · N6 Charter-Rider scan.

  CommandPlan is a plain map with the Python dataclass field names as kebab keywords. The live
  env read is behind #?(:clj …). clojure.core + clojure.string only; portable .cljc."
  (:require [kotoba.lang.text :as str]
            [karakuri.methods.command :as command]))

;; ── service synonyms a member might say (→ canonical registry id; G8 honest beyond this set) ──
(def SERVICE-SYNONYMS
  {"gmail" "google", "googlemail" "google", "gdrive" "google", "drive" "google",
   "gcal" "google", "google-calendar" "google", "calendar" "google", "google" "google",
   "fb" "facebook", "meta" "facebook", "facebook" "facebook",
   "wp" "wordpress", "wordpress" "wordpress", "gh" "github", "github" "github"})

;; ── natural verb → canonical ServiceOp verb (command/VERB-SAFETY classifies the canonical verb) ──
(def NL-VERB
  {"list" "list", "show" "list", "see" "list", "view" "list", "read" "list",
   "get" "get", "fetch" "get", "open" "get",
   "find" "search", "search" "search",
   "create" "create", "add" "add", "new" "create", "make" "create",
   "update" "update", "change" "update", "edit" "update", "rename" "update",
   "set" "set", "publish" "publish",
   "delete" "delete", "remove" "delete", "drop" "delete", "destroy" "delete",
   "export" "export", "download" "export", "backup" "export"})

(def STOPWORDS
  #{"the" "a" "an" "my" "all" "of" "from" "in" "on" "to" "for" "me" "please"
    "and" "with" "some" "any" "this" "that"})

;; ── N6 Charter-Rider §2(a)-(h) representative scan (canonical SSoT is
;;    etzhayyim_organism.sensors.charter_rider.scan(); this is a stdlib stand-in) ──
(def CHARTER-RIDER-TERMS
  {"weapon" "§2(a) force/weapons", "munition" "§2(a) force/weapons", "firearm" "§2(a) force/weapons",
   "casino" "§2(b) gambling", "gambling" "§2(b) gambling", "betting" "§2(b) gambling",
   "adsense" "§2 advertising", "affiliate" "§2 advertising", "ad-network" "§2 advertising",
   "surveil" "§2 surveillance", "stalk" "§2 surveillance", "scrape-everyone" "§2 surveillance",
   "captcha-farm" "§2 detection-evasion", "proxy-rotate" "§2 detection-evasion"})

(def INFERENCE-MURAKUMO "murakumo")   ; G4 invariant

(defn- live-llm-refused
  "ex-info marked as a live-Murakumo-refusal (G4/G6 default-deny)."
  [msg]
  (ex-info msg {:type :live-llm-refused}))

(defn make-command-plan
  "CommandPlan constructor — a plain map mirroring the Python dataclass field defaults."
  [brief & {:keys [ops charter-clean charter-hits inference dry-run]
            :or {ops []
                 charter-clean true
                 charter-hits []
                 inference INFERENCE-MURAKUMO   ; G4
                 dry-run true}}]                ; G6
  {:brief brief
   :ops ops
   :charter-clean charter-clean
   :charter-hits charter-hits
   :inference inference
   :dry-run dry-run})

(defn charter-scan
  "N6: scan a brief (or op) for Charter-Rider §2(a)-(h) prohibited categories → [clean hits].

  Matches a term only at a WORD START (`\\b` before the term, any suffix allowed) so morphological
  variants still hit (surveil→surveillance, gambl→gambling) without substring false-positives
  ('stalk' must NOT fire on bean-stalk; 'betting' must NOT fire on a-betting)."
  [text]
  (let [low (str/lower (or text ""))
        hits (->> CHARTER-RIDER-TERMS
                  (filter (fn [[term _tag]]
                            (re-find (re-pattern (str "\\b" (java.util.regex.Pattern/quote term))) low)))
                  (map second)
                  (into (sorted-set))
                  vec)]
    [(empty? hits) hits]))

(defn- find-service
  [tokens]
  (some (fn [t]
          (or (get SERVICE-SYNONYMS t)
              (when (contains? command/SERVICE-REGISTRY t) t)))
        tokens))

(defn heuristic-parse
  "Best-effort deterministic NL→command (the hermetic fallback; honest about its limits).

  Recognizes a known service + a natural verb, infers a noun from nearby tokens. Returns a
  `<service> <noun>.<verb>` command string, or nil when it cannot confidently parse (G8 — never
  guesses a service that is not in the registry)."
  [brief]
  (let [raw (map #(str/lower (str/replace % #"^[.,!?;:'\"()]+|[.,!?;:'\"()]+$" ""))
                 (str/split (or brief "") #"\s+"))
        tokens (vec (remove str/blank? raw))]
    (if (empty? tokens)
      nil
      (let [service (find-service tokens)]
        (if (nil? service)
          nil
          (let [service-idx (first (keep-indexed
                                    (fn [i t]
                                      (when (or (= t service) (= (get SERVICE-SYNONYMS t) service)) i))
                                    tokens))
                verb-idx (first (keep-indexed
                                 (fn [i t] (when (contains? NL-VERB t) i)) tokens))]
            (if (nil? verb-idx)
              nil
              (let [;; Noun candidates: tokens that name neither the service, a verb, a stopword, nor a flag.
                    candidates (vec (keep-indexed
                                     (fn [i t]
                                       (when (and (not (contains? NL-VERB t))
                                                  (not (contains? STOPWORDS t))
                                                  (not= t service)
                                                  (not (contains? SERVICE-SYNONYMS t))
                                                  (not (str/starts-with? t "--")))
                                         [i t]))
                                     tokens))
                    ;; Prefer the first candidate after the service name, else the last candidate
                    ;; anywhere, else a safe generic.
                    after (->> candidates (filter (fn [[i _t]] (> i service-idx))) (map second))
                    noun (cond
                           (seq after) (first after)
                           (seq candidates) (second (last candidates))
                           :else "items")]
                (str service " " noun "." (get NL-VERB (nth tokens verb-idx)))))))))))

(defn- murakumo-complete
  "G4: the Murakumo NL→command path. Refused unless explicitly operator-gated (default-deny).

  When gated on it would POST to LiteLLM 127.0.0.1:4000 (loopback, TCC-exempt per ADR-2605302355).
  At R0 this membrane refuses; no other inference provider is reachable from here (G4)."
  [_brief operator-attestation env]
  (let [flag (if env
               (get env "KARAKURI_ALLOW_LIVE_LLM")
               #?(:clj (System/getenv "KARAKURI_ALLOW_LIVE_LLM")
                  :default nil))]
    (when (or (not= flag "1") (not operator-attestation))
      (throw (live-llm-refused
              (str "G4/G6: live Murakumo NL planning is operator-gated "
                   "(KARAKURI_ALLOW_LIVE_LLM=1 + operator attestation); R0 uses the deterministic fallback"))))
    ;; Gated path (not exercised at R0): a real impl would POST to 127.0.0.1:4000 and return a command.
    (throw (live-llm-refused "live Murakumo client not wired at R0 (Council activation pending)"))))

(defn plan-from-brief
  "Plan a member's NL brief into an ordered, gated, Charter-scanned ServiceOp list (dry-run).

  `:use-live-llm true` routes through Murakumo (operator-gated; raises if not gated). Otherwise
  the deterministic heuristic is used. Either way every op passes through command/plan so the ToS
  + mutate gates apply (G2/G5), and the brief + ops are Charter-Rider scanned (N6)."
  [brief & {:keys [use-live-llm operator-attestation env]
            :or {use-live-llm false operator-attestation nil env nil}}]
  (let [[clean0 hits0] (charter-scan brief)
        command-line (if use-live-llm
                       (murakumo-complete brief operator-attestation env)
                       (heuristic-parse brief))]
    (let [[clean hits ops]
          (if (and command-line clean0)
            (let [op (command/plan command-line)
                  ;; N6: also scan the resolved op text.
                  [op-clean op-hits] (charter-scan (str (:service op) " " (:noun op) " " (:verb op)))]
              (if op-clean
                [clean0 hits0 [op]]
                [false (vec (into (sorted-set) (concat hits0 op-hits))) []]))
            [clean0 hits0 []])]
      (make-command-plan
       brief :ops ops :charter-clean clean :charter-hits hits
       :inference INFERENCE-MURAKUMO :dry-run true))))

;; Omitted: the __main__ offline demo (CLI entry point; not part of the library surface).
