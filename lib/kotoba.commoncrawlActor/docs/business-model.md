# Business model fit

`kotobase-commoncrawl-actor` grows the searchable corpus behind
net-kotobase's `web.search` (`ai.gftd.apps.kotobase.web.search`) and gives
cloud-itonami business-entity actors (ISIC actors, starting with
`cloud-itonami-isic-8291`) a richer web-presence lookup that complements —
not replaces — `dossier.commoncrawl`'s narrower exists/does-not-exist
verification.

This is deliberately **not** sold as "Google-parity whole-web search" — see
this repo's README "Honest scope" section and the parent ADR
(`90-docs/adr/2607192200-...`). The value proposition is an
incrementally-growing, hybrid-searchable (token + vector) corpus of
domains an operator actually cares about (starting with cloud-itonami's own
company/entity registries), extensible by anyone who forks this repo and
edits `resources/seeds.edn` — no code change, no new infrastructure.

## Who runs this

Same OSS-actor-as-open-business posture as `gftd-talent-actor`/
`cloud-itonami`: anyone may fork and operate their own instance against
their own net-kotobase tenant graph (their own CACAO identity, their own
seed list). There is no vendor lock-in and no per-seat SaaS fee — the cost
is whatever Common Crawl bandwidth + murakumo inference/embeddings + a
scheduler invocation actually consume.
