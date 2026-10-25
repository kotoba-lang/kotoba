(ns tedai.methods.actuate-live
  "tedai (手代) live-actuation membrane — the SINGLE place live input injection could occur (G6/G3).

  1:1 Clojure port of `20-actors/tedai/methods/actuate_live.py`.

  Every path that would actually touch the member's device (click, keystroke, file
  mutation) funnels through `authorize-actuation`. It refuses unless ALL FOUR
  authorities are present:

    1. env flag `TEDAI_ALLOW_LIVE_ACTUATION=1`   (operator's process-level intent)
    2. `operator-token`                           (operator gate; G6)
    3. `council-attestation`                      (Council Lv6+ attestation ref; G6)
    4. `member-sig`                               (member signature over the exact DesktopOp;
                                                   G3/G5 — a server signature is refused)

  Even with all four present, R0 throws (NotImplementedError analogue): the
  input-driver layer (OS accessibility permissions, HID APIs) is R1+ work gated on
  a Council activation ADR. This module proves the *refusal chain*, not execution.

  No clock reads; no network. Host env access is behind `#?(:clj ...)`."
  (:require [kotoba.lang.text] [tedai.methods.desktop :as desktop]))

(def LIVE-ACTUATION-FLAG "TEDAI_ALLOW_LIVE_ACTUATION")

(defn- actuation-refused
  "Raised when live actuation is requested without every required authority (default-deny)."
  [msg]
  (ex-info msg {:kind ::actuation-refused}))

(defn actuation-refused?
  "Predicate over a caught exception: is it an ActuationRefused?"
  [e]
  (= ::actuation-refused (:kind (ex-data e))))

(defn not-implemented
  "Raised when all authorities are present but the driver layer is R1+ (NotImplementedError)."
  [msg]
  (ex-info msg {:kind ::not-implemented}))

(defn not-implemented?
  "Predicate over a caught exception: is it a NotImplementedError analogue?"
  [e]
  (= ::not-implemented (:kind (ex-data e))))

(defn- host-env
  "Read the process environment (host I/O edge); empty on a non-JVM host."
  []
  #?(:clj (into {} (System/getenv))
     :default {}))

(defn- missing-authorities
  [{:keys [operator-token council-attestation member-sig env]}]
  (let [environ (if (nil? env) (host-env) env)]
    (cond-> []
      (not= (get environ LIVE-ACTUATION-FLAG) "1")
      (conj (str "env:" LIVE-ACTUATION-FLAG "=1 (operator process-level intent)"))
      (not (and operator-token (seq operator-token)))
      (conj "operator_token (operator gate, G6)")
      (not (and council-attestation (seq council-attestation)))
      (conj "council_attestation (Council Lv6+ ref, G6)")
      (not (and member-sig (seq member-sig)))
      (conj "member_sig (member signature over the op, G3/G5)"))))

(defn authorize-actuation
  "Authorize (never perform) one live actuation of a DesktopOp.

  Throws ActuationRefused listing every missing authority (default-deny, G6), and
  throws it for a server-signed request by construction — there is no parameter
  through which a platform key could authorize a mutation (G3). A read op still
  requires the full chain.

  With all authorities present, throws a NotImplementedError analogue at R0 — the
  driver layer is R1+."
  [op & {:keys [operator-token council-attestation member-sig env]}]
  (let [missing (missing-authorities {:operator-token operator-token
                                      :council-attestation council-attestation
                                      :member-sig member-sig
                                      :env env})]
    (when (seq missing)
      (throw (actuation-refused
              (str "G6: live actuation refused; missing authorities: "
                   (kotoba.lang.text/join "; " missing)))))
    (when (and (not (contains? #{desktop/SAFETY-READ} (get op :safety)))
               (= (get op :mutate-gate) desktop/MUTATE-READ-ALLOWED))
      ;; A mutating op whose gate claims read-allowed is a planner-drift bug; never fail open.
      (throw (actuation-refused
              (str "G5: mutating op " (get op :noun) "." (get op :verb)
                   " carries mutate_gate=" (pr-str (get op :mutate-gate)) "; refuse"))))
    (when (= (get op :safety) desktop/SAFETY-OUTWARD)
      ;; The outward gate is a Council-level decision distinct from local actuation (G5);
      ;; there is deliberately no parameter here that satisfies it at R0.
      (throw (actuation-refused
              "G5: :outward op (effect leaves the device) — outward gate not satisfiable at R0")))
    (throw (not-implemented
            (str "tedai R0: all authorities present, but the input-driver layer is R1+ "
                 "(Council activation ADR required; ADR-2606101400 G6)")))))
