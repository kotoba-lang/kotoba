(ns shinka.variation
  "Selection and the two variation operators: crossover and mutation.

  Every function here is `[... state] -> [result state']` so a generation is
  reproducible from its seed regardless of evaluation order.

  ## Why crossover is here at all

  `shugyo.policy/random-search` (ARS-lite) and `sha256d.evolve` both search
  by perturbing an incumbent -- mutation only, no recombination. That is the
  right shape when the search space is a single basin or a small closed
  combinatorial set. It is the wrong shape when good solutions are built from
  *parts* that were discovered independently, which is exactly what a
  behaviour policy is: \"kite away from the nearest enemy\" and \"walk toward
  XP gems\" are separate genes that a mutation-only search has to rediscover
  together. Recombination is the one thing neither existing searcher can do,
  and the reason `shinka` exists rather than a third call to `random-search`."
  (:require [shinka.rng :as rng]
            [shinka.genome :as genome]))

;; ---------------------------------------------------------------------------
;; selection
;; ---------------------------------------------------------------------------

(defn tournament
  "Pick one individual by `k`-way tournament. `scored` is a vector of
  `{:genome :fitness}` sorted or not; higher fitness wins. Returns
  `[genome state']`.

  Tournament rather than fitness-proportionate on purpose: fitness here is a
  game score with no meaningful zero and an unbounded top end, so
  proportionate selection would silently change its pressure whenever the
  score scale moved. A tournament only ever compares."
  [scored k st]
  (let [n (count scored)]
    (loop [i 0 st st best nil]
      (if (= i k)
        [(:genome best) st]
        (let [[j st'] (rng/next-int st n)
              c (nth scored j)]
          (recur (inc i) st' (if (or (nil? best) (> (:fitness c) (:fitness best))) c best)))))))

(defn elites
  "The `n` highest-fitness genomes, best first. Pure -- no draws."
  [scored n]
  (->> scored (sort-by :fitness >) (take n) (mapv :genome)))

;; ---------------------------------------------------------------------------
;; crossover
;; ---------------------------------------------------------------------------

(defn uniform-crossover
  "Each gene comes from `a` or `b` with equal probability."
  [a b st]
  (loop [i 0 st st acc []]
    (if (= i (count a))
      [acc st]
      (let [[u st'] (rng/next-double st)]
        (recur (inc i) st' (conj acc (if (< u 0.5) (nth a i) (nth b i))))))))

(defn blend-crossover
  "BLX-alpha: each gene is drawn uniformly from the interval spanned by the
  parents, widened by `alpha` on both sides.

  Unlike uniform crossover this can produce values outside both parents,
  which is what lets a population keep exploring after it has converged onto
  one face of the box. The caller clamps."
  [a b alpha st]
  (loop [i 0 st st acc []]
    (if (= i (count a))
      [acc st]
      (let [x (double (nth a i)) y (double (nth b i))
            lo (min x y) hi (max x y) d (- hi lo)
            [u st'] (rng/next-double st)]
        (recur (inc i) st' (conj acc (+ (- lo (* alpha d)) (* u (+ d (* 2.0 alpha d))))))))))

(defn crossover
  "Dispatch on `:uniform` or `:blend`."
  [kind alpha a b st]
  (case kind
    :uniform (uniform-crossover a b st)
    :blend   (blend-crossover a b alpha st)
    (throw (ex-info "unknown crossover" {:kind kind}))))

;; ---------------------------------------------------------------------------
;; mutation
;; ---------------------------------------------------------------------------

(defn mutate
  "Gaussian mutation. Each gene mutates with probability `rate`; when it does,
  it moves by `sigma * N(0,1) * gene-width`.

  Sigma is scaled by the *gene's own* box width so one sigma means the same
  fraction of the search range for a weight bounded to [-1,1] and for a bias
  bounded to [-10,10]. A sigma expressed in raw units would tune only the
  widest gene."
  [{:keys [dim lo hi] :as spec} g rate sigma st]
  (loop [i 0 st st acc []]
    (if (= i dim)
      [(genome/clamp spec acc) st]
      (let [[u st1] (rng/next-double st)]
        (if (< u rate)
          (let [[z st2] (rng/gaussian st1)
                w (- (nth hi i) (nth lo i))]
            (recur (inc i) st2 (conj acc (+ (double (nth g i)) (* sigma z w)))))
          (recur (inc i) st1 (conj acc (double (nth g i)))))))))
