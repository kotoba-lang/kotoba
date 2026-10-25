(ns ctf.core
  (:require [ctf.model :as m]
            [ctf.ports :as p]))

(defn problems [record]
  (cond-> []
    (and (contains? record :ctf/case-ref) (nil? (:ctf/case-ref record)))
    (conj {:ctf.problem/code :missing-case-ref})
    (seq (remove (set m/routes) (:ctf/routes record)))
    (conj {:ctf.problem/code :unknown-route})
    (and (:ctf/route record) (not (contains? (set m/routes) (:ctf/route record))))
    (conj {:ctf.problem/code :unknown-route})
    (and (:ctf/level record) (not (contains? m/levels (:ctf/level record))))
    (conj {:ctf.problem/code :unknown-level})
    (and (:ctf/level record) (false? (:ctf/non-adjudicating record)))
    (conj {:ctf.problem/code :adjudicating-result})))

(defn- valid! [record]
  (when-let [ps (seq (problems record))]
    (throw (ex-info "invalid CTF record" {:ctf/problems ps})))
  record)

(defn status [results]
  (let [levels (set (map :ctf/level results))]
    (cond
      (contains? levels :deny) :hold
      (some levels [:challenge :monitor :review]) :review
      (seq results) :clear
      :else :not-run)))

(defn screen [port request]
  (valid! request)
  (let [results (mapv #(valid! (p/screen! port request %)) (:ctf/routes request))]
    {:ctf/status (status results)
     :ctf/case-ref (:ctf/case-ref request)
     :ctf/routes (:ctf/routes request)
     :ctf/results results}))
