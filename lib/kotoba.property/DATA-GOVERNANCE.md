# Data Governance

This repository publishes schemas, source metadata, and code. It does not
publish raw natural-person or UBO records.

## Initial jurisdiction policy

| Jurisdiction | Data | Ingestion status | Distribution status |
| --- | --- | --- | --- |
| GB | Companies House PSC data product | allowlisted | governed database only |
| GB | Natural-person land-title owners | disallowed | not collected |
| EU/EEA | General-public UBO registers | disallowed | not collected |

The UK Companies House PSC product provides a daily JSON snapshot of PSCs.
Companies House makes most PSC information public, but excludes home address
and full date of birth. The registrar also permits protection of PSC details
in qualifying cases. An importer must refresh from the source, delete or
supersede protected records, and avoid every field not required for entity
resolution.

UK land-title owner names are public in a property-specific title register,
but this is not an authority to build a person-indexed, redistributable land
owner dataset. HM Land Registry says private-individual name searches are not
available through its Index of Proprietors' Names. Keep direct natural-person
property ownership out of this collection.

The EU Court of Justice invalidated general public access to beneficial
ownership information under the EU AML rules. Do not treat national register
pages as a reusable general-public UBO feed without a jurisdiction-specific
review.

## What may be committed to `data/`

`var/` is a Git-ignored collector cache. `data/` holds committed projections
that other systems load. An extract may move from `var/` to `data/` only when
all of the following hold, and the ADR that authorised it says so:

- the authority entry in `coverage.edn` is `:allow-login-free`;
- the records contain no natural-person data (a public body or a legal entity
  is not a natural person);
- the upstream licence permits redistribution — CC0 for GLEIF, the NYC Open
  Data Terms of Use for NYC-owned parcels;
- every record keeps its source, observation time, licence and disclosure
  class, and the file's manifest line keeps the publish id and source hash.

Reviewed and permitted as of 2026-08-01: GLEIF LEI records (corporate identity,
CC0) and NYC-owned property claims (public-body holders). Everything else stays
in `var/` or in a governed database. Companies House PSC and HM Land Registry
CCOD/OCOD extracts are **not** permitted in `data/` — they are licensed or
person-adjacent.

## 官報 (NPB, JP) — officers named in a company's own statutory notice

Owner decision 2026-09-08: **names printed in a corporate public notice are
public corporate information and this workspace collects them.** A 決算公告
names its 代表取締役 because the Companies Act requires the notice; a 落札公示
names the 契約責任者 for the same kind of reason. Withholding them from the
projection does not protect anyone — the gazette is the publication — and it
loses the field a reader needs to tell two companies of the same name apart.

Two things this decision does **not** move.

1. It does not reopen the rows in the table above. Companies House PSC, HM Land
   Registry proprietor names and EU/EEA general-public UBO registers are refused
   for licence terms and a CJEU ruling, not because a person is named. A policy
   about gazette officers says nothing about those.
2. A person still goes in a field that is about the person:
   `:company/representative`, `:award/contract-officer`. Never
   `:company/address`, never `:grant/ministry`. That rule is not about privacy —
   it is that a wrong value which reads as a right one is the failure this
   collector is written against, and `"代表取締役 田村 圭二"` sitting in an
   address column is exactly that. Measured 2026-09-08: two such values were in
   the committed projection for two and a half weeks.

The parsers refuse a name they cannot read whole. 官報 is set in two columns and
the PDF text stream splits long lines, so `代表取締役社長 中澤` / `俊` arrives as
two; the field is left empty rather than filled with an amputated surname.

## 法人番号 (NTA, JP) — permitted to collect here, published elsewhere

Reviewed 2026-08-18. The National Tax Agency's 全件データ carries no
natural-person data: a 法人番号 is issued to a legal entity or an
unincorporated association, never to a sole proprietor. Its licence,
公共データ利用規約（第1.0版）, permits redistribution with attribution, and
requires a derived work to say that it is derived — both travel in every
manifest line as `:source/attribution`, not only in a README.

Two rules follow, and they differ from GLEIF's:

- The corpus (~2.6 GB) stays in `~/.cache/houjin-bangou` on the node that cut
  it, like every other corpus in this repository.
- **Projections are not committed to this repository.** They go to the private
  `com-junkawasaki/jp-go-nta-houjin-bangou`. The rows are public government
  data; the *selection* is not — a `joined` tier is chosen by which companies
  this workspace does business with, and publishing that selection from a
  public repo would publish a customer list assembled from public parts.

Added 2026-08-03 (ADR-2608031900): **GLEIF Level 2 relationship records**
(`data/gleif-relationship-*.datoms.edn`). Both ends of every edge are LEIs —
that is, legal entities — so the file contains no natural-person data at all.
Same CC0 publish, same manifest contract (publish id + source hash).

This is deliberately **not** the UBO feed the section above declines to build.
GLEIF Level 2 records accounting-consolidation and fund-management
relationships *between legal entities*, self-published by those entities to
their managing LOU under CC0. It never names a natural person, so the CJEU
ruling on public access to beneficial-ownership registers does not reach it,
and neither does the Companies House PSC restriction. If a future ingest tries
to resolve a chain of Level 2 edges down to the individuals at the top, that is
a different dataset under a different review — it does not inherit this one.

Every relationship record keeps `:corporate-relation/validation`, GLEIF's own
evidence tier for the edge. `ENTITY_SUPPLIED_ONLY` means the company asserted
its own parent and no one corroborated it; on the 20260803 publish that is
139,111 of 483,263 edges. Consumers must not present a self-declared edge as a
verified one — the same asymmetry the jurisdiction catalogs elsewhere in this
workspace enforce, for the same reason.

## Required controls

- Preserve source URL, source record identifier, retrieval time, and licence.
- Store only name, company identifier, control nature, and source dates needed
  to express a UBO relation. Never retain home address, full date of birth,
  identity documents, or verification data.
- Enforce the source allowlist before transaction submission.
- Apply source suppression, correction, and refresh events promptly.
- Make entity-resolution confidence explicit; a matching name alone is not a
  reliable identity link.
- Require a documented legal/privacy review before enabling another
  jurisdiction or publishing any raw extract.

## Primary sources checked 2026-07-10

- https://www.gov.uk/guidance/companies-house-data-products
- https://download.companieshouse.gov.uk/en_pscdata.html
- https://www.gov.uk/guidance/your-personal-information-on-the-companies-house-register
- https://www.gov.uk/guidance/finding-information-held-by-hm-land-registry
- https://use-land-property-data.service.gov.uk/datasets/ocod
- https://curia.europa.eu/site/upload/docs/application/pdf/2022-11/cp220188en.pdf
