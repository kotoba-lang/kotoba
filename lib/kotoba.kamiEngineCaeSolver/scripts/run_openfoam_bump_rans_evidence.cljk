(ns run-openfoam-bump-rans-evidence
  "Execute the digest-pinned OpenFOAM NASA TMR 2D bump k-omega SST case."
  (:require [cae.openfoam-bump :as bump]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec [args]
  (let [p (-> (ProcessBuilder. ^java.util.List (mapv str args)) (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream p)) exit (.waitFor p)]
    (when-not (zero? exit) (throw (ex-info "OpenFOAM bump command failed" {:args args :exit exit :output output})))
    output))
(defn- hex [bytes] (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))
(defn- file-evidence [root path]
  (let [file (io/file root path) digest (MessageDigest/getInstance "SHA-256")]
    (when-not (.isFile file) (throw (ex-info "OpenFOAM bump evidence file missing" {:path path})))
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
                                             ".cache/external-solvers/openfoam-bump-rans")))
        _ (delete-tree! root) _ (.mkdirs root)
        mount (str (.getPath root) ":/work")
        base ["docker" "run" "--rm" "--entrypoint" "/bin/bash" "-v" mount image "-lc"]
        copy-command (str "source /opt/OpenFOAM-v2506/etc/bashrc; "
                          "src=\"$FOAM_TUTORIALS/incompressible/simpleFoam/bump2D/setups.orig\"; "
                          "cp -a \"$src/common/.\" /work/; cp -a \"$src/kOmegaSST/.\" /work/; "
                          "mkdir -p /work/0; cp -a /work/0.orig/. /work/0/")
        _ (exec (conj base copy-command))
        dict-file (io/file root "system/blockMeshDict")
        _ (spit dict-file (bump/static-block-mesh-dict (slurp dict-file)))
        command (str "source /opt/OpenFOAM-v2506/etc/bashrc; cd /work; set -e; "
                     "blockMesh > log.blockMesh 2>&1; "
                     "renumberMesh -overwrite -constant > log.renumberMesh 2>&1; "
                     "checkMesh -allTopology -allGeometry -constant > log.checkMesh 2>&1; "
                     "simpleFoam > log.simpleFoam 2>&1; "
                     "latest=$(foamListTimes -latestTime); echo $latest > latest-time.txt")
        _ (exec (conj base command))
        latest (str/trim (slurp (io/file root "latest-time.txt")))
        log-text (slurp (io/file root "log.simpleFoam"))
        ended? (boolean (re-find #"(?m)^End\s*$" log-text))
        converged-iterations (some-> (re-find #"SIMPLE solution converged in (\d+) iterations" log-text)
                                     second Long/parseLong)
        iterations (count (re-seq #"(?m)^Time = \d+" log-text))
        initial-residuals (mapv #(Double/parseDouble (second %))
                                (re-seq #"Initial residual = ([0-9.Ee+-]+)" log-text))
        check-text (slurp (io/file root "log.checkMesh"))
        topology-ok? (and (boolean (re-find #"Boundary definition OK\." check-text))
                          (boolean (re-find #"Number of regions: 1 \(OK\)" check-text))
                          (not (re-find #"negative volume|zero or negative" check-text)))
        maximum-nonorthogonality (some-> (re-find #"Mesh non-orthogonality Max: ([0-9.Ee+-]+)" check-text)
                                         second Double/parseDouble)
        maximum-skewness (some-> (re-find #"Max skewness = ([0-9.Ee+-]+)" check-text)
                                 second Double/parseDouble)
        geometry-warning-count (some-> (re-find #"Failed (\d+) mesh checks\." check-text)
                                       second Long/parseLong)
        yplus (some->> (re-find #"patch bump y\+ : min = ([0-9.Ee+-]+), max = ([0-9.Ee+-]+), average = ([0-9.Ee+-]+)" log-text)
                       rest (mapv #(Double/parseDouble %)))
        shear (some->> (re-find #"min/max\(bump\) = \(([-0-9.Ee+ ]+)\), \(([-0-9.Ee+ ]+)\)" log-text)
                       rest (mapv (fn [row] (mapv #(Double/parseDouble %) (str/split (str/trim row) #"\s+")))))
        input-paths ["0/U" "0/p" "0/k" "0/omega" "0/nut"
                     "constant/transportProperties" "constant/turbulenceProperties"
                     "system/blockMeshDict" "system/controlDict" "system/fvSchemes" "system/fvSolution"]
        result-paths ["log.blockMesh" "log.renumberMesh" "log.checkMesh" "log.simpleFoam"
                      "latest-time.txt" (str latest "/wallShearStress") (str latest "/Cp")]
        passed? (and ended? topology-ok? (< maximum-nonorthogonality 20.0) (< maximum-skewness 0.1)
                     (= converged-iterations iterations) (< iterations 10000)
                     (seq initial-residuals) (= 3 (count yplus)) (= 2 (count shear)))
        envelope {:case-id "openfoam-v2506-nasa-tmr-2d-bump-komega-sst"
                  :solver :openfoam :solver-version (:version manifest) :image-digest digest
                  :command ["blockMesh" "renumberMesh" "checkMesh" "simpleFoam"]
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :input-files (mapv #(file-evidence root %) input-paths)
                  :result-files (mapv #(file-evidence root %) result-paths)
                  :result {:latest-time latest :iterations iterations :converged-iterations converged-iterations
                           :ended? ended? :bump-yplus {:minimum (nth yplus 0) :maximum (nth yplus 1)
                                                      :average (nth yplus 2)}
                           :bump-wall-shear-min (first shear) :bump-wall-shear-max (second shear)
                           :mesh-topology-ok? topology-ok? :geometry-warning-count geometry-warning-count
                           :maximum-nonorthogonality-deg maximum-nonorthogonality
                           :maximum-skewness maximum-skewness :residual-records (count initial-residuals)
                           :maximum-initial-residual (when (seq initial-residuals) (apply max initial-residuals))
                           :minimum-initial-residual (when (seq initial-residuals) (apply min initial-residuals))}
                  :checks {:mesh-topology-ok? topology-ok?
                           :nonorthogonality-below-20-deg? (< maximum-nonorthogonality 20.0)
                           :skewness-below-0.1? (< maximum-skewness 0.1)
                           :geometry-warnings-retained? (pos? geometry-warning-count)
                           :solver-ended? ended?
                           :simple-converged? (= converged-iterations iterations)
                           :converged-before-limit? (< iterations 10000)
                           :residuals-present? (boolean (seq initial-residuals))}
                  :passed? (boolean passed?)
                  :status (if passed? :external-rans-execution-verified :external-rans-execution-rejected)}]
    (when-not passed? (throw (ex-info "OpenFOAM bump RANS evidence rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
