(ns policy.execute
  "A pure decision engine for a policy-as-EDN model. Evaluates each rule's
  condition against a request (via IAttribute port) and combines applicable
  rules' effects by the policy's combining algorithm.

  `decide` returns {:policy/decision :allow|:deny|:not-applicable :policy/by rule-id-or-nil}.

  Algorithm semantics:
    :deny-overrides   — any applicable deny → deny (cite first deny rule);
                        else any applicable allow → allow; else :not-applicable.
    :allow-overrides  — any applicable allow → allow (cite first allow rule);
                        else any applicable deny → deny; else :not-applicable.
    :first-applicable — first applicable rule in declaration order wins;
                        else :not-applicable.

  Condition evaluation:
    leaf        {:policy/attr … :policy/op … :policy/value …} — resolve attr via IAttribute
                then apply op to :policy/value.
    :policy/and — all sub-conditions must hold (short-circuits on false).
    :policy/or  — at least one sub-condition must hold (short-circuits on true).
    :policy/not — negates the sub-condition.
    nil         — unconditional; rule is always applicable.

  Ops:
    :=  :!=  :<  :>  :<=  :>=  — equality / ordering on the resolved value
    :in       — resolved value is a member of :policy/value (a collection)
    :contains — resolved value (a collection) contains :policy/value

  RBAC helper: `permits?` checks whether a named role holds a permission string
  via :policy/roles, without touching IAttribute."
  (:require [kotoba.lang.text :as str]
            [policy.ports   :as p]))

;; --- condition evaluation ---

(defn- eval-op
  "Apply `op` to `resolved` (the attribute value) and `value` (from the condition leaf)."
  [op resolved value]
  (case op
    :=        (= resolved value)
    :!=       (not= resolved value)
    :<        (< resolved value)
    :>        (> resolved value)
    :<=       (<= resolved value)
    :>=       (>= resolved value)
    :in       (boolean (contains? (set value) resolved))
    :contains (boolean (contains? (set resolved) value))
    false))

(defn- eval-cond
  "Evaluate a condition tree `cond-expr` against `request`. Returns boolean.
  A nil condition (unconditional rule) returns true."
  [ports cond-expr request]
  (cond
    (nil? cond-expr)
    true

    (contains? cond-expr :policy/and)
    (every? #(eval-cond ports % request) (:policy/and cond-expr))

    (contains? cond-expr :policy/or)
    (boolean (some #(eval-cond ports % request) (:policy/or cond-expr)))

    (contains? cond-expr :policy/not)
    (not (eval-cond ports (:policy/not cond-expr) request))

    (contains? cond-expr :policy/attr)
    (let [resolved (p/resolve (:attribute ports) (:policy/attr cond-expr) request)]
      (eval-op (:policy/op cond-expr) resolved (:policy/value cond-expr)))

    :else false))

;; --- combining algorithms ---

(defn- combine
  "Apply `algorithm` to `applicable-rules` (in declaration order), returning a decision map."
  [algorithm applicable-rules]
  (case algorithm
    :deny-overrides
    (let [first-deny  (first (filter #(= :deny  (:policy/effect %)) applicable-rules))
          first-allow (first (filter #(= :allow (:policy/effect %)) applicable-rules))]
      (cond
        first-deny  {:policy/decision :deny  :policy/by (:policy/id first-deny)}
        first-allow {:policy/decision :allow :policy/by (:policy/id first-allow)}
        :else       {:policy/decision :not-applicable :policy/by nil}))

    :allow-overrides
    (let [first-allow (first (filter #(= :allow (:policy/effect %)) applicable-rules))
          first-deny  (first (filter #(= :deny  (:policy/effect %)) applicable-rules))]
      (cond
        first-allow {:policy/decision :allow :policy/by (:policy/id first-allow)}
        first-deny  {:policy/decision :deny  :policy/by (:policy/id first-deny)}
        :else       {:policy/decision :not-applicable :policy/by nil}))

    :first-applicable
    (if-let [r (first applicable-rules)]
      {:policy/decision (:policy/effect r) :policy/by (:policy/id r)}
      {:policy/decision :not-applicable :policy/by nil})

    ;; unknown algorithm — treated as not-applicable (validate catches this earlier)
    {:policy/decision :not-applicable :policy/by nil}))

(defn decide
  "Evaluate `pol` against `request` using `ports`.
  Returns {:policy/decision :allow|:deny|:not-applicable :policy/by rule-id-or-nil}."
  [ports pol request]
  (let [applicable (filter #(eval-cond ports (:policy/when %) request)
                           (:policy/rules pol))]
    (combine (:policy/algorithm pol) applicable)))

;; --- RBAC helper (no ports needed) ---

(defn permits?
  "True iff `role-name` has `permission` in `pol`'s :policy/roles map.
  This is a pure RBAC check on the static role table — no attribute resolution."
  [pol role-name permission]
  (contains? (get-in pol [:policy/roles role-name] #{}) permission))

;; --- host-free default ports ---

(def ^:private not-found ::not-found)

(defn- resolve-attr-default
  "Resolve a dotted attr-path (\"user.role\") against a nested request map.
  Each segment is tried first as a keyword key, then as a string key.
  Returns nil if any segment is missing. Falls through to the string-key
  lookup only when the keyword key is genuinely absent -- a resolved value
  of `false` (or any other falsy-but-present value) must be preserved, not
  coerced to nil (an `or`-based fallback would otherwise treat a real
  `false` attribute value the same as \"not found\", silently breaking any
  policy condition that compares an attribute against `false`)."
  [attr-path request]
  (reduce (fn [m k]
            (when (some? m)
              (let [kw-v (get m (keyword k) not-found)]
                (if (= kw-v not-found) (get m k) kw-v))))
          request
          (str/split attr-path #"\.")))

(defn default-ports
  "A host-free IAttribute implementation. Resolves dotted attr paths against the
  request map using keyword-then-string key lookup at each segment.
  \"user.role\" on {:user {:role \"admin\"}} → \"admin\".
  Sufficient to exercise all policy logic without any host; replace with a real
  attribute store or JWT claim resolver for production."
  []
  {:attribute (reify p/IAttribute
                (resolve [_ attr-path request]
                  (resolve-attr-default attr-path request)))})
