(ns tedai.cells.app-resolve.state-machine
  "Phase state machine for the tedai 手代 app_resolve cell.
  1:1 port of cells/app_resolve/state_machine.py (ADR-2606101400). lookup → tier-select → stance.
  Resolves an app against the :representative registry (tedai.methods.desktop), selects the safest
  adapter tier, reports the synthetic-input stance. G2/G6/G8/N7 (browser → karakuri)."
  (:require [tedai.methods.desktop :as desktop]))

(def outcome-unknown-app "unknown-app")           ; G8
(def outcome-route-karakuri "route-to-karakuri")  ; N7

(def state-defaults {"phase" "init" "app" "" "rec" {} "payload" {}})
(defn- cell-state [state] (merge state-defaults (get state "cell_state" {})))

(defn transition-lookup [state]
  (let [cs (cell-state state)
        cs (assoc cs "app" (get state "app" (get cs "app")))
        rec (desktop/resolve-app (get cs "app"))]
    (cond
      (nil? rec)
      {"cell_state" (assoc cs "phase" "refused" "payload" (assoc (get cs "payload") "outcome" outcome-unknown-app)) "next_node" "end"}

      (= (get rec "route") "karakuri")
      {"cell_state" (assoc cs "phase" "routed"
                           "payload" (assoc (get cs "payload") "outcome" outcome-route-karakuri "route" "karakuri")) "next_node" "end"}

      :else
      {"cell_state" (assoc cs "rec" rec "phase" "looked_up") "next_node" "tier_select"})))

(defn transition-tier-select [state]
  (let [cs (cell-state state)]
    {"cell_state" (assoc cs "payload" (assoc (get cs "payload") "tier" (desktop/select-tier (get cs "rec")))
                         "phase" "tier_selected") "next_node" "stance"}))

(defn transition-stance [state]
  (let [cs (cell-state state)
        rec (get cs "rec")
        stance (desktop/t2-stance rec)
        payload (assoc (get cs "payload") "t1Surface" (get rec "t1_surface" "") "t2Stance" stance)
        payload (if (and (= (get payload "tier") desktop/TIER-T2)
                         (contains? #{"permitted" "restricted"} stance))
                  (assoc payload "t2Engine" desktop/T2-ENGINE)
                  payload)]
    {"cell_state" (assoc cs "payload" payload "phase" "resolved") "next_node" "end"}))

(defn solve [_input-state]
  (throw (ex-info "tedai R0 scaffold: activate app_resolve via Council ADR (post-2606101400 ratification)" {:scaffold true})))
