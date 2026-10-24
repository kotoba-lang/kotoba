;; Writes the curated preset list (kami.isekai.presets/presets — the single
;; source of truth network-isekai's deploy script also consumes) as standalone
;; EDN files. Run: bb gen-presets --out ../../gftdcojp/network-isekai/public/assets/isekai
(require '[kami.isekai.presets :refer [presets]]
         '[clojure.java.io :as io]
         '[clojure.pprint :as pp])

(defn- round3 [x] (/ (Math/round (* x 1000.0)) 1000.0))

(defn- clean-floats
  "Round doubles to 3dp so generated EDN reads like the hand-authored scenes
   elsewhere in the catalog, not like raw floating-point arithmetic output."
  [x]
  (cond
    (double? x)  (round3 x)
    (map? x)     (into {} (map (fn [[k v]] [k (clean-floats v)]) x))
    (vector? x)  (mapv clean-floats x)
    (seq? x)     (map clean-floats x)
    :else        x))

(defn write-preset! [out-dir {:keys [id compose]}]
  (let [dir (str out-dir "/" id)
        _ (io/make-parents (str dir "/character.edn"))
        data (clean-floats (compose))]
    (spit (str dir "/character.edn") (with-out-str (pp/pprint data)))
    (str dir "/character.edn")))

(defn -main [& args]
  (let [opts (apply hash-map args)
        out  (get opts "--out" "/tmp/isekai-presets")]
    (doseq [p presets]
      (println "wrote" (write-preset! out p)))
    (println (count presets) "presets written to" out)))

(apply -main *command-line-args*)
