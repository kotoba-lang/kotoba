(ns authority.revocation
  "The revoked-CID store `dango.chain/verify` reads as `:revoked`.

  A store is a set of canonical CID strings (`dango.cid` round-trip). It is a
  snapshot with no provenance: freshness, persistence and who may add to it
  are the host's job, and a store that arrives over the wire is merged, never
  trusted on arrival. Merges only grow — revocation is monotonic, so
  distribution is set union and two hosts that exchange stores converge. There
  is no removal: un-revoking is a new epoch, also the host's job.

  Fail-closed direction: `read` refuses a corrupt payload wholesale instead of
  returning a partial store. This is the opposite choice from
  `authority.scope/parse-all`, deliberately — a partial scope set narrows
  authority (the safe direction), while a partial revocation set widens what
  verifies (the unsafe one). `revoke` of anything that is not a canonical CID
  is loud (`ex-info`), never a silent no-op that lets a caller believe
  something was revoked when it was not."
  (:require [clojure.string :as str]
            [dango.cid :as cid]))

(def empty
  "The store that revokes nothing. Passing it as `:revoked` changes no
  decision — the control case."
  #{})

(defn valid-cid?
  "Is X a canonical CID string (the `dango.cid` round-trip)? Inert values that
  pass but match no block simply never match; anything else is not storable."
  [x]
  (boolean
   (when (and (string? x) (< 1 (count x)) (str/starts-with? x "b"))
     (try (do (cid/cid-bytes x) true)
          (catch #?(:clj Exception :cljs :default) _ false)))))

(defn revoke
  "STORE plus CID. CID must satisfy `valid-cid?`; anything else throws
  `ex-info` with `:revocation/not-a-cid`, because recording nothing while the
  caller proceeds as if something was revoked is a fail-open."
  [store cid]
  (if (valid-cid? cid)
    (conj (set store) cid)
    (throw (ex-info "authority.revocation: not a CID" {:revocation/not-a-cid cid}))))

(defn revoked?
  "Has CID been revoked in STORE?"
  [store cid]
  (contains? (set store) cid))

(defn merge
  "Union of two stores — what distribution exchanges and converges on.
  Commutative and idempotent; nil counts as empty."
  [a b]
  (into #{} (concat a b)))

(defn wire
  "STORE as a sorted vector of CID strings — the canonical distribution form.
  Deterministic: insertion order never shows on the wire."
  [store]
  (vec (sort (set store))))

(defn read
  "A wire vector back into `{:store …}`. Any entry that is not a canonical
  CID, or a payload that is not sequential, yields `{:problems […]}` with NO
  `:store` — a corrupt list is refused whole, never applied partially."
  [payload]
  (cond
    (not (sequential? payload))
    {:problems [[:revocation/not-a-vector payload]]}

    :else
    (let [bad (vec (remove valid-cid? payload))]
      (if (seq bad)
        {:problems (mapv (fn [x] [:revocation/not-a-cid x]) bad)}
        {:store (into #{} payload)}))))
