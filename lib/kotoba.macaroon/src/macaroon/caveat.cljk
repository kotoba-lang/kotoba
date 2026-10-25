(ns macaroon.caveat
  "Caveats as data, not as strings a predicate has to parse back.

  The original macaroon paper makes a first-party caveat an opaque
  application-defined string, and the verifier a list of predicates that each
  try to match it. That is where macaroons get fragile in practice: the
  restriction `time < 2026-09-01` is written by one program and re-parsed by
  another, so a verifier that does not recognise a caveat has to choose
  between ignoring it — which **widens** the token — and refusing it.

  Here a caveat is an EDN map with a `:caveat/kind`, and the choice is made
  once, in one place, in the safe direction: **an unrecognised kind is not
  satisfiable.** A verifier that does not understand a restriction cannot
  conclude the restriction is met.

  ## Four kinds, and three of them are `authority` values

  | kind | means | folds into |
  |---|---|---|
  | `:scope` | narrow to these resources | `authority.scope/meet-sets` |
  | `:before` | not after this instant | the tighter expiry |
  | `:holder` | only this principal | the grant's holder |
  | `:opaque` | anything else | an injected verifier, deny by default |

  The first three exist because they are the ones a capability lattice can
  *fold* rather than merely check: three caveats narrowing scope produce one
  scope set, and the result is again a grant. `:opaque` is the escape hatch
  and it is deliberately the only one that needs a predicate."
  (:require [kotoba.lang.text :as str]))

(def kinds #{:scope :before :holder :opaque})

(defn caveat
  "Normalise a caveat map, or throw naming what is wrong.

  Refusing here rather than at verification time is the point: a token is
  minted once and verified many times, so an unrepresentable restriction
  should fail for the party that can fix it."
  [{:keys [caveat/kind] :as c}]
  (when-not (contains? kinds kind)
    (throw (ex-info (str "unknown caveat kind " (pr-str kind))
                    {:type :macaroon/unknown-caveat-kind :kinds kinds})))
  (case kind
    :scope (let [ss (vec (:caveat/scopes c))]
             (when (empty? ss)
               (throw (ex-info "a :scope caveat with no scopes narrows to nothing by accident"
                               {:type :macaroon/empty-scope-caveat})))
             {:caveat/kind :scope :caveat/scopes ss})
    :before (do (when (str/blank? (str (:caveat/instant c)))
                  (throw (ex-info "a :before caveat needs an instant"
                                  {:type :macaroon/invalid-caveat})))
                {:caveat/kind :before :caveat/instant (:caveat/instant c)})
    :holder (do (when (str/blank? (str (:caveat/did c)))
                  (throw (ex-info "a :holder caveat needs a principal"
                                  {:type :macaroon/invalid-caveat})))
                {:caveat/kind :holder :caveat/did (:caveat/did c)})
    :opaque (do (when (nil? (:caveat/predicate c))
                  (throw (ex-info "an :opaque caveat needs a predicate value"
                                  {:type :macaroon/invalid-caveat})))
                {:caveat/kind :opaque :caveat/predicate (:caveat/predicate c)})))

(defn canonical
  "The bytes a caveat contributes to the signature chain.

  Key order is fixed by construction (the maps above are built with the same
  keys in the same order and rendered through `pr-str` of a sorted map), so
  two programs that agree on the value agree on the bytes. A signature over a
  map whose printing depends on insertion order is a signature over something
  the verifier may not reproduce."
  [c]
  (pr-str (into (sorted-map) c)))

(defn satisfied?
  "Is this caveat met, given `ctx` and an injected `opaque-verify`?

  `ctx` is `{:now instant :holder did}`. Returns false — never throws — for
  a caveat the context cannot answer, because a token being unusable is an
  ordinary outcome and an exception here would be indistinguishable from a
  bug in the caller."
  [{:caveat/keys [kind instant did predicate]} {:keys [now holder]} opaque-verify]
  (case kind
    ;; Scope caveats are folded, not checked: `macaroon.authority` meets them
    ;; into the grant, so by the time anything is asked, the narrowing has
    ;; already happened. Answering true here would be a second, weaker copy
    ;; of that decision.
    :scope true
    :before (boolean (and now instant (neg? (compare now instant))))
    :holder (boolean (and holder (= holder did)))
    :opaque (boolean (and opaque-verify (opaque-verify predicate)))
    false))
