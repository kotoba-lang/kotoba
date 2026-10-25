(ns shinka.genome
  "A genome is a vector of doubles. That is the whole representation.

  `shinka` deliberately does not model chromosomes, alleles, encodings, or
  species. A real-valued vector plus a box constraint is what a policy's
  weights, a controller's gains, a spawn table, and a shader's constants all
  already are; anything richer would force every caller to translate into a
  vocabulary that only this library speaks.

  A `spec` is `{:dim n :lo x :hi y}` with scalar bounds, or `{:dim n :lo [..]
  :hi [..]}` with per-gene bounds. Bounds are a *box*, not a hint: `clamp` is
  applied after every variation operator, so no operator has to defend
  against producing an out-of-range gene."
  (:require [shinka.rng :as rng]))

(defn- bound-at [b i] (if (sequential? b) (nth b i) b))

(defn normalize-spec
  "Expand scalar bounds to per-gene vectors and validate. Returns the spec
  with `:lo`/`:hi` as vectors, so downstream code has exactly one shape."
  [{:keys [dim lo hi] :as spec}]
  (when-not (and (integer? dim) (pos? dim))
    (throw (ex-info "spec :dim must be a positive integer" {:spec spec})))
  (let [lo' (vec (for [i (range dim)] (double (bound-at lo i))))
        hi' (vec (for [i (range dim)] (double (bound-at hi i))))]
    (doseq [i (range dim)]
      (when-not (< (nth lo' i) (nth hi' i))
        (throw (ex-info "spec bound is not lo < hi" {:gene i :lo (nth lo' i) :hi (nth hi' i)}))))
    (assoc spec :lo lo' :hi hi')))

(defn clamp
  "Clamp every gene into the spec's box."
  [{:keys [dim lo hi]} g]
  (vec (for [i (range dim)]
         (let [x (double (nth g i))]
           (max (nth lo i) (min (nth hi i) x))))))

(defn random
  "A uniformly random genome inside the box. Returns `[genome state']`."
  [{:keys [dim lo hi]} st]
  (loop [i 0 st st acc []]
    (if (= i dim)
      [acc st]
      (let [[u st'] (rng/next-double st)]
        (recur (inc i) st' (conj acc (+ (nth lo i) (* u (- (nth hi i) (nth lo i))))))))))

(defn random-population
  "`n` random genomes. Returns `[population state']`."
  [spec n st]
  (loop [i 0 st st acc []]
    (if (= i n)
      [acc st]
      (let [[g st'] (random spec st)] (recur (inc i) st' (conj acc g))))))

;; ---------------------------------------------------------------------------
;; diversity
;; ---------------------------------------------------------------------------

(defn distance
  "Euclidean distance, normalized by the box so it is comparable across
  specs: a distance of 1.0 means the two genomes sit at opposite corners."
  [{:keys [dim lo hi]} a b]
  (let [ss (reduce + 0.0
                   (for [i (range dim)]
                     (let [w (- (nth hi i) (nth lo i))
                           d (/ (- (double (nth a i)) (double (nth b i))) w)]
                       (* d d))))]
    (/ #?(:clj (Math/sqrt ss) :cljs (js/Math.sqrt ss))
       #?(:clj (Math/sqrt (double dim)) :cljs (js/Math.sqrt dim)))))

(defn diversity
  "Mean pairwise normalized distance over the population, in `[0, 1]`.

  This is the number the collapse guard watches. It is O(n^2) in population
  size, which is fine at the scale a fitness evaluation dominates -- and if
  it ever is not, the population is large enough that sampling pairs would be
  the right fix, not dropping the measurement."
  [spec pop]
  (let [n (count pop)]
    (if (< n 2)
      0.0
      (let [pairs (for [i (range n) j (range (inc i) n)] [(nth pop i) (nth pop j)])]
        (/ (reduce + 0.0 (map (fn [[a b]] (distance spec a b)) pairs))
           (count pairs))))))

(defn centroid
  "Gene-wise mean of the population."
  [{:keys [dim]} pop]
  (let [n (count pop)]
    (vec (for [i (range dim)]
           (/ (reduce + 0.0 (map #(double (nth % i)) pop)) n)))))
