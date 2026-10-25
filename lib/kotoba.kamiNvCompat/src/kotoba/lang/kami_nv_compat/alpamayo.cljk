(ns kotoba.lang.kami-nv-compat.alpamayo
  "Drop-in NVIDIA Alpamayo VLA API-compat facade — portable .cljc port of
  src/alpamayo.ts. Mirrors the documented public inference surface of the
  Alpamayo reasoning Vision-Language-Action model (multi-camera images +
  navigation command + egomotion history -> future trajectory + Chain-of-
  Causation reasoning), so existing Alpamayo host code ports to KAMI via
  require-path-only changes.

  Backed by the clean-room kami-drive reasoning planner (michibiki) + BEV
  unicycle model — NO Alpamayo / Cosmos / DRIVE weights, source, or binaries
  are used. This is a from-spec reproduction of the public I/O contract
  (Google v. Oracle, 593 U.S. ___ (2021)).

  AlpamayoR1 has no mutable state (pretrained-name + planner-cfg are both
  fixed at construction, and TS's own createScene-style methods never touch
  mutable `this` either) — no atom/reify needed, matching the rtx-renderer
  precedent. A model is a plain {:pretrained-name :planner-cfg} map; predict
  / predict-async / predict-from-input take it as an explicit first arg.
  `predictAsync` is async in TS (awaiting an optional Murakumo verbalizer);
  on JVM `narrate` is called synchronously, matching the omni-kit-app /
  rtx-renderer precedent that JVM sync has identical semantics to the async
  JS shape here (no true I/O concurrency in this facade either way).

  Charter posture (religious-corp AV invariants):
    - SAE-L4 ceiling — L5 / unconditional autonomy is unrepresentable
      (ADR-2605242000 wadachi, ADR-2606010600 kami-autodrive).
    - NO actuation — `predict` returns a RECOMMENDED trajectory + reasoning;
      it never sends controls to a vehicle.
    - Murakumo-only inference — any language verbalization routes through an
      injected Murakumo callback (LiteLLM 127.0.0.1:4000), never a vendor
      endpoint (ADR-2605215000). Default is a deterministic template.

  Trademark: NVIDIA®, Alpamayo, DRIVE®, Cosmos are trademarks of NVIDIA
  Corporation; this project is not affiliated with or endorsed by NVIDIA.

  nv-compat namespace (ADR-2605261800 D1/D6); AV scope per wadachi /
  kami-autodrive ADRs. Wave 41 of ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.kami-drive.planner :as planner]))

;; ── I/O shapes (mirror the Alpamayo model card) ─────────────────────────────
;;
;; CameraStack        {:name :frames}           — frames are opaque refs
;; EgomotionWaypoint   {:translation :rotation :timestamp}
;; AlpamayoInput       {:images :command :egomotion-history}
;; AlpamayoOutput      {:trajectory :reasoning :explanation}

(def camera-names
  "The four Alpamayo input cameras."
  ["front_wide" "front_tele" "cross_left" "cross_right"])

;; Alpamayo trajectory constants (from the model card).
(def trajectory-horizon-s 6.4)
(def trajectory-hz 10)
(def trajectory-waypoints 64)
(def history-s 0.4)

(def sae-ceiling
  "Highest SAE level the facade will represent. L5 is intentionally absent."
  4)

;; ── model ────────────────────────────────────────────────────────────────

(defn from-pretrained
  "`AlpamayoR1.from_pretrained(...)` mirror. The checkpoint name is accepted
  for API parity; the canonical KAMI engine (michibiki) is always used.
  `opts` = {:planner <partial planner config>}."
  ([] (from-pretrained "nvidia/Alpamayo-R1-10B"))
  ([pretrained-name] (from-pretrained pretrained-name {}))
  ([pretrained-name opts]
   {:pretrained-name pretrained-name
    :planner-cfg     (merge {:horizon-s trajectory-horizon-s :hz trajectory-hz}
                             (:planner opts))}))

(def engine
  "Canonical KAMI engine name behind the facade." "michibiki")

(defn predict
  "Synchronous inference over a structured driving observation. Returns a
  RECOMMENDED 6.4 s trajectory + Chain-of-Causation (deterministic
  narrative)."
  [model obs]
  (let [{:keys [trajectory reasoning]} (planner/plan obs (:planner-cfg model))]
    {:trajectory trajectory :reasoning reasoning :explanation (:narrative reasoning)}))

(defn predict-async
  "Inference with an optional Murakumo verbalizer for the explanation.
  Without `narrate`, falls back to the deterministic template (identical to
  predict). `narrate` = (fn [coc obs] -> explanation-string); an exception
  is swallowed and the deterministic narrative is kept (fail-open, matching
  the TS try/catch around the Murakumo call — unavailable is expected, not
  exceptional)."
  ([model obs] (predict-async model obs nil))
  ([model obs narrate]
   (let [out (predict model obs)]
     (if narrate
       (try
         (let [explanation (narrate (:reasoning out) obs)]
           (-> out
               (assoc :explanation explanation)
               (assoc-in [:reasoning :narrative] explanation)))
         (catch #?(:clj Exception :cljs :default) _ out))
       out))))

(defn- ego-speed-from-history
  "Estimate current ego speed from the last two egomotion samples."
  [history]
  (if (< (count history) 2)
    0
    (let [a  (nth history (- (count history) 2))
          b  (nth history (dec (count history)))
          dt (- (:timestamp b) (:timestamp a))]
      (if (<= dt 0)
        0
        (let [dx (- (get-in b [:translation 0]) (get-in a [:translation 0]))
              dy (- (get-in b [:translation 1]) (get-in a [:translation 1]))]
          (/ (Math/hypot dx dy) dt))))))

(defn predict-from-input
  "Lower-level overload accepting the raw Alpamayo input tuple. The
  egomotion history seeds the ego speed; agents must be provided via
  `obs`'s :agents since this facade ships no vision encoder. `obs` is the
  rest of a DrivingObservation minus :ego / :instruction (those two are
  derived from `input`)."
  [model input obs]
  (predict model (assoc obs
                         :instruction (:command input)
                         :ego {:x 0 :y 0 :yaw 0
                               :speed (ego-speed-from-history (:egomotion-history input))})))

(def kami-engine "michibiki")
(def adr "ADR-2606010600")   ; kami-autodrive (AV autonomy)
