(ns senden.attribution
  "Attribution model (pure). A Touch is {:channel :campaign :timestamp :customer}.
  A conversion has a touch sequence. Attribution models: first-touch, last-touch,
  multi-touch (even), linear."
  (:refer-clojure :exclude [first last]))

(defrecord Touch [channel campaign timestamp customer])

(defn touch [m] (merge {} m))

(defn first-touch [touches] (clojure.core/first (sort-by :timestamp touches)))
(defn last-touch [touches] (clojure.core/last (sort-by :timestamp touches)))

(defn linear-attribution
  "Return {campaign → weight} where each touch in the conversion path gets
  1/N (even distribution)."
  [touches]
  (let [n (count touches)]
    (if (zero? n)
      {}
      (let [w (/ 1 n)]
        (reduce (fn [acc t] (update acc (:campaign t) (fnil + 0) w)) {} touches)))))

(defn multi-touch-credits
  "Return {campaign → credits} summing 1 credit per touch (for counting)."
  [touches]
  (reduce (fn [acc t] (update acc (:campaign t) (fnil + 0) 1)) {} touches))

(declare time-decay-attribution)

(defn attribute
  "Attribution by model: :first, :last, :linear, :multi, :time-decay. Returns
  {campaign → weight/credit}."
  [model touches]
  (case model
    :first  (let [t (first-touch touches)] (if t {(:campaign t) 1.0} {}))
    :last   (let [t (last-touch touches)]  (if t {(:campaign t) 1.0} {}))
    :linear (linear-attribution touches)
    :multi  (multi-touch-credits touches)
    :time-decay (time-decay-attribution touches)
    {}))

(defn time-decay-attribution
  "Time-decay attribution: more recent touches get more credit. Weight of touch
  i = decay^(i from end) where decay ∈ (0,1] (default 0.5). The last touch gets
  weight 1, the second-to-last decay, etc. Returns {campaign → summed weight},
  then normalized so all weights sum to 1."
  ([touches]
   (time-decay-attribution touches 0.5))
  ([touches decay]
   (let [sorted (sort-by :timestamp touches)
         n (count sorted)]
     (if (zero? n)
       {}
       (let [weighted (map-indexed
                       (fn [idx t]
                         ;; distance from the end (0 = last touch)
                         (let [dist (- n 1 idx)
                               w (Math/pow decay dist)]
                           [(:campaign t) w]))
                       sorted)
             summed (reduce (fn [acc [c w]] (update acc c (fnil + 0) w)) {} weighted)
             total (reduce + 0 (vals summed))]
         (if (pos? total)
           (reduce-kv (fn [acc c w] (assoc acc c (/ w total))) {} summed)
           summed))))))
