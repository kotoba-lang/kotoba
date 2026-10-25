(ns karakuri.methods.adapter-live
  "karakuri (絡繰) live-adapter membrane — the single gate every live adapter call crosses (G6).

  1:1 Clojure port of `methods/adapter_live.py`.

  R0 ships parse/plan/dry-run only. The MOMENT karakuri would touch a third-party service for
  real — any T1 official-API call, T2 browser-use action, or T3 export pull/push — the request
  must cross this membrane, which refuses by default and authorizes ONLY when ALL hold:

    - operator process flag KARAKURI_ALLOW_LIVE_ADAPTER=1 (operator opted this host in), AND
    - an operator attestation DID, AND
    - Council Lv6+ (G6), AND
    - a MEMBER signature (G3 no-server-key — the server can never sign; ADR-2605231525).

  The membrane is an AUTHORIZATION boundary, never an invariant override: even when fully
  authorized it returns an authorization descriptor and does NOT itself execute — the actual
  browser-use / API driver is a separate, post-activation component. For a T2 leg it additionally
  requires the op's ToS gate to be OK and its engine to be browser-use. Mirrors the fuchi
  live_gate pattern (ADR-2606052300).

  ServiceOp is the plain map produced by command/plan (keyword keys). The live env read is behind
  #?(:clj …). clojure.core only; portable .cljc."
  (:require [karakuri.methods.command :as command]))

(def LIVE-FLAG "KARAKURI_ALLOW_LIVE_ADAPTER")
(def COUNCIL-MIN-LEVEL 6)                                ; G6
(def VALID-LEGS [command/TIER-T1 command/TIER-T2 command/TIER-T3])

(defn- live-adapter-refused
  "ex-info marked as a live-adapter refusal (default-deny; G6/G3)."
  [msg]
  (ex-info msg {:type :live-adapter-refused}))

(defn authorize-live
  "Authorize (never execute) one live adapter call. Raises unless every gate is satisfied. Returns
  an authorization descriptor on success (still no network performed here)."
  [op & {:keys [operator-attestation member-sig council-level env]
         :or {operator-attestation nil member-sig "" council-level 0 env nil}}]
  (let [flag (if env
               (get env LIVE-FLAG)
               #?(:clj (System/getenv LIVE-FLAG)
                  :default nil))]
    (when (not= flag "1")
      (throw (live-adapter-refused
              (str "G6: live adapter execution is gated; set " LIVE-FLAG "=1 on an opted-in operator host"))))
    (when-not operator-attestation
      (throw (live-adapter-refused "G6: an operator attestation DID is required for live execution")))
    (when (< council-level COUNCIL-MIN-LEVEL)
      (throw (live-adapter-refused
              (str "G6: Council Lv" COUNCIL-MIN-LEVEL "+ required for live execution (got Lv" council-level ")"))))
    (when-not (seq member-sig)
      (throw (live-adapter-refused
              "G3: a member signature is required; the server never signs (no-server-key, ADR-2605231525)")))
    (when-not (some #{(:adapter-tier op)} VALID-LEGS)
      (throw (live-adapter-refused (str "unknown adapter leg " (pr-str (:adapter-tier op))))))

    ;; Leg-specific charter checks (defence in depth — these also held at plan time).
    (when (= (:adapter-tier op) command/TIER-T2)
      (when (not= (:tos-gate op) command/TOS-OK)
        (throw (live-adapter-refused "G2: ToS gate not OK; browser automation refused")))
      (when (not= (:t2-engine op) command/T2-ENGINE)
        (throw (live-adapter-refused "G2: T2 leg requires the browser-use engine"))))

    {"authorized" true
     "leg" (:adapter-tier op)
     "engine" (if (seq (:t2-engine op)) (:t2-engine op) nil)
     "safety" (:safety op)            ; G5 — the driver must honor the mutate gate below
     "mutateGate" (:mutate-gate op)   ; G5 — :read-allowed / :awaiting-member-sig (carried, not re-derived)
     "destructive" (:destructive op)  ; G5 — a destructive leg the driver must surface to the member
     "authorizedBy" "member"          ; G3
     "serverSigned" false             ; G3 — never
     "operatorAttested" true          ; G6
     "councilLevel" council-level     ; G6
     "executed" false                 ; the membrane authorizes; the driver executes (post-R0)
     "note" "authorization only; live driver is a post-activation component (G6)"}))
