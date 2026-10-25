(ns macaroon.authority
  "The one-way door: a verified macaroon becomes an inert `authority` grant.

  Root ADR-2608159400 draws this line and it is the whole reason a second
  token format costs nothing here. A macaroon is a **wire**; `authority` is
  the **decider**. Adding biscuits, CACAOs or UCANs adds wires. It must not
  add deciders, because two deciders are two answers to `does this cover
  that`, and the fleet has measured what happens when the answer is written
  once per scheme (`authority.scope`'s docstring: prefix confusion, latent
  in the comparison rather than in any minter).

  So this namespace has exactly one interesting property, and there is a
  test for it: **it can only narrow.** The grant it produces is the meet of
  the caveats, and `authority.grant/meet` is a greatest lower bound, so a
  caveat cannot widen a token no matter what it says. A malicious caveat is
  arithmetically incapable of granting anything."
  (:require [authority.grant :as grant]
            [authority.scope :as scope]
            [macaroon.core :as core]))

(defn- earlier
  "The tighter of two instants, where nil is unbounded. Same convention
  `authority.grant` uses internally — ISO-8601 UTC compared as strings, which
  is correct for that and wrong for anything else, so callers normalise
  before they get here."
  [a b]
  (cond (nil? a) b (nil? b) a (neg? (compare a b)) a :else b))

(defn ->grant
  "A verified macaroon's caveats, as one grant.

  `base` is what the mint conferred — the root authority the identifier
  stands for, which the verifier looks up, **not** anything carried in the
  token. A token that could name its own base would be a token that grants
  itself.

  Scope caveats fold through `grant/meet`, which is a greatest lower bound,
  so they can only narrow. `:before` folds through the tighter-of-two, so it
  can only shorten. `:holder` follows `grant/meet`'s rule — the child's
  holder wins, because a delegation ends at whoever holds the leaf — and it
  is applied to the folded grant rather than met in as a separate one:
  **a grant carrying only a holder has no scopes, and meeting it would
  narrow the token to nothing.** That is a real edge measured while writing
  this, and it is the reason this function folds values rather than grants."
  [m base]
  (let [caveats (:macaroon/caveats m)
        scope-grants (keep (fn [c] (when (= :scope (:caveat/kind c))
                                     (grant/grant {:scopes (:caveat/scopes c)})))
                           caveats)
        befores (keep (fn [c] (when (= :before (:caveat/kind c)) (:caveat/instant c))) caveats)
        holder (some (fn [c] (when (= :holder (:caveat/kind c)) (:caveat/did c))) caveats)
        narrowed (reduce grant/meet (grant/grant base) scope-grants)]
    (cond-> (assoc narrowed :grant/expires (reduce earlier (:grant/expires narrowed) befores))
      holder (assoc :grant/holder holder))))

(defn authorize
  "Verify, then decide — in that order, and never the other way round.

  Returns the `authority` decision augmented with `:macaroon/verified?`. A
  caller that reads `:authority/allowed?` without checking verification gets
  `false`, because an unverified token yields `grant/nothing`, which covers
  nothing through the ordinary path rather than through a special case."
  [m {:keys [base requested now holder] :as opts}]
  (let [v (core/verify m opts)]
    (if-not (:ok? v)
      {:authority/allowed? false
       :authority/reason (:reason v)
       :macaroon/verified? false
       :authority/effective grant/nothing}
      (let [g (->grant m base)]
        {:authority/allowed? (grant/authorized? g requested {:now now :holder holder})
         :authority/reason (if (grant/authorized? g requested {:now now :holder holder})
                             :granted :not-covered)
         :macaroon/verified? true
         :authority/effective g}))))

(defn scopes-of
  "What the token's scope caveats narrow to, as rendered strings. For audit
  output, where a set of segment vectors is unreadable."
  [g]
  ;; `scope/sorted` already renders. Mapping `render` over its output returns
  ;; a vector of nils, which reads as "one scope, unnameable" rather than as
  ;; a type error -- measured while writing this test.
  (scope/sorted (:grant/scopes g)))
