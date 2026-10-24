(ns policy.model
  "ABAC/RBAC authorization policy as EDN: a plain-data representation of a Policy,
  plus a threading-friendly builder and the queries a decision engine or validator
  needs. No I/O, no third-party deps — portable .cljc (JVM, ClojureScript, SCI).

  A policy is a map keyed by namespaced `:policy/*` keys. Rules are stored in a
  vector (order matters for :first-applicable); roles are an id-keyed map for
  O(1) RBAC lookup:

    {:policy/id \"p1\"
     :policy/algorithm :deny-overrides
     :policy/rules [{:policy/id \"r1\" :policy/effect :allow
                     :policy/when {:policy/attr \"user.role\"
                                   :policy/op   :=
                                   :policy/value \"admin\"}}]
     :policy/roles {\"admin\" #{\"read\" \"write\" \"delete\"}
                    \"user\"  #{\"read\"}}}

  A :policy/when condition is data — a leaf or a combinator:
    leaf        {:policy/attr \"user.score\" :policy/op :>= :policy/value 500}
    combinator  {:policy/and [<cond>…]} / {:policy/or [<cond>…]} / {:policy/not <cond>}")

;; --- allowed value sets ---

(def algorithms
  "Allowed combining algorithms for a policy."
  #{:deny-overrides :allow-overrides :first-applicable})

(def effects
  "Allowed effect values for a rule."
  #{:allow :deny})

(def ops
  "Allowed comparison operators for a leaf condition.
   :=        equality
   :!=       inequality
   :< :> :<= :>=   numeric ordering
   :in       resolved-value is a member of :policy/value (a collection)
   :contains resolved-value (a collection) contains :policy/value"
  #{:= :!= :< :> :<= :>= :in :contains})

;; --- builder (threadable) ---

(defn policy
  "A fresh, empty policy. opts: {:algorithm} (:algorithm defaults to :deny-overrides)."
  ([id] (policy id nil))
  ([id opts]
   {:policy/id        id
    :policy/algorithm (get opts :algorithm :deny-overrides)
    :policy/rules     []
    :policy/roles     {}}))

(defn allow
  "Append an allow rule with `id` and optional condition `cond-expr` to `pol`.
  A rule without a condition is unconditionally applicable."
  ([pol id] (allow pol id nil))
  ([pol id cond-expr]
   (update pol :policy/rules conj
           (cond-> {:policy/id id :policy/effect :allow}
             (some? cond-expr) (assoc :policy/when cond-expr)))))

(defn deny
  "Append a deny rule with `id` and optional condition `cond-expr` to `pol`."
  ([pol id] (deny pol id nil))
  ([pol id cond-expr]
   (update pol :policy/rules conj
           (cond-> {:policy/id id :policy/effect :deny}
             (some? cond-expr) (assoc :policy/when cond-expr)))))

(defn role
  "Add or replace role `role-name` with `permissions` (a set of strings) in `pol`."
  [pol role-name permissions]
  (assoc-in pol [:policy/roles role-name] (set permissions)))

;; --- condition constructors ---

(defn leaf
  "Build a leaf condition: (op (resolve attr request) value).
  attr is a dotted path string (\"user.role\"); op is one of `ops`."
  [attr op value]
  {:policy/attr attr :policy/op op :policy/value value})

(defn and-cond
  "Build an :and combinator — all sub-conditions must hold."
  [& conds]
  {:policy/and (vec conds)})

(defn or-cond
  "Build an :or combinator — at least one sub-condition must hold."
  [& conds]
  {:policy/or (vec conds)})

(defn not-cond
  "Build a :not combinator — the sub-condition must NOT hold."
  [cond]
  {:policy/not cond})

;; --- queries ---

(defn rules     [pol] (:policy/rules pol))
(defn roles     [pol] (:policy/roles pol))
(defn algorithm [pol] (:policy/algorithm pol))
