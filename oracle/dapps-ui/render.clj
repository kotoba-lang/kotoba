;; One-shot JVM oracle renderer (never CI, never a gate). Run by hand:
;;   java -cp <garden>:<hiccup>:<clojure>:src clojure.main render.clj
;; Prints the three Hiccup documents as HTML (real hiccup library) and the
;; Garden styles as CSS (real garden library).
(require '[itonami-dapps-ui :as ui] '[hiccup.core :as h] '[garden.core :as g])

(doseq [id ["sound" "display" "soshiki"]]
  (println (str "=== " id " ==="))
  (println (h/html (ui/hiccup id))))

(println "=== css ===")
(println (pr-str (g/css ui/styles)))
