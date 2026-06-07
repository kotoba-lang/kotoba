---
id: uhl-right-neural-institution-seed-readme
title: UHL-R Institution Registry — Seed data update procedure
status: active
doc_type: how-to
topic: uhl-right-neural-institution-seed
authoritative: true
last_verified: 2026-05-18
authoritative_for:
  - institution seed update procedure
  - source citation policy
related:
  - ../../../../../../../../90-docs/adr/2605181000-uhl-right-neural-project.md
  - ../../../../../../../../90-docs/adr/2605181040-uhl-medical-institution-registry.md
  - ../../../../../../../../90-docs/adr/2605181050-uhl-overseas-referral-paths.md
  - ../../../../../../../../90-docs/adr/2605181060-otarmeni-access-path.md
---

# UHL-R Institution Registry — Seed Data

This directory contains the **initial seed** of the medical institution registry
for the `uhl-right-neural` project (先天性右側感音難聴 / neural軸 治療研究 Pregel).

Schema and public policy are authoritatively defined in:

- **ADR-2605181040** — registry schema + 公開ポリシー
- **ADR-2605181050** — 海外 referral path (referenced via `referral_paths[].path_id`)
- **ADR-2605181060** — Otarmeni access path

## Files

| File | Contents | Count |
|---|---|---|
| `institutions_jp.yaml` | Domestic Japan institutions | 8 |
| `institutions_intl.yaml` | International reference institutions | 7 |

## Hard rules (per ADR-2605181040)

1. **PII zero** — no individual patients, no individual clinicians (PI affiliation only).
2. **Public sources only** — `evidence_url` must be a public source (academic journal,
   official institutional site, peer-reviewed paper, regulatory body — FDA / PMDA / EMA).
   No SNS, no personal blogs.
3. **`last_verified_at` required** — every record must have it. **Staleness window = 180 days.**
   Records older than 180 days are flagged "stale" by `InstitutionMatcherActor` (V16) but
   not excluded.
4. **License** — CC-BY-4.0 for this dataset (distinct from the repo's Apache 2.0 code license).
5. **Legal disclaimer** — this registry is not medical advice. The matcher actor enforces
   `requires_human_review: true` on all outputs.

## Update procedure

1. Open a GitHub issue describing the change (new institution, capability update, count
   refresh).
2. Verifier (currently `jun@etzhayyim.com`) reviews against the source policy above.
3. Update the YAML file. Bump `last_verified_at`. If only verifying without content
   change, still bump the date.
4. PR with a single-line title `[uhl-seed] <institution-id>: <change>`.
5. Merge after review.

## Staleness check (future tooling)

A `lefthook` pre-commit hook will (planned):

- Sample-verify `evidence_url` returns HTTP 200.
- Reject records with `last_verified_at` older than 180 days unless the PR is explicitly
  a staleness refresh (commit message contains `[staleness-refresh]`).

Until tooling exists, run manually before merge.

## Coverage notes (2026-05-18)

**Domestic (JP) coverage**: 8 institutions covering genetic testing (3), pediatric CI (6),
CND-capable CI (4), ABI (1 collaborative), consultation hub (2), and neural regeneration
research (1).

**International coverage**: 7 institutions covering ABI (2 NHS UK sites), gene therapy
sponsorship (1), optogenetic CI research (2), and SGN regeneration research (1).

**Known gaps** (intentional, not registry-blocking):

- No CHORD trial JP site name yet (Regeneron has not publicly disclosed it as of
  2026-05-18). Add when published.
- ABI in Japan: cumulative count is from 2011 (`jp-fukushima-nms-abi`). Refresh needed.
- US treating institutions (not just research) for OTOF gene therapy not yet enumerated.
  Add post-Otarmeni broader rollout.

## Adding a new institution

```yaml
- id: <country-code>-<short-slug>      # e.g., jp-osaka-u-orl
  name_ja: <Japanese display>
  name_en: <English display>
  country: <ISO 3166-1 alpha-2>
  locale: <city, prefecture/state>
  website: <https URL>
  capabilities:
    - kind: <one of: GENETIC_TEST | PED_CI | CND_CI | ABI | GENE_TX_OTOF | OPTO_CI_TRIAL | NEURAL_REGEN_RESEARCH | CONSULT_HUB>
      procedure_record:
        cumulative_count: <int|null>
        count_as_of: <ISO-8601 date|null>
        evidence_url: <https URL — public source per rule 2>
        reimbursement: <hoken | self_pay | trial | unknown>
      notes_ja: <optional plain text>
  referral_paths:
    - path_id: <path slug defined in ADR-2605181050>
  last_verified_at: <today, ISO-8601>
  verified_by: <verifier email>
```
