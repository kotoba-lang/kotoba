(ns karakuri.methods.t2-browser
  "karakuri (絡繰) T2 browser-use adapter — dry-run action-plan builder (ADR-2606039200).

  1:1 Clojure port of `methods/t2_browser.py`.

  T2 is the **ToS-permitted headless-browser** tier. Its engine is **browser-use** — a
  LangGraph-driven browser agent over Playwright — driving the **member's OWN authenticated
  session** (G1). This module turns a T2 ServiceOp into a DECLARATIVE, dry-run browser action
  plan without importing browser-use and without touching the network (G6). Live execution is
  Council Lv6+ + operator gated.

  Charter invariants are enforced structurally over the declarative plan:
  - G2 no detection-evasion — the action vocabulary (BROWSER-ACTIONS) cannot express
    proxy/IP rotation, captcha-solving-as-evasion, stealth fingerprinting, or rate-limit
    circumvention. Those verbs live in EVASION-ACTIONS; building a step with one raises.
  - G2 ToS-honest — a refused ToS gate (or non-T2 op, or non-permitted browser stance) yields
    no plan; build-browser-plan raises.
  - G1 own-account-only — the plan opens the member's own session via the encrypted
    session-grant ref (never a credential, G3); no field points at another account.
  - G6 dry-run — every step is planned, never executed; the `live` flag refuses by construction.

  ServiceOp is the plain map produced by `karakuri.methods.command/plan` (keyword keys). Pairs
  with command.cljc and the adapter_invoke cell. clojure.core only; portable .cljc."
  (:require [karakuri.methods.command :as command]))

;; The browser-use action vocabulary karakuri will plan (member's own session; ToS-honest).
(def BROWSER-ACTIONS
  #{"open_session"   ; attach the member's OWN authenticated session (encrypted grant ref; G1/G3)
    "goto"           ; navigate to an in-account URL
    "wait_for"       ; wait for an element/state (human-paced; respects the site, no busy-loop)
    "read_text"      ; read visible text the member can already see
    "extract"        ; structure read content into a result
    "click"          ; click an in-account control
    "fill"           ; fill a form field (mutate; gated by member signature, G5)
    "select"         ; choose an option
    "submit"         ; submit a form (mutate; member-signature required, G5)
    "screenshot"})   ; capture for the member's own audit trail

;; Structurally forbidden — detection-evasion / anti-bot circumvention (G2 / N2). Unrepresentable:
;; building a step with any of these raises. There is deliberately no flag, knob, or option
;; anywhere in karakuri that turns one on.
(def EVASION-ACTIONS
  #{"solve_captcha"
    "rotate_proxy"
    "set_proxy"
    "spoof_fingerprint"
    "stealth_mode"
    "bypass_ratelimit"
    "randomize_user_agent"
    "evade_detection"})

(defn- evasion-refused
  "ex-info marked as a detection-evasion refusal (G2 / N2 — unrepresentable)."
  [msg]
  (ex-info msg {:type :evasion-refused}))

(defn- t2-not-eligible
  "ex-info marked as a not-charter-eligible-T2 op (wrong tier / ToS refused)."
  [msg]
  (ex-info msg {:type :t2-not-eligible}))

(defn make-step
  "Build one browser-use step, refusing any detection-evasion verb by construction (G2)."
  [action & {:as fields}]
  (cond
    (contains? EVASION-ACTIONS action)
    (throw (evasion-refused
            (str "G2/N2: '" action "' is detection-evasion and is unrepresentable in karakuri")))
    (not (contains? BROWSER-ACTIONS action))
    (throw (ex-info (str "unknown browser action " (pr-str action) " (not in BROWSER-ACTIONS)")
                    {:action action}))
    :else (assoc (or fields {}) "action" action)))

(defn assert-no-evasion
  "G2: verify a step list contains no detection-evasion action (defence in depth)."
  [steps]
  (doseq [step steps]
    (when (contains? EVASION-ACTIONS (get step "action"))
      (throw (evasion-refused
              (str "G2/N2: detection-evasion step present: " (pr-str (get step "action"))))))))

(defn- steps-for
  "Build the dry-run browser-use step skeleton for a ServiceOp (read vs mutate; G5)."
  [op grant-ref]
  (let [base [;; G1/G3: the member's OWN session, via an encrypted grant ref — never a plaintext credential.
              (make-step "open_session" "principal" "member" "account_owner" "member"
                         "grant_ref" grant-ref "server_held_key" false)
              (make-step "goto" "target" (str (:service op) ":" (:noun op)))
              (make-step "wait_for" "target" (:noun op) "human_paced" true)]]
    (if (= (:safety op) command/SAFETY-READ)
      (into base
            [(make-step "read_text" "target" (:noun op))
             (make-step "extract" "as_result" (:noun op))])
      ;; Mutating ops: the plan stops at a member-signature checkpoint; nothing submits without it (G5).
      (into base
            [(make-step "fill" "target" (:noun op) "from_args" (sort (keys (:args op))))
             (make-step "submit" "target" (:noun op) "requires" "member-signature")]))))

(defn build-browser-plan
  "Build a dry-run browser-use action plan for a T2 ServiceOp.

  Refuses (raises) unless the op is a charter-eligible T2 browser-use op:
    - :adapter-tier must be T2 (use the official API for T1 services — Google/Facebook),
    - :tos-gate must be OK (a ToS-prohibited service has no plan; G2),
    - :t2-engine must be browser-use (set by command/plan only on a permitted T2 op).
  `:live true` is refused outright — R0 never executes; live exec is Council Lv6+ + operator
  gated (G6)."
  [op & {:keys [grant-ref live]
         :or {grant-ref "encref:com.etzhayyim.encrypted/<service>-session"
              live false}}]
  (when live
    (throw (t2-not-eligible
            "G6: live browser execution is Council Lv6+ + operator gated; R0 is dry-run only")))
  (when (not= (:adapter-tier op) command/TIER-T2)
    (throw (t2-not-eligible
            (str "not a T2 op (tier=" (pr-str (:adapter-tier op)) "); browser-use is the T2 engine only. "
                 "T1 services (e.g. Google, Facebook) use their official API, not browser automation."))))
  (when (not= (:tos-gate op) command/TOS-OK)
    (throw (t2-not-eligible
            (str "G2: ToS gate is " (pr-str (:tos-gate op)) "; browser automation refused — no plan"))))
  (when (not= (:t2-engine op) command/T2-ENGINE)
    (throw (t2-not-eligible
            (str "G2: browser-automation stance does not permit T2 for service " (pr-str (:service op))))))

  (let [steps (steps-for op grant-ref)]
    (assert-no-evasion steps)  ; G2 defence in depth
    {"engine" command/T2-ENGINE              ; browser-use
     "runtime" "langgraph->wasm"             ; planned in a LangGraph cell, run in-WASM (Murakumo-only)
     "service" (:service op)
     "op" (str (:noun op) "." (:verb op))
     "tier" (:adapter-tier op)
     "safety" (:safety op)
     "mutate_gate" (:mutate-gate op)         ; reads run; mutates wait on member signature (G5)
     "dry_run" true                          ; G6 invariant — R0 never executes
     "detection_evasion" false               ; G2 — unrepresentable by construction
     "steps" steps
     "note" "R0 dry-run; live browser-use execution Council Lv6+ + operator gated (G6)"}))

;; Omitted: the __main__ offline demo (CLI entry point; not part of the library surface).
