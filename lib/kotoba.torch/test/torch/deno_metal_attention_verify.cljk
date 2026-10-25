(ns torch.deno-metal-attention-verify
  "Learned Q/K/V/output attention forward and full VJP parity on Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [torch.core :as core]
            [torch.model :as model]
            [torch.num-backend :as nb]
            [torch.optim :as optim]
            [torch.train :as train]))

(def input-values
  [0.2 -0.1 0.3 0.4, -0.2 0.1 0.5 -0.3, 0.6 0.2 -0.4 0.1,
   -0.1 0.4 0.2 -0.5, 0.3 -0.2 0.1 0.6, -0.4 0.5 0.2 0.0])

(def upstream-values
  [0.3 -0.2 0.5 0.1, -0.4 0.6 -0.1 0.2, 0.2 -0.3 0.4 -0.5,
   -0.2 0.1 0.3 0.4, 0.5 -0.4 0.2 -0.1, 0.1 0.2 -0.3 0.6])

(def target-values
  [0.1 0.0 0.2 -0.1, 0.0 0.2 0.1 0.3, -0.2 0.1 0.0 0.2,
   0.0 -0.1 0.3 0.2, 0.2 0.1 -0.2 0.0, -0.1 0.3 0.1 0.2])

(def input-shape [2 3 4])

(def context-values
  [0.1 0.3 -0.2 0.4, 0.5 -0.1 0.2 0.0,
   -0.3 0.2 0.1 0.6, 0.4 -0.2 0.5 0.1])

(def context-shape [2 2 4])

(def parameter-names [:qw :qb :kw :kb :vw :vb :ow :ob])

(defn- execution-options [backend]
  {:layer-options
   [{:context (arr/from-vec backend context-values context-shape)
     :key-padding-mask (arr/from-vec backend [0 1, 0 0] [2 2])}]})

(defn- approx-vec? [expected actual tolerance]
  (and (= (count expected) (count actual))
       (every? true? (map #(< (Math/abs (- %1 %2)) tolerance)
                          expected actual))))

(defn- run-vjp [backend model*]
  (let [weights (nb/random-weights backend model* 29)]
    (train/prediction-and-gradients
     model* weights
     (arr/from-vec backend input-values input-shape)
     (arr/from-vec backend upstream-values input-shape)
     (execution-options backend))))

(defn- run-inference [backend model*]
  (let [weights (nb/random-weights backend model* 29)]
    (core/run (nb/num-backend backend weights) model*
              (arr/from-vec backend input-values input-shape)
              (execution-options backend))))

(defn- run-mse [backend model*]
  (let [weights (nb/random-weights backend model* 29)]
    (train/loss-and-gradients
     model* weights
     (arr/from-vec backend input-values input-shape)
     (arr/from-vec backend target-values input-shape)
     (execution-options backend))))

(defn- run-training [backend model* steps]
  (let [input (arr/from-vec backend input-values input-shape)
        target (arr/from-vec backend target-values input-shape)]
    (loop [step 0
           weights (nb/random-weights backend model* 29)
           losses []]
      (if (= step steps)
        {:weights weights :losses losses}
        (let [result (train/sgd-step model* weights input target 0.05
                                     (execution-options backend))]
          (recur (inc step) (:weights result) (conj losses (:loss result))))))))

(def adamw-options
  {:learning-rate 0.01 :beta1 0.9 :beta2 0.999
   :eps 1.0e-8 :weight-decay 0.001})

(def sgd-options
  {:learning-rate 0.03 :momentum 0.9 :weight-decay 0.001
   :nesterov true})

(defn- run-stateful-sgd-training [backend model* steps]
  (let [input (arr/from-vec backend input-values input-shape)
        target (arr/from-vec backend target-values input-shape)]
    (loop [step 0 weights (nb/random-weights backend model* 29)
           state nil losses []]
      (if (= step steps)
        {:weights weights :state state :losses losses}
        (let [{:keys [loss gradients]}
              (train/loss-and-gradients model* weights input target
                                        (execution-options backend))
              update (optim/sgd-step weights gradients state sgd-options)]
          (recur (inc step) (:weights update) (:state update)
                 (conj losses loss)))))))

(defn- sgd-arrays [training]
  (let [weights (first (:weights training))
        slots (first (get-in training [:state :slots]))]
    (into {}
          (mapcat (fn [key]
                    [[(keyword (str "sgd-weight-" (name key))) (get weights key)]
                     [(keyword (str "sgd-momentum-" (name key)))
                      (get-in slots [key :momentum-buffer])]])
                  parameter-names))))

(defn- run-adamw-training [backend model* steps]
  (let [input (arr/from-vec backend input-values input-shape)
        target (arr/from-vec backend target-values input-shape)]
    (loop [step 0 weights (nb/random-weights backend model* 29)
           state nil losses []]
      (if (= step steps)
        {:weights weights :state state :losses losses}
        (let [{:keys [loss gradients]}
              (train/loss-and-gradients model* weights input target
                                        (execution-options backend))
              update (optim/adamw-step weights gradients state adamw-options)]
          (recur (inc step) (:weights update) (:state update)
                 (conj losses loss)))))))

(defn- adamw-arrays [training]
  (let [weights (first (:weights training))
        slots (first (get-in training [:state :slots]))]
    (into {}
          (mapcat (fn [key]
                    [[(keyword (str "adamw-weight-" (name key))) (get weights key)]
                     [(keyword (str "adamw-moment-" (name key)))
                      (get-in slots [key :moment])]
                     [(keyword (str "adamw-variance-" (name key)))
                      (get-in slots [key :variance])]])
                  parameter-names))))

(defn- scaled-fixture [backend model*]
  (let [weights (nb/random-weights backend model* 29)
        scaler (optim/grad-scaler {:initial-scale 8.0 :growth-interval 2})
        result (train/loss-and-gradients
                model* weights
                (arr/from-vec backend input-values input-shape)
                (arr/from-vec backend target-values input-shape)
                (assoc (execution-options backend) :loss-scale (:scale scaler)))]
    {:weights weights :gradients (:gradients result) :scaler scaler}))

(defn- flatten-result [result]
  (merge {:prediction (:prediction result)
          :input-gradient (:input-gradient result)
          :context-gradient
          (:context (first (:layer-input-gradients result)))}
         (first (:gradients result))))

(defn- prefix-keys [prefix entries]
  (into {} (map (fn [[label value]]
                  [(keyword (str prefix (name label))) value])) entries))

(defn- ->promise [value]
  (if (instance? js/Promise value) value (js/Promise.resolve value)))

(defn -main [& _]
  (let [model* (model/sequential
                (model/multihead-attention
                 4 2 {:rope? true :rope-theta 10000.0
                      :position-offset 3 :context-position-offset 7}))
        cpu-backend (cpu/cpu-backend)
        expected-vjp (assoc (into {}
                            (map (fn [[label array]] [label (arr/->vec array)]))
                            (flatten-result (run-vjp cpu-backend model*)))
                            :inference (arr/->vec
                                        (run-inference cpu-backend model*)))
        cpu-mse (run-mse cpu-backend model*)
        cpu-training (run-training cpu-backend model* 8)
        cpu-stateful-sgd (run-stateful-sgd-training cpu-backend model* 4)
        cpu-adamw (run-adamw-training cpu-backend model* 4)
        cpu-scaled-fixture (scaled-fixture cpu-backend model*)
        cpu-scaled (optim/scaled-adamw-step
                    (:weights cpu-scaled-fixture)
                    (:gradients cpu-scaled-fixture) nil
                    (:scaler cpu-scaled-fixture) adamw-options)
        expected-adamw (into {} (map (fn [[label array]]
                                       [label (arr/->vec array)]))
                             (adamw-arrays cpu-adamw))
        expected-stateful-sgd
        (into {} (map (fn [[label array]] [label (arr/->vec array)]))
              (sgd-arrays cpu-stateful-sgd))
        expected-trained
        (prefix-keys "trained-"
                     (into {}
                           (map (fn [[label array]] [label (arr/->vec array)]))
                           (first (:weights cpu-training))))
        expected-mse
        (prefix-keys "mse-"
                     (into {:prediction (arr/->vec (:prediction cpu-mse))
                            :context-gradient
                            (arr/->vec
                             (:context (first (:layer-input-gradients cpu-mse))))}
                           (map (fn [[label array]] [label (arr/->vec array)]))
                           (first (:gradients cpu-mse))))]
    (-> (gpu/request-device)
        (.then
         (fn [device]
           (let [backend (gpu/backend device)
                 actual-vjp (assoc (flatten-result (run-vjp backend model*))
                                   :inference (run-inference backend model*))
                 actual-mse-pass (run-mse backend model*)
                 actual-training (run-training backend model* 8)
                 actual-stateful-sgd (run-stateful-sgd-training backend model* 4)
                 actual-adamw (run-adamw-training backend model* 4)
                 gpu-scaled-fixture (scaled-fixture backend model*)
                 actual-mse
                 (prefix-keys "mse-"
                              (into {:prediction (:prediction actual-mse-pass)
                                     :context-gradient
                                     (:context
                                      (first (:layer-input-gradients actual-mse-pass)))}
                                    (first (:gradients actual-mse-pass))))
                 passed (atom 0)
                 check-array
                 (fn [expected label array]
                   (.then
                    (arr/->vec array)
                    (fn [values]
                      (let [tolerance (if (or (.startsWith (name label) "adamw-weight-")
                                              (.startsWith (name label) "sgd-weight-"))
                                        1.0e-3 2.0e-4)]
                        (when-not (approx-vec? (get expected label) values tolerance)
                        (throw (js/Error.
                                (str "Metal " (name label) " diverged from CPU: "
                                     (get expected label) " vs " values)))))
                      (swap! passed inc)
                      (println "✓" (name label)))))
                 array-checks
                 (concat (map (fn [[label array]]
                                (check-array expected-vjp label array))
                              actual-vjp)
                         (map (fn [[label array]]
                                (check-array expected-mse label array))
                              actual-mse)
                         (map (fn [[label array]]
                                (check-array expected-trained label array))
                              (prefix-keys "trained-"
                                           (first (:weights actual-training))))
                         (map (fn [[label array]]
                                (check-array expected-adamw label array))
                              (adamw-arrays actual-adamw))
                         (map (fn [[label array]]
                                (check-array expected-stateful-sgd label array))
                              (sgd-arrays actual-stateful-sgd)))
                 loss-check
                 (.then (->promise (:loss actual-mse-pass))
                        (fn [loss]
                          (when-not (< (Math/abs (- loss (:loss cpu-mse))) 2.0e-4)
                            (throw (js/Error. "Metal MSE loss diverged from CPU")))
                          (swap! passed inc)
                          (println "✓ mse-loss")))
                 training-loss-check
                 (.then
                  (js/Promise.all (into-array (map ->promise (:losses actual-training))))
                  (fn [loss-array]
                    (let [actual-losses (vec (js/Array.from loss-array))
                          expected-losses (:losses cpu-training)]
                      (when-not (and (approx-vec? expected-losses actual-losses 2.0e-4)
                                     (< (last actual-losses) (first actual-losses)))
                        (throw (js/Error. "Metal SGD loss trajectory diverged")))
                      (swap! passed inc)
                      (println "✓ trained-losses" actual-losses))))
                 adamw-loss-check
                 (.then
                  (js/Promise.all (into-array (map ->promise (:losses actual-adamw))))
                  (fn [loss-array]
                    (let [actual-losses (vec (js/Array.from loss-array))]
                      (when-not (and (approx-vec? (:losses cpu-adamw)
                                                  actual-losses 2.0e-4)
                                     (< (last actual-losses) (first actual-losses)))
                        (throw (js/Error. "Metal AdamW loss trajectory diverged")))
                      (swap! passed inc)
                      (println "✓ adamw-losses" actual-losses))))
                 stateful-sgd-loss-check
                 (.then
                  (js/Promise.all
                   (into-array (map ->promise (:losses actual-stateful-sgd))))
                  (fn [loss-array]
                    (let [actual-losses (vec (js/Array.from loss-array))]
                      (when-not
                       (and (approx-vec? (:losses cpu-stateful-sgd)
                                         actual-losses 2.0e-4)
                            (< (last actual-losses) (first actual-losses)))
                        (throw (js/Error. "Metal stateful SGD trajectory diverged")))
                      (swap! passed inc)
                      (println "✓ stateful-sgd-losses" actual-losses))))
                 scaled-control-check
                 (.then
                  (optim/scaled-adamw-step-async
                   (:weights gpu-scaled-fixture)
                   (:gradients gpu-scaled-fixture) nil
                   (:scaler gpu-scaled-fixture) adamw-options)
                  (fn [finite]
                    (when (or (:skipped? finite)
                              (not= 1 (get-in finite [:optimizer-state :step]))
                              (not= 1 (get-in finite [:scaler :growth-tracker])))
                      (throw (js/Error. "Metal async scaled AdamW finite control failed")))
                    (let [overflow-gradients
                          (assoc-in (:gradients gpu-scaled-fixture) [0 :qb]
                                    (arr/from-vec backend
                                                  [js/Infinity 0.0 0.0 0.0] [4]))]
                      (.then
                       (js/Promise.all
                        #js [(arr/->vec (get-in finite [:weights 0 :qw]))
                             (arr/->vec (get-in cpu-scaled [:weights 0 :qw]))
                             (optim/scaled-adamw-step-async
                              (:weights gpu-scaled-fixture) overflow-gradients nil
                              (:scaler gpu-scaled-fixture) adamw-options)])
                       (fn [values]
                         (let [gpu-weight (aget values 0)
                               cpu-weight (aget values 1)
                               overflow (aget values 2)]
                           (when-not (approx-vec? cpu-weight gpu-weight 1.0e-3)
                             (throw (js/Error. "Metal scaled AdamW weight diverged")))
                           (when-not (and (:skipped? overflow)
                                          (nil? (:optimizer-state overflow))
                                          (= 4.0 (get-in overflow [:scaler :scale])))
                             (throw (js/Error. "Metal async overflow skip failed")))
                           (swap! passed inc)
                           (println "✓ async-scaled-adamw finite+overflow")))))))]
             (println "adapter:" (gpu/adapter-description device))
             (-> (js/Promise.all
                  (into-array (conj (vec array-checks)
                                    loss-check training-loss-check adamw-loss-check
                                    stateful-sgd-loss-check scaled-control-check)))
                 (.then (fn [_]
                          (println (str "Metal learned MultiheadAttention training: "
                                        @passed " passed"))))))))
        (.catch (fn [error]
                  (js/console.error (or (.-stack error) error))
                  (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
