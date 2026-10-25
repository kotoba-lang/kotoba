(ns cloudflare.workers.policy
  "Operator-owned, deny-by-default policy for the Cloudflare Workers storage
  capability family.

  The policy is the *only* place authority is expressed. It is host-side data:
  a guest neither reads it nor influences it. Every default here fails closed,
  following `kotoba-lang/kotoba-lang`'s `lang/capability-semantics.edn`
  (`:unknown-kind :deny`, `:missing-grant :deny`, `:fail-closed true`) and
  `kotoba.host-providers/resource-scope`, where an absent network allowlist
  means *no URLs*, not *all URLs*.

  Concretely, absence never grants:

  | absent key            | effective value            |
  |-----------------------|----------------------------|
  | `:caps`               | `#{}` -- nothing permitted |
  | `:key-prefixes`       | `#{}` -- no key reachable  |
  | `:statements`         | `{}` -- no D1 call possible|
  | `:policy/bindings`    | `{}` -- no binding exists  |
  | `:policy/forbid-wildcard` | `true`                 |

  `:policy/forbid-wildcard` defaulting to *true* is deliberate.
  `capability-semantics.edn` says a production local policy MUST set it, and
  a default of `false` would make the safe configuration the one you have to
  remember to write. Wildcard scope (`:any`) therefore requires an explicit
  `:policy/forbid-wildcard false` -- an opt-out an operator has to mean.

  D1 statements are registered here with their SQL text, arity, and mode. The
  guest names a statement; it never authors SQL (see
  `cloudflare.workers.command`). `problems` cross-checks each statement's
  placeholder count against its declared arity so an operator typo surfaces at
  policy-validation time rather than as a runtime bind error.")

(def binding-kinds #{:kv :d1 :r2})
(def statement-modes #{:read :write})

(def default-quota
  "Per-invocation ceilings applied when a policy omits them."
  {:max-commands 32
   :max-write-bytes (* 256 1024)
   :max-d1-statements 8
   :max-reads 32})

(def quota-ceiling
  "Hard ceilings. An operator may tighten a quota; raising one past these is
  clamped, and the clamp is recorded in the normalized policy under
  `:policy/quota-clamped` so it is visible rather than silent. This bounds the
  work a single mis-typed policy can authorize."
  {:max-commands 256
   :max-write-bytes (* 8 1024 1024)
   :max-d1-statements 64
   :max-reads 256})

(def ^:private default-binding-limits
  {:max-value-bytes 65536
   :min-ttl 60
   :max-ttl 86400})

;; ---------------------------------------------------------------------------
;; Normalization
;; ---------------------------------------------------------------------------

(defn- clamp-quota
  [quota]
  (reduce-kv (fn [acc k ceiling]
               (let [v (get acc k)]
                 (if (and (integer? v) (> v ceiling))
                   (-> acc (assoc k ceiling) (update ::clamped (fnil conj #{}) k))
                   acc)))
             quota
             quota-ceiling))

(defn- normalize-binding
  [spec]
  (let [caps (set (:caps spec))
        prefixes (cond
                   (= :any (:key-prefixes spec)) :any
                   (nil? (:key-prefixes spec)) #{}
                   :else (set (:key-prefixes spec)))]
    (merge default-binding-limits
           spec
           {:caps caps
            :key-prefixes prefixes
            :statements (or (:statements spec) {})})))

(defn normalize
  "Apply fail-closed defaults to POLICY and return the effective policy.

  Idempotent. Everything downstream (`admission`, `provider`) expects a
  normalized policy; both call this themselves so a caller cannot skip it."
  [policy]
  (when (some? policy)
    (let [quota (clamp-quota (merge default-quota (:policy/quota policy)))
          clamped (::clamped quota)]
      (cond-> (assoc policy
                     :policy/version (or (:policy/version policy) 1)
                     :policy/forbid-wildcard
                     (not (false? (:policy/forbid-wildcard policy)))
                     :policy/quota (dissoc quota ::clamped)
                     :policy/bindings
                     (reduce-kv (fn [acc k v] (assoc acc k (normalize-binding v)))
                                {}
                                (or (:policy/bindings policy) {})))
        (seq clamped) (assoc :policy/quota-clamped clamped)))))

;; ---------------------------------------------------------------------------
;; Lookups (all fail closed on absence)
;; ---------------------------------------------------------------------------

(defn binding-spec
  [policy binding-name]
  (get-in policy [:policy/bindings binding-name]))

(defn granted?
  "True when BINDING-SPEC carries CAP. Absent `:caps` grants nothing."
  [binding-spec cap]
  (contains? (or (:caps binding-spec) #{}) cap))

(defn wildcard-scope?
  [binding-spec]
  (= :any (:key-prefixes binding-spec)))

(defn key-in-scope?
  "True when KEY sits under one of BINDING-SPEC's allowed prefixes.

  An empty prefix set matches nothing. `:any` matches everything but is only
  reachable when the policy explicitly turned wildcard scoping back on --
  `admission` checks that separately so the denial reason stays specific."
  [binding-spec key]
  (let [prefixes (:key-prefixes binding-spec)]
    (cond
      (= :any prefixes) true
      (empty? prefixes) false
      :else (boolean (some (fn [p] (and (string? p)
                                        (<= (count p) (count key))
                                        (= p (subs key 0 (count p)))))
                           prefixes)))))

(defn statement-spec
  [binding-spec statement-id]
  (get-in binding-spec [:statements statement-id]))

(defn statement-capability
  "Capability kind a registered statement requires, from its *declared* mode."
  [statement-spec]
  (case (:mode statement-spec)
    :read :cf/d1-read
    :write :cf/d1-write
    nil))

;; ---------------------------------------------------------------------------
;; SQL placeholder arity cross-check
;; ---------------------------------------------------------------------------

(defn- char-code
  "Code unit at I. Written as a reader conditional rather than via `int`:
  ClojureScript's `int` is `(bit-or x 0)`, which coerces a non-numeric string
  to 0, so `(int (nth \"a,b\" 1))` is 0 -- indistinguishable from the digit
  zero. That silently made every character look like a digit here."
  [s i]
  #?(:clj  (int (.charAt ^String s i))
     :cljs (.charCodeAt s i)))

(def ^:private code-quote 39)   ; \'
(def ^:private code-question 63) ; \?
(def ^:private code-zero 48)
(def ^:private code-nine 57)

(defn- digit-at?
  [s i n]
  (and (< i n) (<= code-zero (char-code s i) code-nine)))

(defn placeholder-count
  "Number of distinct bound parameters in SQL.

  Single-quoted literals are skipped so a `?` inside a string is not counted.
  Numbered placeholders (`?1`, `?2`) are counted by their highest index, so a
  statement that legitimately reuses `?1` twice still reports arity 1;
  anonymous `?` placeholders are counted by occurrence. Mixing the two styles
  reports the larger of the two counts, which is what a bind call would need."
  [sql]
  (let [n (count sql)]
    (loop [i 0 in-string? false anonymous 0 max-index 0]
      (if (>= i n)
        (max anonymous max-index)
        (let [c (char-code sql i)]
          (cond
            (= c code-quote) (recur (inc i) (not in-string?) anonymous max-index)
            in-string? (recur (inc i) in-string? anonymous max-index)
            (= c code-question)
            (let [digits (loop [j (inc i)]
                           (if (digit-at? sql j n) (recur (inc j)) j))]
              (if (> digits (inc i))
                (let [idx #?(:clj (Long/parseLong (subs sql (inc i) digits))
                             :cljs (js/parseInt (subs sql (inc i) digits) 10))]
                  (recur digits in-string? anonymous (max max-index idx)))
                (recur (inc i) in-string? (inc anonymous) max-index)))
            :else (recur (inc i) in-string? anonymous max-index)))))))

;; ---------------------------------------------------------------------------
;; Policy validation
;; ---------------------------------------------------------------------------

(defn- statement-problems
  [binding-name statement-id spec]
  (let [where {:binding binding-name :statement statement-id}]
    (cond
      (not (map? spec)) [(assoc where :problem :malformed-statement)]
      (not (and (string? (:sql spec)) (pos? (count (:sql spec)))))
      [(assoc where :problem :missing-sql)]
      (not (contains? statement-modes (:mode spec)))
      [(assoc where :problem :invalid-statement-mode :mode (:mode spec))]
      (not (and (integer? (:arity spec)) (not (neg? (:arity spec)))))
      [(assoc where :problem :invalid-statement-arity :arity (:arity spec))]
      :else
      (let [declared (:arity spec)
            found (placeholder-count (:sql spec))]
        (when (not= declared found)
          [(assoc where :problem :statement-arity-mismatch
                  :declared declared :placeholders found)])))))

(defn- binding-problems
  [binding-name spec]
  (let [where {:binding binding-name}]
    (cond
      (not (map? spec)) [(assoc where :problem :malformed-binding)]
      (not (contains? binding-kinds (:kind spec)))
      [(assoc where :problem :invalid-binding-kind :kind (:kind spec))]
      :else
      (let [unknown-caps (remove #{:cf/kv-read :cf/kv-write :cf/d1-read
                                   :cf/d1-write :cf/r2-read :cf/r2-write}
                                 (:caps spec))
            kind-caps (case (:kind spec)
                        :kv #{:cf/kv-read :cf/kv-write}
                        :d1 #{:cf/d1-read :cf/d1-write}
                        :r2 #{:cf/r2-read :cf/r2-write})
            mismatched (remove kind-caps (:caps spec))]
        (concat
         (map (fn [c] (assoc where :problem :unknown-capability :capability c))
              unknown-caps)
         (map (fn [c] (assoc where :problem :capability-kind-mismatch
                             :capability c :kind (:kind spec)))
              (remove (set unknown-caps) mismatched))
         (when (and (not= :d1 (:kind spec)) (seq (:statements spec)))
           [(assoc where :problem :statements-on-non-d1-binding)])
         (mapcat (fn [[sid sspec]] (statement-problems binding-name sid sspec))
                 (:statements spec)))))))

(defn problems
  "Vector of policy problems; empty means the policy is well-formed.

  Well-formed is not the same as permissive: an empty policy is perfectly
  well-formed and authorizes nothing."
  [policy]
  (let [p (normalize policy)]
    (cond
      (nil? p) [{:problem :missing-policy}]
      (not (map? (:policy/bindings p))) [{:problem :malformed-bindings}]
      :else
      (vec
       (concat
        (when (and (false? (:policy/forbid-wildcard p))
                   (some (fn [[_ s]] (wildcard-scope? s)) (:policy/bindings p)))
          [{:problem :wildcard-scope-enabled
            :detail "policy explicitly opted out of :policy/forbid-wildcard and uses :any key scope"
            :severity :warning}])
        (mapcat (fn [[n s]] (binding-problems n s)) (:policy/bindings p)))))))

(defn valid?
  "True when POLICY has no error-severity problems."
  [policy]
  (empty? (remove (comp #{:warning} :severity) (problems policy))))
