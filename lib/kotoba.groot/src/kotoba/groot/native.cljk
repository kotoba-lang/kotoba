(ns kotoba.groot.native
  "The KAMI-native default policy backend: a small affine policy
  (`a = W*obs + b`) and the `[-1,1] -> joint-limit` rescale.

  These are the two pure functions the Rust `kami-groot` crate pulled from
  a sibling crate, `kami-shugyo` (`kami-shugyo/src/policy.rs`
  `LinearPolicy::{zeros,act_batch}` and `rescale_to_limits`). They are
  inlined here rather than depending on a `kotoba.shugyo` port, because
  `kami-groot` only ever used this affine slice of `kami-shugyo` — the
  rest of that crate (vectorized env simulation, `random_search`
  gradient-free training) is a whole separate RL-training-framework port
  and stays out of scope for `kotoba.groot` (see README `Honestly still
  open` / unported items).")

(defn- finite?
  [x]
  #?(:clj  (Double/isFinite (double x))
     :cljs (js/isFinite x)))

(defn linear-policy-zeros
  "A zero-initialized affine policy (`obs-dim -> act-dim`). A zeros policy
  emits `b` unconditionally, i.e. after `rescale-to-limits` the joint-limit
  midpoint."
  [obs-dim act-dim]
  {:policy/obs-dim obs-dim
   :policy/act-dim act-dim
   :policy/w       (vec (repeat (* obs-dim act-dim) 0.0))
   :policy/b       (vec (repeat act-dim 0.0))})

(defn linear-policy-act
  "Map a single-env observation row (`[obs-dim]`) to an action row
  (`[act-dim]`) via `a = W*obs + b` (row-major `w[a*obs-dim + o]`)."
  [{:policy/keys [obs-dim act-dim w b]} obs]
  (vec
   (for [a (range act-dim)]
     (+ (nth b a)
        (reduce + (map * (subvec w (* a obs-dim) (* (inc a) obs-dim)) obs))))))

(defn rescale-to-limits
  "Map a normalized `[-1,1]` action (`[n-dof]`) to joint targets in
  `[lower upper]` per DOF — the standard Isaac Lab action pipeline (a
  squashed policy outputs `[-1,1]`; the env rescales to the joint range).
  `limits` is `[n-dof]` of `[lower upper]`. A DOF with a non-finite limit
  (unbounded joint) passes its (unclamped) action through unchanged."
  [normalized limits]
  (vec
   (map (fn [x [lo hi]]
          (let [a (max -1.0 (min 1.0 x))]
            (if (and (finite? lo) (finite? hi))
              (+ lo (* (+ (* a 0.5) 0.5) (- hi lo)))
              x)))
        normalized limits)))
