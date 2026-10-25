(ns auth.core
  "Entry point. `main` is the shadow-cljs :node-script entry (reads process.argv);
  `-main` is the JVM/clojure -M entry."
  (:require [auth.cli :as cli]))

#?(:cljs
   (defn ^:export main []
     (let [args (vec (drop 2 (js->clj (.-argv js/process))))
           code (cli/run args)]
       (set! (.-exitCode js/process) (or code 0)))))

#?(:clj
   (defn -main [& args]
     (let [code (cli/run (vec args))]
       (flush)
       (System/exit (or code 0)))))
