(ns shinka.evolve
  "The generation loop, as `ask` / `tell`.

  ```clojure
  (def s0 (evolve/init {:spec {:dim 8 :lo -1.0 :hi 1.0} :population 24 :seed 7}))
  (let [{:keys [genomes]} (evolve/ask s0)
        fitnesses         (map my-evaluator genomes)      ; sync, async, remote
        [s1 record]       (evolve/tell s0 fitnesses)]
    (:best-fitness record))
  ```

  ## Why ask/tell rather than a fitness function argument

  The obvious API is `(run spec evaluate generations)`. It was rejected
  because it forces the evaluator to be synchronous, and the evaluator this
  library was written for is a game episode inside a browser page -- a
  promise. An API that takes a fitness *function* can only be used from a
  host where fitness is a value; an API that hands you genomes and accepts
  fitnesses back works from any host, in any order, across a process
  boundary, and can be resumed from a crash by replaying the recorded
  fitnesses. `run` is still here for the synchronous case, built on
  ask/tell rather than the other way round.

  ## What one generation does

  Evaluate -> record -> keep `:elites` best unchanged -> fill the rest by
  (tournament, tournament) -> crossover -> mutate -> clamp. If population
  diversity has fallen below `:diversity-floor`, the worst offspring are
  replaced by fresh random immigrants and the count is recorded.

  The immigrant rule is taken from `sha256d.evolve`, which found that without
  it a population collapses onto two candidates on ranking *noise* and then
  stops searching -- the elites' shared genes can never be recovered by
  mutation alone once every member carries them. `shinka` differs in that it
  measures the collapse (mean pairwise distance) instead of assuming a fixed
  mutation budget prevents it."
  (:require [shinka.rng :as rng]
            [shinka.genome :as genome]
            [shinka.variation :as var]))

(def defaults
  {:population 24
   :elites 2
   :tournament 3
   :crossover :blend
   :alpha 0.35
   :mutation-rate 0.25
   :sigma 0.15
   :sigma-decay 1.0        ; 1.0 = constant; 0.97 = anneal
   :sigma-min 0.01
   :diversity-floor 0.05   ; below this the population has collapsed
   :immigrants 0.25        ; fraction of the population replaced when it has
   :seed 0})

(defn init
  "Build the initial state. `opts` needs `:spec`; everything else has a
  default (see `defaults`)."
  [opts]
  (let [{:keys [spec population seed] :as o} (merge defaults opts)
        _ (when-not spec (throw (ex-info "evolve/init needs :spec" {:opts opts})))
        spec (genome/normalize-spec spec)
        [pop st] (genome/random-population spec population (rng/seed seed))]
    {:spec spec
     :opts (dissoc o :spec)
     :generation 0
     :population pop
     :rng st
     :sigma (:sigma o)
     :best nil
     :evaluations 0
     :history []}))

(defn ask
  "The genomes to evaluate this generation, in order. Pure."
  [{:keys [generation population]}]
  {:generation generation :genomes population})

(defn- stats [xs]
  (let [n (count xs)
        mean (/ (reduce + 0.0 xs) n)
        var (/ (reduce + 0.0 (map #(let [d (- % mean)] (* d d)) xs)) n)]
    {:mean mean
     :std #?(:clj (Math/sqrt var) :cljs (js/Math.sqrt var))
     :max (reduce max xs)
     :min (reduce min xs)}))

(defn tell
  "Feed back the fitnesses for the genomes `ask` returned, in the same order.
  Higher fitness is better. Returns `[state' record]`."
  [{:keys [spec opts generation population rng sigma best evaluations history] :as state}
   fitnesses]
  (let [fs (vec fitnesses)]
    (when-not (= (count fs) (count population))
      (throw (ex-info "tell: fitness count does not match the population"
                      {:expected (count population) :got (count fs)})))
    (let [{:keys [elites tournament crossover alpha mutation-rate
                  sigma-decay sigma-min diversity-floor immigrants]} opts
          scored (mapv (fn [g f] {:genome g :fitness (double f)}) population fs)
          ranked (vec (sort-by :fitness > scored))
          div (genome/diversity spec population)
          gen-best (first ranked)
          best' (if (or (nil? best) (> (:fitness gen-best) (:fitness best)))
                  {:genome (:genome gen-best) :fitness (:fitness gen-best) :generation generation}
                  best)
          collapsed? (< div diversity-floor)
          n (count population)
          n-elite (min elites n)
          n-immigrant (if collapsed?
                        (min (- n n-elite) (max 1 (int (* immigrants n))))
                        0)
          n-offspring (- n n-elite n-immigrant)
          keep (var/elites ranked n-elite)
          ;; offspring
          [kids st1]
          (loop [i 0 st rng acc []]
            (if (= i n-offspring)
              [acc st]
              (let [[pa st1] (var/tournament ranked tournament st)
                    [pb st2] (var/tournament ranked tournament st1)
                    [child st3] (var/crossover crossover alpha pa pb st2)
                    [child st4] (var/mutate spec child mutation-rate sigma st3)]
                (recur (inc i) st4 (conj acc child)))))
          [migrants st2] (if (pos? n-immigrant)
                           (genome/random-population spec n-immigrant st1)
                           [[] st1])
          pop' (vec (concat keep kids migrants))
          sigma' (max sigma-min (* sigma sigma-decay))
          record (merge {:generation generation
                         :best-fitness (:fitness gen-best)
                         :best-genome (:genome gen-best)
                         :all-time-best (:fitness best')
                         :diversity div
                         :collapsed? collapsed?
                         :immigrants n-immigrant
                         :sigma sigma
                         :evaluations (+ evaluations n)}
                        (stats fs))]
      [(assoc state
              :generation (inc generation)
              :population pop'
              :rng st2
              :sigma sigma'
              :best best'
              :evaluations (+ evaluations n)
              :history (conj history (dissoc record :best-genome)))
       record])))

(defn best
  "The best genome seen so far: `{:genome :fitness :generation}` or nil."
  [state]
  (:best state))

(defn run
  "Synchronous convenience: run `generations` generations, calling
  `(evaluate genome)` for every individual. Returns `[state records]`.

  Built on ask/tell rather than the other way round, so this cannot drift
  from the asynchronous path."
  [state evaluate generations]
  (loop [s state i 0 recs []]
    (if (= i generations)
      [s recs]
      (let [{:keys [genomes]} (ask s)
            fs (mapv evaluate genomes)
            [s' r] (tell s fs)]
        (recur s' (inc i) (conj recs r))))))
