(ns run-calculix-thermoplastic-mesh-study
  "Execute 2/4/8-layer coupled thermoplastic meshes and audit each response."
  (:require [cae.calculix-thermoplastic-mesh :as mesh]
            [cae.external-evidence :as evidence]
            [kotoba.lang.edn :as edn]
            [clojure.java.io :as io])
  (:import [java.security MessageDigest]
           [java.time Instant]))

(defn- exec-command [args]
  (let [p (-> (ProcessBuilder. ^java.util.List (mapv str args)) (.redirectErrorStream true) (.start))
        output (slurp (.getInputStream p)) exit (.waitFor p)] {:exit exit :output output}))
(defn- hex [bytes] (apply str (map #(format "%02x" (bit-and % 0xff)) bytes)))
(defn- file-evidence [root path]
  (let [file (io/file root path) digest (MessageDigest/getInstance "SHA-256")]
    (when-not (.isFile file) (throw (ex-info "thermoplastic mesh output missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)] (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))
(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))

(def levels [{:id :coarse :layers 2 :h-relative 4.0}
             {:id :medium :layers 4 :h-relative 2.0}
             {:id :fine :layers 8 :h-relative 1.0}])

(def refined-levels [{:id :coarse :layers 4 :h-relative 4.0}
                     {:id :medium :layers 8 :h-relative 2.0}
                     {:id :fine :layers 16 :h-relative 1.0}])

(def ultrafine-levels [{:id :coarse :layers 8 :h-relative 4.0}
                       {:id :medium :layers 16 :h-relative 2.0}
                       {:id :fine :layers 32 :h-relative 1.0}])

(defn- run-level [root image steady-state? {:keys [id layers h-relative]}]
  (let [name (name id) dir (io/file root name) _ (.mkdirs dir)
        generated (mesh/coupled-input {:layers layers :steady-state? steady-state?})
        _ (spit (io/file dir (str name ".inp")) (:input generated))
        run (exec-command ["docker" "run" "--rm" "-v" (str (.getCanonicalPath dir) ":/work") image "-i" name])
        _ (spit (io/file dir "log.ccx") (:output run))
        log (evidence/calculix-log (:output run))
        result (evidence/calculix-thermoplastic-result
                {:log-text (:output run) :dat-text (slurp (io/file dir (str name ".dat")))
                 :sta-text (slurp (io/file dir (str name ".sta")))})
        temperatures (into {} (map (juxt :node :temperature-K) (:temperatures result)))
        midpoint-temperature (/ (reduce + (map temperatures (:midpoint-nodes generated))) 4.0)
        paths [(str name ".inp") "log.ccx" (str name ".dat") (str name ".frd")
               (str name ".sta") (str name ".cvg")]
        passed? (and (zero? (:exit run)) (:complete? log) (:job-finished? result)
                     (= (:increments result) (:converged-increments result))
                     (pos? (:maximum-peeq result)) (pos? (:maximum-absolute-heat-flux result)))]
    {:id id :layers layers :h-relative h-relative :nodes (:nodes generated)
     :elements (:elements generated) :midpoint-temperature midpoint-temperature
     :maximum-heat-flux (:maximum-absolute-heat-flux result)
     :maximum-peeq (:maximum-peeq result) :increments (:increments result)
     :passed? passed? :files (mapv #(file-evidence dir %) paths)}))

(defn -main [& [mode]]
  (let [steady-state? (contains? #{"steady" "steady-refined" "steady-ultrafine"} mode)
        refined? (= "steady-refined" mode)
        ultrafine? (= "steady-ultrafine" mode)
        selected-levels (cond ultrafine? ultrafine-levels refined? refined-levels :else levels)
        suffix (cond ultrafine? "steady-ultrafine" refined? "steady-refined"
                     steady-state? "steady" :else "transient")
        manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :calculix-2.21-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             (str ".cache/external-solvers/calculix-thermoplastic-mesh-" suffix))))
        _ (delete-tree! root) _ (.mkdirs root)
        inspect (exec-command ["docker" "image" "inspect" image "--format" "{{join .RepoDigests \"\\n\"}}"])
        _ (when-not (and (zero? (:exit inspect)) (.contains (:output inspect) digest))
            (throw (ex-info "CalculiX container digest mismatch" {:expected digest :actual (:output inspect)})))
        run-levels (mapv #(run-level root image steady-state? %) selected-levels)
        study (evidence/thermoplastic-field-sensitivity
               {:levels run-levels :targets {:midpoint-temperature 0.02
                                              :maximum-heat-flux 0.05 :maximum-peeq 0.05}})
        envelope {:case-id (str "calculix-2.21-thermoplastic-" suffix "-three-grid-sensitivity")
                  :solver :calculix :solver-version (:version manifest) :image-digest digest
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :analysis-mode (if steady-state? :steady-state :transient)
                  :study study :passed? (:evidence-passed? study)
                  :status (if (:evidence-passed? study) :external-thermoplastic-sensitivity-verified
                              :external-thermoplastic-sensitivity-rejected)}]
    (when-not (:passed? envelope) (throw (ex-info "thermoplastic mesh evidence rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
