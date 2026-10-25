(ns states.validate
  "Structural validation of an ASL state machine in EDN form. Pure: returns a
  vector of problem maps
  `{:states/severity :error|:warn :states/code … :states/id … :states/msg …}`
  so a caller decides how to surface them. `valid?` is true iff there are no
  :error-level problems (warnings are advisory)."
  (:require [kotoba.dsl.problem :as problem]
            [states.model :as m]))

(defn- states-problem [severity code id msg]
  (problem/problem :states severity code id msg))

;; ---------------------------------------------------------------------------
;; reachability helpers
;; ---------------------------------------------------------------------------

(defn- choice-nexts
  "Collect all :states/next targets from a choice-rule (including nested and/or/not)."
  [rule]
  (concat
   (when (:states/next rule) [(:states/next rule)])
   (when (:states/and  rule) (mapcat choice-nexts (:states/and rule)))
   (when (:states/or   rule) (mapcat choice-nexts (:states/or  rule)))
   (when (:states/not  rule) (choice-nexts (:states/not rule)))))

(defn- state-nexts
  "Return all reachable successor state names from `state-map`."
  [state-map]
  (let [t (:states/type state-map)]
    (cond-> []
      (:states/next    state-map) (conj (:states/next state-map))
      (:states/default state-map) (conj (:states/default state-map))
      (:states/choices state-map) (into (mapcat choice-nexts (:states/choices state-map)))
      (:states/branches state-map) (into []) ;; sub-machines — not tracked at top level
      true                          identity)))

(defn- reachable-from
  "BFS set of state name strings reachable from `start` in `states-map`."
  [states-map start]
  (loop [frontier [start] visited #{}]
    (if-let [cur (first frontier)]
      (if (contains? visited cur)
        (recur (rest frontier) visited)
        (let [nexts (state-nexts (get states-map cur {}))]
          (recur (into (rest frontier) nexts)
                 (conj visited cur))))
      visited)))

;; ---------------------------------------------------------------------------
;; problems
;; ---------------------------------------------------------------------------

(defn problems
  "Return a vector of structural problems with `machine`."
  [machine]
  (let [states   (:states/states machine {})
        ids      (set (keys states))
        start    (:states/start-at machine)
        ps       (transient [])]

    ;; --- StartAt validations ---
    (if (nil? start)
      (conj! ps (states-problem :error :states/missing-start-at nil
                         "machine has no :states/start-at"))
      (when-not (contains? ids start)
        (conj! ps (states-problem :error :states/start-at-not-found start
                           (str "StartAt \"" start "\" is not a defined state")))))

    ;; --- per-state validations ---
    (doseq [[sid smap] states]
      (let [t (:states/type smap)]
        ;; Next/Default must point to existing states
        (when-let [nxt (:states/next smap)]
          (when-not (contains? ids nxt)
            (conj! ps (states-problem :error :states/invalid-next sid
                               (str "state \"" sid "\" Next \"" nxt "\" is not defined")))))
        (when-let [dflt (:states/default smap)]
          (when-not (contains? ids dflt)
            (conj! ps (states-problem :error :states/invalid-default sid
                               (str "state \"" sid "\" Default \"" dflt "\" is not defined")))))
        ;; Choice rule Nexts
        (doseq [rule (:states/choices smap [])]
          (doseq [nxt (choice-nexts rule)]
            (when-not (contains? ids nxt)
              (conj! ps (states-problem :error :states/invalid-choice-next sid
                                 (str "state \"" sid "\" choice Next \"" nxt "\" is not defined"))))))
        ;; warn: choice without Default
        (when (= t :choice)
          (when-not (:states/default smap)
            (conj! ps (states-problem :warn :states/choice-no-default sid
                               (str "choice state \"" sid "\" has no Default")))))))

    ;; --- at least one terminal reachable from StartAt ---
    (when start
      (let [reachable (reachable-from states start)
            terminal? (fn [sid] (m/terminal? (get states sid {})))
            has-terminal (some terminal? reachable)]
        (when-not has-terminal
          (conj! ps (states-problem :error :states/no-terminal start
                             "no terminal state (Succeed/Fail/End:true) is reachable from StartAt")))))

    ;; --- warn: unreachable states ---
    (when start
      (let [reachable (reachable-from states start)]
        (doseq [sid ids]
          (when-not (contains? reachable sid)
            (conj! ps (states-problem :warn :states/unreachable sid
                               (str "state \"" sid "\" is unreachable from StartAt")))))))

    (persistent! ps)))

(defn errors [machine]
  (problem/errors :states (problems machine)))

(defn valid?
  "True iff `machine` has no :error-level structural problems."
  [machine]
  (problem/valid? :states (problems machine)))
