(defn read-count []
  (kqe-count (kqe-get-objects "graphA" "alice" "kg/name")))

(defn query-count []
  (kqe-count (kqe-query "")))
