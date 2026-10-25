(ns kotoba.lang.kami-nv-compat.utsushimi.distribution
  "utsushimi — Replicator distribution primitives. Portable .cljc port of
  src/utsushimi/distribution.ts. Wave 31.

  Mirrors omni.replicator.core.distribution.*: each constructor returns a
  tagged map captured at script time and materialized per-frame by
  `sample` (Replicator's lazy distribution semantics). Bit-reproducible
  via the sampler namespace's LCG (JVM-real; a data-generation-pipeline
  concern, see sampler.cljc for why).

  Dist = {:kind (:uniform|:normal|:truncated-normal|:choice|:sequence|:combine) ...}.
  :sequence carries a mutable cursor (an atom) since sample steps through
  it across calls — every other kind is plain immutable data.

  ADR-2605261800 SD6 / D10.4 utsushimi."
  (:require [kotoba.lang.kami-nv-compat.utsushimi.sampler :as sampler]))

(defn uniform-dist [low high] {:kind :uniform :low (vec low) :high (vec high)})
(defn normal-dist [mean std] {:kind :normal :mean (vec mean) :std (vec std)})
(defn truncated-normal-dist
  [mean std low high]
  {:kind :truncated-normal :mean (vec mean) :std (vec std) :low (vec low) :high (vec high)})
(defn choice-dist [options] {:kind :choice :options (vec options)})
(defn sequence-dist [values] {:kind :sequence :values (vec values) :index (atom 0)})
(defn combine-dist [distributions] {:kind :combine :distributions (vec distributions)})

(declare sample)

(defn- sample-kind
  [dist s]
  (case (:kind dist)
    :uniform (mapv (fn [lo hi] (sampler/next-uniform! s lo hi)) (:low dist) (:high dist))
    :normal (mapv (fn [m std] (sampler/next-normal! s m std)) (:mean dist) (:std dist))
    :truncated-normal (mapv (fn [m std lo hi] (sampler/next-truncated-normal! s m std lo hi))
                             (:mean dist) (:std dist) (:low dist) (:high dist))
    :choice (let [opts (:options dist)
                  idx (min (dec (count opts))
                           (int (Math/floor (* (sampler/next-u01! s) (count opts)))))]
              (opts idx))
    :sequence (let [idx-atom (:index dist)
                    values (:values dist)
                    i (mod @idx-atom (count values))]
                (swap! idx-atom #(mod (inc %) (count values)))
                (values i))
    :combine (vec (mapcat (fn [sub]
                             (let [v (sample sub s)]
                               (if (vector? v) v [v])))
                           (:distributions dist)))))

(defn sample
  "Materialize a distribution to a concrete value (uses the global sampler
  when none is given). Mirrors omni.replicator.core.sample."
  ([dist] (sample dist nil))
  ([dist s]
   (sample-kind dist (or s (sampler/global-sampler)))))
