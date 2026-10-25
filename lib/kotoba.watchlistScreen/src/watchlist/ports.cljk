(ns watchlist.ports
  "The index seam -- watchlist.core never reads a file or hits a database
   directly, only through this protocol. Mirrors isekai.moderation/ekyc's
   'mechanism, not policy' split and kotoba-lang's house host-injection
   convention (num.protocol/IBackend, aml.ports/IAmlScreening, etc).")

(defprotocol IWatchlistIndex
  (entities [index]
    "All entities currently loaded, across every source the index was built
     from. A linear-scan match (watchlist.core/screen) over this is the v1
     performance characteristic -- see README.md/MATURITY.md for the honest
     caveat on scaling this to the full multi-source entity count.")
  (manifests [index]
    "The list-source manifests (watchlist.model/list-manifest maps) behind
     this index's data -- one per source actually loaded. A caller uses
     this to compute staleness (watchlist.model/stale?); an index that
     can't report a manifest for a source can't honestly claim to have
     screened against it."))
