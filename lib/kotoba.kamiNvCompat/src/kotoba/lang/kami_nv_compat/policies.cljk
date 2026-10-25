(ns kotoba.lang.kami-nv-compat.policies
  "MLP policy-checkpoint loader + runner — JVM port of kami-nv-compat's
  src/policies/mlp.ts (ADR-2605261800 §D6). Bridges externally-trained RL
  policies (stable-baselines3 / rsl_rl / Isaac Lab) into a pure MLP forward
  kernel (ReLU hidden, tanh output).

  Wave-1 exemplar of the kami-nv-compat TS->CLJC port (ADR-2607020130).

  JVM (.clj, not .cljc): the one platform seam here is JSON I/O
  (json.data-json); the MLP math is pure. A cljs branch (js/JSON + the same
  math) is a follow-up if a browser consumer materializes -- matching
  witness-quorum / pqh / checkpointer's JVM-first precedent.

  mulberry32 + mlp-policy-forward are inlined here from src/warp/examples.ts
  (the full warp wave is #16); they relocate to a kotoba.lang.kami-nv-compat.warp
  namespace when that wave lands, and this namespace will require it then.

  The on-disk JSON schema is snake_case:
    {:type \"mlp_policy\" :version 1 :obs_dim :hidden_dim :action_dim
     :W1_flat (hidden×obs row-major) :b1 :W2_flat (action×hidden) :b2}.
  Internally the spec map uses those same snake_case keyword keys (the wire
  shape, unchanged), so load/serialize is a direct JSON<->map translation."
  (:require [json.data-json :as json]))

;; ── mulberry32 + MLP forward kernel (inlined from src/warp/examples.ts) ────

(defn- mulberry32
  "Deterministic PRNG (mulberry32): returns a zero-arg fn producing doubles in
  [0,1). Port of src/warp/examples.ts. uint32 arithmetic is kept as positive
  longs (bit-and 0xFFFFFFFF) so bit-shift-right behaves as JS's unsigned >>>."
  [seed]
  (let [s (volatile! (bit-and (long seed) 0xFFFFFFFF))]
    (fn []
      (vswap! s (fn [x] (bit-and (+ x 0x6D2B79F5) 0xFFFFFFFF)))
      (let [t0 @s
            a  (bit-xor t0 (bit-shift-right t0 15))
            t1 (bit-and (unchecked-multiply a (bit-or t0 1)) 0xFFFFFFFF)
            b  (bit-xor t1 (bit-shift-right t1 7))
            im (bit-and (unchecked-multiply b (bit-or t1 61)) 0xFFFFFFFF)
            t2 (bit-xor t1 (bit-and (+ t1 im) 0xFFFFFFFF))
            t3 (bit-xor t2 (bit-shift-right t2 14))]
        (/ (double (bit-and t3 0xFFFFFFFF)) 4294967296.0)))))

(defn- mlp-policy-forward
  "MLP forward kernel (ReLU hidden, tanh output): port of src/warp/examples.ts
  mlpPolicyForwardInline. obs is envs×obs-dim flat (row-major). Returns a flat
  env-major vector of length envs×action-dim."
  [obs w1 b1 w2 b2 obs-dim hidden-dim action-dim]
  (let [n-envs (quot (count obs) obs-dim)
        hidden-per-env (vec
                         (for [env (range n-envs)]
                           (vec
                             (for [h (range hidden-dim)]
                               (let [s (loop [o 0 acc (double (nth b1 h))]
                                         (if (>= o obs-dim) acc
                                           (recur (inc o)
                                                  (+ acc (* (nth w1 (+ (* h obs-dim) o))
                                                            (nth obs (+ (* env obs-dim) o)))))))]
                                 (if (pos? s) s 0.0))))))]
    (vec
      (for [env (range n-envs)
            a   (range action-dim)
            :let [hidden (nth hidden-per-env env)]]
        (let [s (loop [h 0 acc (double (nth b2 a))]
                  (if (>= h hidden-dim) acc
                    (recur (inc h)
                           (+ acc (* (nth w2 (+ (* a hidden-dim) h))
                                     (nth hidden h))))))]
          (Math/tanh s))))))

;; ── spec loaders / serializer / runner ────────────────────────────────────

(defn- num-field
  [raw key]
  (let [v (get raw key)]
    (when-not (integer? v)
      (throw (ex-info (str "load-mlp-from-json: '" (name key) "' must be integer")
                      {:key key :value v})))
    (long v)))

(defn- float-array-field
  [raw key expected-len]
  (let [v (get raw key)]
    (when-not (sequential? v)
      (throw (ex-info (str "load-mlp-from-json: '" (name key) "' must be array")
                      {:key key :value v})))
    (let [got (count v)]
      (when (not= got expected-len)
        (throw (ex-info (str "load-mlp-from-json: '" (name key) "' length=" got
                             ", expected " expected-len)
                        {:key key :got got :expected expected-len}))))
    (vec v)))

(defn load-mlp-from-json
  "Parse + validate an MLP policy spec. Accepts a JSON string or an already-
  parsed map (keyword-keyed)."
  [input]
  (let [raw (if (string? input) (json/read-str input :key-fn keyword) input)]
    (when (not= "mlp_policy" (:type raw))
      (throw (ex-info "load-mlp-from-json: expected type='mlp_policy'"
                      {:type (:type raw)})))
    (when (not= 1 (:version raw))
      (throw (ex-info "load-mlp-from-json: unsupported version (this loader handles version 1)"
                      {:version (:version raw)})))
    (let [obs-dim    (num-field raw :obs_dim)
          hidden-dim (num-field raw :hidden_dim)
          action-dim (num-field raw :action_dim)]
      (when (or (< obs-dim 1) (< hidden-dim 1) (< action-dim 1))
        (throw (ex-info "load-mlp-from-json: dims must be >=1"
                        {:obs_dim obs-dim :hidden_dim hidden-dim :action_dim action-dim})))
      (when (> hidden-dim 128)
        (throw (ex-info "load-mlp-from-json: hidden_dim exceeds kernel MAX_HIDDEN=128"
                        {:hidden_dim hidden-dim})))
      (when (> obs-dim 64)
        (throw (ex-info "load-mlp-from-json: obs_dim exceeds kernel MAX_OBS=64"
                        {:obs_dim obs-dim})))
      (let [w1 (float-array-field raw :W1_flat (* hidden-dim obs-dim))
            b1 (float-array-field raw :b1 hidden-dim)
            w2 (float-array-field raw :W2_flat (* action-dim hidden-dim))
            b2 (float-array-field raw :b2 action-dim)]
        {:type "mlp_policy" :version 1
         :obs_dim obs-dim :hidden_dim hidden-dim :action_dim action-dim
         :W1_flat w1 :b1 b1 :W2_flat w2 :b2 b2}))))

(defn serialize-mlp-to-json
  "Round-trip serializer (the on-disk schema is snake_case). `pretty` indents
  when truthy."
  ([spec] (serialize-mlp-to-json spec false))
  ([spec pretty]
   (let [m (array-map
             :type (:type spec) :version (:version spec)
             :obs_dim (:obs_dim spec) :hidden_dim (:hidden_dim spec) :action_dim (:action_dim spec)
             :W1_flat (vec (:W1_flat spec)) :b1 (vec (:b1 spec))
             :W2_flat (vec (:W2_flat spec)) :b2 (vec (:b2 spec)))]
     (if pretty
       (json/write-str m :indent true)
       (json/write-str m)))))

(defn make-random-mlp-spec
  "Deterministic random MLP fixture (mulberry32 -> He-ish init)."
  [obs-dim hidden-dim action-dim seed]
  (let [rng         (mulberry32 seed)
        he-scale-1  (Math/sqrt (/ 2.0 obs-dim))
        he-scale-2  (Math/sqrt (/ 2.0 hidden-dim))
        w1 (vec (for [_ (range (* hidden-dim obs-dim))]
                  (* (- (* (rng) 2) 1) he-scale-1)))
        b1 (vec (repeat hidden-dim 0))
        w2 (vec (for [_ (range (* action-dim hidden-dim))]
                  (* (- (* (rng) 2) 1) he-scale-2)))
        b2 (vec (repeat action-dim 0))]
    {:type "mlp_policy" :version 1
     :obs_dim obs-dim :hidden_dim hidden-dim :action_dim action-dim
     :W1_flat w1 :b1 b1 :W2_flat w2 :b2 b2}))

(defn run-mlp-policy
  "Run the spec on a flat observation buffer (envs × obs-dim). Returns a flat
  action vector (envs × action-dim)."
  [spec obs]
  (let [obs-dim (:obs_dim spec)]
    (when-not (zero? (mod (count obs) obs-dim))
      (throw (ex-info "run-mlp-policy: obs length not a multiple of obs_dim"
                      {:obs-length (count obs) :obs_dim obs-dim})))
    (mlp-policy-forward obs (:W1_flat spec) (:b1 spec) (:W2_flat spec) (:b2 spec)
                        obs-dim (:hidden_dim spec) (:action_dim spec))))
