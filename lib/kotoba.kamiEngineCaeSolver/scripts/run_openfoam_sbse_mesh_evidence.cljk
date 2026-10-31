(ns run-openfoam-sbse-mesh-evidence
  "Generate and verify the first body-fitted 3D NASA SBSE OpenFOAM volume mesh."
  (:require [cae.sbse-block-mesh :as mesh]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec [args]
  (let [p (-> (ProcessBuilder. ^java.util.List (mapv str args)) (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream p)) exit (.waitFor p)]
    (when-not (zero? exit) (throw (ex-info "SBSE mesh command failed" {:args args :exit exit :output output})))
    output))
(defn- hex [bytes] (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))
(defn- file-evidence [root path]
  (let [file (io/file root path) digest (MessageDigest/getInstance "SHA-256")]
    (when-not (.isFile file) (throw (ex-info "SBSE mesh evidence file missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)] (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))
(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))
(defn- parsed-number [pattern text]
  (some-> (re-find pattern text) second (str/replace #"\.$" "") Double/parseDouble))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :openfoam-v2506-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             ".cache/external-solvers/openfoam-sbse-mesh")))
        _ (delete-tree! root) _ (.mkdirs (io/file root "system"))
        generated (mesh/block-mesh-dict {:nx 48 :ny 24 :nz 24 :wall-normal-grading 10.0})
        _ (spit (io/file root "system/blockMeshDict") (:dict generated))
        _ (spit (io/file root "system/controlDict")
                "FoamFile { format ascii; class dictionary; object controlDict; }\napplication blockMesh;\nstartFrom startTime;\nstartTime 0;\nstopAt endTime;\nendTime 1;\ndeltaT 1;\nwriteControl timeStep;\nwriteInterval 1;\n")
        _ (spit (io/file root "system/fvSchemes")
                "FoamFile { format ascii; class dictionary; object fvSchemes; }\nddtSchemes { default Euler; }\ngradSchemes { default Gauss linear; }\ndivSchemes { default none; }\nlaplacianSchemes { default Gauss linear corrected; }\ninterpolationSchemes { default linear; }\nsnGradSchemes { default corrected; }\n")
        _ (spit (io/file root "system/fvSolution")
                "FoamFile { format ascii; class dictionary; object fvSolution; }\nsolvers {}\n")
        mount (str (.getPath root) ":/work")
        base ["docker" "run" "--rm" "--entrypoint" "/bin/bash" "-v" mount image "-lc"]
        command (str "source /opt/OpenFOAM-v2506/etc/bashrc; cd /work; set -e; "
                     "blockMesh > log.blockMesh 2>&1; checkMesh -allTopology -allGeometry -constant > log.checkMesh 2>&1")
        _ (exec (conj base command))
        check-text (slurp (io/file root "log.checkMesh"))
        cells (long (parsed-number #"cells:\s+(\d+)" check-text))
        regions (long (parsed-number #"Number of regions: (\d+)" check-text))
        max-nonorth (parsed-number #"Mesh non-orthogonality Max: ([0-9.Ee+-]+)" check-text)
        max-skew (parsed-number #"Max skewness = ([0-9.Ee+-]+)" check-text)
        min-volume (parsed-number #"Min volume = ([0-9.Ee+-]+)" check-text)
        mesh-ok? (boolean (re-find #"Mesh OK\." check-text))
        checks {:cell-count? (= cells (:cells generated)) :single-region? (= 1 regions)
                :positive-volume? (pos? min-volume) :nonorthogonality-below-40-deg? (< max-nonorth 40.0)
                :skewness-below-2? (< max-skew 2.0) :mesh-ok? mesh-ok?}
        passed? (every? true? (vals checks))
        paths ["system/blockMeshDict" "system/controlDict" "system/fvSchemes" "system/fvSolution"
               "log.blockMesh" "log.checkMesh"
               "constant/polyMesh/points" "constant/polyMesh/faces"
               "constant/polyMesh/owner" "constant/polyMesh/neighbour" "constant/polyMesh/boundary"]
        envelope {:case-id "openfoam-v2506-nasa-sbse-3d-body-fitted-coarse-mesh"
                  :solver :openfoam :solver-version (:version manifest) :image-digest digest
                  :command ["blockMesh" "checkMesh" "-allTopology" "-allGeometry"]
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :mesh (select-keys generated [:format :nx :ny :nz :cells :blocks :vertices])
                  :result {:cells cells :regions regions :minimum-cell-volume min-volume
                           :maximum-nonorthogonality-deg max-nonorth :maximum-skewness max-skew}
                  :checks checks :files (mapv #(file-evidence root %) paths)
                  :passed? passed? :status (if passed? :external-sbse-volume-mesh-verified
                                               :external-sbse-volume-mesh-rejected)}]
    (when-not passed? (throw (ex-info "SBSE volume mesh evidence rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
