(ns loop-game-autoplay.policy
  "The genome <-> policy mapping and the search space. Zero dependencies.

  A genome is a flat vector of doubles (all `shinka` knows about). A policy is
  `{:obs-dim :act-dim :w :b}` with `w` row-major `w[a*obs-dim + o]` (all
  `shugyo.policy` knows about). This namespace is the only place that knows
  both — and it deliberately does **not** require `shugyo.policy`.

  Why not: `shugyo.policy` pulls in `shugyo.lcg`, which uses
  `goog.math.Long` for u64-faithful arithmetic. nbb has no `goog.math.Long`,
  so requiring it here would make every nbb entry point in this repo
  unloadable — including the training loop, which needs none of it.

  The oracle delegation lives in `loop-game-autoplay.oracle` instead, is JVM
  only, and is used by exactly one caller: the parity gate."
  (:refer-clojure :exclude [spec]))

(def obs-dim
  "Must equal `OBS_DIM` in resources/autoplay-driver.js. Nothing else would
  notice these drifting apart — the driver would read past the end of a short
  weight vector and return NaN — so the parity gate pins it."
  12)

(def act-dim
  "[move-x, move-y, draft-0, draft-1, draft-2]."
  5)

(def genome-dim (+ (* obs-dim act-dim) act-dim))

(def spec
  "The `shinka` search space. Observations are already normalized to roughly
  [-1,1] and the movement action is thresholded at 0.3, so bounds wider than
  this buy saturation rather than expressiveness."
  {:dim genome-dim :lo -3.0 :hi 3.0})

(def spec-opts
  "`shinka.evolve/init` options for this task.

  Sigma anneals (0.97 per generation, floored at 0.03) because the early
  generations need to find *which* behaviours matter and the later ones need
  to stop destroying them. The diversity floor is set above zero rather than
  at it: a survivors-like scores a policy that runs in one direction almost
  as well as one that kites, so the population converges on a mediocre
  plateau long before it converges numerically."
  {:spec spec
   :elites 2
   :tournament 3
   :crossover :blend
   :alpha 0.35
   :mutation-rate 0.2
   :sigma 0.25
   :sigma-decay 0.97
   :sigma-min 0.03
   :diversity-floor 0.06
   :immigrants 0.2})

(defn genome->policy
  "Weights first (row-major, action-major), biases last."
  [g]
  (when-not (= (count g) genome-dim)
    (throw (ex-info "genome has the wrong length"
                    {:expected genome-dim :got (count g)})))
  {:obs-dim obs-dim
   :act-dim act-dim
   :w (vec (map double (take (* obs-dim act-dim) g)))
   :b (vec (map double (drop (* obs-dim act-dim) g)))})

(defn policy->genome [{:keys [w b]}] (vec (concat w b)))

(defn zero-genome [] (vec (repeat genome-dim 0.0)))
