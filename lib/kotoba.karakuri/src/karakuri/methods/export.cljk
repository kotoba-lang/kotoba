(ns karakuri.methods.export
  "karakuri (絡繰) T3 structured-export — the data-portability / anti-lock-in leg (G9).

  1:1 Clojure port of `methods/export.py`.

  The structural inverse of vendor lock-in: pull the MEMBER's OWN data out of a service into a
  portable kotoba-native form (or push it into another service). Two G9 invariants are enforced
  by construction: the export owner is always the member (no third-party PII), and the export is
  always encrypted (an encrypted-envelope ref per com.etzhayyim.encrypted.*, ADR-2605181100 —
  the artifact carries a CID/ref, never plaintext). Live fetch is G6-gated; R0 produces an
  export PLAN only.

  ExportArtifact is a plain map with the Python dataclass field names as kebab keywords. Pure
  clojure.core; portable .cljc."
  (:require [kotoba.lang.text :as str]))

(def MEMBER "member")                                   ; G9 — own data only
(def EXPORT-FORMATS ["kotoba-edn" "json" "csv" "markdown"])
(def ENCREF-PREFIX "encref:")

(defn- owner-violation
  "ex-info marked as an owner violation (G9 — anything but the member's OWN data)."
  [msg]
  (ex-info msg {:type :owner-violation}))

(defn make-export-artifact
  "ExportArtifact constructor — a plain map mirroring the Python dataclass field defaults."
  [service fmt & {:keys [owner encrypted cid secret-ref dry-run roundtrip-ok]
                  :or {owner MEMBER                ; G9 const
                       encrypted true              ; G9 const
                       cid ""                      ; content-addressed ref of the encrypted export
                       secret-ref ""               ; encrypted-envelope ref (G9; never plaintext)
                       dry-run true                ; G6
                       roundtrip-ok false}}]
  {:service service
   :fmt fmt
   :owner owner
   :encrypted encrypted
   :cid cid
   :secret-ref secret-ref
   :dry-run dry-run
   :roundtrip-ok roundtrip-ok})

(defn build-export-plan
  "Build a dry-run T3 export plan for the MEMBER's OWN data (G9). Raises on a non-member owner or
  an unknown format. The plan is encrypted-by-construction; the live fetch is G6-gated."
  [service & {:keys [fmt owner secret-ref]
              :or {fmt "kotoba-edn" owner MEMBER secret-ref ""}}]
  (when (not= owner MEMBER)
    (throw (owner-violation
            "G9 violation: export covers the member's OWN data only; no third-party data/PII")))
  (when-not (some #{fmt} EXPORT-FORMATS)
    (throw (ex-info (str "unknown export format " (pr-str fmt) "; allowed: " (pr-str EXPORT-FORMATS))
                    {:fmt fmt})))
  (when (and (seq secret-ref) (not (str/starts-with? secret-ref ENCREF-PREFIX)))
    (throw (ex-info "G9 violation: secret_ref must be an encrypted-envelope ref (encref:…)"
                    {:secret-ref secret-ref})))

  (make-export-artifact
   service fmt
   :owner MEMBER :encrypted true
   :secret-ref (if (seq secret-ref)
                 secret-ref
                 (str "encref:com.etzhayyim.encrypted/" service "-export"))
   :dry-run true))

(defn verify-roundtrip
  "Portability check: an export must be re-importable in the same kotoba-native shape it left in.

  At R0 this validates the artifact's portability invariants (member-owned, encrypted, known
  format) rather than moving bytes — the live pull/push is G6-gated. Returns the artifact with
  :roundtrip-ok set; raises if it could not be a faithful, charter-clean round-trip."
  [artifact]
  (when (not= (:owner artifact) MEMBER)
    (throw (owner-violation "G9 violation: round-trip of non-member data is refused")))
  (when-not (:encrypted artifact)
    (throw (ex-info "G9 violation: an export must be encrypted to round-trip" {})))
  (when-not (some #{(:fmt artifact)} EXPORT-FORMATS)
    (throw (ex-info (str "non-portable format " (pr-str (:fmt artifact))) {:fmt (:fmt artifact)})))
  (assoc artifact :roundtrip-ok true))
