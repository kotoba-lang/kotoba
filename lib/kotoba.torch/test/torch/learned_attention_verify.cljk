(ns torch.learned-attention-verify
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [torch.model :as model]
            [torch.num-backend :as nb]
            [torch.train :as train]))

(defn -main [& _]
  (let [backend (cpu/cpu-backend)
        model* (model/sequential (model/multihead-attention 4 2))
        weights (nb/random-weights backend model* 29)
        input (arr/from-vec backend
                            [0.2 -0.1 0.3 0.4, -0.2 0.1 0.5 -0.3,
                             0.6 0.2 -0.4 0.1] [3 4])
        target (arr/from-vec backend
                             [0.1 0.0 0.2 -0.1, 0.0 0.2 0.1 0.3,
                              -0.2 0.1 0.0 0.2] [3 4])
        first-pass (train/loss-and-gradients model* weights input target)
        trained (last (take 21 (iterate
                                (fn [{:keys [weights]}]
                                  (train/sgd-step model* weights input target 0.05))
                                {:weights weights})))]
    (when-not (and (= [3 4] (:shape (:prediction first-pass)))
                   (= #{:qw :qb :kw :kb :vw :vb :ow :ob}
                      (set (keys (first (:gradients first-pass)))))
                   (< (:loss trained) (:loss first-pass)))
      (throw (js/Error. "ClojureScript learned attention training failed")))
    (println "CLJS learned MultiheadAttention: passed")
    (println "loss:" (:loss first-pass) "->" (:loss trained))))

(set! *main-cli-fn* -main)
