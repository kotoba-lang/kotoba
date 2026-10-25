(ns num.cljs-verify
  "Run the backend contract against the CPU backend under ClojureScript (node),
  proving the .cljc core actually runs on cljs — not just the JVM."
  (:require [num.cpu :as cpu]
            [num.contract :as contract]))
(defn -main [& _]
  (let [pass (atom 0) fail (atom 0)]
    (contract/verify (cpu/cpu-backend)
      (fn [ok? label] (if ok? (swap! pass inc) (do (swap! fail inc) (println "  ✗" label)))))
    (println (str "cljs CPU contract: " @pass " passed, " @fail " failed"))
    (when (pos? @fail) (js/process.exit 1))))

(set! *main-cli-fn* -main)
