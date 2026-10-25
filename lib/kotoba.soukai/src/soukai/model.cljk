(ns soukai.model
  "Unified data shapes soukai carries across the ingest/assess flow.

  Unlike koyomi (which holds a `calendar.model` event verbatim as :content
  and adds only bookkeeping on top), soukai has no separate upstream domain
  model to defer to — meeting/record-date-snapshot/agenda/vote are soukai's
  OWN ground facts (see `soukai.store`'s docstring for their shapes). This
  namespace holds only `draft`: the secretary-LLM's proposal wrapper.

  Unlike koyomi's `draft` (which carries both an :activity-id — the
  itonami activity driving the request — and an :event-id — the subject),
  soukai's draft doesn't need that two-id indirection: the meeting/agenda
  ground fact a draft is about IS its own driving fact, referenced directly
  by :subject-key. Three draft KINDS share one drafts map
  (convocation/resolution/minutes — see `soukai.store`'s key-convention
  constructors), so :subject-key is a compound `[kind id]` tuple rather
  than koyomi's single :event-id string — this is the field-name adaptation
  soukai's domain needs (kind disambiguation koyomi never had, since it
  only ever drafts one kind of thing: an event)."
  )

(defn draft
  ([subject-key content] (draft subject-key content {}))
  ([subject-key content attrs]
   (merge {:subject-key subject-key
           :content     content
           :confidence  0.0
           :cites       []
           :redactions  []
           :status      :proposed}
          attrs)))
