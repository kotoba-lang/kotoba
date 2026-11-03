(ns run-openfoam-sbse-rans-evidence
  "Run the first real 3D NASA SBSE k-omega SST baseline, fail closed."
  (:require [cae.sbse-block-mesh :as mesh]
            [cae.sbse-grid-study :as grid-study]
            [cae.sbse-rans :as rans]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec [args]
  (let [p (-> (ProcessBuilder. ^java.util.List (mapv str args)) (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream p)) exit (.waitFor p)]
    (when-not (zero? exit)
      (throw (ex-info "SBSE RANS command failed" {:args args :exit exit :output output})))
    output))
(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))
(defn- hex [bytes] (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))
(defn- file-evidence [root path]
  (let [file (io/file root path) digest (MessageDigest/getInstance "SHA-256")]
    (when-not (.isFile file) (throw (ex-info "SBSE RANS evidence file missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)]
                   (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))
(defn- write-file! [root path content]
  (let [file (io/file root path)] (.mkdirs (.getParentFile file)) (spit file content)))
(defn- number [x] (Double/parseDouble x))
(defn- parsed-number [pattern text] (some-> (re-find pattern text) second number))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :openfoam-v2506-arm64)
        image (:image manifest) digest (:image-digest manifest)
        level-name (System/getenv "SBSE_GRID_LEVEL")
        level (some-> level-name keyword)
        grid-controls (if level (grid-study/grid level)
                          {:level :baseline :nx 48 :ny 24 :nz 24 :wall-normal-grading 10.0})
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             (str ".cache/external-solvers/openfoam-sbse-rans-" (name (:level grid-controls))))))
        reuse? (= "1" (System/getenv "CAE_REUSE_RUN"))
        _ (when-not reuse? (delete-tree! root)) _ (.mkdirs root)
        generated (if level (mesh/layered-block-mesh-dict grid-controls)
                       (mesh/block-mesh-dict grid-controls))
        case (rans/case-files (cond-> rans/default-experiment level (assoc :wall-treatment :low-re)))
        _ (when-not reuse?
            (doseq [[path content] (:files case)] (write-file! root path content)))
        _ (when-not reuse? (write-file! root "system/blockMeshDict" (:dict generated)))
        mount (str (.getPath root) ":/work")
        base ["docker" "run" "--rm" "--entrypoint" "/bin/bash" "-v" mount image "-lc"]
        command (str "source /opt/OpenFOAM-v2506/etc/bashrc; cd /work; set -e; "
                     (when-not reuse?
                       (str "blockMesh > log.blockMesh 2>&1; "
                            (when-not level "renumberMesh -overwrite -constant > log.renumberMesh 2>&1; ")
                            "checkMesh -allTopology -allGeometry -constant > log.checkMesh 2>&1; "
                            (when level "potentialFoam > log.potentialFoam 2>&1; ")
                            "simpleFoam > log.simpleFoam 2>&1; "))
                     "latest=$(foamListTimes -latestTime); "
                     "simpleFoam -postProcess -func wallShearStress -latestTime > log.postProcess 2>&1; "
                     "simpleFoam -postProcess -func yPlus -latestTime >> log.postProcess 2>&1; "
                     "simpleFoam -postProcess -func writeCellCentres -latestTime > log.writeCellCentres 2>&1; "
                     "echo $latest > latest-time.txt")
        _ (exec (conj base command))
        latest (str/trim (slurp (io/file root "latest-time.txt")))
        log-text (slurp (io/file root "log.simpleFoam"))
        post-text (slurp (io/file root "log.postProcess"))
        check-text (slurp (io/file root "log.checkMesh"))
        ended? (boolean (re-find #"(?m)^End\s*$" log-text))
        converged-iterations (some-> (re-find #"SIMPLE solution converged in (\d+) iterations" log-text)
                                     second Long/parseLong)
        iterations (count (re-seq #"(?m)^Time = \d+" log-text))
        residuals (mapv #(number (second %)) (re-seq #"Initial residual = ([0-9.Ee+-]+)" log-text))
        yplus (some->> (re-find #"patch floorBump y\+ : min = ([0-9.Ee+-]+), max = ([0-9.Ee+-]+), average = ([0-9.Ee+-]+)" post-text)
                       rest (mapv number))
        shear (some->> (re-find #"min/max\(floorBump\) = \(([-0-9.Ee+ ]+)\), \(([-0-9.Ee+ ]+)\)" post-text)
                       rest (mapv (fn [row] (mapv number (str/split (str/trim row) #"\s+")))))
        max-nonorth (parsed-number #"Mesh non-orthogonality Max: ([0-9.Ee+-]+)" check-text)
        max-skew (parsed-number #"Max skewness = ([0-9.Ee+-]+)" check-text)
        min-volume (parsed-number #"Min volume = ([0-9.Ee+-]+)" check-text)
        mesh-ok? (boolean (re-find #"Mesh OK\." check-text))
        topology-ok? (and (boolean (re-find #"Boundary definition OK\." check-text))
                          (boolean (re-find #"Number of regions: 1 \(OK\)" check-text)))
        concave? (boolean (re-find #"\*\*\*Concave cells" check-text))
        mesh-warning-count (some-> (re-find #"Failed (\d+) mesh checks\." check-text) second Long/parseLong)
        boundary-layer-mesh-acceptable? (and level topology-ok? (pos? min-volume)
                                             (< max-nonorth 40.0) (< max-skew 2.0) (not concave?)
                                             (= 3 mesh-warning-count))
        output-paths [(str latest "/wallShearStress") (str latest "/yPlus")
                      (str latest "/Cx") (str latest "/Cz")]
        xs (rans/patch-values (slurp (io/file root latest "Cx")) "floorBump")
        zs (rans/patch-values (slurp (io/file root latest "Cz")) "floorBump")
        stresses (rans/patch-values (slurp (io/file root latest "wallShearStress")) "floorBump")
        faces (mapv (fn [x z stress] {:x x :z z :shear-x (first stress)}) xs zs stresses)
        dataset-root (io/file ".cache/huggingface-datasets/nasa-tmr-sbse-ofi")
        ofi-file (io/file dataset-root "Other_exp_Data/Speedbump_sep_exp/Data_OFI/OFI_bump36_Mp1.dat")
        _ (when-not (.isFile ofi-file) (throw (ex-info "verified NASA SBSE OFI dataset is required" {:path (.getPath ofi-file)})))
        correlation (rans/correlate-ofi (rans/parse-ofi (slurp ofi-file)) faces
                                        (:velocity-m-s (:conditions case)))
        correlation-qualified? (and (<= (:rmse-cf correlation) 0.001)
                                    (>= (:within-experimental-uncertainty-fraction correlation) 0.68)
                                    (<= (:maximum-face-distance-m correlation) 0.03))
        input-paths (concat ["system/blockMeshDict"] (sort (keys (:files case))))
        checks {:mesh-accepted? (or mesh-ok? boundary-layer-mesh-acceptable?)
                :topology-ok? topology-ok? :positive-volume? (pos? min-volume)
                :boundary-layer-quality-warnings-retained? (or (nil? level) (= 3 mesh-warning-count))
                :no-concave-cells? (not concave?)
                :nonorthogonality-below-40-deg? (< max-nonorth 40.0)
                :skewness-below-2? (< max-skew 2.0) :solver-ended? ended?
                :simple-converged? (and (some? converged-iterations) (= converged-iterations iterations))
                :converged-before-limit? (< iterations 5000) :residuals-present? (boolean (seq residuals))
                :floor-yplus-present? (= 3 (count yplus)) :floor-wall-shear-present? (= 2 (count shear))
                :wall-resolved-yplus? (or (nil? level) (and (= 3 (count yplus)) (<= (second yplus) 2.0)))}
        passed? (every? true? (vals checks))
        envelope {:case-id (str "openfoam-v2506-nasa-sbse-3d-" (name (:level grid-controls)) "-komega-sst")
                  :solver :openfoam :solver-version (:version manifest) :image-digest digest
                  :command (cond-> ["blockMesh"]
                             (nil? level) (conj "renumberMesh") true (conj "checkMesh")
                             level (conj "potentialFoam") true (conj "simpleFoam"))
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :experiment-source {:dataset-id "nasa-tmr-sbse-ofi"
                                      :file "Other_exp_Data/Speedbump_sep_exp/Data_OFI/OFI_bump36_Mp1.dat"
                                      :measured-inputs (select-keys rans/default-experiment
                                                                    [:velocity-m-s :pressure-pa :temperature-c :relative-humidity])
                                      :model-assumptions (select-keys rans/default-experiment
                                                                      [:turbulence-intensity :turbulence-length-scale-m])}
                  :conditions (:conditions case)
                  :mesh (merge (select-keys generated [:format :nx :ny :nz :cells :blocks :vertices])
                               (when level (select-keys (grid-study/enrich grid-controls)
                                                       [:level :wall-normal-grading :boundary-layer-thickness-m
                                                        :boundary-layer-cells :boundary-layer-grading
                                                        :minimum-first-layer-height-m :maximum-first-layer-height-m
                                                        :cell-expansion-ratio])))
                  :input-files (mapv #(file-evidence root %) input-paths)
                  :result-files (mapv #(file-evidence root %) (concat ["log.blockMesh"]
                                                                     (when-not level ["log.renumberMesh"])
                                                                     ["log.checkMesh"]
                                                                     (when level ["log.potentialFoam"])
                                                                     [
                                                                       "log.simpleFoam" "log.postProcess" "log.writeCellCentres"
                                                                       "latest-time.txt"] output-paths))
                  :result {:latest-time latest :iterations iterations :converged-iterations converged-iterations
                           :floor-yplus (when yplus {:minimum (nth yplus 0) :maximum (nth yplus 1) :average (nth yplus 2)})
                           :floor-wall-shear-min (first shear) :floor-wall-shear-max (second shear)
                           :maximum-nonorthogonality-deg max-nonorth :maximum-skewness max-skew
                           :minimum-cell-volume-m3 min-volume :literal-check-mesh-ok? mesh-ok?
                           :mesh-quality-warning-count mesh-warning-count
                           :residual-records (count residuals)
                           :ofi-correlation (dissoc correlation :matches)}
                  :checks checks :passed? passed?
                  :qualification {:execution (if passed? :qualified :rejected)
                                  :wall-resolution (if (get checks :wall-resolved-yplus?) :qualified :rejected)
                                  :experimental-correlation (if correlation-qualified? :qualified :rejected)
                                  :correlation-criteria {:maximum-rmse-cf 0.001
                                                         :minimum-uncertainty-coverage 0.68
                                                         :maximum-face-distance-m 0.03}
                                  :industrial-accuracy :not-qualified}
                  :status (if passed? :external-sbse-rans-execution-verified
                                      :external-sbse-rans-execution-rejected)}]
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (when-not passed? (throw (ex-info "SBSE RANS execution rejected" envelope)))
    (prn envelope)))
