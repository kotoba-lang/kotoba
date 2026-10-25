(ns kotoba.dtn.router
  "Pure store-and-forward routing decision for a DTN bundle.

  This is a **direct-neighbor-or-store heuristic, plus one honestly-scoped
  extension: static single-hop-relay-via-a-configured-next-hop**. Given a
  bundle and the set of links currently known, route-decision either (1)
  forwards over a directly reachable link to the bundle's destination, or
  (2) — only when no direct link exists — consults a caller-supplied,
  PRE-CONFIGURED `routes` table for a next-hop that IS directly reachable
  and relays via it, or (3) holds the bundle in store awaiting a future
  contact opportunity (custody-free store-and-carry).

  The relay extension is deliberately narrow: `routes` is a static table
  the caller supplies (e.g. a node operator's own config) — there is NO
  automatic route discovery, NO route advertisement/gossip between nodes,
  and NO dynamic topology learning here. It is NOT full Contact Graph
  Routing (CGR, RFC 9174) — no future-contact-schedule lookahead, no
  multi-hop path search over a contact graph — and it is NOT epidemic /
  PRoPHET-style multi-hop relay routing — no forwarding to a
  non-destination neighbor on the probabilistic bet that they'll carry the
  bundle closer to its destination; a relay only happens via an explicit,
  operator-configured `{:dtn/destination ... :dtn/next-hop ...}` entry.
  This is one step beyond the prior direct-neighbor-or-store heuristic —
  'single-hop-relay-via-a-configured-next-hop' — not a general multi-hop
  routing protocol. An honestly-scoped subset, the same way kotoba-lang/apn
  documents its RWA solver as a single-link-deviation heuristic rather than
  full k-shortest-paths: this namespace does not claim multi-hop routing
  capability the code doesn't have.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.dtn :as dtn]))

(def default-priority
  "Default transport-kind preference order when route-decision isn't given
  an explicit priority: cheapest/fastest first. Callers running
  resilience-first (e.g. internet is known down) should pass their own
  ordering — see route-decision's :priority option."
  [:internet-overlay :mesh-radio :satellite])

(def default-max-hops
  "Default ceiling on :dtn/hop-count before route-decision refuses to
  return :relay (falls through to :store instead). A simple, honest
  loop-prevention heuristic — NOT proper DTN routing-loop detection (no
  per-node 'seen this bundle-id before' dedup here; see route-decision's
  docstring and kotoba.dtn.transport.tcp for where a lightweight
  seen-bundle-id set is layered on top at the transport level)."
  8)

(defn- priority-rank [priority]
  (into {} (map-indexed (fn [i k] [k i]) priority)))

(defn- reachable-link-to [links neighbor-eid]
  (first (filter #(and (= (:dtn/neighbor %) neighbor-eid) (:dtn/reachable? %)) links)))

(defn route-decision
  "Decide what to do with bundle given the currently known links.

  Finds links in links whose :dtn/neighbor equals the bundle's
  :dtn/destination AND whose :dtn/reachable? is true (a direct-neighbor
  match only). Among matches, prefers the one whose :dtn/transport-kind is
  earliest in priority (an ordered vector of transport-kinds; defaults to
  default-priority, but MUST be overridable — a resilience-first caller
  might pass [:mesh-radio :satellite :internet-overlay] when internet is
  down). A transport-kind absent from priority ranks after every listed
  kind.

  When NO direct link to the destination is reachable, and an optional
  `routes` coll is given (entries shaped
  {:dtn/destination eid :dtn/next-hop eid} — 'to reach :dtn/destination,
  forward to :dtn/next-hop instead'), looks for a routes entry whose
  :dtn/destination matches the bundle's :dtn/destination, then for a link
  in links whose :dtn/neighbor matches that entry's :dtn/next-hop AND is
  reachable. If both are found — and the bundle's current hop count (the
  `hop-count` option, defaulting to 0 when omitted, since kotoba.dtn/bundle
  itself has no :dtn/hop-count field; callers/transport layers that relay
  are expected to track and pass this) is below `max-hops` (defaults to
  default-max-hops) — returns {:dtn/action :relay :dtn/via <link>
  :dtn/next-hop <next-hop-eid>}, a distinct action keyword from :forward:
  a relay hop forwards the bundle one step CLOSER to its destination via a
  configured intermediate, not a final-hop delivery to the bundle's own
  destination, and callers (e.g. the transport layer, for logging/metrics)
  need to be able to tell the two apart even though the actual socket
  write is identical either way.

  Loop prevention is intentionally simple: when hop-count >= max-hops, no
  :relay is returned regardless of routes — a bundle that has hopped too
  many times without reaching its destination gets held (:store), not
  endlessly bounced. This is NOT proper DTN routing-loop detection (no
  per-bundle-id dedup here); see kotoba.dtn.transport.tcp for an optional,
  additional seen-bundle-id suppression layered on top at the transport
  level.

  Falls through to {:dtn/action :store} when there's no direct link, no
  matching routes entry, the matched next-hop isn't currently reachable,
  or hop-count is at/over max-hops."
  [bundle links & {:keys [priority routes hop-count max-hops]}]
  (let [priority   (or priority default-priority)
        rank       (priority-rank priority)
        fallback   (count priority)
        dest       (:dtn/destination bundle)
        candidates (filter #(and (= (:dtn/neighbor %) dest) (:dtn/reachable? %)) links)
        best       (when (seq candidates)
                     (apply min-key #(get rank (:dtn/transport-kind %) fallback) candidates))]
    (cond
      best
      {:dtn/action :forward :dtn/via best}

      (< (or hop-count 0) (or max-hops default-max-hops))
      (let [route    (first (filter #(= (:dtn/destination %) dest) routes))
            next-hop (:dtn/next-hop route)
            via      (when next-hop (reachable-link-to links next-hop))]
        (if via
          {:dtn/action :relay :dtn/via via :dtn/next-hop next-hop}
          {:dtn/action :store}))

      :else
      {:dtn/action :store})))

(defn expire-store
  "Partition bundles into kept/expired per kotoba.dtn/expired? at now-ms.
  Returns {:kept [...] :expired [...]} — the store-and-forward eviction
  pass a node runs to drop bundles whose retention constraint has elapsed."
  [bundles now-ms]
  (let [{expired true kept false} (group-by #(dtn/expired? % now-ms) bundles)]
    {:kept (vec (or kept [])) :expired (vec (or expired []))}))
