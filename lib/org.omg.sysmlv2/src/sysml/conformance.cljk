(ns sysml.conformance
  "Executable conformance checks against OMG's published SysML 2.0
  informative Simple Vehicle Model."
  (:require [sysml.text :as text]))

(def official-simple-vehicle-url
  "https://www.omg.org/cgi-bin/doc?ptc/25-04-31.sysml")

(defn check-string [source]
  (let [model (text/parse-string source "conformance-model")
        emitted (text/emit-string model)
        reparsed (text/parse-string emitted "conformance-model")
        elements (vals (:kerml/elements model))
        opaque (filter #(= :opaque-syntax (:sysml/element-kind %)) elements)]
    {:accepted? true
     :round-trip? (= model reparsed)
     :element-count (count elements)
     :semantically-modeled-count (- (count elements) (count opaque))
     :opaque-count (count opaque)
     :emitted-character-count (count emitted)}))

(defn check-official-example []
  (check-string (slurp official-simple-vehicle-url)))

(defn -main [& _]
  (let [result (check-official-example)]
    (prn result)
    (when-not (and (:accepted? result) (:round-trip? result))
      (throw (ex-info "SysML official-example conformance failed" result)))))
