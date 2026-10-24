(ns tedai.methods.t2-vision
  "tedai (手代) T2 vision-pointer adapter — dry-run computer-use plan builder (ADR-2606101400).

  1:1 Clojure port of `20-actors/tedai/methods/t2_vision.py`.

  T2 is the stance-permitted vision-pointer tier — the computer-use shape:
  screenshot → locate → click/type on the member's OWN paired device (G1). Its
  engine is on-device vision (baien edge / LAN Murakumo — G4): a screenshot NEVER
  leaves the device. This module turns a T2 DesktopOp into a DECLARATIVE, dry-run
  action plan WITHOUT any input driver and WITHOUT touching the screen (G6).

  - G8 no-surveillance: the action vocabulary (`VISION-ACTIONS`) cannot express
    ambient watching/keylogging/camera/microphone capture; those verbs live in
    `SURVEILLANCE-ACTIONS` and constructing a step with one raises.
  - G2 no detection-evasion: anti-cheat bypass / DRM circumvention / input forgery
    live in `EVASION-ACTIONS`; same refusal.
  - G4 on-device vision: the only evidence action is `evidence_hash` (a sha256 of
    the frame; the raw frame stays on-device under the member's key — G9).
  - G1/G3 own-device-only: every plan opens with the member's own pairing grant
    (an encrypted ref, never a credential).
  - G6 dry-run: every step is planned, never executed; the `live` flag refuses.

  Pairs with `desktop.cljc` (the DesktopOp parser/planner). Pure portable .cljc;
  string-keyed step maps; ':ns/name' kept AS strings."
  (:require [tedai.methods.desktop :as desktop]))

;; The vision-pointer action vocabulary tedai will plan (member's own device; op-scoped observation).
(def VISION-ACTIONS
  #{"attach_pairing"   ; attach the member's OWN paired device (encrypted pairing-grant ref; G1/G3)
    "observe_screen"   ; one op-scoped frame of the member's own session (G8: never ambient)
    "locate"           ; find a UI element in the observed frame (on-device vision; G4)
    "wait_for"         ; wait for an element/state (human-paced)
    "read_text"        ; read visible text the member can already see
    "extract"          ; structure read content into a result
    "click"            ; click a located control (mutate; gated by member signature, G5)
    "type_text"        ; type into a located field (mutate; member-signature required, G5)
    "press_key"        ; press a key/chord (mutate; gated)
    "scroll"           ; scroll a located surface
    "evidence_hash"})  ; sha256 the frame for the member's audit trail (G9 — never the raw frame)

;; Structurally forbidden — surveillance (G8 / N1 / N4). Unrepresentable: building a step with any
;; of these raises. There is deliberately no flag, knob, or option anywhere in tedai that turns one on.
(def SURVEILLANCE-ACTIONS
  #{"watch_user"
    "monitor_idle"
    "track_presence"
    "keylog"
    "capture_camera"
    "capture_microphone"
    "record_other_person"
    "exfiltrate_screen"
    "upload_frame"})

;; Structurally forbidden — detection-evasion / input forgery (G2 / N2). Same refusal.
(def EVASION-ACTIONS
  #{"bypass_anticheat"
    "bypass_drm"
    "evade_bot_detection"
    "spoof_input_driver"
    "forge_hid_device"
    "randomize_input_timing"})

;; ── exceptions (ported as ex-info with a :kind tag) ──────────────────────────

(defn- surveillance-refused
  "Raised when a vision step would perform surveillance (G8 / N1 — unrepresentable)."
  [msg]
  (ex-info msg {:kind ::surveillance-refused}))

(defn- evasion-refused
  "Raised when a vision step would perform detection-evasion (G2 / N2 — unrepresentable)."
  [msg]
  (ex-info msg {:kind ::evasion-refused}))

(defn- t2-not-eligible
  "Raised when an op is not a charter-eligible T2 vision-pointer op (wrong tier / stance refused)."
  [msg]
  (ex-info msg {:kind ::t2-not-eligible}))

(defn surveillance-refused?
  "Predicate over a caught exception: is it a SurveillanceRefused?"
  [e]
  (= ::surveillance-refused (:kind (ex-data e))))

(defn evasion-refused?
  "Predicate over a caught exception: is it an EvasionRefused?"
  [e]
  (= ::evasion-refused (:kind (ex-data e))))

(defn t2-not-eligible?
  "Predicate over a caught exception: is it a T2NotEligible?"
  [e]
  (= ::t2-not-eligible (:kind (ex-data e))))

;; ── step construction (surveillance/evasion unrepresentable by construction) ──

(defn make-step
  "Build one vision step, refusing surveillance and evasion verbs by construction (G8/G2).

  `fields` is a map of additional step fields (string-keyed)."
  ([action] (make-step action {}))
  ([action fields]
   (cond
     (contains? SURVEILLANCE-ACTIONS action)
     (throw (surveillance-refused
             (str "G8/N1: '" action "' is surveillance and is unrepresentable in tedai")))

     (contains? EVASION-ACTIONS action)
     (throw (evasion-refused
             (str "G2/N2: '" action "' is detection-evasion and is unrepresentable in tedai")))

     (not (contains? VISION-ACTIONS action))
     (throw (ex-info (str "unknown vision action " (pr-str action) " (not in VISION-ACTIONS)")
                     {:action action}))

     :else (assoc fields "action" action))))

(defn assert-no-forbidden
  "G8/G2: verify a step list contains no surveillance or evasion action (defence in depth)."
  [steps]
  (doseq [step steps]
    (let [action (get step "action")]
      (when (contains? SURVEILLANCE-ACTIONS action)
        (throw (surveillance-refused (str "G8/N1: surveillance step present: " (pr-str action)))))
      (when (contains? EVASION-ACTIONS action)
        (throw (evasion-refused (str "G2/N2: detection-evasion step present: " (pr-str action))))))))

(defn- steps-for
  "Build the dry-run vision-pointer step skeleton for a DesktopOp (read vs mutate; G5)."
  [op grant-ref]
  (let [base
        [;; G1/G3: the member's OWN paired device, via an encrypted grant ref — never a credential.
         (make-step "attach_pairing" {"principal" "member" "device_owner" "member"
                                      "grant_ref" grant-ref "server_held_key" false})
         ;; G8: one op-scoped frame of the member's own session; never ambient, never retained raw.
         (make-step "observe_screen" {"scope" "op" "session_owner" "member" "retain_raw" false})
         (make-step "locate" {"target" (get op :noun) "engine" desktop/T2-ENGINE})
         (make-step "wait_for" {"target" (get op :noun) "human_paced" true})]
        body
        (if (= (get op :safety) desktop/SAFETY-READ)
          [(make-step "read_text" {"target" (get op :noun)})
           (make-step "extract" {"as_result" (get op :noun)})]
          ;; Mutating ops: the plan stops at a member-signature checkpoint; nothing clicks without it (G5).
          [(make-step "click" {"target" (get op :noun) "requires" "member-signature"})
           (make-step "type_text" {"target" (get op :noun)
                                   "from_args" (vec (sort (keys (get op :args))))
                                   "requires" "member-signature"})])]
    ;; G9: evidence is a hash of the frame, never the frame.
    (conj (into base body)
          (make-step "evidence_hash" {"algo" "sha256" "raw_frame_retained" false}))))

(defn build-vision-plan
  "Build a dry-run vision-pointer action plan for a T2 DesktopOp.

  Refuses (throws T2NotEligible) unless the op is a charter-eligible T2
  vision-pointer op:
    - `:adapter-tier` must be T2 (use the scripting API for T1 apps),
    - `:stance-gate` must be OK (a synthetic-input-prohibited app has no plan; G2),
    - `:t2-engine` must be on-device-vision (set by `desktop/plan` only on a permitted T2 op).
  `:live true` is refused outright — R0 never actuates (G6)."
  [op & {:keys [grant-ref live]
         :or {grant-ref "encref:com.etzhayyim.encrypted/<device>-pairing"
              live false}}]
  (when live
    (throw (t2-not-eligible
            "G6: live input injection is Council Lv6+ + operator gated; R0 is dry-run only")))
  (when (not= (get op :adapter-tier) desktop/TIER-T2)
    (throw (t2-not-eligible
            (str "not a T2 op (tier=" (pr-str (get op :adapter-tier)) "); vision-pointer is the T2 engine only. "
                 "Apps with a scripting/accessibility surface use T1, not pixels."))))
  (when (not= (get op :stance-gate) desktop/STANCE-OK)
    (throw (t2-not-eligible
            (str "G2: stance gate is " (pr-str (get op :stance-gate)) "; synthetic input refused — no plan"))))
  (when (not= (get op :t2-engine) desktop/T2-ENGINE)
    (throw (t2-not-eligible
            (str "G2: synthetic-input stance does not permit T2 for app " (pr-str (get op :app))))))

  (let [steps (steps-for op grant-ref)]
    (assert-no-forbidden steps)  ; G8/G2 defence in depth
    {"engine" desktop/T2-ENGINE                 ; on-device vision (baien edge / LAN Murakumo; G4)
     "runtime" "langgraph->wasm"                ; planned in a LangGraph cell, run in-WASM (Murakumo-only)
     "app" (get op :app)
     "op" (str (get op :noun) "." (get op :verb))
     "tier" (get op :adapter-tier)
     "safety" (get op :safety)
     "mutate_gate" (get op :mutate-gate)        ; reads run; mutates wait on member signature (G5)
     "dry_run" true                             ; G6 invariant — R0 never actuates
     "surveillance" false                       ; G8 — unrepresentable by construction
     "detection_evasion" false                  ; G2 — unrepresentable by construction
     "frame_leaves_device" false                ; G4/G9 — evidence is a hash, raw frame stays on-device
     "steps" steps
     "note" "R0 dry-run; live input injection Council Lv6+ + operator gated (G6)"}))

;; Note: the Python `if __name__ == "__main__"` offline demo is omitted (not a unit).
