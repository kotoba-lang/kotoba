# kotoba-iso3166

ISO 3166-1 alpha-3 country registry for kotoba-lang and itonami open
businesses -- the jurisdiction/market-entry counterpart to `kotoba-industry`
(ISIC-coded businesses), `kotoba-occupation` (ISCO-08-coded occupations),
and `kotoba-cofog` (COFOG-coded government functions).

This repository maps each country to the technology capabilities needed to
run an independent public-sector market-entry & procurement-compliance
navigator business for that jurisdiction.

## Contract

```clojure
(require '[kotoba.iso3166 :as iso3166])

(iso3166/get-country "JPN")
(iso3166/required-technologies "DEU")
(iso3166/readiness "USA" #{:identity :forms :dmn :bpmn :audit-ledger})
```

## Layers

- business: customer-facing open ISO 3166 market-entry blueprint
- iso3166: country-coded operating domain (which jurisdiction's rules apply)
- technology: reusable kotoba-lang capability stack
- implementation: concrete repos, services and operators

ISIC classifies what a *business* produces; ISCO classifies what a *worker*
does; COFOG classifies what *government function* a service serves; ISO 3166
classifies **which jurisdiction's market-entry and public-procurement rules
apply**. `cloud-itonami-iso3166-{code}` publishes forkable OSS operator
businesses that help an ALREADY-INCORPORATED operator win and service a
public-sector contract in that specific country -- distinct from
`cloud-itonami-M6910` (company *incorporation* itself) and from
`cloud-itonami-cofog-{code}` (a jurisdiction-agnostic operator template for
ONE public function). See `docs/cloud-itonami.md` for the full boundary with
adjacent etzhayyim/cloud-itonami actors.

At the COUNTRY level, a country is not itself a business-function taxonomy,
so entries are FLAT -- every one of the 193 current UN-member states is
independently blueprint-eligible. ADR-2607040100 adds a SECOND, AGENCY level
for Japan only (`:level :ministry` / `:agency` / `:independent-commission`,
`:parent "JPN"`), mirroring COFOG's division/group coordinator+leaf pattern
(ADR-2606301900): `cloud-itonami-iso3166-jpn` is the country-level
coordinator, and per-agency blueprints (`cloud-itonami-iso3166-jpn-meti`,
etc.) are leaves under it. Use `(iso3166/children "JPN")` to list them. Other
countries stay flat until this pattern is validated.

## Current ISO 3166 Blueprints (country level)

| Code | Country | Blueprint |
|---|---|---|
| JPN | Japan | **`:implemented`** Independent Public-Sector Market-Entry & Procurement Compliance Service -- Japan |
| USA | United States of America | **`:implemented`** Independent Public-Sector Market-Entry & Procurement Compliance Service -- United States |
| DEU | Federal Republic of Germany | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Germany |
| KEN | Kenya | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Kenya |
| IND | Republic of India | Independent Public-Sector Market-Entry & Procurement Compliance Service -- India |
| BRA | Federative Republic of Brazil | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Brazil |
| GBR | United Kingdom | Independent Public-Sector Market-Entry & Procurement Compliance Service -- United Kingdom |
| SGP | Singapore | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Singapore |
| ARE | United Arab Emirates | Independent Public-Sector Market-Entry & Procurement Compliance Service -- United Arab Emirates |
| AUS | Commonwealth of Australia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Australia |
| KOR | Republic of Korea | Independent Public-Sector Market-Entry & Procurement Compliance Service -- South Korea |
| POL | Poland | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Poland |
| MEX | United Mexican States | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Mexico |
| SAU | Kingdom of Saudi Arabia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Saudi Arabia |
| CAN | Canada | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Canada |
| NZL | New Zealand | Independent Public-Sector Market-Entry & Procurement Compliance Service -- New Zealand |
| ZAF | Republic of South Africa | Independent Public-Sector Market-Entry & Procurement Compliance Service -- South Africa |
| CHL | Chile | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Chile |
| NGA | Nigeria | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Nigeria |
| IDN | Republic of Indonesia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Indonesia |
| IRL | Ireland | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Ireland |
| NLD | Kingdom of the Netherlands | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Netherlands |
| VNM | Vietnam | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Vietnam |
| THA | Thailand | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Thailand |
| COL | Colombia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Colombia |
| ESP | Spain | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Spain |
| PHL | Philippines | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Philippines |
| PER | Peru | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Peru |
| ITA | Italian Republic | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Italy |
| BGD | Bangladesh | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Bangladesh |
| ARG | Argentine Republic | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Argentina |
| GHA | Ghana | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Ghana |
| FRA | French Republic | Independent Public-Sector Market-Entry & Procurement Compliance Service -- France |
| EGY | Egypt | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Egypt |
| PAK | Pakistan | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Pakistan |
| TUR | Republic of Türkiye | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Turkey |
| MAR | Morocco | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Morocco |
| ETH | Ethiopia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Ethiopia |
| SWE | Sweden | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Sweden |
| KAZ | Kazakhstan | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Kazakhstan |
| QAT | Qatar | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Qatar |
| CHN | People's Republic of China | **`:implemented`** Independent Public-Sector Market-Entry & Procurement Compliance Service -- China |
| CRI | Costa Rica | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Costa Rica |
| CZE | Czech Republic | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Czech Republic |
| UKR | Ukraine | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Ukraine |
| ISR | Israel | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Israel |
| URY | Uruguay | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Uruguay |
| EST | Estonia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Estonia |
| RWA | Rwanda | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Rwanda |
| PAN | Panama | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Panama |
| GEO | Georgia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Georgia |
| JOR | Jordan | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Jordan |
| SEN | Senegal | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Senegal |
| NPL | Nepal | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Nepal |
| FIN | Finland | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Finland |
| TUN | Tunisia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Tunisia |
| NOR | Norway | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Norway |
| LKA | Sri Lanka | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Sri Lanka |
| BWA | Botswana | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Botswana |
| DNK | Denmark | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Denmark |
| LVA | Latvia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Latvia |
| ECU | Ecuador | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Ecuador |
| ISL | Iceland | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Iceland |
| LTU | Lithuania | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Lithuania |
| ZMB | Zambia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Zambia |
| HUN | Hungary | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Hungary |
| HRV | Croatia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Croatia |
| NAM | Namibia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Namibia |
| SVK | Slovakia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Slovakia |
| BOL | Bolivia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Bolivia |
| KHM | Cambodia | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Cambodia |
| RUS | Russian Federation | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Russia |
| BEL | Belgium | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Belgium |
| AUT | Austria | Independent Public-Sector Market-Entry & Procurement Compliance Service -- Austria |

**`:implemented` (running actors)**: `JPN`, `USA`, `CHN` — see the corresponding `cloud-itonami-iso3166-{jpn,usa,chn}` repos (`marketentry` actors).

80/193 countries are at or above `:blueprint` (77 `:blueprint` + 3 `:implemented`). USA now has a deliberate 15-body agency-level extension (parent `USA`), mirroring the Japan coordinator+leaf pattern. Remaining country entries stay `:spec` for future promotion along the same maturity ladder.

Alpha-3 code + English/local name are reused verbatim from
`com-etzhayyim-ooyake`'s Wikidata-verified `gov-units.*.edn` registries (a
one-time maintainer pull of CURRENT UN members, 2026-06-03), not re-derived
-- same reuse discipline `kotoba-cofog` applied to `matsurigoto`'s COFOG
backbone.

## Current ISO 3166 Blueprints (Japan agency level)

| Code | Agency | Ooyake ID | Blueprint |
|---|---|---|---|
| JPN-METI | Ministry of Economy, Trade and Industry (経済産業省) | `gov.jpn.meti` | Independent METI-Regulated Trade & Industrial-Policy Compliance Service -- Japan |
| JPN-MOF | Ministry of Finance (財務省) | `gov.jpn.mof` | Independent MOF-Regulated Customs & Tax Compliance Service -- Japan |
| JPN-DIGITAL | Digital Agency (デジタル庁) | `gov.jpn.digital` | Independent Digital-Agency-Regulated GovTech Procurement Compliance Service -- Japan |
| JPN-JFTC | Fair Trade Commission / 公正取引委員会 | `gov.jpn.competition` | Independent JFTC Antitrust & Bid-Rigging Compliance Service -- Japan |
| JPN-PPC | Personal Information Protection Commission / 個人情報保護委員会 | `gov.jpn.dataprotection` | Independent PPC Personal-Data Compliance Service -- Japan |
| JPN-MOJ | Ministry of Justice (法務省) | `gov.jpn.moj` | Independent MOJ-Regulated Corporate Registry & Status-of-Residence Compliance Service -- Japan |
| JPN-MHLW | Ministry of Health, Labour and Welfare (厚生労働省) | `gov.jpn.mhlw` | Independent MHLW-Regulated Labor-Standards Compliance Service -- Japan |
| JPN-FSA | Financial Services Agency (金融庁) | `gov.jpn.finreg` | Independent FSA Payment-Services & Financial-Regulatory Compliance Service -- Japan |
| JPN-MAFF | Ministry of Agriculture, Forestry and Fisheries (農林水産省) | `gov.jpn.maff` | Independent MAFF Food-Safety & JAS-Certification Compliance Service -- Japan |
| JPN-MLIT | Ministry of Land, Infrastructure, Transport and Tourism (国土交通省) | `gov.jpn.mlit` | Independent MLIT Construction-Business Licensing Compliance Service -- Japan |
| JPN-MOE | Ministry of the Environment (環境省) | `gov.jpn.moe` | Independent MOE Environmental-Assessment & Waste-Permit Compliance Service -- Japan |
| JPN-MOFA | Ministry of Foreign Affairs (外務省) | `gov.jpn.mofa` | Independent MOFA ODA/JICA Tender-Eligibility Compliance Service -- Japan |
| JPN-MOD | Ministry of Defense (防衛省) | `gov.jpn.mod` | Independent MOD Defense-Equipment Transfer & Security-Clearance Compliance Service -- Japan |
| JPN-AUDIT | Board of Audit (会計検査院) | `gov.jpn.audit` | Independent Board-of-Audit Readiness Compliance Service -- Japan |
| JPN-CAO | Cabinet Office (内閣府) | `gov.jpn.cao` | Independent Cabinet-Office Cross-Ministerial Program Compliance Service -- Japan |
| JPN-MIC | Ministry of Internal Affairs and Communications (総務省) | `gov.jpn.mic` | Independent MIC Telecom & Broadcasting Licensing Compliance Service -- Japan |
| JPN-MEXT | Ministry of Education, Culture, Sports, Science and Technology (文部科学省) | `gov.jpn.mext` | Independent MEXT Research-Grant & School-Accreditation Compliance Service -- Japan |
| JPN-RECONSTRUCTION | Reconstruction Agency (復興庁) | `gov.jpn.reconstruction` | Independent Reconstruction-Agency Special-Zone Procurement Compliance Service -- Japan |
| JPN-STATISTICS | Statistics Japan (総務省統計局) | `gov.jpn.statistics` | Independent Statistics-Japan Reporting-Obligation Compliance Service -- Japan |

**19/19 Japan agencies are now `:maturity :blueprint` — full coverage
complete** (ADR-2607040100 + ADR-2607040200 + ADR-2607040300 +
ADR-2607040400 + ADR-2607040500), spanning all three agency types
(ministry / agency / independent commission). Every agency entry's
`:ooyake-id` cross-references the source record in `com-etzhayyim-ooyake`'s
`gov-units.jp-central.seed.edn` / `gov-units.seed.edn` /
`gov-units.oversight-*.edn` (IDs, names, and official URLs reused verbatim,
not re-derived).


## Current ISO 3166 Blueprints (United States agency level)

Deliberate 15-body subset (not the full federal org chart) spanning cabinet
departments, agencies, and independent commissions most relevant to public-
sector market entry (ADR-2607105600).

| Code | Body | Ooyake ID | Focus |
|---|---|---|---|
| USA-GSA | General Services Administration | `gov.usa.gsa` | SAM.gov / Schedules |
| USA-SBA | Small Business Administration | `gov.usa.sba` | set-asides |
| USA-TREASURY | Department of the Treasury | `gov.usa.treasury` | EIN / tax |
| USA-DOC | Department of Commerce | `gov.usa.doc` | BIS export control |
| USA-DOD | Department of Defense | `gov.usa.dod` | DFARS |
| USA-DHS | Department of Homeland Security | `gov.usa.dhs` | cyber / SCRM |
| USA-DOL | Department of Labor | `gov.usa.dol` | labor standards |
| USA-HHS | Department of Health and Human Services | `gov.usa.hhs` | health awards |
| USA-DOT | Department of Transportation | `gov.usa.dot` | transportation Buy America |
| USA-DOE | Department of Energy | `gov.usa.doe` | energy procurement |
| USA-VA | Department of Veterans Affairs | `gov.usa.va` | VA vendor |
| USA-EPA | Environmental Protection Agency | `gov.usa.epa` | environmental |
| USA-FTC | Federal Trade Commission | `gov.usa.ftc` | competition |
| USA-SEC | Securities and Exchange Commission | `gov.usa.sec` | disclosure posture |
| USA-FCC | Federal Communications Commission | `gov.usa.fcc` | telecom procurement |

## Test

```bash
kbb -M:test
```
