(ns kotoba.codebase.typed-migrate
  "Re-address a stored `kotoba.typed-definition.v1` definition under identity
  layer 2, whose CID is the payload-v2 DefCID `kotoba.kir.definition-identity`
  mints.

  Why this is a migration and not a re-encoding: layer-1 CIDs are PUBLISHED.
  Measured 2026-09-02, kotoba-lang `lang/package-registry.edn`
  `:registry/definition-cids` names
  `bafyreif7drknz5fumncb5gqdo2jqel7hulxbzwcoohq2gsds2zm26pe6oe`; that block is
  committed at `site/assets/ipfs/` and `site/dist/ipfs/`, is inside a signed
  publication record and an ML-DSA attestation, and answers 200 from
  kotoba-lang.org and kotoba.cloud. Rewriting it in place would invalidate a
  signature over bytes other people hold. So: both layers exist, layer 1 stays
  the default and stays readable, and moving is an explicit act with a record.

  ## What cannot be migrated, and why saying so is the point

  Two v1 shapes are refused rather than approximated:

  - a recursive group (`kotoba.typed-group.v1` / `.typed-member.v1`), because
    layer 2 seals dependencies as CIDs and a cycle has no CID;
  - an effect row that layer 1 already stringified. `typed-code`'s
    `stable-name` falls through to `str`, so a compiler wire row was stored as
    the STRING \"[:cap/call 9]\". Parsing that back would mean guessing that
    the string denotes wire id 9 and then guessing the operation the catalog
    names for it -- two guesses sealed into an identity. The id is recoverable
    only from the catalog that was in force when the block was written, which
    the block does not record. Refusing keeps the guess out of the hash.

  A definition whose effects were stored as ordinary operation names migrates
  fine: those ARE the sealed vocabulary."
  (:require [kotoba.lang.text :as str]
            [kotoba.codebase.ir :as ir]
            [kotoba.kir.definition-identity :as di]
            [kotoba.codebase.store :as store]
            [kotoba.codebase.typed-code :as typed]
            [kotoba.codebase.typed-eval :as typed-eval]))

(defn- fail! [problem message data]
  (throw (ex-info message (assoc data :problem problem))))

(def ^:private stringified-wire-row
  "The exact shape layer 1 produced for a compiler row. Recognised so the
  refusal can name what it saw, instead of failing later on a keyword whose
  name happens to contain brackets."
  #"^\[:cap/call\s+\d+\]$")

(defn- effect-keyword
  "One layer-1 effect string as the keyword layer 2 seals, or a refusal."
  [s]
  (when-not (string? s)
    (fail! :typed-migrate/effect-row-unmigratable
           "stored effect row member is not a string" {:member s}))
  (when (re-matches stringified-wire-row s)
    (fail! :typed-migrate/effect-row-unmigratable
           (str "stored effect row member is a stringified compiler wire row: " s)
           {:member s
            :hint (str "layer 1 sealed [:cap/call <id>] as its printed form; the operation "
                       "name is recoverable only from the catalog in force when the block "
                       "was written, which the block does not record. Recompile from source "
                       "under identity-version 2 with :capability-id->name instead.")}))
  (when-not (re-matches #"[^\[\]{}()\s:\"',`;/]+(/[^\[\]{}()\s:\"',`;/]+)?" s)
    (fail! :typed-migrate/effect-row-unmigratable
           (str "stored effect row member is not an operation name: " s)
           {:member s}))
  (if-let [i (str/index-of s "/")]
    (keyword (subs s 0 i) (subs s (inc i)))
    (keyword s)))

(defn- type-form [form]
  (typed-eval/decode-view-form
   form
   {:name-of (fn [_]
               (fail! :typed-migrate/reference-in-type
                      "a type carries a definition reference" {}))
    :member-name (fn [_]
                   (fail! :typed-migrate/reference-in-type
                          "a type carries a group reference" {}))}))

(defn- body-form
  "The stored canonical body, decoded with dependency links turned into the
  ordinary-data reference layer 2 admits."
  [form]
  (typed-eval/decode-view-form
   form
   {:name-of (fn [cid] {:op :kir/definition-ref :cid cid})
    :member-name (fn [_]
                   (fail! :typed-migrate/recursive-group-unmigratable
                          "a recursive group has no layer-2 representation"
                          {:hint (str "layer 2 seals dependencies as CIDs and a cycle has "
                                      "none; leave recursive groups on identity-version 1")}))}))

(defn plan
  "Plan the layer-2 re-addressing of the layer-1 definition at V1-CID.

  Reads only: nothing is written, and the returned `:v2-cid` is exactly what
  `store/put-block!` would file `:block` under."
  ([root v1-cid] (plan root v1-cid {}))
  ([root v1-cid {:keys [profile-version desugar-contract-version]}]
   (let [block (store/get-block root v1-cid)
         version (typed/block-identity-version block)]
     (when (nil? version)
       (fail! :typed-migrate/not-a-typed-definition
              "block is not a typed definition of either identity layer"
              {:cid v1-cid :schema (when (map? block) (get block "schema"))}))
     (when (= 2 version)
       (fail! :typed-migrate/already-migrated
              "block is already a kotoba.typed-definition.v2 identity payload"
              {:cid v1-cid}))
     (when-not (= typed/schema (get block "schema"))
       (fail! :typed-migrate/recursive-group-unmigratable
              (str "only " typed/schema " migrates; this block is " (get block "schema"))
              {:cid v1-cid :schema (get block "schema")}))
     (let [interface-cid (ir/link->cid (get block "interface"))
           interface (store/get-block root interface-cid)]
       (when-not (= "kotoba.typed-interface.v1" (get interface "schema"))
         (fail! :typed-migrate/not-an-interface
                "linked block is not a kotoba.typed-interface.v1"
                {:cid interface-cid :schema (get interface "schema")}))
       (let [arity (get interface "arity")
             params (mapv #(symbol (str "k" %)) (range arity))
             function {:params params
                       :param-types (mapv type-form (get interface "paramTypes"))
                       :result (type-form (get interface "result"))}
             schemas (into {} (map (fn [[name definition]]
                                     [(type-form name) (type-form definition)]))
                           (get interface "schemas"))
             payload (typed/definition-payload
                      {:function function
                       :params params
                       :body (body-form (get block "body"))
                       :dependencies (mapv ir/link->cid (get block "dependencies"))
                       :schemas schemas
                       :effect-row (into #{} (map effect-keyword) (get interface "effects"))
                       :profile-version profile-version
                       :desugar-contract-version desugar-contract-version})]
         {:v1-cid v1-cid
          :v1-interface-cid interface-cid
          :payload payload
          :block (typed/definition-block-v2 payload)
          :v2-cid (di/definition-cid payload)})))))

(defn migrate!
  "Plan and persist. Returns the plan; the layer-1 block is left where it is,
  because something published still points at it."
  ([root v1-cid] (migrate! root v1-cid {}))
  ([root v1-cid opts]
   (let [{:keys [v2-cid block] :as planned} (plan root v1-cid opts)]
     (store/put-block! root v2-cid block)
     planned)))
