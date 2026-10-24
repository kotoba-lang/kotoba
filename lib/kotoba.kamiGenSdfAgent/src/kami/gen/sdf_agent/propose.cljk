(ns kami.gen.sdf-agent.propose
  "Default v0 `:propose` implementation -- a deterministic, heuristic EDN-CSG-
  program generator, NOT an LLM call. This is the documented injection seam:
  `kami.gen.sdf-agent/generate` takes `:propose` as a `(fn [brief history] ->
  program)` and this namespace's `default-propose` is only the fixture/
  fallback wired in by default. A real deployment swaps in an LLM-backed
  function with the exact same signature (e.g. one that prompts a
  vision-or-text model with `brief` + the previous round's render + critique
  and parses its CSG-EDN response) -- no other code in this repo needs to
  change.

  `default-propose` builds a fixed 3-part CSG template (body / hood-head /
  beak union) sized from `brief` keywords on round 1, then on later rounds
  applies the previous round's `:edit-suggestion` (from the critique fn) as a
  literal, bounded numeric edit to that same template -- a real, observable
  round-over-round feedback loop, just not one driven by a language model in
  v0. World convention used throughout this repo: z is up, +y is \"front\"
  (the direction primitives like the beak point outward).")

(def front-axis :y)

(defn- wants? [brief re] (boolean (and brief (re-find re brief))))

(defn base-program
  "Round-1 baseline: a body sphere, a hood/head sphere stacked on top, and a
  forward-pointing beak cone -- sized generically, colored yellow only if
  `brief` mentions \"yellow\" (a stand-in for a real per-brief LLM read)."
  [brief]
  (let [body-r 1.0
        head-r 0.6
        head-z 1.35
        beak-r 0.16
        beak-h 0.30
        beak-color (if (wants? brief #"(?i)yellow") [0.95 0.78 0.05 1.0] [0.5 0.5 0.5 1.0])
        body-color [0.08 0.08 0.1 1.0]
        hood-color (if (wants? brief #"(?i)hood") [0.12 0.12 0.16 1.0] [0.5 0.5 0.5 1.0])]
    [:union
     [:sphere {:r body-r :center [0.0 0.0 0.0] :color body-color}]
     [:sphere {:r head-r :center [0.0 0.0 head-z] :color hood-color}]
     [:cone {:r beak-r :h beak-h :r2 0.0 :axis front-axis
             :at [0.0 (* head-r 0.82) head-z] :color beak-color}]]))

(defn- clamp [x lo hi] (max lo (min hi x)))

(defn apply-edit
  "Applies one `:edit-suggestion` map (as produced by
  `kami.gen.sdf-agent.critique`) to `program` (assumed to be
  `base-program`'s fixed `[:union body head beak]` shape). Unknown/`:noop`/
  `nil` edits return `program` unchanged. Factors are clamped to keep any
  single edit bounded (no runaway scale from a bad suggestion)."
  [program edit]
  (if (or (nil? edit) (= :noop (:op edit)))
    program
    (let [[u body head beak] program]
      (case (:op edit)
        :scale-axis
        (if (= :z (:axis edit))
          (let [factor (clamp (double (:factor edit 1.0)) 0.5 2.0)
                [head-tag head-p] head
                [beak-tag beak-p] beak
                new-z (* factor (nth (:center head-p) 2))]
            [u body
             [head-tag (assoc head-p :center (assoc (:center head-p) 2 new-z))]
             [beak-tag (assoc beak-p :at (assoc (:at beak-p) 2 new-z))]])
          program)

        :resize-part
        (if (= :beak (:part edit))
          (let [factor (clamp (double (:factor edit 1.0)) 0.4 2.5)
                [beak-tag beak-p] beak]
            [u body head
             [beak-tag (assoc beak-p :r (* factor (:r beak-p)) :h (* factor (:h beak-p)))]])
          program)

        program))))

(defn default-propose
  "`(fn [brief history] -> program)` -- the default v0 injection for
  `:propose`. `history` is the vector of prior round maps `generate` has
  accumulated so far (each with `:program` `:score` `:critique`)."
  [brief history]
  (if (empty? history)
    (base-program brief)
    (let [{:keys [program critique]} (last history)]
      (apply-edit program (:edit-suggestion critique)))))
