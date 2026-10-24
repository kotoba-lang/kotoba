(ns identify.core
  (:require [identify.model :as m]
            [identify.ports :as p]))

(defn problems [identifier]
  (cond-> []
    (not (contains? m/identifier-types (:identify.identifier/type identifier)))
    (conj {:identify.problem/code :unknown-identifier-type})
    (nil? (:identify.identifier/value identifier))
    (conj {:identify.problem/code :missing-identifier-value})))

(defn candidate-problems [candidate]
  (let [confidence (:identify.candidate/confidence candidate)]
    (cond-> []
      (nil? (:identify.candidate/subject candidate))
      (conj {:identify.problem/code :missing-candidate-subject})
      (or (not (number? confidence)) (< confidence 0) (> confidence 1000))
      (conj {:identify.problem/code :candidate-confidence-out-of-range}))))

(defn- valid-candidate! [candidate]
  (when-let [ps (seq (candidate-problems candidate))]
    (throw (ex-info "invalid identify candidate" {:identify/problems ps})))
  candidate)

(defn identify [port identifier]
  (when-let [ps (seq (problems identifier))]
    (throw (ex-info "invalid identifier" {:identify/problems ps})))
  (->> (p/resolve-candidates port identifier)
       (map valid-candidate!)
       (sort-by :identify.candidate/confidence >)
       vec))

(defn top-candidate [port identifier min-confidence]
  (first (filter #(>= (:identify.candidate/confidence %) min-confidence)
                 (identify port identifier))))

(defn calibrate-confidence [candidate calibration]
  (let [source (or (:identify.candidate/source candidate)
                   (:identify.candidate/asserter candidate))
        rule (get calibration source)
        confidence (:identify.candidate/confidence candidate)
        calibrated (cond
                     (number? rule) (* confidence rule)
                     (fn? rule) (rule confidence candidate)
                     :else confidence)]
    (assoc candidate :identify.candidate/confidence
           (-> calibrated (max 0) (min 1000) long))))

(defn merge-candidates
  ([candidates] (merge-candidates candidates {}))
  ([candidates opts]
   (let [conflict-delta (or (:conflict-delta opts) 50)
         merged (->> candidates
                     (group-by :identify.candidate/subject)
                     (mapv (fn [[subject cs]]
                             (let [ordered (sort-by :identify.candidate/confidence > cs)
                                   best (first ordered)
                                   evidence-refs (->> ordered
                                                      (mapcat (fn [c]
                                                                (concat (some-> c :identify.candidate/evidence-ref vector)
                                                                        (:identify.candidate/evidence-refs c))))
                                                      (remove nil?)
                                                      distinct
                                                      vec)
                                   assertions (mapv #(select-keys %
                                                                  [:identify.candidate/asserter
                                                                   :identify.candidate/source
                                                                   :identify.candidate/confidence
                                                                   :identify.candidate/evidence-ref])
                                                    ordered)]
                               (assoc best
                                      :identify.candidate/subject subject
                                      :identify.candidate/evidence-refs evidence-refs
                                      :identify.candidate/assertions assertions)))))]
     (let [ordered (vec (sort-by :identify.candidate/confidence > merged))
           top (:identify.candidate/confidence (first ordered))
           top-subject (:identify.candidate/subject (first ordered))
           conflict-subjects (->> ordered
                                  (filter #(and top
                                                (not= (:identify.candidate/subject %) top-subject)
                                                (<= (- top (:identify.candidate/confidence %)) conflict-delta)))
                                  (map :identify.candidate/subject)
                                  set)
           conflict-subjects (if (seq conflict-subjects)
                               (conj conflict-subjects top-subject)
                               conflict-subjects)]
       (mapv #(assoc % :identify.candidate/conflict?
                     (contains? conflict-subjects (:identify.candidate/subject %)))
             ordered)))))

(defn identify-merged
  ([port identifier] (identify-merged port identifier {}))
  ([port identifier opts]
   (let [calibration (:calibration opts)
         candidates (identify port identifier)
         candidates (if calibration
                      (mapv #(calibrate-confidence % calibration) candidates)
                      candidates)]
     (merge-candidates candidates opts))))
