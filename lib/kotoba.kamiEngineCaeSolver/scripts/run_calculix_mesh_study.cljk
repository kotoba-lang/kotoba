(ns run-calculix-mesh-study
  "Run three real C3D8 cantilever meshes and emit Richardson/GCI evidence."
  (:require [cae.calculix-mesh :as mesh]
            [cae.external-evidence :as evidence]
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
    (when-not (.isFile file) (throw (ex-info "expected mesh-study file is missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)] (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))

(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))

(def levels
  [{:id :coarse :nx 10 :ny 1 :nz 1 :h-relative 8.0}
   {:id :medium :nx 20 :ny 2 :nz 2 :h-relative 4.0}
   {:id :fine :nx 40 :ny 4 :nz 4 :h-relative 2.0}
   {:id :ultrafine :nx 80 :ny 8 :nz 8 :h-relative 1.0}])

(defn- run-level [root image {:keys [id nx ny nz h-relative]}]
  (let [name (name id) level-root (io/file root name) _ (.mkdirs level-root)
        generated (mesh/cantilever-input {:nx nx :ny ny :nz nz})
        input-name (str name ".inp") input-file (io/file level-root input-name)
        _ (spit input-file (:input generated))
        run (exec-command ["docker" "run" "--rm" "-v" (str (.getCanonicalPath level-root) ":/work")
                           image "-i" name])
        _ (spit (io/file level-root "log.ccx") (:output run))
        log (evidence/calculix-log (:output run))
        tip (evidence/calculix-tip-displacement (slurp (io/file level-root (str name ".dat"))))
        paths [input-name "log.ccx" (str name ".dat") (str name ".frd")
               (str name ".sta") (str name ".cvg")]
        passed? (and (zero? (:exit run)) (:complete? log) (= 1.0 (:time tip))
                     (= (count (:tip-nodes generated)) (:node-count tip))
                     (number? (:mean-uz tip)))]
    {:id id :nx nx :ny ny :nz nz :h-relative h-relative
     :elements (:element-count generated) :nodes (:node-count generated)
     :tip-nodes (:node-count tip) :value (:mean-uz tip) :tip-spread (:spread-uz tip)
     :exit-code (:exit run) :log log :files (mapv #(file-evidence level-root %) paths)
     :passed? passed?}))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :calculix-2.21-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             ".cache/external-solvers/calculix-mesh-study")))
        _ (delete-tree! root) _ (.mkdirs root)
        inspect (exec-command ["docker" "image" "inspect" image "--format" "{{join .RepoDigests \"\\n\"}}"])
        _ (when-not (and (zero? (:exit inspect)) (.contains (:output inspect) digest))
            (throw (ex-info "CalculiX container digest mismatch" {:expected digest :actual (:output inspect)})))
        run-levels (mapv #(run-level root image %) levels)
        baseline (evidence/mesh-convergence-evidence {:levels (subvec run-levels 0 3)})
        refined (evidence/mesh-convergence-evidence {:levels (subvec run-levels 1 4)})
        improvement (evidence/mesh-refinement-improvement
                     {:baseline baseline :refined refined :target-gci 0.03})
        envelope {:case-id "calculix-2.21-nlgeom-cantilever-four-level-gci"
                  :solver :calculix :solver-version (:version manifest) :image-digest digest
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :study improvement :passed? (:passed? improvement)
                  :status (if (:passed? improvement) :external-mesh-refinement-verified
                              :external-mesh-refinement-rejected)}]
    (when-not (:passed? envelope) (throw (ex-info "CalculiX mesh study rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
