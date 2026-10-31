(ns run-mpi-evidence
  "Execute two identical real OpenMPI runs and emit fail-closed rank evidence."
  (:require [cae.external-evidence :as evidence]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec-command [args]
  (let [process (-> (ProcessBuilder. ^java.util.List (mapv str args))
                    (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream process)) exit (.waitFor process)]
    {:exit exit :output output}))

(defn- hex [bytes] (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))

(defn- file-evidence [root path]
  (let [file (io/file root path) digest (MessageDigest/getInstance "SHA-256")]
    (when-not (.isFile file) (throw (ex-info "expected MPI evidence file is missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop []
          (let [n (.read in buffer)]
            (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))

(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string
                     :openmpi-4.1.6-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             ".cache/external-solvers/openmpi-pi")))
        _ (delete-tree! root) _ (.mkdirs root)
        copied-source (io/file root "rank_worker.c")
        _ (with-open [in (io/input-stream (io/file "containers/mpi/rank_worker.c"))
                      out (io/output-stream copied-source)] (io/copy in out))
        inspect (exec-command ["docker" "image" "inspect" image "--format"
                               "{{join .RepoDigests \"\\n\"}}"])
        _ (when-not (and (zero? (:exit inspect)) (.contains (:output inspect) digest))
            (throw (ex-info "OpenMPI container digest mismatch"
                            {:expected digest :actual (:output inspect)})))
        docker-command (vec (concat ["docker" "run" "--rm" image]
                                    (drop 3 (:commands manifest))))
        runs (mapv (fn [index]
                     (let [run (exec-command docker-command)
                           path (str "run-" index ".log")]
                       (spit (io/file root path) (:output run))
                       (assoc run :path path)))
                   [1 2])
        envelope (evidence/mpi-process-evidence
                  {:case-id "openmpi-4.1.6-four-rank-pi"
                   :solver-version (:version manifest) :image-digest digest
                   :command (:commands manifest) :exit-codes (mapv :exit runs)
                   :worker-source (file-evidence root "rank_worker.c")
                   :output-files (mapv #(file-evidence root (:path %)) runs)
                   :run-texts (mapv :output runs) :error-tolerance 1.0e-12
                   :platform "linux/arm64-container" :executed-at (str (Instant/now))})]
    (when-not (:passed? envelope) (throw (ex-info "MPI evidence rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
