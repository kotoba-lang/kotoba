(ns run
  (:require [loop-lei-catalog.core :as loop]
            [kotoba.lang.text :as str]))

(def argv (vec (drop 2 (js->clj (.-argv js/process)))))
(defn- flag [n] (let [i (.indexOf (clj->js argv) n)]
                  (when (and (>= i 0) (< (inc i) (count argv))) (nth argv (inc i)))))

(let [r (loop/run-cycle! {:dry-run? (boolean (some #{"--dry-run"} argv))
                          :contact-limit (some-> (flag "--contact-limit") js/parseInt)})
      b (:maturity (:before r)) a (:maturity (:after r))]
  (println "observe -> evaluate -> decide -> act -> record-evidence complete")
  (println "maturity:" (.toFixed (:score b) 4) "->" (.toFixed (:score a) 4)
           (str "(measured weight " (.toFixed (:measured-weight a) 2) ")"))
  (println "weakest axis:" (name (:axis (first (:actions (:after r))))))
  (println "action:" (:action (:action r)) "ok=" (:ok (:action r)))
  (doseq [x (:actions (:after r))]
    (println (str "  " (name (:axis x)) " = "
                  (if (= :unmeasured (:score x)) "unmeasured" (.toFixed (:score x) 3))
                  "  leverage " (if (js/isFinite (:leverage x)) (.toFixed (:leverage x) 4) "inf"))))
  (println "countries:" (:present (:gaps (:after r))) "/" (:target (:gaps (:after r)))
           " absent:" (count (:absent (:gaps (:after r)))))
  (println "ledger:" (:ledger-path r)))
