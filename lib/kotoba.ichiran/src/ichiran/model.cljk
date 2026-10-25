(ns ichiran.model
  "Pure data shapes ichiran holds. `draft` is the actor's own control-plane
  record — activity-id / workbook-id / content / confidence / cites /
  redactions / tenant / status. `content` is NEVER ichiran's own
  representation: it is verbatim `kotoba-lang/sheets` EDN (a `sheets.model`
  workbook item, built with sheets.model's own constructors) — ichiran holds
  it, it does not reinterpret or reimplement it (ADR-2607062030). `artifact`
  is the itonami-activity-shaped ground fact a tally is drafted FOR
  (id/repo/title/status); its :repo is the tenant a draft must match
  (TallyGovernor's tenant-isolation invariant, ichiran.governor/
  ichiran.policy).")

(defn draft
  "An ichiran draft record. `content` is a sheets.model workbook EDN item
  (built with sheets.model's own constructors) — ichiran never builds its own
  shape for it. `workbook-id` is the id of that workbook (its own
  :sheets/id) — kept alongside `activity-id` because a single itonami
  activity's tally workbook is its own addressable artifact (the ichiran
  analog of koyomi's activity-id/event-id pair, adapted to teian's flat
  single-draft-per-artifact store shape: draft-of is still keyed by
  activity-id, workbook-id is carried for audit/port calls)."
  ([activity-id workbook-id content] (draft activity-id workbook-id content {}))
  ([activity-id workbook-id content attrs]
   (merge {:activity-id activity-id
           :workbook-id workbook-id
           :content content
           :confidence 0.0
           :cites []
           :redactions []
           :tenant nil
           :status :proposed}
          attrs)))

(defn artifact
  "The itonami-activity ground fact a tally workbook is drafted for. :repo is
  the tenant identity (e.g. \"gftdcojp/cloud-itonami\") a draft's own :tenant
  must equal — a cross-tenant draft is a HARD governor violation."
  ([id repo title] (artifact id repo title {}))
  ([id repo title attrs]
   (merge {:id id :repo repo :title title :status :open} attrs)))
