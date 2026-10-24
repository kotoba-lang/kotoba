"""ooyake 公 Pregel cell catalog (R0 scaffold; outward cells gated).

Per ADR-2606021600. ooyake is the READ-SIDE structural atlas of public
administration. Cells:

  unit_registry   maintain/resolve the :gov.unit/* tree (reuben, continuous)
  reconcile       reconcile units vs external authorities (reuben, event)
  address_ingest  ingest 住所/窓口 from official sources (gad, event)
  procedure_link  link :gov.procedure/* ↔ toritsugi + chigiri + bpmn (gad, event)
  atlas_serve     serve per-unit profile + READ-ONLY XRPC (naphtali, continuous)
  freshness       re-verify within the freshness window (naphtali, continuous)

CONSTITUTIONAL gates (ADR-2606021600 §4):
  G3   observational mirror only — never the gov, never an official channel,
       never issues/accepts on a gov's behalf (§2(c))
  G4   public-data-only — only public official sources; respect robots/ToS/
       rate-limits; no behind-auth access (LIVE reconcile/ingest gated here)
  G5   non-fabrication — provenance + last-verified + sourcing on every datom;
       :representative never counted as coverage
  G9   read-side only — never files/submits/mutates a gov record (→ toritsugi);
       never audits/adjudicates (→ danjo)
  G10  civic wayfinding, never a target-list

R1 status: `reconcile` runs in BUNDLED mode (offline, deterministic, against
registry/authority-reference.edn) — that path is NOT gated. The LIVE mode (real
Wikidata / 行政機関コード / 全国地方公共団体コード / GeoNames fetch) raises until
Council Lv6+ ratifies and operator enables it (G4). All other cells are R0
scaffolds and raise on solve().
"""
