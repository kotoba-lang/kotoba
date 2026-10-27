(ns kotoba-harness.search
  "Staged System One search. Stages run in dependency order and functions in
  stage order; each function is verified on its own and frozen once it passes.
  Inside a function the policy fills one typed hole per decision.

  Backtracking:
  - verification failure rewinds to the most recent decision that still has an
    untried alternative (chronological), and the rejected assembly with its
    failure count is shown to the policy;
  - when the policy answers `stop` at a hole (no acceptable fill here), the
    search escalates OUTWARD: it rewinds to the next earlier decision with an
    untried alternative, up to the outermost operation of the function. A
    wrong outermost choice is therefore reachable, which purely chronological
    retry could not reach once the policy stopped at a leaf."
  (:require [clojure.string :as str] [kotoba-harness.catalog :as c]))

(def instructions
  (str "Fill only the hole marked ? in the active function's assembly (_ marks holes filled later). "
       "Ancestors already perform part of the goal: choose the subexpression needed at this position, not the whole goal again. "
       "A parameter or literal may fully satisfy the hole. Never repeat a rejected assembly. "
       "No source text is accepted. next-page shows more legal candidates; stop means no candidate here can be right, "
       "which revises an earlier choice."))

(defn describe [cand]
  (case (:kind cand)
    :argument (str "parameter " (:name cand) " " (:type cand))
    :literal (str "literal " (pr-str (:value cand)) " " (:type cand))
    (:operation :call) (str "(" (:emit cand) " " (str/join " " (map str (:in cand))) ") -> " (:out cand) ". " (:description cand))
    :page "show more legal candidates"
    :stop "no candidate here can be right; revise an earlier choice"))

(defn admit
  "The answer must be a distribution over exactly the offered labels whose
  winner is the choice. Jev reports probabilities rounded to two decimals, so
  the sum may miss 1 by up to 0.005 per label."
  [choices {:keys [choice probabilities confidence] :as answer}]
  (let [labels (set (map :id choices))]
    (when-not (and (contains? labels choice) (= labels (set (keys probabilities)))
                   (every? #(and (number? %) (<= 0 % 1)) (vals probabilities))
                   (number? confidence) (<= 0 confidence 1)
                   (<= (js/Math.abs (- 1 (reduce + (vals probabilities)))) (+ 1e-9 (* 0.005 (count labels))))
                   (every? #(<= % (get probabilities choice)) (vals probabilities)))
      (c/refuse! :invalid-distribution {:answer (dissoc answer :usage)}))
    (first (filter #(= choice (:id %)) choices))))

(defn hole-role
  "What the focused hole means to its parent: which parameter of a call, or
  which child of an operation."
  [program state {:keys [path function]}]
  (if (= 2 (count path))
    (str "the whole body of " function ", returning " (:returns (c/function program function)))
    (let [parent (get-in state (subvec path 0 (- (count path) 2))) i (last path)]
      (case (:kind parent)
        :call (let [a (nth (:args (c/function program (:emit parent))) i)]
                (str "argument " (inc i) " of " (count (:children parent)) " in the call to " (:emit parent)
                     ": the parameter " (:name a) " " (:type a)))
        (str "child " i " of " (:id parent) " (" (:description (first (filter #(= (:id parent) (:id %)) c/operations))) ")")))))

(defn request [program state target page rejected fixed-sources]
  (let [f (c/function program (:function target)) s (c/stage program (:stage f))
        focused (assoc-in state (:path target) {:kind :focus})]
    {:goal (:goal program)
     :stage {:id (:id s) :goal (:goal s)}
     :function (str (c/signature f) "...)")
     :function-goal (:goal f)
     :assembly (c/render (get-in focused [:bodies (:id f)]) "_")
     :hole-type (:hole (:node target))
     :hole-role (hole-role program state target)
     :verified-functions fixed-sources
     :rejected-assemblies rejected
     :page page}))

(defn run-unit!
  "Assemble and verify one function (UNIT); earlier functions are frozen. decide! gets {:state string :instructions
  string :criteria {id description}} and returns a promise of an answer.
  verify! gets {id kotoba-body} for every assembled function and returns a
  promise of {:passed bool :failures string}."
  [program unit fixed decide! verify! {:keys [max-attempts audit attempts escalate?]}]
  (let [stage-id (:stage (c/function program unit))
        state0 {:bodies (into {} (map (fn [f] [(:id f) (cond (contains? fixed (:id f)) (get fixed (:id f))
                                                              (= unit (:id f)) (c/hole (:returns f) 0)
                                                              :else {:kind :pending})])
                                       (:functions program)))}
        fixed-sources (into {} (map (fn [[id ast]] [id (c/render ast)]) fixed))
        frames (atom []) rejected (atom []) n-attempts (atom 0)
        decisions #(count @audit)]
    (letfn [(rewind! [cause]
              (if-let [i (last (keep-indexed (fn [i f] (when (seq (:remaining f)) i)) @frames))]
                (let [frame (nth @frames i)]
                    (reset! frames (subvec @frames 0 i))
                    (swap! audit conj {:stage stage-id :function unit :event cause :rewound-to (:choice frame)})
                    (step (:state frame) (:excluded frame) 0))
                (c/refuse! :search-exhausted {:stage stage-id :function unit})))
            (ask [req choices retry]
              (when (>= (decisions) (:max-decisions program)) (c/refuse! :decision-budget))
              (let [started (.now js/performance)]
                (-> (decide! req)
                    (.then (fn [answer]
                             (swap! audit conj {:stage stage-id :function unit :choice (:choice answer) :confidence (:confidence answer)
                                                :probabilities (:probabilities answer) :offered (mapv :id choices)
                                                :model (:model answer) :usage (:usage answer)
                                                :wall-ms (- (.now js/performance) started)})
                             (try (admit choices answer)
                                  (catch :default e
                                    (if (zero? retry) (ask req choices 1) (throw e)))))))))
            (step [state excluded page]
              (if-let [target (c/first-hole program state)]
                (let [legal (vec (remove #(contains? excluded (:id %)) (c/candidates program target)))
                      size (dec (:candidate-limit program))
                      shown (vec (take size (drop (* page size) legal)))
                      more? (< (+ (* page size) (count shown)) (count legal))
                      choices (conj shown (if more? {:id "next-page" :kind :page} {:id "stop" :kind :stop}))
                      req {:state (pr-str (request program state target page @rejected fixed-sources))
                           :instructions instructions
                           :criteria (into {} (map (juxt :id describe) choices))}]
                  (if (empty? shown)
                    (rewind! :empty-hole)
                    (-> (ask req choices 0)
                        (.then (fn [chosen]
                                 (case (:kind chosen)
                                   :page (step state excluded (inc page))
                                   :stop (if escalate? (rewind! :stop-escalation) (c/refuse! :policy-stopped {:stage stage-id :function unit}))
                                   (do (swap! frames conj {:state state :choice (:id chosen)
                                                           :excluded (conj excluded (:id chosen))
                                                           :remaining (vec (remove #(= (:id chosen) (:id %)) legal))})
                                       (step (c/apply-choice program state target chosen) #{} 0))))))))
                (complete state)))
            (complete [state]
              (let [bodies (into {} (keep (fn [[id ast]] (when-not (= :pending (:kind ast)) [id (c/render ast)])) (:bodies state)))
                    n (swap! n-attempts inc)]
                (-> (verify! bodies)
                    (.then (fn [v]
                             (swap! attempts conj {:stage stage-id :function unit :attempt n :bodies bodies :verification v})
                             (cond (:passed v) {:state state :bodies bodies :verification v}
                                   (>= n max-attempts) (c/refuse! :stage-rejected {:stage stage-id :function unit})
                                   :else (do (swap! rejected conj {:assembly (into {} (filter #(not (contains? fixed (key %))) bodies))
                                                                   :failed-cases (:failures v)})
                                             (rewind! :verification-failed))))))))]
      (step state0 #{} 0))))

(defn run!
  "Every function, stage by stage in dependency order; each function is
  verified and frozen as soon as its body is complete, so a failure is never
  attributed to a sibling. Returns a promise of {:bodies :verification}."
  [program decide! verify! {:keys [max-attempts escalate?] :or {max-attempts 6 escalate? true}} audit attempts]
  (letfn [(go [ids fixed last-v]
            (if (empty? ids)
              (js/Promise.resolve {:bodies (into {} (map (fn [[id ast]] [id (c/render ast)]) fixed)) :verification last-v})
              (-> (run-unit! program (first ids) fixed decide! verify! {:max-attempts max-attempts :escalate? escalate? :audit audit :attempts attempts})
                  (.then (fn [{:keys [state verification]}]
                           (go (rest ids)
                               (into {} (remove #(= :pending (:kind (val %))) (:bodies state)))
                               verification))))))]
    (go (map :id (c/ordered-functions program)) {} nil)))
