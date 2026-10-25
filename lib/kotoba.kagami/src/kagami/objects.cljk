(ns kagami.objects
  "⑰ kotoba-git object-plane block transfer for P3b (ADR-2607160005).

  P3b gossip replicates the fleet HEAD (a single record). This module adds
  the actual OBJECT-GRAPH transfer: once a machine learns a peer's head-cid,
  it computes what git objects it is missing (bonsai.log/missing-since —
  the pull-negotiation primitive) and pulls exactly those blocks, verifying
  it can reconstruct the head afterward. No silent full-repo copy; only the
  delta the receiver lacks moves.

  Pure cljc over a kotoba-git arrangement db (objects are datoms keyed by
  content hash). Needs the kotoba-git classpath (arrangement/prolly-tree/
  io-ipld/io-multiformats/org-ietf-cbor on the kotobase classpath)."
  (:require [bonsai.object :as obj]
            [bonsai.log :as glog]))

(defn read-object
  "Read a CID as whichever object kind it is (blob | tree | commit).
  -> {:kind :cid :data} or nil."
  [db cid]
  (or (when-let [b (obj/read-blob db cid)]  {:kind :blob :cid cid :bytes b})
      (when-let [t (obj/read-tree db cid)]  {:kind :tree :cid cid :entries (:entries t)})
      (when-let [c (obj/read-commit db cid)]{:kind :commit :cid cid :commit
                                             (select-keys c [:tree :parents :author :message :ts])})))

(defn visible-to?
  "Access control for private-repo object transfer (Radicle visibility model,
  B in the daily-driver plan). A public repo is visible to everyone; a private
  repo only to dids in its allow set. visibility:
    {:private? bool :allow #{did ...}}  (nil / absent = public)."
  [visibility peer-did]
  (or (nil? visibility)
      (not (:private? visibility))
      (contains? (:allow visibility) peer-did)))

(defn pack
  "Objects the peer needs to reconstruct head-cid, given the CIDs it `have`s.
  Returns a transfer bundle [obj ...] (each obj as read-object).
  3-arity is public (back-compat). 5-arity gates a PRIVATE repo: throws if
  the requesting peer-did is not in the repo's visibility allow set — a
  private repo's blocks are never served to a non-allowed peer."
  ([db head-cid have] (pack db head-cid have nil nil))
  ([db head-cid have visibility peer-did]
   (when-not (visible-to? visibility peer-did)
     (throw (ex-info "private repo: peer not in visibility allow set — refusing to serve objects"
                     {:peer peer-did :private? true})))
   (->> (glog/missing-since db head-cid have)
        (keep #(read-object db %))
        vec)))

(defn unpack
  "Apply a transfer bundle into a receiver db. Content-addressed writes are
  idempotent (re-deriving the same CID), so re-applying is a no-op. Returns
  [db' applied-cids]. Verifies each written CID matches the advertised CID
  (a peer cannot smuggle a different object under a claimed CID)."
  [db bundle]
  (reduce
   (fn [[d applied] {:keys [kind cid] :as o}]
     (let [[d' got] (case kind
                      :blob   (obj/write-blob d (:bytes o))
                      :tree   (obj/write-tree d (:entries o))
                      :commit (obj/write-commit d (:commit o)))]
       (when (not= (str got) (str cid))
         (throw (ex-info "object cid mismatch — corrupt/forged block"
                         {:advertised cid :computed got :kind kind})))
       [d' (conj applied got)]))
   [db []] bundle))

(defn have-set
  "The complete object set reachable from head-cid (its transitive closure of
  CIDs), for advertising to a peer as `have`. `missing-since db head #{}`
  returns exactly the reachable CIDs (it subtracts the empty have-set).
  Empty set if head unknown."
  [db head-cid]
  (if (nil? head-cid) #{}
      (glog/missing-since db head-cid #{})))

(defn reconstructable?
  "Can this db fully reconstruct head-cid — is every object reachable from it
  actually READABLE here? (missing-since returns reachable CIDs regardless of
  presence, so reconstructability is: every reachable CID reads back non-nil.)"
  [db head-cid]
  (every? #(some? (read-object db %))
          (glog/missing-since db head-cid #{})))
