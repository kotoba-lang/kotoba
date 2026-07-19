(ns kotoba.qualification-reference-oracle)

(defn bounded-risk-score [amount trust]
  (let [base (+ (* amount 3) 7)]
    (if (> trust 2)
      (- base trust)
      (+ base 10))))
