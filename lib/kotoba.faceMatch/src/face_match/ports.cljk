(ns face-match.ports
  "The face-embedding/comparison seam. NO IMPLEMENTATION SHIPS IN THIS
   REPO OR ANYWHERE ELSE IN THIS ORG TODAY (2026-07-19) -- see README.md
   and MATURITY.md for why. This protocol exists so a future real
   implementation (a license-cleared, benchmarked embedding model, ported
   to kotoba-lang/torch+num and validated against a real false-accept/
   false-reject rate) has a clean seam to plug into, mirroring
   mrz.ports/IZoneOcr and face-liveness.ports/ILandmarkTracker's own
   host-injection shape.")

(defprotocol IFaceMatcher
  (compare-faces [matcher selfie-image document-image]
    "`selfie-image`/`document-image` are opaque to this protocol -- a real
     implementation defines its own shape. Returns {:match? bool
     :confidence double} on a real, validated comparison, or nil if no
     comparison could be attempted. No implementation of this protocol
     exists in this repo."))
