(ns kotoba.p2p.sync
  "P2P graph-sync protocol for kotoba's content-addressed commit chains —
  pure state machine, transport injected.

  Composes the layers below it instead of re-implementing them:

    - `kotoba.net.gossip`   — announce routing: content-hash dedup +
                              deterministic fanout (GossipSub semantics);
    - `kotoba.net.bitswap`  — `commits-since` delta over the commit log
                              (WantSince semantics);
    - `chain.core`          — chain walk + tamper/seq verification
                              (`kotoba-lang/chain`, renamed from
                              `commit-dag`, ADR-2607050800; this repo
                              tracks a current post-rename SHA);
    - `kotoba-client`       — CID-verified block ingest and the generic
                              tag-42 missing-blocks walk (`ipld-hydrate`).

  The tag-42 migration is what makes this protocol small: chain prev,
  snapshot state, index roots and tree children are all REAL IPLD links,
  so \"sync a graph\" collapses to \"hydrate the announced head CID to
  convergence, then `verify-chain`\". There is no per-schema transfer
  logic anywhere in this namespace.

  Purity contract: every handler is `(node, msg) -> {:node node'
  :effects [{:to peer-id :msg m} ...]}`. The ONLY side effects go through
  the node's injected `:store` ports (`put!`/`get-fn` — the same
  convention prolly-tree/chain use); the transport that delivers
  `:effects` is entirely the host's (see `kotoba.p2p.loopback` for the
  in-memory reference transport). No sockets, no crypto handshake, no
  wire framing here — a QUIC/WebRTC/WebTransport adapter is a host
  follow-up, not this namespace's job.

  Trust model: blocks are CID-verified on ingest (a lying peer's bytes
  are skipped, never stored), and a head is only adopted after
  `verify-chain` passes over fully-local blocks. A peer that withholds
  or corrupts blocks can stall sync (liveness), never corrupt state
  (safety) — the same split the browser read-plane ADR records: trust
  lives in the CID, not the transport.

  Head-record *signing* (proving an announce came from the graph owner)
  is pluggable, not built in: `new-node` takes optional `:sign-announce`
  (applied to every self-originated announce before it's gossiped) and
  `:verify-announce?` (checked before a peer's announce is trusted enough
  to chase with `want-since` — an unverified announce is still relayed,
  gossip-style, just not acted on locally) hooks. Both default to a no-op
  (`identity`/`(constantly true)`), so existing callers are unaffected.
  This namespace deliberately carries no crypto or identity scheme of its
  own — see e.g. `kotoba-lang/kotoba-rad`'s `kotoba-rad.announce` for a
  concrete did:key/sigref-based pair of hooks that plug in here."
  (:require [kotoba.net.gossip :as gossip]
            [kotoba.net.bitswap :as bitswap]
            [chain.core :as cd]
            [kotoba-client.core :as kc]
            [kotoba-client.ipld-hydrate :as ih]))

(def default-fanout
  "Gossip mesh degree D (matches kotoba.net.gossip's default)."
  6)

;; ── node state ────────────────────────────────────────────────────────────────
(defn new-node
  "A sync node: `id` names this peer, `store` is the injected block store
  `{:put! (cid bytes -> _) :get-fn (cid -> bytes-or-nil)}`.
  `:graphs` maps graph-id -> {:head-cid <cid> :seq <n> [:pending {...}]}.

  `opts` (optional, 3-arity): `:sign-announce` (fn [msg] -> msg') applied
  to every self-originated announce before it's gossiped (e.g. to attach
  a signature field); `:verify-announce?` (fn [msg] -> boolean) checked
  before a PEER's announce is trusted enough to chase with `want-since`.
  Both default to a no-op so 2-arity callers are unaffected."
  ([id store] (new-node id store {}))
  ([id store {:keys [sign-announce verify-announce?]
              :or {sign-announce identity verify-announce? (constantly true)}}]
   {:id id
    :peers (gossip/empty-peer-state)
    :seen (gossip/empty-seen-cache 1024)
    :graphs {}
    :store store
    :sign-announce sign-announce
    :verify-announce? verify-announce?}))

(defn add-peer
  "Register `peer-id` as reachable, subscribed to `topics` (graph-ids)."
  [node peer-id topics]
  (update node :peers gossip/add-peer peer-id (set topics)))

(defn set-head
  "Adopt `head-cid`/`seq` as the local head for `graph` (e.g. after a local
  commit!). Announcing it is a separate, explicit step — see `announce`."
  [node graph head-cid seq]
  (update-in node [:graphs graph] merge {:head-cid head-cid :seq seq}))

(defn head
  "{:head-cid :seq} for `graph`, or nil."
  [node graph]
  (when-let [{:keys [head-cid seq]} (get-in node [:graphs graph])]
    (when head-cid {:head-cid head-cid :seq seq})))

(defn- commit-log
  "The local commit log for `graph` as bitswap-shaped `[{:seq :cid} ...]`
  (oldest first), derived from the chain — no separate log is
  maintained."
  [node graph]
  (if-let [{:keys [head-cid]} (head node graph)]
    (mapv #(select-keys % [:seq :cid])
          (cd/chain (:get-fn (:store node)) head-cid))
    []))

;; ── announce (self-originated gossip) ─────────────────────────────────────────
(defn- announce-msg [node graph]
  (let [{:keys [head-cid seq]} (head node graph)
        msg {:type :head-announce :graph graph
             :head-cid head-cid :seq seq
             :origin (:id node) :from (:id node)}]
    ((:sign-announce node identity) msg)))

(defn announce
  "Gossip our local head for `graph` to the mesh. Returns {:node :effects}.
  Marks our own announce as seen so the mesh's echo of it dedups."
  [node graph]
  (if-let [_ (head node graph)]
    (let [msg (announce-msg node graph)
          targets (gossip/gossip-fanout (:peers node) graph #{(:id node)}
                                        default-fanout)
          h (gossip/content-hash (dissoc msg :from))]
      {:node (update node :seen gossip/mark-seen h)
       :effects (mapv (fn [t] {:to t :msg msg}) targets)})
    {:node node :effects []}))

;; ── handlers ──────────────────────────────────────────────────────────────────
(defn- handle-announce
  "Relay via gossip (dedup + fanout, :from rewritten to us, :origin kept),
  and — if the announced head is ahead of ours — ask the origin for the
  commit delta since our seq."
  [node {:keys [graph head-cid seq origin from] :as msg}]
  (let [{:keys [seen-cache forward]}
        (gossip/route-message (:peers node) (:seen node)
                              {:topic graph :payload (dissoc msg :from)
                               :from from :self (:id node)
                               :d default-fanout})
        node' (assoc node :seen seen-cache)
        fwd (mapv (fn [{:keys [to]}] {:to to :msg (assoc msg :from (:id node))})
                  forward)
        local-seq (get (head node graph) :seq -1)
        stale? (or (<= seq local-seq)
                   (= head-cid (:head-cid (head node graph)))
                   (not ((:verify-announce? node (constantly true)) msg)))]
    {:node node'
     :effects (if stale?
                fwd
                (conj fwd {:to origin
                           :msg (assoc (bitswap/make-want-since
                                        graph local-seq
                                        (:head-cid (head node graph)))
                                       :type :want-since
                                       :origin (:id node))}))}))

(defn- handle-want-since
  "Serve the requester the commit-log delta past their seq (bitswap
  WantSince semantics over the chain-derived log)."
  [node {:keys [graph-cid since-seq origin]}]
  (let [entries (bitswap/commits-since (commit-log node graph-cid)
                                       {:since-seq since-seq})
        {:keys [head-cid seq]} (head node graph-cid)]
    {:node node
     :effects [{:to origin
                :msg {:type :commits :graph graph-cid :entries entries
                      :head-cid head-cid :head-seq seq
                      :origin (:id node)}}]}))

(defn- promote
  "All blocks for the pending head are local: verify the chain and adopt it,
  then re-announce to our own mesh (so propagation continues hop by hop).
  A chain that fails verification is dropped, never adopted."
  [node graph]
  (let [{:keys [head-cid seq]} (get-in node [:graphs graph :pending])
        node' (update-in node [:graphs graph] dissoc :pending)]
    (if (cd/verify-chain (:get-fn (:store node)) head-cid)
      (announce (set-head node' graph head-cid seq) graph)
      {:node node' :effects []})))

(defn- want-or-promote
  "If blocks are still missing under the pending head, ask `source` for
  them; when the same want-set comes back twice with no progress (a
  withholding/lying peer), drop the pending head — stall, don't loop and
  don't adopt. Otherwise promote."
  [node graph source]
  (let [store (:store node)
        {:keys [head-cid last-missing]} (get-in node [:graphs graph :pending])
        missing (ih/missing-cids head-cid store)]
    (cond
      (empty? missing)
      (promote node graph)

      (= (set missing) last-missing)
      {:node (update-in node [:graphs graph] dissoc :pending) :effects []}

      :else
      {:node (assoc-in node [:graphs graph :pending :last-missing]
                       (set missing))
       :effects [{:to source
                  :msg {:type :want-blocks :graph graph :cids (vec missing)
                        :origin (:id node)}}]})))

(defn- handle-commits
  "Record the announced head as pending and start hydrating toward it."
  [node {:keys [graph entries head-cid head-seq origin]}]
  (if (and (seq entries) head-cid)
    (-> node
        (assoc-in [:graphs graph :pending]
                  {:head-cid head-cid :seq head-seq :source origin})
        (want-or-promote graph origin))
    {:node node :effects []}))

(defn- handle-want-blocks
  "Serve whichever of the wanted blocks we actually have (want/have
  intersection, keyed straight off the injected store)."
  [node {:keys [graph cids origin]}]
  (let [get-fn (:get-fn (:store node))
        blocks (into {} (keep (fn [c] (when-let [b (get-fn c)] [c b]))) cids)]
    {:node node
     :effects [{:to origin
                :msg {:type :blocks :graph graph :blocks blocks
                      :origin (:id node)}}]}))

(defn- handle-blocks
  "CID-verify and ingest each received block (a mismatching block is
  skipped — never stored), then continue hydrating or promote."
  [node {:keys [graph blocks origin]}]
  (let [{:keys [put!]} (:store node)]
    (doseq [[cid bytes] blocks]
      (when (try (kc/ingest-block cid bytes)
                 (catch #?(:clj Exception :cljs :default) _ nil))
        (put! cid bytes)))
    (if (get-in node [:graphs graph :pending])
      (want-or-promote node graph origin)
      {:node node :effects []})))

(defn handle
  "Pure protocol step: `(node, msg) -> {:node node' :effects [...]}`.
  Unknown message types are ignored (forward compatibility)."
  [node msg]
  (case (:type msg)
    :head-announce (handle-announce node msg)
    :want-since    (handle-want-since node msg)
    :commits       (handle-commits node msg)
    :want-blocks   (handle-want-blocks node msg)
    :blocks        (handle-blocks node msg)
    {:node node :effects []}))
