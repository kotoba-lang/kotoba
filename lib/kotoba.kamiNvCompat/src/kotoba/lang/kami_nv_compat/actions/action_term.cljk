(ns kotoba.lang.kami-nv-compat.actions.action-term
  "ActionTerm base + ActionManager — JVM port of src/actions/action-term.ts.
  Mirrors isaaclab.envs.mdp.actions.ActionTerm (Isaac Lab 1.x). One ActionTerm
  processes one slice of the policy's flat action vector (process-actions! →
  scale + offset), then writes the result onto the env (apply-actions!).
  ActionManager composes multiple terms into a single combined action vector.
  Wave 16c of ADR-2607020130.")

(defprotocol IActionTerm
  (action-dim       [this])
  (process-actions! [this raw])
  (apply-actions!   [this env])
  (reset-term!      [this]))

(defn make-action-term-state
  "Build the base state map for an ActionTerm: cfg, action-dim, raw/processed
  action atoms. Subclasses call this then reify IActionTerm."
  [cfg]
  (when (or (nil? (:joint-names cfg)) (empty? (:joint-names cfg)))
    (throw (ex-info "ActionTerm: cfg.joint-names must be non-empty" {:cfg cfg})))
  (let [dim (or (:action-dim cfg) (count (:joint-names cfg)))]
    {:cfg cfg
     :action-dim dim
     :raw-actions (atom (vec (repeat dim 0)))
     :processed-actions (atom (vec (repeat dim 0)))}))

(defn base-process-actions!
  "Default process: scale + offset element-wise into processed-actions."
  [term raw]
  (let [dim (:action-dim term)
        s (get-in term [:cfg :scale] 1.0)
        o (get-in term [:cfg :offset] 0.0)]
    (when (not= (count raw) dim)
      (throw (ex-info (str "ActionTerm: expected " dim " action elements, got " (count raw))
                      {:expected dim :got (count raw)})))
    (reset! (:raw-actions term) (vec raw))
    (reset! (:processed-actions term) (vec (map #(+ (* % s) o) raw)))))

(defn base-reset! [term]
  (let [dim (:action-dim term)]
    (reset! (:raw-actions term) (vec (repeat dim 0)))
    (reset! (:processed-actions term) (vec (repeat dim 0)))))

;; ── ActionManager ─────────────────────────────────────────────────────────

(defn action-manager
  "Build an ActionManager from a vector of IActionTerm instances."
  [terms]
  (when (or (nil? terms) (empty? terms))
    (throw (ex-info "ActionManager requires at least one ActionTerm" {})))
  (let [offsets (loop [ts (seq terms) off 0 acc []]
                  (if (empty? ts)
                    acc
                    (let [t (first ts)]
                      (recur (rest ts) (+ off (action-dim t)) (conj acc off)))))]
    {:terms terms
     :offsets offsets
     :total-action-dim (reduce + (map action-dim terms))}))

(defn manager-process-actions! [mgr raw]
  (let [expected (:total-action-dim mgr)]
    (when (not= (count raw) expected)
      (throw (ex-info (str "ActionManager: expected " expected " action elements, got " (count raw))
                      {:expected expected :got (count raw)})))
    (doseq [[i term] (map-indexed vector (:terms mgr))]
      (let [start (nth (:offsets mgr) i)]
        (process-actions! term (subvec (vec raw) start (+ start (action-dim term))))))))

(defn manager-apply-actions! [mgr env]
  (doseq [term (:terms mgr)] (apply-actions! term env)))

(defn manager-reset! [mgr]
  (doseq [term (:terms mgr)] (reset-term! term)))
