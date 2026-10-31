(ns run-calculix-evidence
  "Run digest-pinned CalculiX and emit input/result/analytic evidence."
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
    (when-not (.isFile file) (throw (ex-info "expected evidence file is missing" {:path path})))
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
                                             ".cache/external-solvers/calculix-axial")))
        _ (delete-tree! root) _ (.mkdirs root)
        input (io/file root "axial.inp")
        _ (with-open [in (io/input-stream (io/resource "cae/cases/calculix/axial.inp"))
                      out (io/output-stream input)] (io/copy in out))
        inputs [(file-evidence root "axial.inp")]
        actual-digests (:output (exec-command ["docker" "image" "inspect" image "--format" "{{join .RepoDigests \"\\n\"}}"]))
        _ (when-not (.contains actual-digests digest)
            (throw (ex-info "CalculiX container digest mismatch" {:expected digest :actual actual-digests})))
        run (exec-command ["docker" "run" "--rm" "-v" (str (.getPath root) ":/work") image "-i" "axial"])
        _ (spit (io/file root "log.ccx") (:output run))
        result-paths ["log.ccx" "axial.frd" "axial.sta" "axial.cvg"]
        results (mapv #(file-evidence root %) result-paths)
        frd-text (slurp (io/file root "axial.frd"))
        run-evidence (evidence/process-evidence
                      {:case-id "calculix-2.21-axial-unit-cube" :solver :calculix
                       :solver-version (:version manifest) :image-digest digest
                       :command (:commands manifest) :exit-code (:exit run) :input-files inputs
                       :result-files results :log-text (:output run) :result-text frd-text
                       :platform "linux/arm64-container" :executed-at (str (Instant/now))})
        displacement (get-in run-evidence [:result :maximum-absolute-uz])
        expected 0.001 relative-error (/ (Math/abs (- displacement expected)) expected)
        analytic {:quantity :maximum-displacement-m :computed displacement :expected expected
                  :relative-error relative-error :tolerance 1.0e-5 :passed? (<= relative-error 1.0e-5)}
        run-evidence (assoc run-evidence :analytic-check analytic)
        output (io/file root "evidence.edn")]
    (when-not (and (:passed? run-evidence) (:passed? analytic))
      (throw (ex-info "CalculiX evidence rejected" run-evidence)))
    (spit output (pr-str run-evidence))
    (prn (select-keys run-evidence [:case-id :solver :solver-version :image-digest :status :log :result :analytic-check]))))
