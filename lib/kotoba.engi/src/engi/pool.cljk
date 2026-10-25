(ns engi.pool
  "The bodies behind the ids consensus orders — the deployment resolver
  `engi.chain` left as a seam.

  `inga.chain/decode-block` turns a committed proposal id into an advance
  through `(fn [id] -> advance-or-nil)`, and `engi.chain/resolver` builds one
  over a lookup. Nothing implemented the lookup, so a deployment had a bridge
  with no ground under one end. This is that ground.

  ## Why a pool, and not a read

  The obvious implementation reads the entry out of its author's kotobase
  graph. It is the wrong one: `decode-block` runs INSIDE block application,
  which has to be pure, total and identical on every replica. A network read
  there is none of the three — it can fail, it can be slow, and two replicas
  reading at different moments read different things.

  So the payload arrives BEFORE the order does, which is what every chain
  does and what `inga.chain`'s halt already assumed: a replica that cannot
  resolve a committed proposal must sync, not invent. `missing` is the list
  to sync, `known?` is the guard for the vote path, and `resolver` is the
  seam filled in.

  ## Admission is where the checking goes

  Everything a replica can establish about an entry on its own it establishes
  once, on the way in — not per block, and not inside `apply`:

  - the id IS the entry's CID (so an id cannot name a body it does not
    address, and two replicas cannot hold different bodies under one id)
  - the author signed it (`verify-fn`, injected — `engi.crypto` is cljs-only
    and this namespace is portable, the same reason `inga` injects its own
    crypto rather than importing it)
  - the advance it produces passes `inga.chain/valid-advance?`, checked here
    by `engi.chain/advance` + shape, so a proposal that would halt the apply
    path is one this replica never votes for

  What admission does NOT check is whether the entry is economically valid —
  `fold-balance`'s job, answered against the author's whole chain, and the
  application's question rather than the pool's.

  ## A fork is admitted, deliberately

  Two entries from one head are two valid entries with different CIDs. The
  pool holds both: refusing the second would hide from consensus exactly the
  thing consensus is there to catch, and `inga.state` records the fork when
  the second one is ordered. `authored` is how a detector gets both at once
  for `engi.core/detect-fork`."
  (:require [engi.chain :as chain]))

(def refusal-reasons
  "The closed set `admit` may name, for the reason `inga.state` keeps its own
  closed: a caller-chosen reason is caller-chosen data, and a pool is fed by
  the network."
  #{:not-an-entry :author-missing :id-mismatch :bad-signature :invalid-advance})

(defn pool
  "An empty pool.

  `verify-fn` is `(fn [author entry] -> truthy)` and is REQUIRED. A pool that
  cannot check a signature would admit anyone's entry under anyone's name,
  and every replica downstream would agree about it — which is the failure
  that looks most like success. Missing it is a deployment error and throws,
  the same judgement `inga.state` makes about a missing `:invoke-fn`."
  [{:keys [verify-fn]}]
  (when-not (ifn? verify-fn)
    (throw (ex-info "engi.pool/pool: verify-fn is not callable"
                    {:type :engi.pool/invalid-seam :seam :verify-fn})))
  {:verify-fn verify-fn :entries {}})

(defn- refuse [reason] {:refused reason})

(defn admit
  "Take `entry` as authored by `author`. `{:pool p'}` or `{:refused reason}`.

  Idempotent: the same entry admitted twice is the same pool, because the id
  is the CID and the CID is a function of the content. That matters because
  the network will deliver the same entry more than once and a pool that
  counted arrivals would be a pool with state nobody agreed on."
  [{:keys [verify-fn] :as p} author entry]
  (let [advance (when (and (map? entry) (string? author)) (chain/advance author entry))]
    (cond
      (not (map? entry)) (refuse :not-an-entry)
      (or (not (string? author)) (empty? author)) (refuse :author-missing)
      (not (chain/valid-advance? advance)) (refuse :invalid-advance)
      (not (verify-fn author entry)) (refuse :bad-signature)
      :else {:pool (assoc-in p [:entries (:entry advance)] {:author author :entry entry})})))

(defn admit!
  "`admit` with the refusal dropped — the shape a receive loop wants when it
  is going to log and continue either way. Returns the pool, changed or not."
  [p author entry]
  (or (:pool (admit p author entry)) p))

(defn known?
  "Can this replica resolve `id`?

  The vote-path guard `inga.chain` asks for: a replica that votes for a
  proposal it cannot resolve is voting to halt itself, and `valid-advance?`
  cannot notice because there is nothing to check."
  [p id] (contains? (:entries p) id))

(defn missing
  "The ids in `proposals` this pool cannot resolve — what to sync, in the
  order they appeared, so the answer to a halt is a list and not a hunt."
  [p proposals]
  (vec (distinct (remove #(known? p %) proposals))))

(defn lookup
  "`{:author _ :entry _}` for `id`, or nil. The shape `engi.chain/resolver`
  takes."
  [p id] (get (:entries p) id))

(defn resolver
  "An `inga.chain/decode-block` resolver reading this pool.

  `pool-fn` is `(fn [] -> pool)` rather than a pool value, because a machine
  is built once and applies blocks for as long as it runs — handing it a
  snapshot would resolve only what had arrived by construction time. It is a
  function rather than an atom so this namespace does not decide how a
  deployment holds its state."
  [pool-fn]
  (when-not (ifn? pool-fn)
    (throw (ex-info "engi.pool/resolver: pool-fn is not callable"
                    {:type :engi.pool/invalid-seam :seam :pool-fn})))
  (chain/resolver (fn [id] (lookup (pool-fn) id))))

(defn authored
  "Every entry `author` has in this pool, seq order.

  What `engi.core/detect-fork` takes, and the reason a fork is admitted
  rather than refused: the evidence has to be somewhere before consensus
  orders one of the pair."
  [p author]
  (->> (vals (:entries p))
       (filter #(= author (:author %)))
       (map :entry)
       (sort-by :engi/seq)
       vec))

(defn size
  "How many entries are held. For an operator deciding when to prune, which
  is a decision this namespace does not make for them: what is safe to drop
  depends on what consensus has already ordered."
  [p] (count (:entries p)))
