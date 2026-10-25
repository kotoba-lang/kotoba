(ns face-match.core
  "Face-match comparison. HONESTY NOTE (do not remove, read before touching
   this ns): comparing a selfie photo against a document photo needs a real
   face-embedding model with a real, validated false-accept/false-reject
   rate -- this repo does not have one, does not attempt to fake one, and
   does not know of any legitimately portable open-weights model this org
   could responsibly hand-port and ship without real benchmark data (see
   MATURITY.md for the full reasoning and the re-evaluation conditions).

   `compare` therefore ALWAYS routes to human review when called with no
   matcher (the only way it is called anywhere in this org today) --
   shipping an unvalidated home-grown embedding path here would give
   exactly the false confidence ('looks like it verified, actually
   didn't') the whole eKYC/AML effort this repo is part of was structured
   to avoid (see kotoba-lang/mrz's ADR-2607198200 for the same principle
   applied to document optical capture)."
  (:require [face-match.model :as model]
            [face-match.ports :as ports]))

(defn match
  "Compare `selfie-image` against `document-image`. Without a `matcher`
   (the default, and the only way any caller in this org invokes this
   today), always returns {:face-match/status :review
   :face-match/reason :not-implemented} -- route the check to human
   review, never auto-approve or auto-reject a face-match check.

   `matcher` is an OPTIONAL injected face-match.ports/IFaceMatcher -- the
   seam a real future implementation would plug into. If given and it
   returns a real outcome, that outcome is surfaced (:verified/:flagged);
   if given and it returns nil (couldn't attempt a comparison), this still
   falls back to :review, never to a guess."
  ([selfie-image document-image] (match selfie-image document-image nil {}))
  ([selfie-image document-image matcher opts]
   (if-let [outcome (and matcher (ports/compare-faces matcher selfie-image document-image))]
     (model/compare-result (merge opts {:status (if (:match? outcome) :verified :flagged)
                                         :confidence (:confidence outcome)
                                         :reason nil}))
     (model/compare-result (merge opts {:status :review
                                         :confidence nil
                                         :reason (if matcher :matcher-returned-nil :not-implemented)})))))
