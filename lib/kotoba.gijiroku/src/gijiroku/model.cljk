(ns gijiroku.model
  "The canonical meeting-record data model shared by every Platform
  implementation and by the Store. Plain maps, no I/O — Zoom/Meet/Teams
  clients each normalize their native payloads into these shapes so the rest
  of the actor (scribe-LLM, PrivacyGovernor, Store) never branches on
  platform.

    meeting    — {:id :platform :external-id :title :host :tenant
                  :participants [{:id :email :domain}] :status :scheduled-start}
    consent    — {:meeting-id :recording-announced? :participant-consents
                  {participant-id bool} :legal-basis :jurisdiction}
    recording  — {:id :meeting-id :platform :asset-ref :duration-s :format}
                 asset-ref points at object storage (e.g. a B2 key) or the
                 platform's own download URL — raw bytes never enter the
                 store or git.
    transcript — {:id :meeting-id :source :lang :segments
                  [{:seg-id :speaker :t0 :t1 :text :sensitive #{}}]}
                 :sensitive is a set of tags (:health :legal :financial ...)
                 a redaction pass or the ingest source may pre-mark.
    minutes    — the committed assessment: {:meeting-id :summary :decisions
                  :action-items :cites :redactions :by}

  :tenant is the consuming org (\"cloud-itonami\" \"cloud-manimani\" ...) —
  the PrivacyGovernor's tenant-isolation invariant keys off it."
  (:require [kotoba.lang.text :as str]))

(defn external-domain?
  "Is `email`'s domain outside `tenant-domain`? Used to flag guest
  participants for the PrivacyGovernor's high-stakes distribute gate."
  [tenant-domain email]
  (let [domain (some-> email (str/split #"@") second str/lower)]
    (boolean (and domain tenant-domain (not= domain (str/lower tenant-domain))))))

(defn participant-ids [meeting] (mapv :id (:participants meeting)))

(defn sensitive-segments [transcript]
  (filterv #(seq (:sensitive %)) (:segments transcript)))
