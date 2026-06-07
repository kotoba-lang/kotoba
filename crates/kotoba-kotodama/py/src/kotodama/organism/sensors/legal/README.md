# kotodama.organism.sensors.legal — Legal-corpus sensors

Per **ADR-2605262800**. Five sensor families that extend the DatasetSensor
Protocol from ADR-2605262400 §3 to legal documents.

## Sensor families

| Family | Protocol class | Bucket family | Wave-1 implementations |
|---|---|---|---|
| Statute | `LegalStatuteSensor` | `law/statutes/<jurisdiction>/` | `us_usc_sensor` + `us_cfr_sensor` + `jp_egov_sensor` + `eu_eurlex_sensor` + `uk_legislation_sensor` |
| Case | `LegalCaseSensor` | `law/cases/<court>/` | W2 deliverable |
| Treaty | `LegalTreatySensor` | `law/treaties/<corpus>/` | W3 deliverable |
| Procedure | `LegalProcedureSensor` | `law/procedures/<body>/` | W2 deliverable |
| Template | `LegalTemplateSensor` | `law/templates/<corpus>/` | W3 deliverable |

## Wave-1 anchor jurisdictions (5)

| Sensor | Source | License | Tier |
|---|---|---|---|
| `us_usc_sensor` | US Code (Office of Law Revision Counsel) | public domain | A |
| `us_cfr_sensor` | Code of Federal Regulations (GPO) | public domain | A |
| `jp_egov_sensor` | e-Gov 法令 API | CC-BY 4.0 | A |
| `eu_eurlex_sensor` | EUR-Lex consolidated treaties + regulations + directives | free reuse with citation | A |
| `uk_legislation_sensor` | legislation.gov.uk | OGL v3.0 | A |

## Passive-only invariant (G8)

Sensors MUST NOT perform live scraping of courts.go.jp / legislation.gov.uk
/ EUR-Lex at organism-tick time. They MUST NOT submit live API queries to
commercial legal-research vendors. Pre-published archive fetches via
`e7m-dataset` at ingest time only.

PROHIBITED upstream sources (Charter Rider §2(e) + §2(c)):

- Westlaw
- LexisNexis
- Bloomberg Law
- Wolters Kluwer

These vendors maintain closed query-tracking infrastructure that could
expose member legal posture to commercial parties; their inclusion is
constitutionally rejected.

## Judicial-party redaction policy

`judicial_party_redactor.py` honors per-jurisdiction publication-redaction
practice:

- US / UK / IN / BR / CA / AU / ICJ / ICC → pass-through (parties named in
  published opinions);
- DE / FR / JP / CN → pass-through (parties pseudonymized upstream);
- ECHR → honor HUDOC anonymization where present;
- JP 家庭裁判所 / 少年裁判所 → reject if anonymization broken upstream.

chigiri does NOT re-identify or de-anonymize. Right-to-be-forgotten DSARs
route through chigiri's `data_privacy` cell (R2+) to upstream publishers;
chigiri does NOT unilaterally remove pinned content.

## R0 status

- `base.py` — Protocol definitions for all 5 sensor families + Observation
  dataclasses;
- `judicial_party_redactor.py` — Per-jurisdiction policy table + redaction
  helpers;
- `us_usc_sensor.py` — W1 first-anchor scaffold (path-resolution +
  deterministic hot_sample); actual NDJSON parsing TODO at W1 ratification.

## Related

- `/90-docs/adr/2605262800-public-data-legal-corpus-ipfs-ingestion.md` — primary ADR
- `/90-docs/adr/2605262400-public-data-organism-ipfs-ingestion.md` — parent (geo / netreg / etc. buckets)
- `/90-docs/adr/2605262700-chigiri-legal-procedure-tier-b-actor-r0.md` — primary consumer actor
- `../base.py` — DatasetSensor Protocol parent
- `../rir_delegated_sensor.py` — sibling pattern reference
- `../pii_filter.py` — general PII filter (runs before Charter Rider scan)
- `/70-tools/baien-moemoekyun-train/recipes/legal/` — training corpus recipes
