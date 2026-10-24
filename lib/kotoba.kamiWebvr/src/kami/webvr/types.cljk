(ns kami.webvr.types
  "Pure data shapes for the choice-based scenario engine (ported from
   kami-engine-sdk's src/lib/webvr/types.ts). All keys/values are plain EDN --
   no platform code, runs identically on the JVM and in ClojureScript.")

;; Stage keywords map to NIST CSF categories (see the original TS comments):
;;   :detect=DE.AE/DE.CM, :triage=RS.AN, :contain=RS.MI, :communicate=RS.CO,
;;   :eradicate=RS.MI cont'd, :recover=RC.RP/RC.IM, :govern=GV
(def stages #{:detect :triage :contain :communicate :eradicate :recover :govern})

(def severities #{:info :low :medium :high :critical})

;; :scada-room=中央監視室 :cleanroom=クリーンルーム :chemical-yard=薬液タンクヤード
;; :utility-room=用力室 :server-room=情報系サーバ室(Purdue L4-L5)
;; :executive-room=役員会議室 :press=プレス対応室
(def location-kinds
  #{:scada-room :cleanroom :chemical-yard :utility-room
    :server-room :executive-room :press})

(def node-effect-kinds
  #{:red-alarm :orange-smoke :data-leak :press-flash :dawn-light :green-check :monitor-flicker})

;; IncidentKpi: {:mttd-sec :mttr-sec :downtime-min :regulatory-risk-permille
;;               :data-loss-gb :cost-yen-deci}
(def zero-kpi
  {:mttd-sec 0 :mttr-sec 0 :downtime-min 0
   :regulatory-risk-permille 0 :data-loss-gb 0 :cost-yen-deci 0})

(defn- clamp-permille [v]
  (cond (< v 0) 0 (> v 1000) 1000 :else (int v)))

(defn apply-kpi-delta
  "base + delta -> a new IncidentKpi. mttd-sec/mttr-sec/downtime-min are summed
   unclamped; regulatory-risk-permille is summed then clamped to [0,1000] and
   truncated to an int; data-loss-gb/cost-yen-deci are summed then floored at 0.
   Ported 1:1 from applyKpiDelta in incident-pregel.ts (deliberately preserves
   that function's asymmetric clamping -- downtime-min is NOT floored at 0
   despite intuitively also being non-negative, matching the original)."
  [base delta]
  {:mttd-sec (+ (:mttd-sec base) (get delta :mttd-sec 0))
   :mttr-sec (+ (:mttr-sec base) (get delta :mttr-sec 0))
   :downtime-min (+ (:downtime-min base) (get delta :downtime-min 0))
   :regulatory-risk-permille (clamp-permille (+ (:regulatory-risk-permille base)
                                                 (get delta :regulatory-risk-permille 0)))
   :data-loss-gb (max 0 (+ (:data-loss-gb base) (get delta :data-loss-gb 0)))
   :cost-yen-deci (max 0 (+ (:cost-yen-deci base) (get delta :cost-yen-deci 0)))})

;; IncidentChoice: {:id :label :hint :next :delta :grade :rationale :reference}
;;   :grade is one of #{:best :ok :bad}
;; IncidentNode: {:id :stage :severity :location :briefing :choices :terminal
;;                :camera-hint :cine :effects}
;;   :terminal, when present, is one of #{:success :partial :failure}
;; IncidentScenario: {:id :title :synopsis :start :nodes}
;;   :nodes is a map of node-id -> IncidentNode
;; IncidentDecisionLog: {:node-id :choice-id :taken-at :kpi-after :grade}
;; IncidentState: {:current :kpi :history :done :outcome}
