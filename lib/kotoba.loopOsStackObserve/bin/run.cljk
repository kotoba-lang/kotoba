(ns run
  (:require [loop-os-stack-observe.core :as loop]))

(let [root (or (System/getenv "OS_STACK_ROOT") ".")
      r (loop/run-cycle! {:root root})]
  (println "observe -> evaluate -> decide -> act -> record-evidence complete")
  (println "open gaps:" (mapv name (:gaps-open-list (:entry r))))
  (println "next tranche:" (some-> (:next-tranche r) :gap name))
  (println "  action:" (some-> (:next-tranche r) :action))
  (println "evidence ledger:" (:ledger-path r)))
