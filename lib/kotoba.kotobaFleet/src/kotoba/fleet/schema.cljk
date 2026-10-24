(ns kotoba.fleet.schema
  "Datom schema for fleet coordination (ADR-2606302000). Five entity kinds, all
  append-only:

    :work/*      — a unit of work (repo / module / file-set) to be done
    :lease/*     — an agent's optimistic claim on a :work unit (TTL'd)
    :proposal/*  — an agent's proposed write (intent only; not yet in git)
    :claim/*     — reserved for finer-grained sub-claims (future)
    :receipt/*   — the governor's accept/reject + materialize record

  An entity is a flat set of [e a v t] datoms keyed by its `:*/id`. `e` is the
  id; `t` is the append ordinal (causal order). This is the kotoba Datom-log
  shape (cf. datom-clj); kept inline + zero-dep so the lib stands alone.")

(def kinds
  "The fleet entity kinds and their attributes (documentation + validation)."
  {:work     #{:work/id :work/unit :work/state :work/created-by :work/t}
   :lease    #{:lease/id :lease/work :lease/agent :lease/granted-at
               :lease/ttl-ms :lease/released :lease/t}
   :proposal #{:proposal/id :proposal/work :proposal/agent :proposal/payload
               :proposal/idempotency-key :proposal/t}
   :claim    #{:claim/id :claim/work :claim/agent :claim/t}
   :receipt  #{:receipt/id :receipt/proposal :receipt/work :receipt/verdict
               :receipt/reason :receipt/t}})

(defn entity->datoms
  "Flatten an entity map (must contain exactly one `*/id` attr) into [e a v t]
  tuples, stamping each with tx ordinal `t`. nil values are dropped."
  [ent t]
  (let [id-attr (first (filter #(= "id" (name %)) (keys ent)))
        e       (get ent id-attr)]
    (when (nil? id-attr)
      (throw (ex-info "entity has no */id attribute" {:entity ent})))
    (into [[e id-attr (get ent id-attr) t]]
          (for [[a v] (dissoc ent id-attr) :when (some? v)]
            [e a v t]))))

(defn valid-kind?
  "True when every attribute of `ent` belongs to `kind`'s declared attribute set."
  [kind ent]
  (let [allowed (get kinds kind)]
    (and (some? allowed)
         (every? allowed (keys ent)))))
