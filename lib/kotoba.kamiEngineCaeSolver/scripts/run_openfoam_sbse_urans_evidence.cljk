(ns run-openfoam-sbse-urans-evidence
  "Execute wall-resolved NASA SBSE PIMPLE/URANS and time-average wall Cf."
  (:require [cae.sbse-block-mesh :as mesh]
            [cae.sbse-grid-study :as grid-study]
            [cae.sbse-rans :as rans]
            [cae.sbse-urans :as urans]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec [args]
  (let [p (-> (ProcessBuilder. ^java.util.List (mapv str args)) (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream p)) exit (.waitFor p)]
    (when-not (zero? exit) (throw (ex-info "SBSE URANS command failed" {:args args :exit exit :output output})))
    output))
(defn- cleanup-container! [name]
  (let [p (-> (ProcessBuilder. ^java.util.List ["docker" "rm" "-f" name])
              (.redirectErrorStream true) (.start))]
    (slurp (.getInputStream p)) (.waitFor p) nil))
(defn- delete-tree! [file] (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))
(defn- write-file! [root path content]
  (let [file (io/file root path)] (.mkdirs (.getParentFile file)) (spit file content)))
(defn- hex [bytes] (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))
(defn- file-evidence [root path]
  (let [file (io/file root path) digest (MessageDigest/getInstance "SHA-256")]
    (when-not (.isFile file) (throw (ex-info "URANS evidence file missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)] (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))
(defn- number [x] (Double/parseDouble (str/replace x #"\.$" "")))
(defn- parsed-number [pattern text] (some-> (re-find pattern text) second number))
(defn- env-number [name fallback] (if-let [x (System/getenv name)] (number x) fallback))
(defn- shear-series [text velocity average-start]
  (->> (str/split-lines text)
       (keep (fn [line]
               (when-let [[_ t x] (re-find #"^\s*([0-9.Ee+-]+)\s+\(\s*([-0-9.Ee+]+)\s+[-0-9.Ee+]+\s+[-0-9.Ee+]+\s*\)" line)]
                 (let [time (number t)]
                   (when (>= time average-start)
                     {:time time :value (rans/skin-friction-coefficient (number x) velocity)})))))
       vec))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :openfoam-v2506-arm64)
        image (:image manifest) digest (:image-digest manifest)
        level (keyword (or (System/getenv "SBSE_GRID_LEVEL") "coarse"))
        pilot? (= "1" (System/getenv "SBSE_URANS_PILOT"))
        reuse? (= "1" (System/getenv "CAE_REUSE_RUN"))
        continue? (= "1" (System/getenv "SBSE_URANS_CONTINUE"))
        grid-controls (grid-study/grid level)
        defaults (if pilot? (assoc urans/default-run :end-time-s 0.002 :average-start-s 0.001
                                    :maximum-courant 0.3 :maximum-delta-t-s 1.0e-5
                                    :write-interval-s 0.0005)
                    urans/default-run)
        run (assoc defaults :end-time-s (env-number "SBSE_URANS_END_TIME" (:end-time-s defaults))
                            :average-start-s (env-number "SBSE_URANS_AVERAGE_START" (:average-start-s defaults))
                            :initial-delta-t-s (env-number "SBSE_URANS_INITIAL_DT" (:initial-delta-t-s defaults))
                            :maximum-delta-t-s (env-number "SBSE_URANS_MAX_DT" (:maximum-delta-t-s defaults))
                            :maximum-courant (env-number "SBSE_URANS_MAX_CO" (:maximum-courant defaults))
                            :start-from (if continue? :latest-time :start-time))
        ranks (long (env-number "SBSE_MPI_RANKS" 4.0))
        parallel? (> ranks 1)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             (str ".cache/external-solvers/openfoam-sbse-urans-" (name level)
                                                  (when pilot? "-pilot")))))
        _ (when (and (not reuse?) (not continue?)) (delete-tree! root)) _ (.mkdirs root)
        generated (mesh/layered-block-mesh-dict grid-controls)
        case (urans/case-files rans/default-experiment run)
        _ (when-not reuse?
            (doseq [[path content] (:files case)
                    :when (or (not continue?) (not (str/starts-with? path "0/")))]
              (write-file! root path content)))
        _ (when-not reuse? (write-file! root "system/decomposeParDict"
                       (str "FoamFile { format ascii; class dictionary; object decomposeParDict; }\n"
                            "numberOfSubdomains " ranks ";\nmethod scotch;\n")))
        _ (when-not reuse? (write-file! root "system/blockMeshDict" (:dict generated)))
        mount (str (.getPath root) ":/work")
        container-name (str "kami-cae-sbse-urans-" (name level) (when pilot? "-pilot"))
        base ["docker" "run" "--rm" "--name" container-name "--entrypoint" "/bin/bash" "-v" mount image "-lc"]
        solver-log (if continue? "log.pimpleFoam.continue" "log.pimpleFoam")
        command (str "source /opt/OpenFOAM-v2506/etc/bashrc; cd /work; set -e; "
                     (when-not continue?
                       (str "blockMesh > log.blockMesh 2>&1; "
                            "checkMesh -allTopology -allGeometry -constant > log.checkMesh 2>&1; "
                            "potentialFoam > log.potentialFoam 2>&1; "))
                     (if parallel?
                       (str "decomposePar -force > log.decomposePar 2>&1; "
                            "mpirun --allow-run-as-root --oversubscribe -np " ranks
                            " pimpleFoam -parallel > " solver-log " 2>&1; "
                            "reconstructPar -latestTime > log.reconstructPar 2>&1; ")
                       (str "pimpleFoam > " solver-log " 2>&1; "))
                     "latest=$(foamListTimes -latestTime); echo $latest > latest-time.txt; "
                     "pimpleFoam -postProcess -func yPlus -latestTime > log.postProcess 2>&1; "
                     "pimpleFoam -postProcess -func writeCellCentres -latestTime > log.writeCellCentres 2>&1; "
                     "pimpleFoam -postProcess -func 'fieldMinMax(U)' -latestTime > log.minmaxU 2>&1; "
                     "pimpleFoam -postProcess -func 'fieldMinMax(k)' -latestTime > log.minmaxK 2>&1")
        _ (when-not reuse?
            (do (cleanup-container! container-name)
                (let [hook (Thread. #(cleanup-container! container-name))]
                  (.addShutdownHook (Runtime/getRuntime) hook)
                  (try (exec (conj base command))
                       (finally
                         (try (.removeShutdownHook (Runtime/getRuntime) hook)
                              (catch IllegalStateException _ nil)))))))
        latest (str/trim (slurp (io/file root "latest-time.txt")))
        latest-number (number latest)
        log-text (slurp (io/file root solver-log)) check-text (slurp (io/file root "log.checkMesh"))
        post-text (slurp (io/file root "log.postProcess"))
        ended? (boolean (re-find #"(?m)^End\s*$" log-text))
        max-co (apply max 0.0 (map #(number (second %)) (re-seq #"Courant Number mean: [0-9.Ee+-]+ max: ([0-9.Ee+-]+)" log-text)))
        yplus (some->> (re-find #"patch floorBump y\+ : min = ([0-9.Ee+-]+), max = ([0-9.Ee+-]+), average = ([0-9.Ee+-]+)" post-text)
                       rest (mapv number))
        series-files (->> (file-seq root)
                          (filter #(and (.isFile %) (= "surfaceFieldValue.dat" (.getName %))
                                        (str/includes? (.getPath %) "floorShearSeries")))
                          (sort-by #(.getPath %)))
        series (->> series-files
                    (mapcat #(shear-series (slurp %) (:velocity-m-s (:conditions case)) (:average-start-s run)))
                    (filter #(<= (:time %) latest-number))
                    (sort-by :time) (reduce (fn [xs sample]
                                             (if (= (:time (peek xs)) (:time sample)) (conj (pop xs) sample)
                                                 (conj xs sample))) []))
        even-series (if (odd? (count series)) (subvec series 1) series)
        stationarity (when (>= (count even-series) 20) (urans/stationarity even-series {}))
        temporal-coverage (urans/temporal-coverage run (:velocity-m-s (:conditions case)))
        mean-path (str latest "/wallShearStressMean")
        mean-file (io/file root mean-path)
        mean-present? (.isFile mean-file)
        max-nonorth (parsed-number #"Mesh non-orthogonality Max: ([0-9.Ee+-]+)" check-text)
        max-skew (parsed-number #"Max skewness = ([0-9.Ee+-]+)" check-text)
        min-volume (parsed-number #"Min volume = ([0-9.Ee+-]+)" check-text)
        maximum-velocity (parsed-number #"max\(mag\(U\)\) = ([0-9.Ee+-]+)" (slurp (io/file root "log.minmaxU")))
        maximum-k (parsed-number #"max\(k\) = ([0-9.Ee+-]+)" (slurp (io/file root "log.minmaxK")))
        execution-checks {:solver-ended? ended? :courant-below-limit? (<= max-co (* 1.05 (:maximum-courant run)))
                :positive-volume? (pos? min-volume) :nonorthogonality-below-40-deg? (< max-nonorth 40.0)
                :skewness-below-2? (< max-skew 2.0) :yplus-present? (= 3 (count yplus))
                :mean-wall-shear-present? mean-present? :series-present? (pos? (count series))
                :velocity-field-bounded? (< maximum-velocity (* 2.0 (:velocity-m-s (:conditions case))))
                :turbulence-field-bounded? (< maximum-k 100.0)
                :no-turbulence-bounding? (not (re-find #"bounding (?:k|omega)" log-text))}
        checks (assoc execution-checks
                      :temporal-coverage-sufficient? (:passed? temporal-coverage)
                      :statistically-stationary? (boolean (:passed? stationarity))
                      :pilot-temporal-coverage-waived? (boolean pilot?)
                      :pilot-stationarity-waived? (boolean pilot?))
        passed? (and (every? true? (vals execution-checks))
                     (or pilot? (:passed? temporal-coverage))
                     (or pilot? (boolean (:passed? stationarity))))
        relative-path (fn [file] (str (.relativize (.toPath root) (.toPath file))))
        paths (concat (sort (keys (:files case))) ["system/blockMeshDict" "log.blockMesh"
                                                     "log.checkMesh" "log.potentialFoam"]
                                                    (when parallel? ["log.decomposePar" "log.reconstructPar"])
                                                    [solver-log
                                                     "log.postProcess" "log.writeCellCentres" "log.minmaxU" "log.minmaxK"
                                                     "latest-time.txt"
                                                     (str latest "/yPlus") (str latest "/Cx") (str latest "/Cz")]
                      (map relative-path series-files)
                      (when mean-present? [mean-path]))
        envelope {:case-id (str "openfoam-v2506-nasa-sbse-3d-" (name level) "-urans-komega-sst"
                                (when pilot? "-pilot") (when continue? "-continuation"))
                  :solver :openfoam :solver-version (:version manifest) :image-digest digest
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :command (if continue?
                             (if parallel?
                               ["decomposePar -force" (str "mpirun -np " ranks " pimpleFoam -parallel")
                                "reconstructPar -latestTime"]
                               ["pimpleFoam (startFrom latestTime)"])
                             (if parallel?
                               ["blockMesh" "checkMesh" "potentialFoam" "decomposePar"
                                (str "mpirun -np " ranks " pimpleFoam -parallel") "reconstructPar"]
                               ["blockMesh" "checkMesh" "potentialFoam" "pimpleFoam"]))
                  :mesh (merge (select-keys generated [:format :nx :ny :nz :cells :blocks :vertices])
                               (grid-study/enrich grid-controls))
                  :run (assoc run :mpi-ranks ranks) :conditions (:conditions case)
                  :result {:latest-time latest :maximum-courant max-co :wall-shear-samples (count series)
                           :temporal-coverage temporal-coverage
                           :stationarity stationarity
                           :floor-yplus (when yplus {:minimum (nth yplus 0) :maximum (nth yplus 1) :average (nth yplus 2)})
                           :maximum-nonorthogonality-deg max-nonorth :maximum-skewness max-skew
                           :minimum-cell-volume-m3 min-volume}
                  :field-bounds {:maximum-velocity-m-s maximum-velocity
                                 :maximum-turbulent-kinetic-energy-m2-s2 maximum-k}
                  :checks checks :files (mapv #(file-evidence root %) paths) :passed? passed?
                  :qualification {:execution (if passed? :qualified :rejected)
                                  :temporal-coverage (if (:passed? temporal-coverage)
                                                       :qualified :not-qualified)
                                  :statistical-stationarity (if (and stationarity (:passed? stationarity))
                                                               :qualified :not-qualified)
                                  :grid-convergence :not-qualified :experimental-validation :not-qualified
                                  :industrial-accuracy :not-qualified}
                  :status (if passed? :external-sbse-urans-execution-verified
                                      :external-sbse-urans-execution-rejected)}]
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (when-not passed? (throw (ex-info "SBSE URANS evidence rejected" envelope)))
    (prn envelope)))
