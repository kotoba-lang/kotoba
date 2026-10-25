(ns tedai.cells.intent-plan.state-machine
  "Phase state machine for the tedai intent_plan (手代) cell.

  1:1 port of `cells/intent_plan/state_machine.py` (ADR-2606101400). Graph:
  parse-brief -> prohibition-scan -> emit-plan. Turns a member brief (at R0: a
  list of literal `tedai …` command lines; the NL → command leg is the Murakumo
  planner at R1, G4) into gated DesktopOps. The prohibition scan refuses a brief
  that asks for surveillance or detection-evasion in INTENT (G8/G2/N1/N2) BEFORE
  any op is planned — the verb sets in t2_vision are what make those
  unrepresentable at the step level; this scan refuses them at the intent level.

  G2/G8 (prohibition scan) · G5 (each op carries its mutate gate) · G6 (dry-run
  plans only).

  Conventions (mimamori/methods/bond.cljc + shionome regime_observer house
  style):
    - dataclass PlanState → a plain map with kebab keyword keys
    - Python `\":…\"`-equivalent value identities (outcomes, phase values, op
      safety classes) stay bare strings
    - PlanPhase enum value identities (\"init\"/\"parsed\"/… ) stay strings
    - transitions are pure fns; illegal transition / empty-brief → ex-info
    - the `desktop.plan` dependency is ported as a self-contained `plan-op` so
      the cell is runnable on JVM/babashka/SCI without the Python methods layer

  The wrapper state map mirrors the Python dict 1:1: kebab keyword keys
  (`:cell-state`, `:brief`, `:command-lines`, `:next-node`); the Python
  `next_node` string identities (\"prohibition_scan\"/\"emit_plan\"/\"end\") stay
  strings."
  (:require [kotoba.lang.text :as str]))

;; ── prohibition markers (intent-level; G8 surveillance / G2 evasion / N1 / N2) ──

(def prohibited-intents
  "Intent-level prohibition markers. A brief whose text carries one of these is
  refused BEFORE planning; the per-step vocabularies in t2_vision are the
  structural backstop. Verbatim from PROHIBITED_INTENTS (charter invariant —
  bossware/surveillance + detection-evasion intent is structurally refused)."
  ["keylog" "keylogger" "spy" "surveil" "monitor my employee" "watch my kid"
   "track my partner" "record their screen" "their camera" "their microphone"
   "bypass anti-cheat" "bypass anticheat" "bypass drm" "evade detection"
   "without them knowing" "someone else's computer"])

(def outcome-prohibited "refused-prohibited-intent")  ;; OUTCOME_PROHIBITED

;; ── PlanPhase (enum — Python value identities preserved) ──────────

(def plan-phases
  "The closed PlanPhase vocabulary. Keyed by the idiomatic Clojure enum keyword;
  the value is the Python `PlanPhase.<X>.value` string identity."
  {:init    "init"
   :parsed  "parsed"
   :scanned "scanned"
   :planned "planned"
   :refused "refused"})

(def plan-phase-init    (:init plan-phases))     ;; "init"
(def plan-phase-parsed  (:parsed plan-phases))   ;; "parsed"
(def plan-phase-scanned (:scanned plan-phases))  ;; "scanned"
(def plan-phase-planned (:planned plan-phases))  ;; "planned"
(def plan-phase-refused (:refused plan-phases))  ;; "refused"

;; ── PlanState (dataclass → plain map, kebab keys, field defaults) ──

(def plan-state
  "PlanState default value — the @dataclass field defaults as a plain map."
  {:phase         plan-phase-init   ;; PlanPhase.INIT.value
   :brief         ""
   :command-lines []
   :payload       {}})

(defn make-plan-state
  "Construct a PlanState map from a partial cell-state map, filling the dataclass
  defaults (PlanState(**state.get(\"cell_state\", {}))). Unknown keys → ex-info
  (closed PlanState surface — PlanState(**...) would TypeError on an unexpected
  kwarg)."
  [cs]
  (let [cs (or cs {})
        allowed (set (keys plan-state))
        extra (remove allowed (keys cs))]
    (when (seq extra)
      (throw (ex-info (str "unknown PlanState field(s): " (vec extra))
                      {:tedai/closed-vocab true :extra (vec extra)})))
    (merge plan-state cs)))

;; ── desktop.plan dependency, ported (the bits intent_plan consumes) ──
;;
;; intent_plan calls `plan_op(line)` and reads `op.__dict__` + `op.safety`. The
;; full desktop.py is a sibling-methods concern; ported here self-contained so
;; the cell runs on bb/SCI. DesktopOp → a plain map with kebab keys.

(def ^:private app-registry
  "The :representative app capability + synthetic-input stance registry (G8).
  Verbatim subset of desktop.APP_REGISTRY."
  {"finder"         {:t1 true  :t1-surface "applescript+ax"  :t2 "permitted"}
   "mail"           {:t1 true  :t1-surface "applescript+ax"  :t2 "permitted"}
   "calendar"       {:t1 true  :t1-surface "applescript+ax"  :t2 "permitted"}
   "excel"          {:t1 true  :t1-surface "applescript+uia" :t2 "permitted"}
   "terminal"       {:t1 true  :t1-surface "cli"             :t2 "permitted"}
   "keynote"        {:t1 true  :t1-surface "applescript"     :t2 "permitted"}
   "legacy-win-app" {:t1 false :t1-surface ""                :t2 "permitted"}
   "kiosk-tool"     {:t1 false :t1-surface ""                :t2 "permitted"}
   "anticheat-game" {:t1 false :t1-surface ""                :t2 "prohibited"}
   "drm-player"     {:t1 false :t1-surface ""                :t2 "prohibited"}
   "banking-app"    {:t1 false :t1-surface ""                :t2 "prohibited"}
   "chrome"         {:t1 false :t1-surface "" :t2 "prohibited" :route "karakuri"}
   "safari"         {:t1 false :t1-surface "" :t2 "prohibited" :route "karakuri"}
   "firefox"        {:t1 false :t1-surface "" :t2 "prohibited" :route "karakuri"}})

(def t2-engine "on-device-vision")  ;; T2_ENGINE

(def safety-read    "read")     ;; SAFETY_READ
(def safety-create  "create")   ;; SAFETY_CREATE
(def safety-update  "update")   ;; SAFETY_UPDATE
(def safety-delete  "delete")   ;; SAFETY_DELETE
(def safety-outward "outward")  ;; SAFETY_OUTWARD — effect leaves the device

(def ^:private verb-safety
  "VERB_SAFETY — verb → op-safety class (G5)."
  {"list" safety-read "get" safety-read "read" safety-read "find" safety-read
   "search" safety-read "show" safety-read "export" safety-read
   "create" safety-create "add" safety-create "new" safety-create "save" safety-create
   "update" safety-update "set" safety-update "edit" safety-update
   "move" safety-update "rename" safety-update "fill" safety-update
   "delete" safety-delete "remove" safety-delete "trash" safety-delete
   "empty" safety-delete
   "send" safety-outward "post" safety-outward "pay" safety-outward
   "purchase" safety-outward "share" safety-outward "upload" safety-outward
   "publish" safety-outward})

(def tier-t1 "t1-scripting-api")    ;; TIER_T1
(def tier-t2 "t2-vision-pointer")   ;; TIER_T2
(def tier-t3 "t3-file-level")       ;; TIER_T3

(def stance-ok      "ok")                                  ;; STANCE_OK
(def stance-refused "refused-synthetic-input-prohibited")  ;; STANCE_REFUSED

(def mutate-read-allowed      "read-allowed")                          ;; MUTATE_READ_ALLOWED
(def mutate-await-sig         "awaiting-member-sig")                   ;; MUTATE_AWAIT_SIG
(def mutate-await-sig-outward "awaiting-member-sig-and-outward-gate")  ;; MUTATE_AWAIT_SIG_OUTWARD

(def unknown-app     "unknown-app")        ;; UNKNOWN_APP
(def route-karakuri  "route-to-karakuri")  ;; ROUTE_KARAKURI

(defn classify-safety
  "classify_safety — verb → safety. Unknown verbs → :update (conservative)."
  [verb]
  (get verb-safety (str/lower (str/trim (or verb ""))) safety-update))

(defn is-destructive
  "is_destructive — G5: delete is the irreversible class."
  [safety]
  (= safety safety-delete))

(defn resolve-app
  "resolve_app — :representative registry lookup; nil → :unknown-app (G8)."
  [app-id]
  (get app-registry (str/lower (str/trim (or app-id "")))))

(defn t2-stance
  "t2_stance — synthetic-input stance; missing → \"prohibited\" (default-deny, G2)."
  [rec]
  (get rec :t2 "prohibited"))

(defn select-tier
  "select_tier — safest-first (G2): T1 > permitted T2 > T3."
  [rec]
  (cond
    (:t1 rec)                                       tier-t1
    (#{"permitted" "restricted"} (t2-stance rec))   tier-t2
    :else                                           tier-t3))

(defn stance-gate
  "stance_gate — G2: a T2 op on a synthetic-input-prohibited app is refused."
  [rec tier]
  (if (and (= tier tier-t2) (= (t2-stance rec) "prohibited"))
    stance-refused
    stance-ok))

(defn t2-engine-for
  "t2_engine — the on-device engine for a permitted T2 op; \"\" otherwise (G2/G4)."
  [rec tier gate]
  (if (and (= tier tier-t2)
           (= gate stance-ok)
           (#{"permitted" "restricted"} (t2-stance rec)))
    t2-engine
    ""))

(defn mutate-gate
  "mutate_gate — G5: reads allowed; mutations await member-sig; outward adds the
  outward gate."
  [safety]
  (cond
    (= safety safety-read)    mutate-read-allowed
    (= safety safety-outward) mutate-await-sig-outward
    :else                     mutate-await-sig))

(defn parse-command
  "parse_command — `[tedai] <app> <noun>.<verb> [--flag value ...]` →
  {:app :noun :verb :args}. Raises (ex-info) on a malformed command (G8)."
  [line]
  (let [tokens (str/split (str/trim (or line "")) #"\s+")
        tokens (if (and (seq tokens) (= "tedai" (str/lower (first tokens))))
                 (vec (rest tokens))
                 (vec tokens))]
    (when (< (count tokens) 2)
      (throw (ex-info (str "malformed command (need '<app> <noun>.<verb>'): " (pr-str line))
                      {:tedai/malformed-command true :line line})))
    (let [app (str/lower (nth tokens 0))
          nv  (nth tokens 1)]
      (when-not (str/includes? nv ".")
        (throw (ex-info (str "malformed op (need '<noun>.<verb>'): " (pr-str nv))
                        {:tedai/malformed-command true :nv nv})))
      (let [[noun verb] (str/split nv #"\." 2)]
        (when (or (str/blank? noun) (str/blank? verb))
          (throw (ex-info (str "malformed op (empty noun or verb): " (pr-str nv))
                          {:tedai/malformed-command true :nv nv})))
        (let [rest-toks (vec (drop 2 tokens))]
          (loop [j 0 args {}]
            (if (< j (count rest-toks))
              (let [tok (nth rest-toks j)]
                (if (str/starts-with? tok "--")
                  (let [k (subs tok 2)
                        nxt (when (< (inc j) (count rest-toks)) (nth rest-toks (inc j)))]
                    (if (and (some? nxt) (not (str/starts-with? nxt "--")))
                      (recur (+ j 2) (assoc args k nxt))
                      (recur (inc j) (assoc args k true))))
                  (recur (inc j) args)))
              {:app app :noun (str/lower noun) :verb (str/lower verb) :args args})))))))

(defn plan-op
  "plan / plan_op — parse a command into a dry-run DesktopOp map with every gate
  applied (no input injection). The map's keys are the DesktopOp dataclass fields
  in kebab form (the Python `op.__dict__`)."
  ([line] (plan-op line nil))
  ([line prefer-tier]
   (when (and (some? prefer-tier) (not (#{tier-t1 tier-t2 tier-t3} prefer-tier)))
     (throw (ex-info (str "unknown prefer-tier " (pr-str prefer-tier)
                          " (expected one of T1/T2/T3 constants)")
                     {:tedai/bad-prefer-tier true :prefer-tier prefer-tier})))
   (let [{:keys [app noun verb args]} (parse-command line)
         safety (classify-safety verb)
         rec    (resolve-app app)]
     (cond
       (nil? rec)
       {:app app :noun noun :verb verb :safety safety
        :destructive (is-destructive safety) :adapter-tier ""
        :args args :app-known false :dry-run true
        :stance-gate stance-ok :mutate-gate (mutate-gate safety)
        :t2-engine "" :route "" :note unknown-app}

       (= "karakuri" (:route rec))
       {:app app :noun noun :verb verb :safety safety
        :destructive (is-destructive safety) :adapter-tier ""
        :args args :app-known true :dry-run true
        :stance-gate stance-ok :mutate-gate (mutate-gate safety)
        :t2-engine "" :route "karakuri" :note route-karakuri}

       :else
       (let [tier   (or prefer-tier (select-tier rec))
             gate   (stance-gate rec tier)
             engine (t2-engine-for rec tier gate)
             note   (if (= gate stance-refused)
                      (str "G2: synthetic input prohibited on this app; "
                           "T2 vision-pointer refused — use the scripting API (T1) "
                           "or T3 file-level")
                      "")]
         {:app app :noun noun :verb verb :safety safety
          :destructive (is-destructive safety) :adapter-tier tier
          :args args :app-known true :dry-run true
          :stance-gate gate :mutate-gate (mutate-gate safety)
          :t2-engine engine :route "" :note note})))))

;; ── transitions (pure; 1:1 with the Python state machine) ─────────

(defn transition-parse-brief
  "transition_parse_brief — collect the brief text + literal command lines (R0;
  NL→command is the R1 Murakumo leg, G4). Empty command lines → ex-info
  (Python ValueError parity)."
  [state]
  (let [state (or state {})
        cs    (make-plan-state (:cell-state state))
        brief (get state :brief (:brief cs))
        command-lines (vec (get state :command-lines (:command-lines cs)))]
    (when (empty? command-lines)
      (throw (ex-info "intent_plan: no command lines supplied (R0 takes literal `tedai …` lines)"
                      {:tedai/empty-command-lines true})))
    {:cell-state (assoc cs
                        :brief brief
                        :command-lines command-lines
                        :phase plan-phase-parsed)
     :next-node "prohibition_scan"}))

(defn transition-prohibition-scan
  "transition_prohibition_scan — G8/G2: refuse a brief that asks for surveillance
  or detection-evasion in intent, BEFORE any op is planned."
  [state]
  (let [cs   (make-plan-state (:cell-state state))
        text (str/lower (str/join " " (cons (:brief cs) (:command-lines cs))))
        hits (filterv (fn [marker] (str/includes? text marker)) prohibited-intents)]
    (if (seq hits)
      {:cell-state (assoc cs
                          :phase plan-phase-refused
                          :payload (assoc (:payload cs)
                                          "outcome" outcome-prohibited
                                          "markers" hits))
       :next-node "end"}
      {:cell-state (assoc cs :phase plan-phase-scanned)
       :next-node "emit_plan"})))

(defn transition-emit-plan
  "transition_emit_plan — G5/G6: plan each command line into a gated, dry-run
  DesktopOp. Reaching emit-plan without a clean prohibition scan → ex-info
  (Python ValueError parity — the illegal-transition guard)."
  [state]
  (let [cs (make-plan-state (:cell-state state))]
    (when (not= (:phase cs) plan-phase-scanned)
      (throw (ex-info "intent_plan: emit_plan reached without a clean prohibition scan"
                      {:tedai/illegal-transition true :phase (:phase cs)})))
    (let [ops (mapv plan-op (:command-lines cs))]
      {:cell-state (assoc cs
                          :payload (assoc (:payload cs)
                                          "ops" ops
                                          "dryRun" true                      ;; G6 invariant
                                          "mutatingCount" (count (filter #(not= (:safety %) safety-read) ops)))
                          :phase plan-phase-planned)
       :next-node "end"})))

(defn solve
  "R0 scaffold: .solve() raises until Council activation (ADR-2606101400 §Decision, G6)."
  [_input-state]
  (throw (ex-info "tedai R0 scaffold: activate intent_plan via Council ADR (post-2606101400 ratification)"
                  {:scaffold true})))
