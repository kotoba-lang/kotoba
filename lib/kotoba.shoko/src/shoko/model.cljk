(ns shoko.model
  "Pure data shapes shoko holds. shoko does NOT reimplement the file/folder
  EDN model — `kotoba-lang/drive` (`drive.model`) already has a portable,
  pure-EDN model (`drive`/`folder`/`file`/`add-child`/`children`) with ZERO
  ACL/sharing concept (verified — grepping acl|access-control|permission|share
  across it is a zero hit). shoko's `draft` holds a `drive.model` file/folder
  item verbatim as :content and adds only what its own governor needs on top:
  the activity/file this archival record is for, confidence/cites/redactions,
  and a status.

  `grant` is shoko's OWN ACL ledger — drive.model has no access-control
  concept at all, so shoko must carry it independently. A grant is keyed by
  the (principal, file-id) pair (`grant-id`); ArchiveGovernor's
  share-requires-acl invariant (kekkai.acl's deny-by-default analog) treats a
  principal as 'known' only once SOME grant record already exists for them
  (on ANY file, not necessarily this one) — an entirely unregistered
  principal can never receive a brand-new share (see shoko.governor).")

(defn draft
  "A shoko archival draft. `content` is a drive.model EDN item (a file/folder
  built with drive.model's own constructors) — shoko never builds its own
  shape for it."
  ([activity-id file-id content] (draft activity-id file-id content {}))
  ([activity-id file-id content attrs]
   (merge {:activity-id activity-id
           :file-id     file-id
           :content     content
           :confidence  0.0
           :cites       []
           :redactions  []
           :status      :proposed}
          attrs)))

(defn grant-id
  "The composite Store key for a (principal, file-id) grant pair."
  [principal file-id]
  (str principal "@" file-id))

(defn grant
  "A shoko ACL grant record — the actor's own access-control ledger entry,
  since drive.model itself has none. :access is a set of capability
  keywords (e.g. #{:read}). :granted-by/:granted-at are filled in at commit
  time by the human who approved the :file/share (never self-asserted by the
  archive-LLM's proposal)."
  ([principal file-id] (grant principal file-id {}))
  ([principal file-id attrs]
   (merge {:principal   principal
           :file-id     file-id
           :access      #{:read}
           :granted-by  nil
           :granted-at  nil}
          attrs)))

(defn activity
  "The itonami activity a file archival/share is driven by. :repo is the
  tenant identity (e.g. \"gftdcojp/cloud-itonami\") a file's own :tenant
  must equal — a cross-tenant draft/share is a HARD governor violation."
  ([id repo title] (activity id repo title {}))
  ([id repo title attrs]
   (merge {:id id :repo repo :title title :status :open} attrs)))
