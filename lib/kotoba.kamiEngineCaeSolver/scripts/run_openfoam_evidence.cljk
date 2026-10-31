(ns run-openfoam-evidence
  "Run a digest-pinned OpenFOAM tutorial and emit hash-complete EDN evidence."
  (:require [cae.external-evidence :as evidence]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec-command! [args]
  (let [process (-> (ProcessBuilder. ^java.util.List (mapv str args))
                    (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream process))
        exit (.waitFor process)]
    (when-not (zero? exit)
      (throw (ex-info "external command failed" {:args args :exit exit :output output})))
    output))

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
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :openfoam-v2506-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             ".cache/external-solvers/openfoam-cavity")))
        _ (delete-tree! root) _ (.mkdirs root)
        mount (str (.getPath root) ":/work")
        base ["docker" "run" "--rm" "--entrypoint" "/bin/bash" "-v" mount image "-lc"]
        _ (exec-command! (conj base "source /opt/OpenFOAM-v2506/etc/bashrc; cp -a \"$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity/.\" /work/"))
        input-paths ["0/U" "0/p" "constant/transportProperties" "system/blockMeshDict"
                     "system/controlDict" "system/fvSchemes" "system/fvSolution"]
        inputs (mapv #(file-evidence root %) input-paths)
        command "source /opt/OpenFOAM-v2506/etc/bashrc; cd /work; blockMesh > log.blockMesh 2>&1 && icoFoam > log.icoFoam 2>&1"
        _ (exec-command! (conj base command))
        result-paths ["log.blockMesh" "log.icoFoam" "0.5/U" "0.5/p"]
        results (mapv #(file-evidence root %) result-paths)
        log-text (slurp (io/file root "log.icoFoam"))
        actual-digests (exec-command! ["docker" "image" "inspect" image "--format" "{{join .RepoDigests \"\\n\"}}"])
        _ (when-not (.contains actual-digests digest)
            (throw (ex-info "container digest mismatch" {:expected digest :actual actual-digests})))
        run-evidence (evidence/process-evidence
                      {:case-id "openfoam-v2506-icofoam-cavity" :solver :openfoam
                       :solver-version (:version manifest) :image-digest digest
                       :command (:commands manifest) :exit-code 0 :input-files inputs
                       :result-files results :log-text log-text :platform "linux/arm64-container"
                       :executed-at (str (Instant/now))})
        output (io/file root "evidence.edn")]
    (when-not (:passed? run-evidence)
      (throw (ex-info "OpenFOAM evidence rejected" run-evidence)))
    (spit output (pr-str run-evidence))
    (prn (-> (select-keys run-evidence [:case-id :solver :solver-version :image-digest :status :log])
             (update :log dissoc :residuals)))))
