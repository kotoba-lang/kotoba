(ns watchlist.adapters.eu-consolidated
  "EU Consolidated Financial Sanctions List -- NOT IMPLEMENTED in v1.

   HONESTY NOTE (do not remove): unlike OFAC's sdn.xml and the UN's
   consolidated.xml (both freely downloadable over plain HTTPS, no
   authentication -- this repo's OFAC/UN adapters were built and tested
   against the real, live files), the EU's own machine-readable source (the
   Financial Sanctions Files / FSD API at
   webgate.ec.europa.eu/fsd/fsf/public/...) requires a REGISTERED ACCESS
   TOKEN to fetch -- confirmed during this repo's development: every
   unauthenticated attempt returned HTTP 500. Provisioning that token is a
   real owner action (register at the EU's sanctions portal), not something
   this repo can script around, and this ns will not guess at a schema it
   has never actually seen live data for -- doing so would risk exactly the
   false-confidence failure mode (a parser that LOOKS like it handles EU
   sanctions data without ever having been checked against the real thing)
   this repo's other adapters were built specifically to avoid.

   Once a token is provisioned (see README.md), implement this the same way
   as watchlist.adapters.ofac-sdn / .un-consolidated: fetch real live data,
   verify the parser against it, THEN add :eu-consolidated to
   watchlist.model/sources.")

(defn parse
  "Always throws -- see this ns's module doc. Present so a caller wiring up
   all three sources gets a clear, immediate, honest failure instead of a
   silent no-op or fabricated result."
  [_xml-str]
  (throw (ex-info "watchlist.adapters.eu-consolidated: not implemented -- the EU FSD API requires a registered access token this repo does not have. See this ns's module doc." {})))
