(ns gijiroku.consent
  "Pure consent/privacy evaluation over meeting + consent ground facts — the
  gijiroku analog of kekkai.acl. No I/O, no store: plain maps, so both the
  independent PrivacyGovernor and the mock scribe-LLM can evaluate the same
  rules without coupling the censor to the proposer.

  A meeting's recording is consent-clean only when a `:consent/record` ground
  fact exists, recording was announced, a legal basis is on file, AND no
  participant explicitly declined — silence (no consent record at all, or a
  participant simply absent from `:participant-consents`) is NOT treated as
  consent, but neither is an explicit decline overridable by the meeting-level
  fields: `:participant-consents` was captured in the data model and seed
  fixtures from the start but never actually READ here, so a participant who
  explicitly declined (`{id false}`) was silently treated identically to one
  who consented."
  (:require [gijiroku.model :as m]))

(defn consent-clean?
  "Is `consent` sufficient to allow committing minutes for this meeting?"
  [consent]
  (boolean (and consent
                (:recording-announced? consent)
                (seq (:legal-basis consent))
                (not-any? false? (vals (:participant-consents consent))))))

(defn tenant-recipients
  "Filter `recipient-ids` down to those that are participants of `meeting`
  (deny-by-default: distribute never reaches an id outside the meeting's own
  roster/tenant)."
  [meeting recipient-ids]
  (let [allowed (set (m/participant-ids meeting))]
    (vec (filter allowed recipient-ids))))

(defn cross-tenant-recipients
  "Recipient ids NOT present in the meeting's own participant roster — a
  tenant-isolation violation if non-empty."
  [meeting recipient-ids]
  (let [allowed (set (m/participant-ids meeting))]
    (vec (remove allowed recipient-ids))))

(defn unredacted-sensitive-cites
  "Cited transcript segment ids that carry a :sensitive tag but are NOT
  covered by any of the proposal's declared `redactions` (seg-ids)."
  [transcript cites redactions]
  (let [sensitive-ids (set (map :seg-id (m/sensitive-segments transcript)))
        redacted (set redactions)]
    (vec (remove redacted (filter sensitive-ids cites)))))

(defn external-participants
  "Participants whose email domain differs from `tenant-domain` — presence of
  any flags the meeting's distribute op high-stakes."
  [meeting tenant-domain]
  (->> (:participants meeting)
       (filter #(m/external-domain? tenant-domain (:email %)))
       (mapv :id)))
