(ns cae.protocol
  "Clean-room, serializable protocols for MPI jobs, mesh exchange and coupling."
  (:require [kotoba.lang.text :as str]))

(defn mpi-message [{:keys [source target tag payload]}]
  {:source (long source) :target (long target) :tag (keyword tag) :payload payload :protocol :mpi-like-v1})

(defn collective [{:keys [operation ranks values]}]
  {:operation (keyword operation) :ranks (vec (map long ranks)) :values (vec values) :protocol :collective-v1})

(defn halo-message [{:keys [rank neighbor field indices values]}]
  {:rank (long rank) :neighbor (long neighbor) :field (keyword field) :indices (vec indices) :values (vec values) :protocol :halo-v1})

(defn job-spec [{:keys [executable arguments environment ranks threads cwd]}]
  {:executable (str executable) :arguments (vec (map str arguments)) :environment (or environment {}) :ranks (long (or ranks 1)) :threads (long (or threads 1)) :cwd cwd :protocol :host-job-v1})

(defn validate-job [job]
  (doseq [k [:executable :arguments :ranks :threads]]
    (when-not (contains? job k) (throw (ex-info "job spec missing field" {:field k}))))
  (when-not (pos? (:ranks job)) (throw (ex-info "job ranks must be positive" {:ranks (:ranks job)})))
  (when-not (pos? (:threads job)) (throw (ex-info "job threads must be positive" {:threads (:threads job)})))
  (assoc job :validated? true :protocol :host-job-v1))

(defn launch-vector
  "Return an argv vector; never invokes a shell or interpolates user strings."
  ([job] (launch-vector job "mpirun"))
  ([job launcher]
   (let [{:keys [executable arguments ranks]} (validate-job job)]
     (if (= 1 ranks)
       (vec (concat [executable] arguments))
       (vec (concat [launcher "-np" (str ranks) executable] arguments))))))

(defn rank-environment [job rank]
  (let [job (validate-job job)]
    (merge (:environment job) {"KOTOBA_MPI_RANK" (str (long rank))
                                "KOTOBA_MPI_SIZE" (str (:ranks job))
                                "KOTOBA_OMP_THREADS" (str (:threads job))})))

(defn coupling-message [{:keys [participant mesh field time values]}]
  {:participant (keyword participant) :mesh mesh :field (keyword field) :time (double time) :values (vec values) :protocol :partitioned-coupling-v1})

(defn openfoam-case-path [root relative]
  (let [root (str/replace (str root) #"/+$" "") relative (str/replace (str relative) #"^/+" "")]
    (str root "/" relative)))
