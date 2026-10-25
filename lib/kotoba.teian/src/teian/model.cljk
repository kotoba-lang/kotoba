(ns teian.model
  "Pure data shapes teian holds. `draft` is the actor's own control-plane
  record — activity-id / kind (:deck|:doc|:sheet) / content / confidence /
  cites / redactions / tenant / status. `content` is NEVER teian's own
  representation: it is verbatim `kotoba-lang/slides` EDN (a `slides.model`
  workspace/deck/doc/sheet item) — teian holds it, it does not reinterpret or
  reimplement it (ADR-2607062000). `artifact` is the itonami-activity-shaped
  ground fact a draft is drafted FOR (id/repo/title/status); its :repo is the
  tenant a draft must match (BriefingGovernor's tenant-isolation invariant,
  teian.governor/teian.policy).")

(defn draft
  "A teian draft record. `content` is a slides.model EDN item (a deck/doc/
  sheet built with slides.model's own constructors) — teian never builds its
  own shape for it."
  ([activity-id kind content] (draft activity-id kind content {}))
  ([activity-id kind content attrs]
   (merge {:activity-id activity-id
           :kind kind
           :content content
           :confidence 0.0
           :cites []
           :redactions []
           :tenant nil
           :status :proposed}
          attrs)))

(defn artifact
  "The itonami-activity ground fact a briefing is drafted for. :repo is the
  tenant identity (e.g. \"gftdcojp/cloud-itonami\") a draft's own :tenant
  must equal — a cross-tenant draft is a HARD governor violation."
  ([id repo title] (artifact id repo title {}))
  ([id repo title attrs]
   (merge {:id id :repo repo :title title :status :open} attrs)))
