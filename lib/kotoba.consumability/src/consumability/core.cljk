(ns consumability.core
  "What makes a producer consumable, and how much of it a given producer has.

  A producer here is anything that publishes a surface others could call: a
  deployed actor, a worker, an API. This namespace owns the *definition* and the
  *scoring*, and nothing else — it performs no I/O. A caller probes the world and
  hands the observations in; an orchestrator decides what to do about the result.
  That split is deliberate: `manifest/repository-rules.edn` forbids a `loop-*`
  from owning domain scoring truth, so the truth lives here where anything can
  reuse it and a loop can only consume it.

  ## The ladder

  Consumability is a ladder, not a checklist:

    :addressed       declares an address at all
    :reachable       answers at that address
    :describable     serves a machine-readable contract saying what to call
    :discoverable    announces itself where a stranger would look
    :agent-callable  exposes a protocol an agent can drive (MCP or equivalent)

  Each rung is only meaningful if the one below it holds. A contract on a
  producer nobody can reach describes nothing; a discovery document pointing at a
  dead address is worse than none, because it spends a consumer's attention
  before failing.

  **So the score is the highest rung reached, and not a weighted average.** A
  weighted average would report a producer as 60% consumable while it is
  unreachable, and 60% of nothing is nothing. This is the single most important
  decision in this namespace: it is what stops the number from flattering the
  fleet. `rung-index` makes the ordering explicit rather than implied by map
  order.

  ## Unknown is not absent

  A probe that could not run yields `:unknown`, never `false`. An unreachable
  network and a producer that refuses are different facts, and collapsing them
  reports an outage as a design gap. `assess` keeps them apart and `summary`
  counts them separately, which mirrors the discipline
  `cloud.itonami.app.fleet/probe-health!` already applies to health."
  (:require [kotoba.lang.text :as str]))

;; ---------- the ladder ----------

(def ladder
  "The rungs, lowest first. Order is the semantics — see the ns docstring."
  [:addressed :reachable :describable :discoverable :agent-callable])

(def ^:private rung-order
  (into {} (map-indexed (fn [i r] [r i])) ladder))

(defn rung-index
  "Position of `rung` in the ladder, or nil if it is not a rung."
  [rung]
  (get rung-order rung))

(defn below
  "The rungs strictly below `rung`, lowest first."
  [rung]
  (if-let [i (rung-index rung)]
    (subvec ladder 0 i)
    []))

;; ---------- what each rung asks of an observation ----------
;;
;; An observation is a plain map, produced by whatever did the probing:
;;
;;   {:producer  "cloud-itonami-marketplace-order"
;;    :endpoint  "https://…"            ; nil when the producer has no address
;;    :health    {:path "/health" :status 200}
;;    :contract  {:path "/openapi.json" :status 404}
;;    :discovery [{:path "/llms.txt" :status 404}
;;                {:path "/.well-known/ai-plugin.json" :status 404}]
;;    :agent     {:path "/mcp" :status 404}}
;;
;; A key that is absent means "not probed" and scores :unknown. A key present
;; with a nil :status means the probe ran and failed to get an answer — also
;; :unknown, because a timeout is not a 404.

(defn- ok-status? [status]
  (and (integer? status) (<= 200 status 299)))

(def machine-readable-types
  "Content types a consumer can parse without a browser. `text/plain` is here for
  `llms.txt`; `text/html` is deliberately absent."
  ["application/json" "application/yaml" "application/x-yaml" "text/yaml"
   "application/openapi" "text/plain" "+json"])

(defn machine-readable?
  "Does this content type describe something a program can read?

  This is domain truth, not transport detail, which is why it lives here. A
  Cloudflare Pages project answers **every** path with `200 text/html` and its
  SPA index — measured 2026-07-30 on three live actors, where
  `/openapi.json` returned `200 text/html`. Scoring 2xx alone reported those
  three as describable, discoverable AND agent-callable when the true answer for
  all three rungs was zero. A rung that HTML can satisfy is a rung that measures
  nothing."
  [content-type]
  (let [t (some-> content-type str/lower)]
    (boolean (and t (some #(str/includes? t %) machine-readable-types)))))

(defn- probe-verdict
  "true / false / :unknown for one probe result.

  `:content-type` is checked only when the probe reported one — an observer that
  does not collect it gets status-only scoring rather than a silent `false`,
  because absent instrumentation is unmeasured, not refused."
  ([probe] (probe-verdict probe false))
  ([probe machine-readable-required?]
   (cond
     (nil? probe) :unknown
     (nil? (:status probe)) :unknown
     (not (ok-status? (:status probe))) false
     (and machine-readable-required? (contains? probe :content-type))
     (machine-readable? (:content-type probe))
     :else true)))

(defn- any-verdict
  "true if any probe answered, false if all answered and none did, :unknown when
  nothing was probed. A mix of false and :unknown is false only if at least one
  real refusal was seen — otherwise the absence is unmeasured, not proven."
  [probes]
  (let [vs (map #(probe-verdict % true) probes)]
    (cond
      (empty? vs) :unknown
      (some true? vs) true
      (some false? vs) false
      :else :unknown)))

(defn rung-verdict
  "true / false / :unknown for one rung against one observation."
  [rung observation]
  (case rung
    :addressed (let [e (:endpoint observation)]
                 (if (contains? observation :endpoint)
                   (boolean (and (string? e) (seq (str/trim e))))
                   :unknown))
    ;; :reachable asks only "did it answer" — a health endpoint that serves HTML
    ;; is still reachable, and Pages answering its index is a true answer to
    ;; that question. The rungs above it ask for something parseable.
    :reachable (probe-verdict (:health observation))
    :describable (probe-verdict (:contract observation) true)
    :discoverable (any-verdict (:discovery observation))
    :agent-callable (probe-verdict (:agent observation) true)
    :unknown))

;; ---------- assessment ----------

(defn assess
  "Score one observation.

  Returns `{:producer :reached :rung :verdicts :gap :unknown}`:

    :reached   the rungs held, in ladder order, stopping at the first that did
               not hold — because nothing above a broken rung is usable
    :rung      the highest rung reached, or nil when even :addressed fails
    :gap       the first rung that did NOT hold; the only actionable one
    :unknown   true when the ladder stopped on an unmeasured rung rather than a
               refused one. A caller must not report this as a gap: it is a hole
               in the probing, and acting on it would 'fix' something that may
               already work."
  [observation]
  (let [verdicts (into {} (map (fn [r] [r (rung-verdict r observation)])) ladder)
        reached (vec (take-while #(true? (get verdicts %)) ladder))
        gap (first (drop (count reached) ladder))]
    {:producer (:producer observation)
     :verdicts verdicts
     :reached reached
     :rung (last reached)
     :gap gap
     :unknown (= :unknown (get verdicts gap))}))

(defn assess-all [observations]
  (mapv assess observations))

;; ---------- fleet-level reading ----------

(defn summary
  "How many producers reached each rung, plus how many stopped on an unmeasured
  rung. `:unmeasured` is reported separately and never folded into a rung count —
  a fleet that has not been probed must not read as a fleet that failed."
  [assessments]
  (let [reached-counts
        (into {} (map (fn [r] [r (count (filter #(some #{r} (:reached %)) assessments))])) ladder)]
    {:producers (count assessments)
     :reached reached-counts
     :unmeasured (count (filter :unknown assessments))}))

(defn gaps
  "Actionable gaps grouped by rung: {rung [producer …]}. Producers whose gap is
  merely unmeasured are excluded — see `assess`."
  [assessments]
  (->> assessments
       (remove :unknown)
       (filter :gap)
       (group-by :gap)
       (reduce-kv (fn [m rung as] (assoc m rung (mapv :producer as))) {})))

(defn rank
  "Gaps in the order worth working on, most leverage first.

  Two things decide leverage and they are ordered deliberately:

    1. **How low the rung is.** A gap at :addressed blocks every rung above it,
       so closing it is worth more per producer than a gap at :agent-callable.
    2. **How many producers share it.** Among gaps at the same rung, the one
       more producers are stuck behind moves more of the fleet.

  Low-rung-first is the primary key on purpose. Sorting by population first
  would rank 'add MCP to the 9 reachable actors' above 'give the other 1,199 an
  address', which optimises a number instead of the fleet: the 9 are already the
  only ones anyone can use."
  [assessments]
  (->> (gaps assessments)
       (map (fn [[rung producers]]
              {:rung rung
               :rung-index (rung-index rung)
               :producers (vec (sort producers))
               :blocked (count producers)}))
       (sort-by (juxt :rung-index #(- (:blocked %))))
       vec))

(defn consumable?
  "A producer is consumable when a stranger can find out what to call and call
  it — :describable is the line. Below it a consumer needs the source, which
  means it is not a consumer of the surface but a reader of the repository."
  [assessment]
  (boolean (some #{:describable} (:reached assessment))))
