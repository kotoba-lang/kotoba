(ns probe2
  (:require ["fs" :as fs] [manifest-reality.checks :as c]))
(let [f (c/audit {:west (fs/readFileSync "/tmp/mr-broken.yml" "utf8")})]
  (println "broken west.yml (6ebf4b4b5fc) findings:" (count f))
  (doseq [x f] (println "  " (:check x) (:severity x) (:subject x) (pr-str (:detail x)))))
