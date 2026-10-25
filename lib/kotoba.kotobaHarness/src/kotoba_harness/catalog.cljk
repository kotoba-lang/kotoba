(ns kotoba-harness.catalog
  "Typed kotoba block catalog. A program declares functions, literals and
  stages; every function body is an AST whose holes are typed. The policy only
  ever returns a candidate id; source text is emitted here from a whitelist of
  kotoba typed-subset operations."
  (:require [clojure.string :as str]))

(defn refuse! [reason & [data]] (throw (ex-info (str "kotoba-harness refused: " (name reason)) (assoc data :reason reason))))

(defn refusal
  "Refusal data of E, unwrapping an interpreter error that wraps the ex-info."
  [e] (loop [e e] (cond (nil? e) nil (:reason (ex-data e)) (ex-data e) :else (recur (ex-cause e)))))

(def types #{:i64 :bool})
(def operations
  "Kotoba typed-subset operations admitted for assembly. :emit is the kotoba head."
  [{:id "add" :emit "+" :in [:i64 :i64] :out :i64 :description "Child 0 plus child 1."}
   {:id "subtract" :emit "-" :in [:i64 :i64] :out :i64 :description "Child 0 minus child 1 (order matters)."}
   {:id "multiply" :emit "*" :in [:i64 :i64] :out :i64 :description "Child 0 times child 1."}
   {:id "minimum" :emit "min" :in [:i64 :i64] :out :i64 :description "The smaller of the two children."}
   {:id "maximum" :emit "max" :in [:i64 :i64] :out :i64 :description "The larger of the two children; (max 0 x) clamps x at zero."}
   {:id "less-than" :emit "<" :in [:i64 :i64] :out :bool :description "True exactly when child 0 is strictly less than child 1."}
   {:id "equal" :emit "=" :in [:i64 :i64] :out :bool :description "True exactly when the two integer children are equal."}
   {:id "if-i64" :emit "if" :in [:bool :i64 :i64] :out :i64 :description "If child 0 then child 1 else child 2."}
   {:id "if-bool" :emit "if" :in [:bool :bool :bool] :out :bool :description "If child 0 then child 1 else child 2."}])
(def operation-ids (set (map :id operations)))

(defn identifier? [s] (and (string? s) (boolean (re-matches #"[a-z][a-z0-9-]{0,63}" s))))

(defn stage-order [program]
  (loop [remaining (:stages program) done []]
    (if (empty? remaining) done
        (if-let [ready (first (filter #(every? (set done) (:depends-on %)) remaining))]
          (recur (remove #(= (:id ready) (:id %)) remaining) (conj done (:id ready)))
          (refuse! :stage-cycle)))))

(defn compile-program
  "Validate a program map. Refuses anything outside the closed shape."
  [p]
  (let [fns (:functions p) stages (:stages p) fn-ids (set (map :id fns)) stage-ids (set (map :id stages))]
    (when-not (and (string? (:goal p)) (<= 1 (count (:goal p)) 4096)
                   (vector? fns) (<= 1 (count fns) 16) (= (count fns) (count fn-ids))
                   (vector? stages) (<= 1 (count stages) 16) (= (count stages) (count stage-ids))
                   (vector? (:literals p)) (<= (count (:literals p)) 32)
                   (pos-int? (:max-decisions p)) (<= (:max-decisions p) 256)
                   (pos-int? (:max-depth p)) (<= (:max-depth p) 16)
                   (integer? (:candidate-limit p)) (<= 4 (:candidate-limit p) 16))
      (refuse! :program-shape))
    (doseq [f fns]
      (when-not (and (identifier? (:id f)) (contains? stage-ids (:stage f))
                     (or (nil? (:goal f)) (and (string? (:goal f)) (<= 1 (count (:goal f)) 1024))) (contains? types (:returns f))
                     (vector? (:args f)) (<= (count (:args f)) 8)
                     (= (count (:args f)) (count (set (map :name (:args f)))))
                     (every? #(and (identifier? (:name %)) (contains? types (:type %))) (:args f)))
        (refuse! :function-contract {:function (:id f)})))
    (doseq [l (:literals p)]
      (when-not (and (identifier? (:id l)) (case (:type l) :i64 (integer? (:value l)) :bool (boolean? (:value l)) false))
        (refuse! :literal-contract {:literal (:id l)})))
    (doseq [s stages]
      (when-not (and (identifier? (:id s)) (string? (:goal s))
                     (every? operation-ids (:operations s)) (every? fn-ids (:calls s)) (every? stage-ids (:depends-on s)))
        (refuse! :stage-contract {:stage (:id s)})))
    (let [order (stage-order p) rank (zipmap order (range))]
      ;; A stage may only call functions of itself or of earlier stages.
      (doseq [s stages c (:calls s)]
        (when (> (rank (:stage (first (filter #(= c (:id %)) fns)))) (rank (:id s)))
          (refuse! :stage-call-dependency {:stage (:id s) :call c})))
      (assoc p :stage-order order))))

(defn function [program id] (first (filter #(= id (:id %)) (:functions program))))
(defn stage [program id] (first (filter #(= id (:id %)) (:stages program))))
(defn ordered-functions [program]
  (mapcat (fn [s] (filter #(= s (:stage %)) (:functions program))) (:stage-order program)))

(defn hole [type depth] {:hole type :depth depth})
(defn first-hole
  "Depth-first, left-to-right first open hole over the functions in stage order."
  [program state]
  (letfn [(walk [node path]
            (cond (:hole node) {:node node :path path}
                  :else (some identity (map-indexed (fn [i c] (walk c (conj path :children i))) (:children node)))))]
    (some (fn [f] (some-> (get-in state [:bodies (:id f)]) (walk [:bodies (:id f)])
                          (assoc :function (:id f))))
          (ordered-functions program))))

(defn candidates
  "Every legal fill for TARGET: parameters and literals of the right type, then
  stage-admitted operations and calls (only below :max-depth)."
  [program {node :node fid :function}]
  (let [f (function program fid) t (:hole node) s (stage program (:stage f))
        deep? (< (:depth node) (:max-depth program))]
    (vec (concat
          (for [a (:args f) :when (= t (:type a))]
            {:id (str "argument-" (:name a)) :kind :argument :name (:name a) :type t})
          (for [l (:literals program) :when (= t (:type l))]
            {:id (str "literal-" (:id l)) :kind :literal :value (:value l) :type t})
          (when deep?
            (for [op operations :when (and (= t (:out op)) (some #{(:id op)} (:operations s)))]
              (assoc op :kind :operation)))
          (when deep?
            (for [c (:calls s) :let [g (function program c)] :when (= t (:returns g))]
              {:id (str "call-" c) :kind :call :function c :emit c :in (mapv :type (:args g)) :out t
               :description (str "Call " c " with arguments (" (str/join ", " (map :name (:args g))) ") in that order.")}))))))

(defn apply-choice [program state target candidate]
  (when-not (and (= target (first-hole program state)) (some #(= (:id candidate) (:id %)) (candidates program target)))
    (refuse! :illegal-connection {:candidate (:id candidate)}))
  (let [depth (:depth (:node target))]
    (assoc-in state (:path target)
              (cond-> (select-keys candidate [:id :kind :name :value :emit])
                (:in candidate) (assoc :children (mapv #(hole % (inc depth)) (:in candidate)))))))

(defn render
  "Kotoba source for NODE. Open holes render as HOLE-TEXT and a :focus marker
  as ? (used to show the policy the partial assembly); emission refuses holes."
  ([node] (render node nil))
  ([node hole-text]
   (cond (:hole node) (or hole-text (refuse! :unresolved-hole))
         :else (case (:kind node)
                 :argument (:name node)
                 :literal (pr-str (:value node))
                 :focus "?"
                 (:operation :call) (str "(" (:emit node) " " (str/join " " (map #(render % hole-text) (:children node))) ")")
                 :pending (or hole-text (refuse! :unresolved-hole))))))

(defn signature [f]
  (str "(defn " (:id f) " [" (str/join " " (map #(str (:name %) " " (:type %)) (:args f))) "] " (:returns f) " "))

(defn splice
  "Replace only the stub line of each function in BODIES; all other bytes of
  BASELINE stay identical."
  [program baseline bodies]
  (let [lines (str/split baseline #"\n" -1)
        sigs (into {} (map (fn [id] [(signature (function program id)) id]) (keys bodies)))
        hits (atom 0)
        out (mapv (fn [line]
                    (if-let [[sig id] (first (filter #(str/starts-with? line (key %)) sigs))]
                      (do (swap! hits inc) (str sig (get bodies id) ")"))
                      line)) lines)]
    (when-not (= @hits (count bodies)) (refuse! :baseline-shape))
    (str/join "\n" out)))
