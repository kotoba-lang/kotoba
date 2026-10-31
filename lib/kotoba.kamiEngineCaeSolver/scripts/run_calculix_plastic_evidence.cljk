(ns run-calculix-plastic-evidence
  "Run a real elastoplastic load/unload cycle and emit residual-state evidence."
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
    (when-not (.isFile file) (throw (ex-info "expected plastic evidence file is missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)] (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))

(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :calculix-2.21-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             ".cache/external-solvers/calculix-plastic")))
        _ (delete-tree! root) _ (.mkdirs root)
        _ (with-open [in (io/input-stream (io/resource "cae/cases/calculix/plastic_cycle.inp"))
                      out (io/output-stream (io/file root "plastic_cycle.inp"))] (io/copy in out))
        inspect (exec-command ["docker" "image" "inspect" image "--format" "{{join .RepoDigests \"\\n\"}}"])
        _ (when-not (and (zero? (:exit inspect)) (.contains (:output inspect) digest))
            (throw (ex-info "CalculiX container digest mismatch" {:expected digest :actual (:output inspect)})))
        run (exec-command ["docker" "run" "--rm" "-v" (str (.getPath root) ":/work")
                           image "-i" "plastic_cycle"])
        _ (spit (io/file root "log.ccx") (:output run))
        result-paths ["log.ccx" "plastic_cycle.dat" "plastic_cycle.frd"
                      "plastic_cycle.sta" "plastic_cycle.cvg"]
        result (evidence/calculix-plastic-result
                {:log-text (:output run) :dat-text (slurp (io/file root "plastic_cycle.dat"))
                 :sta-text (slurp (io/file root "plastic_cycle.sta"))})
        evaluated (evidence/calculix-plastic-checks result)
        checks (assoc (:checks evaluated) :exit-zero? (zero? (:exit run)))
        passed? (and (zero? (:exit run)) (:passed? evaluated))
        envelope {:case-id "calculix-2.21-elastoplastic-load-unload" :solver :calculix
                  :solver-version (:version manifest) :image-digest digest
                  :command ["ccx" "-i" "plastic_cycle"] :exit-code (:exit run)
                  :input-files [(file-evidence root "plastic_cycle.inp")]
                  :result-files (mapv #(file-evidence root %) result-paths)
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :result result :checks checks :passed? passed?
                  :status (if passed? :external-plastic-cycle-verified
                              :external-plastic-cycle-rejected)}]
    (when-not passed? (throw (ex-info "CalculiX plastic-cycle evidence rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
