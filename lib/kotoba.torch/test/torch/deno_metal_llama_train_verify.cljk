(ns torch.deno-metal-llama-train-verify
  "Mixed-precision GQA Llama block backward and AdamW on Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [torch.model :as model]
            [torch.num-backend :as nb]
            [torch.optim :as optim]
            [torch.train :as train]))

(def input-values [2 0 2 5 7 5 11 13])
(def target-values [0 2 5 7 5 11 13 -100])
(def vocabulary-size 32000)
(def embedding-size 128)
(def hidden-size 256)
(def input-shape [1 8])
(def target-shape [1 8])
(def parameter-names
  [:attn-norm :qw :kw :vw :ow :ffn-norm :gate :up :down])
(def parameter-paths
  (vec (concat [[0 :w]]
               (map #(vector 1 %) parameter-names)
               (map #(vector 2 %) parameter-names)
               [[3 :w] [4 :w]])))
(def adamw-options {:learning-rate 0.001 :weight-decay 0.0})

(defn- approx-vec? [expected actual absolute relative]
  (and (= (count expected) (count actual))
       (every? true? (map #(< (Math/abs (- %1 %2))
                              (+ absolute (* relative (Math/abs %1))))
                          expected actual))))

(defn- error-stats [expected actual]
  (let [errors (mapv #(Math/abs (- %1 %2)) expected actual)]
    {:max (reduce max 0.0 errors)
     :mean (/ (reduce + errors) (max 1 (count errors)))
     :reference-max (reduce max 0.0 (map #(Math/abs %) expected))}))

(defn- acceptable-error? [{:keys [max mean reference-max]}
                           max-atol range-rtol mean-atol]
  (and (< max (+ max-atol (* range-rtol reference-max)))
       (< mean mean-atol)))

(defn- arrays [entries]
  (mapv (fn [[layer key]] (get (nth entries layer) key)) parameter-paths))

(defn- release-pass! [pass]
  (arr/release! (:prediction pass))
  (when-let [gradients (:gradients pass)]
    (arr/release-all! (arrays gradients))))

(defn- nested-arrays [value]
  (cond
    (and (map? value) (:backend value) (:handle value)) [value]
    (map? value) (mapcat nested-arrays (vals value))
    (sequential? value) (mapcat nested-arrays value)
    :else []))

(defn- continue-training
  [backend model* input target state remaining losses samples]
  (.then
   (js/Promise.resolve (:loss state))
   (fn [loss]
     (arr/release! (:prediction state))
     (let [losses (conj losses loss)
           samples (conj samples (gpu/backend-stats backend))]
       (if (zero? remaining)
         {:state state :losses losses :samples samples}
         (.then
          (train/mixed-precision-adamw-step-async
           model* (:weights state) input target
           (:optimizer-state state) (:scaler state)
           {:autocast-dtype :f16 :loss :cross-entropy :ignore-index -100
            :release-inputs? true :adamw-options adamw-options})
          (fn [next-state]
            (continue-training backend model* input target next-state
                               (dec remaining) losses samples))))))))

(defn -main [& _]
  (let [model* (model/sequential
                (model/embedding vocabulary-size embedding-size)
                (model/llama-block embedding-size 4 hidden-size
                                   {:kv-heads 2 :position-offset 2})
                (model/llama-block embedding-size 4 hidden-size
                                   {:kv-heads 2 :position-offset 2})
                (model/rmsnorm embedding-size)
                (model/lm-head embedding-size vocabulary-size))
        cpu-backend (cpu/cpu-backend)
        scaler (optim/grad-scaler {:initial-scale 8.0 :growth-interval 2})
        cpu-weights (nb/random-weights cpu-backend model* 79)
        cpu-pass (train/loss-and-gradients
                  model* cpu-weights
                  (arr/from-vec cpu-backend input-values input-shape)
                  (arr/from-vec cpu-backend target-values target-shape)
                  {:loss :cross-entropy :ignore-index -100
                   :loss-scale (:scale scaler)})
        cpu-step (optim/scaled-adamw-step
                  cpu-weights (:gradients cpu-pass) nil scaler adamw-options)
        expected-prediction (arr/->vec (:prediction cpu-pass))
        expected-gradients (mapv arr/->vec (arrays (:gradients cpu-pass)))
        expected-weights (mapv arr/->vec (arrays (:weights cpu-step)))]
    (-> (gpu/request-device)
        (.then
         (fn [device]
           (let [backend (gpu/backend device)
                 started (.now js/performance)
                 weights (nb/random-weights backend model* 79)
                 input (arr/from-vec backend input-values input-shape)
                 target (arr/from-vec backend target-values target-shape)
                 pass (train/loss-and-gradients
                       model* weights input target
                       {:autocast-dtype :f16 :loss :cross-entropy
                        :ignore-index -100 :loss-scale (:scale scaler)})
                 step-weights (nb/random-weights backend model* 79)
                 step (train/mixed-precision-adamw-step-async
                       model* step-weights
                       input target
                       nil scaler {:autocast-dtype :f16
                                   :loss :cross-entropy :ignore-index -100
                                   :release-inputs? true
                                   :adamw-options adamw-options})]
             (.then
              step
              (fn [updated]
                (.then
                 (js/Promise.all
                  (into-array
                   (concat [(:loss pass) (arr/->vec (:prediction pass))]
                           (map arr/->vec (arrays (:gradients pass)))
                           (map arr/->vec (arrays (:weights updated))))))
                 (fn [values]
                   (let [values (vec (array-seq values))
                         actual-loss (nth values 0)
                         actual-prediction (vec (nth values 1))
                         parameter-count (count parameter-paths)
                         gradient-end (+ 2 parameter-count)
                         actual-gradients (mapv vec (subvec values 2 gradient-end))
                         actual-weights (mapv vec (subvec values gradient-end
                                                          (+ gradient-end
                                                             parameter-count)))
                         prediction-error (error-stats expected-prediction
                                                       actual-prediction)
                         gradient-errors (mapv error-stats expected-gradients
                                               actual-gradients)
                         prediction-ok? (acceptable-error? prediction-error
                                                           0.03 0.002 0.01)
                         gradients-ok? (every? #(acceptable-error? % 0.05 0.01 0.03)
                                               gradient-errors)
                         weights-ok? (every? true?
                                             (map #(approx-vec? %1 %2 0.03 0.01)
                                                  expected-weights actual-weights))
                         state-ok? (and (false? (:skipped? updated))
                                        (= 1 (get-in updated
                                                     [:optimizer-state :step]))
                                        (= :f16 (:dtype (:prediction pass)))
                                        (every? #(= :f32 (:dtype %))
                                                (arrays (:gradients pass))))
                         loss-ok? (< (Math/abs (- actual-loss (:loss cpu-pass)))
                                     0.02)
                         elapsed-ms (- (.now js/performance) started)
                         stats (gpu/backend-stats backend)
                         resource-ok? (and (< elapsed-ms 120000.0)
                                           (< (:peak-live-bytes stats)
                                              (* 512 1024 1024)))]
                     (println "adapter:"
                              (or (gpu/adapter-description device) "Apple Metal"))
                     (println "vocabulary:" vocabulary-size
                              "elapsed-ms:" elapsed-ms
                              "peak-live-bytes:" (:peak-live-bytes stats)
                              "live-bytes:" (:live-bytes stats))
                     (println (str "Llama LM F16 prediction: "
                                   (if prediction-ok? "passed" "failed")))
                     (println (str "Llama LM F16 21-parameter VJP: "
                                   (if gradients-ok? "passed" "failed")))
                     (println (str "Llama LM async AdamW: "
                                   (if (and weights-ok? state-ok? loss-ok?)
                                     "passed" "failed")))
                     (if-not (and prediction-ok? gradients-ok? weights-ok?
                                  state-ok? loss-ok? resource-ok?)
                       (do
                         (js/console.error
                          #js {:loss #js [(:loss cpu-pass) actual-loss]
                               :prediction prediction-ok?
                               :prediction-error (clj->js prediction-error)
                               :gradients gradients-ok?
                               :gradient-errors (clj->js gradient-errors)
                               :weights weights-ok?
                               :state state-ok?
                               :resources resource-ok?})
                         (.exit js/Deno 1))
                       (do
                         (release-pass! pass)
                         (arr/release-all! (arrays weights))
                         (.then
                          (continue-training backend model* input target updated
                                             3 [] [])
                          (fn [{:keys [state losses samples]}]
                            (let [live-bytes (mapv :live-bytes samples)
                                  live-buffers (mapv :live-buffers samples)
                                  small-live
                                  (mapv (fn [sample]
                                          (into (sorted-map)
                                                (filter (fn [[bytes _]]
                                                          (<= bytes 8192)))
                                                (:live-buffers-by-size sample)))
                                        samples)
                                  plateau? (apply = (take-last 3 live-bytes))
                                  decreasing? (every? true? (map > losses (rest losses)))]
                              (println "continued-losses:" losses)
                              (println "continued-live-bytes:" live-bytes)
                              (println "continued-live-buffers:" live-buffers)
                              (println "continued-small-live:" small-live)
                              (println (str "Llama LM memory plateau: "
                                            (if plateau? "passed" "failed")))
                              (println (str "Llama LM CE decreases: "
                                            (if decreasing? "passed" "failed")))
                              (arr/release-all!
                               (concat (arrays (:weights state))
                                       (nested-arrays (:optimizer-state state))
                                       [input target]))
                              (when-not (and plateau? decreasing?)
                                (.exit js/Deno 1)))))))))))))))
        (.catch (fn [error]
                  (js/console.error error)
                  (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
