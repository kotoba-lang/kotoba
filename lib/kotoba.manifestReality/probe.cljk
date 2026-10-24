(ns probe
  (:require ["fs" :as fs] [cljs.reader :as reader]
            [manifest-reality.checks :as c]))
(let [west (fs/readFileSync "/tmp/mr-west.yml" "utf8")
      m (first (reader/read-string (fs/readFileSync "/tmp/mr-repos.edn" "utf8")))
      km {:rad-rids (reader/read-string (:manifest.repos/rad-rids m))
          :datalad  (reader/read-string (:manifest.repos/datalad m))
          :archived (reader/read-string (:manifest.repos/archived m))}
      f (c/audit {:west west :keyed-maps km})]
  (println "findings:" (count f))
  (println "summary:" (pr-str (c/summary f)))
  (println "errors:" (count (c/errors f)))
  (doseq [x (take 8 f)] (println "  " (:check x) (:severity x) (:subject x))))
