(ns denrei.model
  "Unified data shapes denrei carries across the ingest/assess flow.

  denrei does NOT reimplement the communication-space schema —
  `kotoba-lang/kaisha` (`kaisha.model`) already has a portable, pure-EDN
  space/channel/message model (:kaisha/id/author/body/at/thread/reactions)
  with ZERO posting/consent/governor concept. denrei's `draft` holds that
  message EDN verbatim inside :content and adds only what its own governor
  needs on top: a :tenant (for tenant-isolation), the target :channel, plus
  the usual propose/govern bookkeeping (:confidence :cites :redactions
  :status).

    draft   — the post-LLM's proposed content for a kaisha.model message:
              activity-id (the itonami activity driving this), message-id,
              content ({:tenant :space :channel :message <kaisha message EDN>}),
              confidence, cites, redactions, status (:proposed/:posted).
    contact — a member's consent record, keyed by @mention handle — the
              denrei analog of tayori.store's contact map (mirrored 1:1:
              same :consent :known|:blocked / :first-contact? semantics),
              applied to mentioned members instead of message recipients.")

(defn draft
  ([activity-id message-id content] (draft activity-id message-id content {}))
  ([activity-id message-id content attrs]
   (merge {:activity-id activity-id
           :message-id  message-id
           :content     content
           :confidence  0.0
           :cites       []
           :redactions  []
           :status      :proposed}
          attrs)))

(defn contact
  ([handle] (contact handle {}))
  ([handle attrs]
   (merge {:handle handle :consent :known :first-contact? false} attrs)))
