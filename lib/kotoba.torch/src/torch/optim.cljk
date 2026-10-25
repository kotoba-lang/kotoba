(ns torch.optim
  "Immutable optimizers over torch.train's weight/gradient layout."
  (:require [num.array :as arr]
            [num.core :as nm]
            [num.tensor :as t]))

(defn- fail [message data]
  (throw (ex-info (str "torch.optim: " message) data)))

(defn grad-scaler
  "Create immutable dynamic loss-scaling state."
  ([] (grad-scaler {}))
  ([options]
   (let [{:keys [initial-scale growth-factor backoff-factor growth-interval]}
         (merge {:initial-scale 65536.0 :growth-factor 2.0
                 :backoff-factor 0.5 :growth-interval 2000}
                options)]
     (when-not (and (pos? initial-scale) (> growth-factor 1.0)
                    (< 0.0 backoff-factor 1.0) (pos-int? growth-interval))
       (fail "invalid GradScaler options" {:options options}))
     {:scale initial-scale :growth-factor growth-factor
      :backoff-factor backoff-factor :growth-interval growth-interval
      :growth-tracker 0})))

(def scaler-float-keys
  "The GradScaler fields that are FLOATS, as data rather than as a list
  repeated at each caller.

  This exists because of a boundary, not because of a preference. A checkpoint
  descriptor crosses JSON, and JSON has one number type: `32.0` is written
  `32` and read back an integer, so a scaler that round-trips through a
  checkpoint comes back with `:scale 32` where it saved `32.0`. Nothing is
  numerically wrong at that instant, and everything downstream then does
  integer arithmetic where it did float arithmetic.

  The fix belongs HERE and not in the JSON writer: JSON cannot carry the
  distinction, so the layer that KNOWS the schema has to restore it."
  #{:scale :growth-factor :backoff-factor})

(def scaler-integer-keys
  "And the fields that are integers. Listed rather than derived as the rest,
  so a field added to the scaler has to be classified deliberately instead of
  inheriting whichever branch happens to be the default."
  #{:growth-interval :growth-tracker})

(defn restore-scaler
  "Restore SCALER's declared numeric types after a round trip that could not
  carry them. nil for nil, so a checkpoint without a scaler stays without one.

  Refuses an unknown shape rather than passing it through: a field this
  namespace does not classify is a field whose type nobody decided, and
  silently keeping whatever JSON returned is how the defect this function
  exists for got in."
  [scaler]
  (when scaler
    (when-not (= (set (keys scaler))
                 (into scaler-float-keys scaler-integer-keys))
      (fail "unknown GradScaler shape" {:keys (vec (sort (keys scaler)))}))
    (reduce-kv (fn [out k v]
                 (assoc out k (if (contains? scaler-float-keys k)
                                (double v)
                                (long v))))
               {} scaler)))

(defn- finite-number? [x]
  #?(:clj (Double/isFinite (double x))
     :cljs (js/isFinite x)))

(defn unscale-gradients
  "Divide aligned gradients by `scale`, returning gradients and overflow flag."
  [gradients scale]
  (when-not (and (number? scale) (pos? scale))
    (fail "scale must be positive" {:scale scale}))
  (let [found-inf? (volatile! false)
        unscaled
        (mapv (fn [gradient]
                (when gradient
                  (into {}
                        (map (fn [[key value]]
                               (let [xs (mapv (fn [x]
                                                (when-not (finite-number? x)
                                                  (vreset! found-inf? true))
                                                (/ x scale))
                                              (arr/->vec value))]
                                 [key (arr/from-vec (:backend value) xs (:shape value))])))
                        gradient)))
              gradients)]
    {:gradients unscaled :found-inf? @found-inf?}))

(defn update-grad-scaler
  "Grow the scale after stable steps or back it off after overflow."
  [scaler found-inf?]
  (if found-inf?
    (assoc scaler :scale (* (:scale scaler) (:backoff-factor scaler))
                  :growth-tracker 0)
    (let [tracker (inc (:growth-tracker scaler))]
      (if (= tracker (:growth-interval scaler))
        (assoc scaler :scale (* (:scale scaler) (:growth-factor scaler))
                      :growth-tracker 0)
        (assoc scaler :growth-tracker tracker)))))

(defn- update-parameter
  [parameter gradient moment variance step
   options]
  (t/adamw-step parameter gradient moment variance step options))

(defn- scalar-like [array value]
  (arr/from-vec (:backend array)
                (repeat (arr/nelems (:shape array)) value)
                (:shape array)))

(defn- scale [array value]
  (nm/mul array (scalar-like array value)))

(defn- validate-aligned! [weights gradients optimizer options]
  (when-not (= (count weights) (count gradients))
    (fail (str "invalid " optimizer " weights/gradients")
          {:weights (count weights) :gradients (count gradients)
           :options options}))
  (doseq [[weight gradient] (map vector weights gradients)]
    (when (or (not= (some? weight) (some? gradient))
              (and weight (not= (set (keys weight)) (set (keys gradient)))))
      (fail (str optimizer " parameter/gradient layout differs")
            {:parameters (some-> weight keys) :gradients (some-> gradient keys)}))))

(defn sgd-step
  "Apply one PyTorch-style SGD update without tensor readback.

  Supports momentum, dampening, coupled weight decay, Nesterov, and maximize.
  State is nil initially and then contains aligned momentum buffers. As in
  PyTorch, the first momentum buffer is initialized from the complete adjusted
  gradient and therefore does not apply dampening on its first step."
  ([weights gradients state] (sgd-step weights gradients state {}))
  ([weights gradients state options]
   (let [{:keys [learning-rate momentum dampening weight-decay nesterov maximize]
          :as normalized}
         (merge {:learning-rate 1.0e-3 :momentum 0.0 :dampening 0.0
                 :weight-decay 0.0 :nesterov false :maximize false}
                options)]
     (when-not (and (pos? learning-rate) (not (neg? momentum))
                    (not (neg? dampening)) (not (neg? weight-decay))
                    (boolean? nesterov) (boolean? maximize)
                    (or (not nesterov)
                        (and (pos? momentum) (zero? dampening))))
       (fail "invalid SGD options" {:options normalized}))
     (validate-aligned! weights gradients "SGD" normalized)
     (let [previous (or (:slots state) (vec (repeat (count weights) nil)))
           step (inc (long (or (:step state) 0)))
           results
           (mapv
            (fn [weight gradient slots]
              (when weight
                (into {}
                      (map
                       (fn [[key parameter]]
                         (let [raw-gradient (get gradient key)
                               adjusted (if (pos? weight-decay)
                                          (nm/add raw-gradient
                                                  (scale parameter weight-decay))
                                          raw-gradient)
                               old-buffer (get-in slots [key :momentum-buffer])
                               buffer (when (pos? momentum)
                                        (if old-buffer
                                          (nm/add (scale old-buffer momentum)
                                                  (scale adjusted (- 1.0 dampening)))
                                          adjusted))
                               direction (cond
                                           (and nesterov buffer)
                                           (nm/add adjusted (scale buffer momentum))
                                           buffer buffer
                                           :else adjusted)
                               delta (scale direction learning-rate)
                               parameter' ((if maximize nm/add nm/sub)
                                           parameter delta)]
                           [key {:parameter parameter'
                                 :momentum-buffer buffer}]))
                       weight))))
            weights gradients previous)]
       {:weights
        (mapv (fn [result]
                (when result
                  (into {} (map (fn [[key value]] [key (:parameter value)])) result)))
              results)
        :state
        {:step step
         :slots
         (mapv (fn [result]
                 (when result
                   (into {}
                         (keep (fn [[key value]]
                                 (when-let [buffer (:momentum-buffer value)]
                                   [key {:momentum-buffer buffer}])))
                         result)))
               results)}}))))

(defn adamw-step
  "Apply one AdamW update.

  `weights` and `gradients` use torch.train's aligned vector-of-parameter-maps
  layout. `state` is nil initially, then the returned `:state`."
  ([weights gradients state]
   (adamw-step weights gradients state {}))
  ([weights gradients state options]
   (let [{:keys [learning-rate beta1 beta2 eps weight-decay]
          :as normalized-options}
         (merge {:learning-rate 1.0e-3
                 :beta1 0.9
                 :beta2 0.999
                 :eps 1.0e-8
                 :weight-decay 0.01}
                options)]
     (when-not (and (= (count weights) (count gradients))
                  (pos? learning-rate) (< 0.0 beta1 1.0) (< 0.0 beta2 1.0)
                  (pos? eps) (not (neg? weight-decay)))
       (fail "invalid AdamW inputs/options" {:options normalized-options}))
     (let [step (inc (long (or (:step state) 0)))
         previous-slots (or (:slots state) (vec (repeat (count weights) nil)))
         results
         (mapv
          (fn [weight gradient slot]
            (when weight
              (when-not (= (set (keys weight)) (set (keys gradient)))
                (fail "parameter/gradient keys differ"
                      {:parameters (keys weight) :gradients (keys gradient)}))
              (into {}
                    (map (fn [[key parameter]]
                           (let [old-m (get-in slot [key :moment])
                                 old-v (get-in slot [key :variance])]
                             [key (update-parameter parameter (get gradient key)
                                                    old-m old-v step
                                                    normalized-options)])))
                    weight)))
          weights gradients previous-slots)
         next-weights
         (mapv (fn [result]
                 (when result
                   (into {} (map (fn [[key values]] [key (:parameter values)])) result)))
               results)
         next-slots
         (mapv (fn [result]
                 (when result
                   (into {} (map (fn [[key values]]
                                   [key {:moment (:moment values)
                                         :variance (:variance values)}])) result)))
               results)]
       {:weights next-weights :state {:step step :slots next-slots}}))))

(defn scaled-adamw-step
  "Unscale gradients and conditionally apply AdamW.

  On overflow, weights and optimizer state are returned unchanged while the
  scaler backs off. `:skipped?` makes the control-flow decision explicit."
  ([weights scaled-gradients optimizer-state scaler]
   (scaled-adamw-step weights scaled-gradients optimizer-state scaler {}))
  ([weights scaled-gradients optimizer-state scaler options]
   (let [{:keys [gradients found-inf?]}
         (unscale-gradients scaled-gradients (:scale scaler))
         next-scaler (update-grad-scaler scaler found-inf?)]
     (if found-inf?
       {:weights weights :optimizer-state optimizer-state
        :scaler next-scaler :skipped? true}
       (let [{:keys [weights state]}
             (adamw-step weights gradients optimizer-state options)]
         {:weights weights :optimizer-state state
          :scaler next-scaler :skipped? false})))))

(defn- device-unscale-gradients [gradients scale]
  (let [results
        (mapv (fn [gradient]
                (when gradient
                  (into {} (map (fn [[key value]]
                                  [key (t/unscale-gradient value scale)]))
                        gradient)))
              gradients)]
    {:gradients
     (mapv (fn [gradient]
             (when gradient
               (into {} (map (fn [[key result]] [key (:gradient result)]))
                     gradient)))
           results)
     :flags (vec (mapcat (fn [gradient]
                           (map (comp :found-inf val) gradient))
                         (remove nil? results)))}))

(defn- gradient-arrays [gradients]
  (mapcat (fn [gradient] (when gradient (vals gradient))) gradients))

(defn scaled-adamw-step-async
  "Asynchronously unscale/check gradients and apply AdamW without tensor readback.

  On ClojureScript this returns a Promise. Device backends download only one
  scalar overflow flag per parameter; unscaled gradients, weights, and AdamW
  slots remain device-resident. JVM returns an already-completed
  CompletableFuture with the same result shape."
  ([weights scaled-gradients optimizer-state scaler]
   (scaled-adamw-step-async weights scaled-gradients optimizer-state scaler {}))
  ([weights scaled-gradients optimizer-state scaler options]
   (let [{:keys [gradients flags]}
         (device-unscale-gradients scaled-gradients (:scale scaler))
         finish
         (fn [flag-values]
           (let [found-inf? (boolean (some #(pos? (first %)) flag-values))
                 next-scaler (update-grad-scaler scaler found-inf?)]
             (if found-inf?
               (do
                 (arr/release-all! (concat flags (gradient-arrays gradients)))
                 {:weights weights :optimizer-state optimizer-state
                  :scaler next-scaler :skipped? true})
               (let [{:keys [weights state]}
                     (adamw-step weights gradients optimizer-state options)]
                 (arr/release-all! (concat flags (gradient-arrays gradients)))
                 {:weights weights :optimizer-state state
                  :scaler next-scaler :skipped? false}))))]
     #?(:cljs
        (.then (js/Promise.all
                (into-array
                 (map (fn [flag]
                        (js/Promise.resolve (arr/->vec flag))) flags)))
               (fn [values] (finish (vec (js/Array.from values)))))
        :clj
        (java.util.concurrent.CompletableFuture/completedFuture
         (finish (mapv arr/->vec flags)))))))
