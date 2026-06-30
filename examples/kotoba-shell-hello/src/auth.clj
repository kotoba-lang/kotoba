(defn run [n]
  (if (has-capability? "graph/x" "read")
    (+ n 1)
    0))
