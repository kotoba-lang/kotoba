(ns commoncrawl.policy
  "Governor — the independent gate a fetched-and-LLM-extracted page must
  clear before `:commit` ever calls `commoncrawl.kotobase/ingest!`. The
  LLM (`commoncrawl.llm`) has no notion of scope/budget/trust; this MUST
  be a separate check able to reject a proposal and fall back to HOLD
  (write nothing) — same single invariant every actor in this workspace
  shares (talent.policy's docstring: 'the LLM has no notion of permission
  ... so this MUST be a separate system').

  Three checks, HARD (a HOLD no downstream node can override — there is no
  human-approval node in this actor's graph, unlike talent's
  `:request-approval`, so a HARD violation here is final):

    1. Seed-domain scope — is the target domain actually in the configured
       seed list (`commoncrawl.seeds`)? ADR-2607192200's whole honesty
       claim ('not arbitrary-keyword whole-web discovery') is enforced
       HERE, not by convention — fetching/ingesting anything outside the
       seed list is a hard violation with no override.
    2. Exclude list — an operator-maintained denylist (robots.txt-shaped:
       a domain a seed owner has asked not to be (re-)crawled) always
       wins over the seed list.
    3. Per-tick fetch budget — `commoncrawl.loop`'s outer driver already
       caps how many graph runs it starts per tick, but this is checked
       again here too (defense in depth, same 'governor rejects, actor
       never proceeds regardless of what called it' posture every actor
       in this workspace uses) given a budget snapshot in `context`.

  One SOFT check (confidence floor) — low LLM-extraction confidence still
  routes to HOLD in THIS actor (there is no approval node to escalate to),
  but is recorded with a distinct `:soft?`/`:rule :low-confidence` basis so
  an operator reviewing the ledger can tell 'we chose not to trust this
  extraction' apart from 'this was out of scope' — and so a future
  human-approval node could be added without changing this contract."
  (:require [commoncrawl.seeds :as seeds]))

(def confidence-floor
  "Below this, an LLM extraction is not trusted enough to commit
  unattended — same idea as talent.policy/confidence-floor, tuned lower
  (0.5 vs 0.6) because a wrong :category/:summary here is a much lower-
  stakes mistake than an HR evaluation error (worst case: a mediocre
  search snippet, not a discriminatory personnel action)."
  0.5)

(defn- out-of-scope? [seeds domain] (nil? (seeds/seed-for-domain seeds domain)))

(defn- excluded? [exclude-set domain] (contains? (or exclude-set #{}) domain))

(defn- budget-exceeded? [{:keys [used cap]}]
  (and (number? used) (number? cap) (>= used cap)))

(defn check
  "request: {:domain :url} — the seed being processed this run.
  context: {:seeds [...] :exclude #{...} :budget {:used :cap}}.
  proposal: the commoncrawl.llm/advise proposal (needs :confidence).

  Returns {:ok? bool :hard? bool :violations [{:rule :detail} ...]
           :soft? bool :confidence num}.
    :hard?  — at least one HARD violation (scope/exclude/budget). Forces
              HOLD, unconditionally.
    :soft?  — confidence below floor, no hard violation. Also HOLDs in
              this actor (no approval node) but tagged distinctly.
    :ok?    — clean AND not soft: safe to commit."
  [{:keys [domain]} {:keys [seeds exclude budget]} proposal]
  (let [hard (into []
                   (concat
                    (when (out-of-scope? seeds domain)
                      [{:rule :out-of-scope :detail (str domain " is not in the configured seed list")}])
                    (when (excluded? exclude domain)
                      [{:rule :excluded :detail (str domain " is on the exclude list")}])
                    (when (budget-exceeded? budget)
                      [{:rule :budget-exceeded
                        :detail (str "tick fetch budget exhausted (" (:used budget) "/" (:cap budget) ")")}])))
        conf (:confidence proposal 0.0)
        hard? (boolean (seq hard))
        soft? (and (not hard?) (< conf confidence-floor))]
    {:ok? (and (not hard?) (not soft?))
     :hard? hard?
     :soft? soft?
     :violations hard
     :confidence conf}))

(defn hold-fact
  "The audit fact written when a proposal is rejected (HOLD). Mirrors
  talent.policy/hold-fact's shape (`:t :policy-hold`, `:basis` = rule
  names) so ledger tooling shared across actors (e.g. a future cross-actor
  ledger viewer) can render either without special-casing."
  [{:keys [domain url]} verdict]
  {:t :policy-hold
   :domain domain
   :url url
   :basis (mapv :rule (:violations verdict))
   :violations (:violations verdict)
   :soft? (:soft? verdict)
   :confidence (:confidence verdict)})
