(ns run-calculix-plastic-mesh-study
  "Execute three gradient-plastic meshes and audit maximum PEEQ sensitivity."
  (:require [cae.calculix-plastic-mesh :as mesh]
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
    (when-not (.isFile file) (throw (ex-info "plastic mesh output missing" {:path path})))
    (with-open [in (io/input-stream file)]
      (let [buffer (byte-array 65536)]
        (loop [] (let [n (.read in buffer)] (when (pos? n) (.update digest buffer 0 n) (recur))))))
    {:path path :sha256 (hex (.digest digest)) :bytes (.length file)}))
(defn- delete-tree! [file]
  (when (.exists file) (doseq [f (reverse (file-seq file))] (.delete f))))

(def levels [{:id :coarse :divisions 2 :h-relative 4.0}
             {:id :medium :divisions 4 :h-relative 2.0}
             {:id :fine :divisions 8 :h-relative 1.0}])

(defn- run-level [root image {:keys [id divisions h-relative]}]
  (let [name (name id) dir (io/file root name) _ (.mkdirs dir)
        generated (mesh/gradient-plastic-input {:divisions divisions})
        _ (spit (io/file dir (str name ".inp")) (:input generated))
        run (exec-command ["docker" "run" "--rm" "-v" (str (.getCanonicalPath dir) ":/work") image "-i" name])
        _ (spit (io/file dir "log.ccx") (:output run))
        log (evidence/calculix-log (:output run))
        field (evidence/calculix-plastic-field (slurp (io/file dir (str name ".dat"))))
        paths [(str name ".inp") "log.ccx" (str name ".dat") (str name ".frd")
               (str name ".sta") (str name ".cvg")]
        passed? (and (zero? (:exit run)) (:complete? log) (= 1.0 (:time field))
                     (pos? (:sample-count field)) (pos? (:maximum-peeq field)))]
    (merge {:id id :divisions divisions :h-relative h-relative :nodes (:nodes generated)
            :elements (:elements generated) :files (mapv #(file-evidence dir %) paths)
            :passed? passed? :value (:maximum-peeq field)} field)))

(defn -main [& _]
  (let [manifest (-> "cae/external-solvers.edn" io/resource slurp edn/read-string :calculix-2.21-arm64)
        image (:image manifest) digest (:image-digest manifest)
        root (.getCanonicalFile (io/file (or (System/getenv "CAE_EXTERNAL_RUN_DIR")
                                             ".cache/external-solvers/calculix-plastic-mesh")))
        _ (delete-tree! root) _ (.mkdirs root)
        inspect (exec-command ["docker" "image" "inspect" image "--format" "{{join .RepoDigests \"\\n\"}}"])
        _ (when-not (and (zero? (:exit inspect)) (.contains (:output inspect) digest))
            (throw (ex-info "CalculiX container digest mismatch" {:expected digest :actual (:output inspect)})))
        run-levels (mapv #(run-level root image %) levels)
        study (evidence/plastic-field-sensitivity {:levels run-levels :local-target 0.05})
        envelope {:case-id "calculix-2.21-plastic-peeq-mesh-sensitivity"
                  :solver :calculix :solver-version (:version manifest) :image-digest digest
                  :platform "linux/arm64-container" :executed-at (str (Instant/now))
                  :study study :passed? (:evidence-passed? study)
                  :status (if (:evidence-passed? study) :external-plastic-sensitivity-verified
                              :external-plastic-sensitivity-rejected)}]
    (when-not (:passed? envelope) (throw (ex-info "plastic mesh evidence rejected" envelope)))
    (spit (io/file root "evidence.edn") (pr-str envelope))
    (prn envelope)))
