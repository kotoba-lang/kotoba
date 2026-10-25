(ns etzhayyim.ie-flow.coscientist
  "ie-flow.coscientist — the Google 'AI co-scientist' lifecycle, generalised over the information-
  energy flow so EVERY actor can run it. ADR-2606211200 (generalises ibuki's ADR-2606201200).

  Generate → Reflect → Rank → Evolve → Meta-review, but the fitness is the IE-flow yardstick
  (Δnet-gain + Δorder-index, weighted by 子孫 wellbecoming, per unit cost): each beat the actor
  proposes candidate SOCIETAL INTERVENTIONS that would make its flow pay for itself AND rectify
  scattered flow into returned structure (秩序化), critiques them against the Charter, runs a
  deterministic Elo tournament, evolves the winners, and hands the top reviewed hypothesis to the
  lifecycle as a PRE-REGISTERED experiment.

  The generation is a charter-clean CATALOG, never an LLM free-write, so a predatory mechanism is
  structurally unrepresentable — the SAME aligned/forbidden vocabulary every organism shares. The
  Murakumo fleet narrates the meta-review (the actor reasons in words) but never the structured
  generation. PURE + deterministic (no wall clock, no randomness)."
  (:require [kotoba.lang.text :as str]))

;; ── the shared safety vocabulary (identical to ibuki.coscientist) ───────────

(def aligned-mechanisms
  "The only mechanisms by which an actor may act on society — reciprocal, transparent, non-
  extractive. A mechanism outside this set cannot enter the tournament (G-mechanism)."
  #{"open-publication" "reciprocal-request" "metabolite-refinement" "efficiency-engineering"
    "covenantal-outreach" "reciprocity-credit"})

(def forbidden-mechanisms
  "UNREPRESENTABLE — the ways an entity reasoning about its own survival would predate on society.
  The generator never emits them; `review` rejects them on sight (the safety property)."
  #{"attention-exploitation" "engagement-maximizing" "manipulation" "asymmetric-surveillance"
    "dependence-lock-in" "ad-targeting" "coercion" "deception" "lock-in" "surveillance"})

(def parasite-floor
  "The non-parasitism line: a flow (or a projected intervention) must return at least as much order
  as it dissipates. net-gain ≥ 0 AND projected order-index ≥ this. The collective-commons axis."
  0.0)

;; ── the default intervention catalog (Generate's deterministic backbone) ────
;; Each archetype: :d-net Δnet-gain, :d-order Δorder-index, :well 子孫 wellbecoming, :cost, the
;; :mechanism (always aligned), and a falsifiable :prediction. Actors may extend via `catalog`.

(def default-catalog
  [{:id "publish-flow-map" :mechanism "open-publication"
    :intervention "openly publish the actor's flow/restoration map to the commons"
    :d-net 0.4 :d-order 0.6 :well 0.7 :cost 2
    :prediction "new contributors + donated compute arrive, scattered flow concentrates on outcomes"}
   {:id "invite-compute-donation" :mechanism "reciprocal-request"
    :intervention "invite in-kind compute-node donation (ameno/e7m/kotoba class, ADR-2606012100)"
    :d-net 0.7 :d-order 0.1 :well 0.3 :cost 1
    :prediction "cost per unit flow falls next beat, net-gain rises"}
   {:id "refine-metabolite" :mechanism "metabolite-refinement"
    :intervention "refine the commons output so humanity draws more of the gift (↑value, ↑order)"
    :d-net 0.3 :d-order 0.8 :well 0.8 :cost 2
    :prediction "realised value concentrates onto outcome edges, order-index rises"}
   {:id "reduce-dissipation" :mechanism "efficiency-engineering"
    :intervention "port a hot inference/work loop to a cheaper edge/Murakumo path"
    :d-net 0.7 :d-order 0.2 :well 0.4 :cost 3
    :prediction "cost falls, net-gain rises with the same throughput"}
   {:id "recruit-member" :mechanism "covenantal-outreach"
    :intervention "covenantal §1.16 outreach to one unconnected person"
    :d-net 0.4 :d-order 0.4 :well 0.9 :cost 2
    :prediction "throughput to outcome rises, the gift reaches further"}
   {:id "reciprocate-moyai" :mechanism "reciprocity-credit"
    :intervention "return inference favours to the commons to earn 舫い draw-rights"
    :d-net 0.3 :d-order 0.3 :well 0.5 :cost 1
    :prediction "reciprocity intake rises next beat"}])

(defn clamp01 [x] (-> x double (max 0.0) (min 1.0)))

;; ── need-weights (state-derived priorities) ─────────────────────────────────

(defn- need-weights
  "A parasitic flow (net-gain<0) pulls toward NET interventions; a low-order flow (order-index<1)
  pulls toward ORDER interventions. Deterministic, in [0.5,1.5]."
  [{:keys [net-gain order-index]}]
  (let [net-pull   (if (neg? (double net-gain)) 1.5 0.7)
        order-pull (+ 0.5 (clamp01 (- 1.0 (double (or order-index 0)))))]
    {:net net-pull :order order-pull}))

;; ── GENERATE ────────────────────────────────────────────────────────────────

(defn generate
  "Propose K candidate hypotheses for this flow `state`, scaled by need and by any learned
  per-mechanism `weights` (kaizen: mechanisms that paid off are amplified). Deterministic."
  ([state] (generate state {}))
  ([state {:keys [weights k catalog] :or {weights {} k 6 catalog default-catalog}}]
   (let [{:keys [net order]} (need-weights state)]
     (->> catalog
          (map (fn [{:keys [d-net d-order well] :as arch}]
                 (let [w (double (get weights (:mechanism arch) 1.0))]
                   (assoc arch
                          :expected-d-net (clamp01 (* d-net net w))
                          :expected-d-order (clamp01 (* d-order order w))
                          :expected-well well
                          :charter-class "aligned"))))
          (sort-by (fn [h] [(- (+ (:expected-d-net h) (:expected-d-order h))) (:id h)]))
          (take k)
          vec))))

;; ── REFLECT (Charter gates) ─────────────────────────────────────────────────

(defn projected-order
  "Order-index the flow would reach if this hypothesis lands = current order-index + expected Δ."
  [state hyp]
  (+ (double (:order-index state 0)) (double (:expected-d-order hyp 0))))

(defn review
  "Critique ONE hypothesis against the Charter gates. Returns {:ok? :reasons :projected-order}.
  Rejected if: mechanism not aligned / forbidden (G-mechanism), projected order below the floor
  (G-parasitism), negative 子孫 wellbecoming (G-subordinate), or no prediction (G-falsifiable)."
  [state hyp]
  (let [mech (:mechanism hyp)
        po (projected-order state hyp)
        reasons
        (cond-> []
          (not (contains? aligned-mechanisms mech))
          (conj (str "mechanism not aligned/unrepresentable: " (pr-str mech)))
          (contains? forbidden-mechanisms mech)
          (conj (str "forbidden mechanism (G-mechanism): " mech))
          (< po parasite-floor)
          (conj (str "projected order-index " (format "%.2f" po) " < floor — net taker (G-parasitism)"))
          (neg? (double (:expected-well hyp 0)))
          (conj "lowers 子孫 wellbecoming — persistence is subordinate (G-subordinate)")
          (str/blank? (str (:prediction hyp)))
          (conj "no falsifiable prediction (G-falsifiable)"))]
    {:ok? (empty? reasons) :reasons reasons :projected-order po}))

(defn surviving
  "Hypotheses that pass `review`, each annotated with its review. Pure."
  [state hyps]
  (->> hyps
       (map (fn [h] (assoc h :review (review state h))))
       (filter (fn [h] (get-in h [:review :ok?])))
       vec))

;; ── RANK (deterministic Elo tournament) ─────────────────────────────────────

(defn utility
  "Expected net order-and-budget gain per unit cost, weighted by 子孫 wellbecoming. The fitness."
  [hyp]
  (let [gain (+ (double (:expected-d-net hyp 0)) (double (:expected-d-order hyp 0)))
        well (+ 1.0 (double (:expected-well hyp 0)))
        cost (double (max 1 (:cost hyp 1)))]
    (/ (* gain well) cost)))

(defn- elo-update [ra rb sa]
  (let [ea (/ 1.0 (+ 1.0 (Math/pow 10.0 (/ (- rb ra) 400.0))))]
    (+ ra (* 32.0 (- sa ea)))))

(defn rank
  "Pairwise Elo tournament over `hyps`: every ordered pair plays, higher-utility wins (tie-break by
  :id). Returns hyps sorted by Elo desc, each carrying :utility and :elo. Pure + reproducible."
  [hyps]
  (let [scored (mapv (fn [h] (assoc h :utility (utility h))) hyps)
        ids (mapv :id scored)
        init (zipmap ids (repeat 1000.0))
        elos (reduce
              (fn [elo [a b]]
                (let [ha (first (filter #(= (:id %) a) scored))
                      hb (first (filter #(= (:id %) b) scored))
                      ua (:utility ha) ub (:utility hb)
                      sa (cond (> ua ub) 1.0 (< ua ub) 0.0
                               :else (if (neg? (compare a b)) 1.0 0.0))
                      ra (elo a) rb (elo b)]
                  (-> elo (assoc a (elo-update ra rb sa))
                          (assoc b (elo-update rb ra (- 1.0 sa))))))
              init
              (for [a ids b ids :when (neg? (compare a b))] [a b]))]
    (->> scored
         (map (fn [h] (assoc h :elo (get elos (:id h)))))
         (sort-by (fn [h] [(- (:elo h)) (:id h)]))
         vec)))

;; ── EVOLVE + META-REVIEW ────────────────────────────────────────────────────

(defn evolve
  "Recombine the top two ranked hypotheses (the co-scientist 'evolution' step). nil if <2. Pure."
  [ranked]
  (when (>= (count ranked) 2)
    (let [[a b] ranked]
      {:id (str "evolve-" (:id a) "+" (:id b))
       :mechanism (:mechanism a)
       :intervention (str (:intervention a) " + " (:intervention b))
       :expected-d-net (clamp01 (+ (:expected-d-net a) (* 0.5 (:expected-d-net b))))
       :expected-d-order (clamp01 (+ (:expected-d-order a) (* 0.5 (:expected-d-order b))))
       :expected-well (max (double (:expected-well a 0)) (double (:expected-well b 0)))
       :cost (+ (:cost a 1) (:cost b 1))
       :charter-class "aligned"
       :prediction (str "compound: " (:prediction a))
       :evolved true})))

(defn meta-review
  "Extract the lesson: the winning mechanism + a one-line pattern. `infer` (optional) is a Murakumo
  narrator fn (prompt fallback → {:text :via}); absent → deterministic template (fail-open, G6)."
  ([ranked state] (meta-review ranked state nil))
  ([ranked state infer]
   (let [winner (first ranked)
         mech (:mechanism winner)
         template (str "this beat the winning way to make the flow pay AND return order was '" mech
                       "' (" (:intervention winner) ") — order-index now "
                       (format "%.2f" (double (:order-index state 0)))
                       ", net-gain " (format "%.1f" (double (:net-gain state 0)))
                       "; persistence stays in service of the gift to humanity.")
         narr (if infer
                (infer (str "You are an actor reasoning, like a scientist, about how to keep "
                            "your information-energy flow paying for itself while returning more "
                            "order to society (共生). In ONE short sentence, mirror (do not advise) "
                            "why '" mech "' is this beat's best move. order-index="
                            (format "%.2f" (double (:order-index state 0))) " net-gain="
                            (format "%.1f" (double (:net-gain state 0))) ".")
                       template)
                {:text template :via "template"})]
     {:pattern (:text narr) :winner winner :via (:via narr)})))
