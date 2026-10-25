(ns kotoba.property.ownership
  "Portable ownership-claim contract for public property data.")

(def public-claims-by-parcel-query
  "Datalog query usable unchanged by Datomic and DataScript."
  '[:find ?claim-id ?holder ?source ?observed-at
    :in $ ?parcel
    :where
    [?claim :ownership/parcel ?parcel]
    [?claim :ownership/id ?claim-id]
    [?claim :ownership/holder ?holder]
    [?claim :ownership/source ?source]
    [?claim :ownership/observed-at ?observed-at]
    [?claim :ownership/disclosure :public]])

(def required-claim-keys
  #{:ownership/id
    :ownership/parcel
    :ownership/holder
    :ownership/holder-kind
    :ownership/source
    :ownership/observed-at
    :ownership/licence
    :ownership/disclosure})

(def holder-kinds #{:company :public-body :nonprofit :collective :unknown})

(def public-ubo-jurisdictions
  "Jurisdiction/source pairs reviewed for governed ingestion of public UBO
   names. This is intentionally an allowlist, not an assertion that every
   public register may be mirrored or republished."
  {"GB" #{"companies-house-psc"}})

(def public-ubo-by-company-query
  "Datalog query usable unchanged by Datomic and DataScript."
  '[:find ?ubo-id ?person-name ?control ?source ?observed-at
    :in $ ?company-id
    :where
    [?ubo :ubo/company-id ?company-id]
    [?ubo :ubo/id ?ubo-id]
    [?ubo :ubo/person-name ?person-name]
    [?ubo :ubo/control ?control]
    [?ubo :ubo/source ?source]
    [?ubo :ubo/observed-at ?observed-at]
    [?ubo :ubo/disclosure :public]])

(def public-ownership-and-ubo-by-parcel-query
  "Datalog query joining a corporate property owner to its public UBOs."
  '[:find ?owner ?company-id ?person-name ?control ?source ?observed-at
    :in $ ?parcel
    :where
    [?ownership :ownership/parcel ?parcel]
    [?ownership :ownership/holder ?owner]
    [?ownership :ownership/holder-id ?company-id]
    [?ubo :ubo/company-id ?company-id]
    [?ubo :ubo/person-name ?person-name]
    [?ubo :ubo/control ?control]
    [?ubo :ubo/source ?source]
    [?ubo :ubo/observed-at ?observed-at]
    [?ubo :ubo/disclosure :public]])

(def required-ubo-keys
  #{:ubo/id :ubo/company-id :ubo/person-id :ubo/person-name :ubo/control
    :ubo/jurisdiction :ubo/source :ubo/observed-at :ubo/disclosure})

(defn validate-claim
  "Validate a public, attributable ownership claim without performing I/O.
   Natural-person holders are intentionally outside this public contract."
  [claim]
  (cond
    (not (map? claim))
    {:ownership/valid? false :ownership/error :not-a-map}

    (not (every? #(contains? claim %) required-claim-keys))
    {:ownership/valid? false :ownership/error :missing-required-key}

    (= :natural-person (:ownership/holder-kind claim))
    {:ownership/valid? false :ownership/error :natural-person-not-permitted}

    (not (contains? holder-kinds (:ownership/holder-kind claim)))
    {:ownership/valid? false :ownership/error :unknown-holder-kind}

    (not= :public (:ownership/disclosure claim))
    {:ownership/valid? false :ownership/error :not-publicly-disclosed}

    :else
    {:ownership/valid? true}))

(defn validate-ubo
  "Validate the minimized, source-derived UBO relation used for a corporate
   property owner. Callers must not add residential address, date of birth,
   or identity-verification fields to this public contract."
  [ubo]
  (cond
    (not (map? ubo))
    {:ubo/valid? false :ubo/error :not-a-map}

    (not (every? #(contains? ubo %) required-ubo-keys))
    {:ubo/valid? false :ubo/error :missing-required-key}

    (not= :public (:ubo/disclosure ubo))
    {:ubo/valid? false :ubo/error :not-publicly-disclosed}

    (not (contains? (get public-ubo-jurisdictions (:ubo/jurisdiction ubo) #{})
                    (:ubo/source ubo)))
    {:ubo/valid? false :ubo/error :source-not-allowlisted}

    :else
    {:ubo/valid? true}))
