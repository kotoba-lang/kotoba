(ns koyomi.model
  "Unified data shapes koyomi carries across the ingest/assess flow.

  koyomi does NOT reimplement the calendar event schema — `kotoba-lang/calendar`
  (`calendar.model`) already has a portable, pure-EDN event model
  (:calendar/id/title/start/end/attendees/links) with ZERO ICS-export/consent/
  governor concept (verified — grepping ics|ical|share|publish across it is a
  zero hit). koyomi's `draft` holds that event EDN verbatim as :content and
  adds only what its own governor needs on top: a :tenant (for
  tenant-isolation) plus the usual propose/govern bookkeeping (:confidence
  :cites :redactions :status).

    draft   — the schedule-LLM's proposed content for a calendar.model event:
              activity-id (the itonami activity driving this), event-id,
              content (a calendar.model event EDN, :tenant-tagged),
              confidence, cites, redactions, status (:proposed/:shared).
    contact — an attendee's consent record — the koyomi analog of
              tayori.store's contact map (mirrored 1:1: same :consent
              :known|:blocked / :first-contact? semantics), applied to
              calendar attendees instead of message recipients."
  )

(defn draft
  ([activity-id event-id content] (draft activity-id event-id content {}))
  ([activity-id event-id content attrs]
   (merge {:activity-id activity-id
           :event-id    event-id
           :content     content
           :confidence  0.0
           :cites       []
           :redactions  []
           :status      :proposed}
          attrs)))

(defn contact
  ([attendee] (contact attendee {}))
  ([attendee attrs]
   (merge {:attendee attendee :consent :known :first-contact? false} attrs)))
