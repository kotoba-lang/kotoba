(ns kotoba.dtn.link
  "Link/contact records — a directly observed neighbor over whatever
  transport is currently available. Pure data, no network I/O and no
  liveness probing of its own: callers populate :dtn/reachable? from
  whatever transport layer (internet-overlay P2P, mesh radio, satellite)
  they actually run.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.dtn :as dtn]))

(def transport-kinds
  "The transport kinds this substrate is deliberately scoped to: an
  internet-overlay P2P link, a local mesh-radio link, or a satellite link.
  Not an open-ended enum — kotoba.dtn.router only knows how to prioritize
  these three."
  #{:internet-overlay :mesh-radio :satellite})

(defn link
  "Construct a link/contact record to a neighbor. id is caller-assigned.
  neighbor-e164 is the neighbor's E.164 number (wrapped to a dtn: EID).
  transport-kind must be one of transport-kinds.

  Optional: :reachable? (defaults to false — an unconfirmed link is not
  assumed reachable), :bandwidth-bps, :last-seen (caller's own clock/epoch,
  opaque to this namespace).

  Returns nil when transport-kind is not recognized or neighbor-e164 is
  not a valid E.164 number."
  [id neighbor-e164 transport-kind & {:keys [reachable? bandwidth-bps last-seen]}]
  (when (contains? transport-kinds transport-kind)
    (when-let [neighbor (dtn/eid neighbor-e164)]
      {:dtn/link-id id
       :dtn/neighbor neighbor
       :dtn/transport-kind transport-kind
       :dtn/reachable? (boolean reachable?)
       :dtn/bandwidth-bps bandwidth-bps
       :dtn/last-seen last-seen})))
