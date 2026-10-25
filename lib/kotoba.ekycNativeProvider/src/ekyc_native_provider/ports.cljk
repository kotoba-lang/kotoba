(ns ekyc-native-provider.ports
  "The evidence-fetch seam. ekyc.adapters.provider's IEkycProviderClient
   contract (which this repo implements, see .core) only ever hands a
   provider a REFERENCE (:evidence-ref / :custody-ref) to already-stored
   evidence -- ekyc.model/evidence and ekyc.adapters.provider's own
   evidence-payload carry no raw bytes field at all, by design (raw
   document/selfie/frame data goes through ekyc.adapters.kagi-custody
   separately, upstream of this provider). ekyc.adapters.provider only
   defines a WRITE-side custody protocol (IEvidenceCustody/commit-evidence!)
   -- there is no read-back protocol anywhere in ekyc for a provider to
   resolve a ref back to content, so this repo defines its own, mirroring
   the same host-injection shape every sibling engine repo already uses
   (mrz.ports/IZoneOcr, face-liveness.ports/ILandmarkTracker,
   face-match.ports/IFaceMatcher).

   NO IMPLEMENTATION SHIPS IN THIS REPO. A real integration supplies one
   backed by wherever it actually stores evidence (e.g.
   ekyc.adapters.kagi-custody's kagi:// store).")

(defprotocol IEvidenceFetcher
  (fetch-evidence [fetcher check evidence-ref]
    "Resolve `evidence-ref` to the per-check content
     ekyc-native-provider.core/score-check expects for `check`:
       :document-ocr -> {:mrz-lines [line1 line2 ...]}
       :liveness     -> {:challenge <face-liveness.model/challenge>
                          :frames [<face-liveness.model/frame> ...]}
       :face-match   -> {:selfie ... :document-photo ...}
     Returns nil if the reference cannot be resolved (a caller must treat
     nil as 'cannot score this evidence', never as an automatic pass or
     fail -- see .core/score-check's own fail-to-:review discipline)."))
