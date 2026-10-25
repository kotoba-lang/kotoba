#!/usr/bin/env kbb
;; Key-register shape + no-private-material gate (R-002 residual).
;;
;; Usage (repo root):
;;   bb scripts/check-key-register.bb [key-register.edn]
;;
;; Validates registers/key-register.edn structure, production public-key
;; requirements, and forbids PEM private blocks. Exit 1 on failure.
(require '[babashka.classpath :refer [add-classpath]]
         '[clojure.edn :as edn]
         '[clojure.java.io :as io])

(def script-dir (-> *file* io/file .getAbsoluteFile .getParentFile))
(def root (.getParentFile script-dir))
(add-classpath (str (io/file root "src")))

(require '[kotoba.security.key-lifecycle :as kl])

(def args (vec *command-line-args*))
(def register-file
  (if (first args)
    (io/file (first args))
    (io/file root "registers/key-register.edn")))

(let [register (edn/read-string (slurp register-file))
      result (kl/check-register register)]
  (if (:valid? result)
    (do (doseq [k (:keys register)]
          (println "ok" (:key/id k)
                   (str "status=" (name (:key/status k)))
                   (str "intent=" (name (or (:key/intent k) :unspecified)))
                   (str "storage=" (name (:key/storage k)))))
        (println "ok key-register" (str "keys=" (count (:keys register)))))
    (do (println "FAIL" (:message result) (pr-str (:data result)))
        (System/exit 1))))
