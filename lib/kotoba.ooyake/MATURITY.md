# ooyake 公 — Maturity Scorecard

Honest status per the gov-coverage maturity model (ADR-2605250680). Coverage gated
by `:sourcing` (G5): only `:authoritative` rows count.

## 2026-07-25 — 公人 (public office holders) admitted; G6 amended

The atlas answered *which body* and *where* but never *who* — despite its own manifest
calling it the read-side SSoT for the "who / where / how" of public administration. G6
read "no personal data" and N7 "NOT a store of officials' personal data", which was
broader than the invariant it was protecting: the thing that actually mattered was
**private** data, not the public fact that a named person holds a named office.

Owner instruction 2026-07-25 (「公人は記録して ok」/「charter からその personal と言う
のが強すぎるので、charter も更新して ok」) → **G6 amended, N7 narrowed** (ADR-2607253000):

- **New**: `registry/gov-officeholders.*.edn` — **718 current office holders across 461
  units and 197 jurisdictions**, pulled from Wikidata on 2026-07-25 and keyed by the
  atlas's own `:gov.unit/wikidata`, so `:gov.person/unit` always resolves to a real
  `:gov.unit/id` (no name-matching step, no orphan rows). Heads of state / heads of
  government / legislature chairs / constitutional-court presidents / central-bank
  governors / foreign-finance-defence ministers / oversight-body heads.
- **Still unrepresentable**: private/home contact, address, birth data, family,
  finances, health, movements, schedule, religion, party. Those attributes are not
  declared in `gov-officeholders.schema.edn` and not requested from any upstream query —
  they cannot be present-but-empty. `scripts/verify_officeholders.cljk` fails the build
  if an attribute matching any of them ever appears.
- **G10 unchanged** (civic wayfinding, never a target-list) and binds every row: this
  answers "who holds this office", never "where is this person". **G11 unchanged**: no
  evaluation, ranking or score of a person — holding an office is a fact, not a verdict.
- **Current-only, and dated**: statements carrying an end date (P582) and deprecated
  ranks are excluded, and every row carries `:gov.person/last-verified`. Office holders
  change; a row without that date would assert more than it knows. Live evidence that
  this matters: the UK head-of-government row read `since 2026-07-20` — five days before
  the pull, and after this agent's own training cutoff. The dated row was right and the
  prior belief was stale, which is exactly the failure mode `last-verified` exists for.
- Coverage is **honest, not complete**: 718 holders against 7,089 atlas units. Wikidata
  carries current holders for heads of state/government densely and for court presidents
  and ministry heads thinly. That is a coverage gap to fill, never a claim that those
  offices are vacant.

## 2026-07-25 (2) — office-holder coverage +46%, and a weekly refresh

The first 公人 pull only asked "does this body point directly at a person?"
(P35/P6/P488/P1037/P169/P1308). That is how Wikidata records heads of state, and
almost nothing else — foreign/finance/defence ministries came back 61/389 covered
and legislatures 31/186.

**Pass B** now also asks the question the other way round: `position -P2389-> unit`,
then `person -P39-> position`. That is the shape most ministers and speakers are
actually stored in, and it carries the **real office title** ("Minister of Foreign
Affairs") instead of the structural property name Pass A can offer ("Director / Head").

- **718 → 1,050 holders across 461 → 761 units**, 197 jurisdictions. Core ministries
  61 → 245 units covered (16% → 63%), central banks 70 → 105 (58% → 76%), legislatures
  31 → 66 (19% → 35%). 445 rows now carry a real office title.
- **Currency is decided differently in Pass B, on purpose.** P39 statements pile up
  historical holders with no end date — Albania's foreign ministry had 20+ undated
  predecessors — so "no end date = current" does not work there. Pass B requires a start
  date and takes the latest per (unit, office); undated rows are not promoted to current
  on a guess.
- **Undated Pass A rows now lose to dated Pass B rows for the same unit.** Wikidata
  leaves statements open when someone leaves office: France's economy ministry listed
  Antoine Armand (out since Dec 2024) beside his correct successor Éric Lombard. The
  stale row is dropped; the dated one stands.
- `.github/workflows/refresh-officeholders.yml` re-reads every holder weekly and commits.
  Who holds an office is a fact that changes on a scale of days — the UK
  head-of-government row was five days old at first pull — so `:gov.person/last-verified`
  is only meaningful if something re-takes the reading. The job fails rather than commits
  when a group's count collapses (upstream outage must not land as "these offices are
  vacant") or when the G6 / linkage / provenance gate fails, so the charter boundary is
  enforced on every automated write and not only when a human looks.
- Still honest about the remainder: 1,050 holders against 7,089 atlas units. Courts
  (19/62) and oversight bodies (78/327) stay thin because Wikidata is thin there.

## 2026-06-05 — cross-actor world-model reconcile (ooyake↔tsumugi)

The atlas was a structural SSoT that *other* actors consumed, but nothing actually
JOINED it to tsumugi's 縁/取 karma graph — `:gov.unit/organism` was defined in the
ontology, populated by no unit, and reconciled by no code. Closed that gap:

- New cell `cells/world_model/` (`WorldModelCell` + pure `reconcile_world_model`):
  joins `:gov.unit/*` (structure) ↔ tsumugi `:organism/*` (karma) over the shared
  `:gov.unit/organism` id-space. Classifies every **power-bearing** unit (country /
  supranational / cabinet / ministry / agency / bureau / legislature / court) as
  **confirmed / derived / dangling / proposed**; local service surface
  (窓口 / ward / division / prefecture) is **excluded by construction** (G1 power-only,
  never a target-list / G10). Read-side (G9) — emits `out/world-model.kotoba.edn`
  (proposed `:latent` / `:representative` organisms + links), never mutates a seed;
  `mode="live"` write-back is Council+operator gated.
- Wired the first real link: `gov.jpn.meti` → `org.state.jp.meti` (the one gov body
  tsumugi's seed carries). Honest result: **1 confirmed / 3,503 proposed of 3,504
  power-bearing units (0.03% reconciled)** — the world model is mostly unreconciled,
  which is the honest R1 state; growth needs more verified gov organisms, not number
  inflation.
- **Coverage step (same day): 1 → 4 confirmed links** by curating real, publicly-
  documented regulator→regulated ties into tsumugi's karma seed (FSA→MUFG, BOJ→MUFG,
  SEC→Apple/Microsoft/NVIDIA/Alphabet, all `:tends`, low grasping-load, `:representative`)
  and wiring the `:gov.unit/organism` links: `gov.jpn.finreg`→`org.state.jp.fsa`,
  `gov.jpn.boj`→`org.state.jp.boj`, **new `gov.usa.sec`**→`org.state.us.sec`. The US
  SEC was a genuine atlas gap (`gov.usa.finreg` is the CFTC) — adding it lifts ooyake
  coverage too. Reconciled 0.03%→**0.11% (4/3,505)**; gate floor raised to 4 with an
  explicit expected-set check; tsumugi graph 19→22 organisms / 28→34 縁, still 1
  connected component (TSMC still top 取). No fabrication — every tie is documented.
- **Coverage step 2: 4 → 6 confirmed.** US Fed → MUFG (foreign-banking-organization
  supervision) + EU → Apple/Google/Microsoft (antitrust + DMA gatekeeper, heavily
  documented) wired via `gov.usa.fed`→`org.state.us.fed` and `gov.eu`→`org.state.eu`.
  Reconciled →**0.17% (6/3,506)**; gate floor → 6; tsumugi 22→24 organisms / 34→38 縁,
  1 component. Taiwan (NDF→TSMC) deferred to its own fire (atlas has no Taiwan units
  yet; a geopolitically-sensitive country addition handled deliberately, G11).
- **Coverage step 3: 6 → 9 confirmed.** Competition/antitrust authorities wired to
  landmark documented matters: UK CMA → NVIDIA + Arm (blocked NVIDIA–Arm acquisition),
  US DOJ Antitrust → Google (US v. Google search-monopoly), JFTC → Toyota (subcontracting
  oversight) — via `gov.gbr.competition`→`org.state.uk.cma`,
  `gov.usa.competition`→`org.state.us.doj-antitrust`, `gov.jpn.competition`→`org.state.jp.jftc`.
  Reconciled →**0.26% (9/3,506)**; gate floor → 9; tsumugi 24→27 organisms / 38→42 縁,
  1 component. Taiwan (NDF→TSMC) STILL deferred — adding a contested-status country in
  an autonomous loop fire needs an explicit human decision (G11), flagged for the operator.
- **Maturity step 4 — the cross-graph JOIN (not just node count).** The world model
  now resolves **government→entity stewardship paths**: reconciled gov-unit → its
  organism → `:tends`/`:custodies` 縁 → entity. `reconcile_world_model` gained an
  `edges` arg (`load_edges` from the tsumugi seed) + a `government_stewardship` view;
  CLI prints it, EDN artifact carries a `:government-stewardship` block, gate asserts
  ≥10 paths all originating at reconciled units. **20 concrete paths** today (e.g.
  `gov.eu --:tends--> Apple`, `gov.usa.sec --:tends--> NVIDIA`, `gov.jpn.meti --:tends-->
  Toyota`). This turns the reconcile from *matched nodes* into the queryable structure↔
  karma join the world model exists to produce. +4 sector-breadth enrichment 縁
  (METI→Honda/DENSO, EU→NVIDIA, JFTC→Sony; no new gov organisms). tsumugi 27 organisms
  / 42→46 縁, 1 component; cell tests 10→13. All suites green.
- **Maturity step 5 — kotoba PERSISTENCE path.** The world model was a file; now it
  has a canonical-substrate ingest. `deploy/ingest_world_model.py` (sibling of
  `ingest_records.py`, reuses its `post_batch` write path) projects the **reconciled,
  factual** world model into the named graph **`world-model-v1`**: one `world.gov`
  entity per reconciled gov-unit carrying `world/organism` (→ its tsumugi organism)
  and `world/stewards` (→ each entity it :tends/:custodies). Today **9 reconciled gov
  nodes (~56 datoms) + 20 stewardship relations**. PROPOSED/latent links are NOT
  persisted as facts (file-only candidates until an operator applies them — G5/G9).
  Dry-run by default (no `KOTOBA_TOKEN`); live ingest operator-gated; never auto-seals
  (WAL-durable, `kotoba commit` is the operator's cadence). Wired into `run_tests.sh`
  as a dry-run gate. Closes the original "kotobaでの永続化 + world model" loop: the
  join is now a persistable Datom graph, not just an artifact.
- **Maturity step 6 — bidirectional query + actor consumption.** The world model is
  now CONSUMABLE, not just computed. Cell gains pure helpers `stewarded_entities_of`
  (gov-unit → entities) and `regulators_of` (entity → governing bodies, the reverse
  cross-actor question). Wired into `deploy/consumers_example.py` as a 6th consumer
  (`world_model_regulators`) so tsumugi/danjo/kanae read the join instead of re-deriving
  it — e.g. `regulators_of(Apple)` → {gov.eu, gov.usa.sec}, `regulators_of(MUFG)` →
  {gov.jpn.finreg, gov.jpn.boj, gov.usa.fed}. `scripts/world_model.py --entity <org>`
  exposes it on the CLI. cell tests 13→15; consumers self-test extended; all green.
- **Maturity step 7 — SSoT drift-lock + doc refresh (seed-independent hardening).**
  `cells/world_model/test_consistency.py` (the ake/fuchi/noroshi pattern) binds six
  facts to one source of truth so the feature can't silently rot: every committed
  `:gov.unit/organism` link resolves to a real tsumugi organism (structural zero-
  dangling); links are 1:1 (no two units claim one organism); the gate's
  `EXPECTED_CONFIRMED` ⊆ wired links AND `CONFIRMED_FLOOR == len(EXPECTED_CONFIRMED)`
  (no stale floor); the manifest declares the cell; the ingest graph name == the
  artifact graph header (`world-model-v1`); the runner wires all three world_model
  gates. 6 checks, wired into `run_tests.sh`. README "World model" section refreshed
  to the full capability (stewardship/query/persistence/drift-lock). All green.
- Hardened into a gate: `scripts/world_model_coverage.py` (confirmed-floor, zero
  dangling, civic-surface-excluded, zero-orphan, well-formed-EDN) + `cells/world_model/
  test_world_model_cell.py` (10 tests). All wired into `deploy/run_tests.sh`.
- Registered as ooyake's 7th cell (manifest), documented (AGENTS.md / README).

## 2026-06-03 — statistics + prosecution + revenue (239)

Third oversight wave (national statistical offices finally landed via a light
instances-only SPARQL + REST entity-resolution approach that dodges the WDQS 504):
- `gov-units.oversight-statistics.edn` **172** — national statistical offices (`Q480242`).
- `gov-units.oversight-prosecutor.edn` **32** — public-prosecution / prosecutor-general
  offices (`Q1092499`∪`Q11775750`), `:branch :judicial`.
- `gov-units.oversight-revenue.edn` **35** — tax / revenue authorities (`Q573607`);
  NTA/IRS/HMRC already in the finance layers were deduped out.
239 bodies. Atlas now **6535 units / 47 files, 6533 QIDs all unique, 6531
:authoritative**.

## 2026-06-03 — independent regulators (130)

Second oversight wave — independent regulatory authorities, `:level :agency`
`:branch :independent`, subagent Wikidata pulls:
- `gov-units.oversight-anticorruption.edn` **41** — anti-corruption agencies (`Q4774348`).
- `gov-units.oversight-dataprotection.edn` **41** — data-protection authorities (`Q3242920`).
- `gov-units.oversight-competition.edn` **16** — competition/antitrust authorities (`Q1465684`).
- `gov-units.oversight-financial-regulator.edn` **32** — financial regulators ex-central-bank (`Q105062392`).
130 bodies. National statistical offices (`Q480242`) still deferred (persistent WDQS
504 on that join). HONEST: a few rows are sub-national/association mis-typings from
the one-per-country dedup. Atlas now **6296 units / 44 files, 6294 QIDs all unique,
6292 :authoritative**.

## 2026-06-03 — independent oversight / accountability bodies (135)

On-mission layer (consumed by danjo/toritate/himotoki): independent accountability
institutions, `:level :agency` `:branch :independent`, subagent Wikidata pulls:
- `gov-units.oversight-audit.edn` **19** — supreme audit institutions (courts of audit
  / national audit offices; `Q10983451`∪`Q43306178`).
- `gov-units.oversight-ombudsman.edn` **24** — ombudsman / public-defender offices (`Q169180`).
- `gov-units.oversight-electoral.edn` **65** — electoral management bodies (`Q935741`).
- `gov-units.oversight-nhri.edn` **27** — national human-rights institutions
  (`Q4806410`∪`Q3511443`).
135 bodies; national statistical offices (`Q480242`) deferred (WDQS timeouts).
HONEST: Wikidata sometimes types sub-national bodies under these classes, so the
one-per-country dedup may pick a non-national body for a few states. Atlas now
**6166 units / 40 files, 6164 QIDs all unique, 6162 :authoritative**.

## 2026-06-05 — subdivision name-local: Latin-diacritic (Azerbaijan 69 + Romania 42) (2070 → 2181)

Continued the Latin-diacritic front. 2 web-research subagents. **111 endonyms added with ASCII
romanization, 0 nulls.** all name-local 2070 → **2181**; subdivision 1056 → **1167**.

- Azerbaijan 69 — Azeri Latin (ə/ç/ş/ğ/ı), HIGH yield: the stored English names are fully anglicized
  and genuinely diverge — Aghstafa→Ağstafa, Jabrayil→Cəbrayıl, Khachmaz→Xaçmaz, Gazakh→Qazax,
  Ganja→Gəncə, Baku→Bakı, Shaki→Şəki, Sumgait→Sumqayıt, Kalbajar→Kəlbəcər. romanized = ASCII fold.
- Romania 42 counties — Romanian (ă/â/î/ș/ț); English already carried diacritics so the gain is the
  verified native field (București) + ASCII search keys.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Next Latin-diacritic candidates: Indonesia 37,
Croatia 21 (č/ć/ž/š/đ), Lithuania 59 (county-level, ė/š/ž/ū), Latvia 41, plus the larger plain-Latin
sets (Slovenia 212, Uganda 135) where name-local ≈ name-en (lowest yield).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Latin-diacritic (Turkey 81 + Vietnam 34) (1955 → 2070)

Opened the Latin-script-but-distinctive-orthography front. 2 web-research subagents.
**115 endonyms added with ASCII romanization, 0 nulls.** all name-local 1955 → **2070**;
subdivision 941 → **1056** (crossed 1000).

- Turkey 81 provinces — proper Turkish orthography incl. dotted-İ (İstanbul corrected from "Istanbul",
  İzmir, Şanlıurfa, Çanakkale, Diyarbakır, Muğla, Gümüşhane, Iğdır); romanized = ASCII fold.
- Vietnam 34 — full Vietnamese diacritics; **corrected the 4 ASCII-only city names**: Hanoi → Hà Nội,
  Da Nang → Đà Nẵng, Haiphong → Hải Phòng, Ho Chi Minh City → Thành phố Hồ Chí Minh.

Note: for these two the English name already carried most diacritics, so the chief gains are (a) the
verified native endonym field, (b) the dotted-İ / full-tone corrections, (c) ASCII romanized search keys.
This is the lower-yield Latin-script axis (vs the now-complete distinct-script sets) but Turkey/Vietnam
sit at the high end of it because their orthography genuinely diverges from plain ASCII.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Next Latin-diacritic candidates: Azerbaijan 69
(ə/ç/ş/ğ), Indonesia 37, Romania 42 (ă/â/î/ş/ţ), Croatia 21 (č/ć/ž/š/đ), Iceland, etc.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — official-url: high-tier institution gap audit (G5 honest-null) (5983 → 5984)

Pivoted axis: the non-Latin subdivision name-local front is effectively complete, so this iteration
audited the **66 high-tier institutions** (supranational/legislature/court/ministry/agency) that still
lacked an official-url — the highest-value url gaps (a ministry/court URL is genuinely verifiable, vs a
subdivision's generic provincial portal). 3 web-research subagents (Wikidata P856 + direct fetch).

**Outcome = the honest finding (G5): only 1 of 66 has a verifiable official site.**
- **ADDED**: Equatorial Guinea Senate → https://senado-gq.org/ (Wikidata P856 Q14759322; the Chamber of
  Deputies has no separate site, so this represents the parliament). official-url 5983 → **5984**.
- **65 verified honest-null** — recorded here so future iterations do NOT re-research them. Reasons:
  - Fragile/conflict/closed states with no institutional web presence (Afghanistan, Syria, Sudan, CAR,
    DRC, Eritrea, North Korea, South Sudan, Guinea-Bissau, Chad, Niger, Mauritania, Togo, Turkmenistan …).
  - Dissolved / not-yet-constituted bodies (Syria Supreme Constitutional Court dissolved; Tunisia
    Constitutional Court not yet constituted; Sudan National Legislature dissolved 2019).
  - No permanent secretariat by design (BRICS, G7 — rotating-chair/presidency sites only, null per policy).
  - Institutions that don't exist as labelled (Bank of Kiribati → became ANZ Kiribati 2001, no central
    bank; India Data Protection Board constituted Nov 2025, no .gov.in site yet; Indonesia PDP authority
    not yet operational).
  - **Data-quality flags (NOT in our registry, so nothing to clean — but noted)**: widely-cited URLs that
    are now HIJACKED/parked and should never be ingested — Comoros Assembly `assemblee-comores.com`
    (Polish business directory; stale on Wikidata P856), St Lucia `stluciaarchives.org` (construction
    template), Haiti/Syria national-library domains (dead/renamed post-2024).

Residual: 2 wikidata gaps remain (gov.jpn.mof.nta.tokyo 東京国税局 + .kojimachi 麹町税務署, JP tax-office
sub-units) — left honest-null pending primary-source QID verification (no guessing).

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Published-index authoritative-scope gate
(check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: non-Latin sweep (Afghanistan+NKorea+Israel+Lebanon+Belarus+Tajik+Kyrgyz+SriLanka+Bangladesh+Nepal) (1859 → 1955)

Swept the remaining genuinely non-Latin subdivision sets across 10 countries / 8 scripts in one pass.
4 web-research subagents (Wikidata P1705 + lang labels). **96 endonyms added with romanization, 0 nulls.**

- all-units name-local: 1859 → **1955**; subdivision name-local: 845 → **941**.
- Afghanistan 34 (Perso-Arabic Dari/Pashto — کابل/Kabul, هرات/Herat, کندهار/Kandahar …).
- North Korea 12 (DPRK Hangul — 평양직할시, 량강도 initial-ㄹ, 라선특별시; McCune–Reischauer DPRK-style romanization).
- Israel 7 (Hebrew מחוז form), Lebanon 6 (Arabic).
- Belarus 7 + Tajikistan 5 + Kyrgyzstan 1 (Cyrillic — Belarusian вобласць, Tajik вилоят, Kyrgyz шаары).
- Sri Lanka 9 (Sinhala පළාත), Bangladesh 8 (Bengali বিভাগ), Nepal 7 (Devanagari प्रदेश).

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. **All major distinct-script subdivision sets
now covered** (Arabic, Hangul, Hebrew, Cyrillic, Devanagari, Bengali, Sinhala, Tamil, Lao, Thaana,
Dzongkha/Tibetan, Ge'ez, Georgian, Armenian, Greek, Han, Cyrillic-RU). Remaining gaps are predominantly
Latin-script subdivisions (Slovenia 212 municipalities, Uganda 135, Turkey 81, etc.) where name-local
≈ name-en — a lower-yield, separate axis for future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Gulf + Maghreb Arabic (Morocco+Oman+Qatar+UAE+Kuwait+Bahrain) (1810 → 1859)

Cleared the remaining Arabic-script subdivision sets across 6 states in one pass. 2 web-research
subagents (Wikidata P1705 + ar Wikipedia). **49 endonyms added with romanization, 0 nulls.**

- all-units name-local: 1810 → **1859**; subdivision name-local: 796 → **845**.
- Morocco 12 regions (طنجة تطوان الحسيمة, الدار البيضاء سطات, مراكش آسفي; Oriental = الشرق).
- Oman 11 (محافظة form; جنوب/شمال الباطنة + الشرقية pairs); Qatar 9 (بلدية form); UAE 7 (إمارة form);
  Kuwait 6 + Bahrain 4 (محافظة; Bahrain Southern/Northern use adjectival المحافظة الجنوبية/الشمالية).

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Arabic-script subdivision coverage now
complete (DZ, LY, YE, SY, JO, MA, OM, QA, AE, KW, BH, IR, IQ + EG). Remaining non-Latin subdivision
sets: North Korea 12 (Hangul), Sri Lanka 9 (Sinhala/Tamil), Bangladesh 8 (Bengali), Nepal 7
(Devanagari), Tajikistan 5 (Cyrillic), Kyrgyzstan 1, plus scattered — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: S/SE Asia + Ge'ez (Bhutan+Maldives+Laos+Ethiopia) (1739 → 1810)

Four more distinct scripts in one pass — Dzongkha (Tibetan), Thaana, Lao, Amharic Ge'ez. 4 web-research
subagents (Wikidata P1705 + lang labels). **71 endonyms added with romanization, 0 nulls.**

- all-units name-local: 1739 → **1810**; subdivision name-local: 725 → **796**.
- Bhutan 20 dzongkhag (ཐིམ་ཕུ་རྫོང་ཁག/Thimphu, སྤ་རོ་རྫོང་ཁག/Paro …) — Dzongkha Tibetan script.
- Maldives 20 administrative atolls — official Thaana atoll-code form (ހއ. Haa Alif, އައްޑޫ Addu),
  ISO-3166-2:MV aligned; readable name carried in romanized.
- Laos 17 (ຫຼວງພະບາງ/Louangphabang; Vientiane Capital ນະຄອນຫຼວງວຽງຈັນ distinct from province ວຽງຈັນ;
  Bokeo Thai-char contamination fixed → ບໍ່ແກ້ວ).
- Ethiopia 14 regions/cities (አዲስ አበባ, ኦሮሚያ, ትግራይ …) — Amharic Ge'ez.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining non-Latin subdivision sets now
small/mixed: Morocco 12, North Korea 12, Oman 11, Sri Lanka 9 (Sinhala/Tamil), Qatar 9, Bangladesh 8,
UAE 7, Nepal 7, Kuwait 6, Tajikistan 5, Bahrain 4, Kyrgyzstan 1, plus scattered — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Caucasus + Central Asia (Georgia+Armenia+Kazakhstan) (1698 → 1739)

Three distinct own-scripts in one pass — Georgian Mkhedruli, Armenian, Kazakh Cyrillic. 3 web-research
subagents (Wikidata P1705). **41 endonyms added with romanization, 0 nulls.**

- all-units name-local: 1698 → **1739**; subdivision name-local: 684 → **725**.
- Georgia 12 (თბილისი/Tbilisi, აჭარის ავტონომიური რესპუბლიკა, სამეგრელო-ზემო სვანეთი …) — Mkhedruli.
- Armenia 11 (Երևան/Yerevan, Արագածոտնի մարզ … "X-i marz" genitive form).
- Kazakhstan 18 (Kazakh Cyrillic constitutional form; regions облысы, cities қаласы; incl. Astana
  Астана қаласы, Baikonur Байқоңыр қаласы).

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining non-Latin subdivision sets:
Bhutan 20 (Dzongkha), Maldives 20 (Thaana), Lao 17, Ethiopia 14 (Ge'ez), Morocco 12, North Korea 12,
Oman 11, Sri Lanka 9 (Sinhala/Tamil), Qatar 9, plus smaller ones — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Arabic cluster Libya+Yemen+Syria+Jordan (1628 → 1698)

Cleared the remaining large Arabic-script subdivision sets in one pass — 4 web-research subagents
(Wikidata native labels P1705 + ar labels). **70 Arabic endonyms added with romanization, 0 nulls.**

- all-units name-local: 1628 → **1698**; subdivision name-local: 614 → **684**.
- Libya 22 shabiyat (بنغازي/Banghazi, طرابلس/Tarabulus, مصراتة/Misratah …) — bare proper-name form
  consistent with the P1705 values that exist; Derna/Jufra municipality-form labels normalized to
  district proper names درنة/الجفرة.
- Yemen 22 (محافظة <name>; capital kept as أمانة العاصمة not forced to محافظة; Socotra =
  محافظة أرخبيل سقطرى).
- Syria 14 + Jordan 12 governorates (محافظة form).

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining non-Latin subdivision sets now
mostly smaller / mixed-script: Bhutan 20, Maldives 20, Kazakhstan 18, Lao 17, Ethiopia 14, Morocco 12,
North Korea 12, Georgia 12, Armenia 11, Oman 11, Sri Lanka 9, Qatar 9, etc.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Algeria 58 wilayas (1570 → 1628)

Continued the subdivision endonym front with all 58 Algerian wilayas in Arabic. 5 web-research
subagents (Wikidata native labels). **58 Arabic endonyms added with romanization.**

- all-units name-local: 1570 → **1628**; subdivision name-local: 556 → **614**.
- official ولاية<Name> form (ولاية الجزائر/Wilayat al-Jazair = Algiers, ولاية وهران = Oran, ولاية قسنطينة
  = Constantine); includes the 10 NEW 2019 wilayas (تيميمون Timimoun … المنيعة El Meniaa). Arabic forms
  preferred over French exonyms (e.g. Relizane = غليزان/Ghulizan). All romanized.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining non-Latin subdivision sets:
Libya 22, Yemen 22, Bhutan 20, Maldives 20, Kazakhstan 18, Lao 17, Ethiopia 14, Syria 14, Morocco 12,
Jordan 12, North Korea 12, Georgia 12, Armenia 11, Oman 11, plus smaller ones — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Cambodia + Mongolia + Myanmar (1503 → 1570)

Continued the subdivision endonym front with 3 distinct SE/Central-Asian scripts. 6 web-research
subagents (Wikidata native labels). **67 endonyms added with romanization** (Cambodia 24 provinces
[Khmer], Mongolia 22 provinces [Cyrillic], Myanmar 21 regions/states/self-admin [Burmese]).

- all-units name-local: 1503 → **1570**; subdivision name-local: 489 → **556**.
- Cambodia ខេត្ត<Name> (ខេត្តកំពង់ចាម; Phnom Penh = រាជធានីភ្នំពេញ). Mongolia <Name> аймаг
  (Орхон аймаг; Ulaanbaatar = Улаанбаатар, a municipality, no аймаг suffix). Myanmar regions
  <Name>တိုင်းဒေသကြီး + states <Name>ပြည်နယ် + the 6 self-administered zones/division
  (ကိုယ်ပိုင်အုပ်ချုပ်ခွင့်ရဒေသ/ရတိုင်း — captured the zone-vs-division distinction for Wa). All romanized.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining non-Latin subdivision sets:
Yemen 22, Maldives 20, Bhutan 20, Lao 17, Iraq done, Georgia/Armenia, Kazakhstan/Tajikistan/Kyrgyz,
Greek-Cyprus, Bangladesh, Nepal, Sri Lanka, Ethiopia — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Iran + Iraq + Tunisia (1430 → 1503)

Continued the subdivision endonym front with the Persian + Arabic cluster. 7 web-research subagents
(Wikidata native labels). **73 endonyms added with romanization** (Iran 31 provinces [Persian],
Iraq 18 governorates [Arabic], Tunisia 24 governorates [Arabic]).

- all-units name-local: 1430 → **1503** (crossed 1,500); subdivision name-local: 416 → **489**.
- Iran استان<Name> (استان تهران/Ostan-e Tehran, استان خراسان رضوی; noun-first adjective order captured —
  آذربایجان شرقی East Azarbaijan). Iraq محافظة<Name> (محافظة بغداد; Kurdish-region governorates Erbil/
  Duhok/Sulaymaniyah given in Arabic per registry standard). Tunisia ولاية<Name> (ولاية تونس; Kef =
  ولاية الكاف with the definite article; Wikidata ق form preferred over the regional ڨ glyph). All romanized.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining big non-Latin subdivision sets:
Khmer 24, Mongolia 22, Yemen 22, Myanmar 21, Maldives 20, Bhutan 20, Lao 17, Georgia/Armenia/
Kazakhstan/Tajikistan/Kyrgyzstan, Greek-Cyprus, Bangladesh — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Serbia + Bulgaria + Ukraine Cyrillic (1346 → 1430)

Continued the subdivision endonym front with a 3-country Cyrillic cluster. 7 web-research subagents
(Wikidata native labels). **84 Cyrillic endonyms added with romanization** (Serbia 30 districts,
Bulgaria 28 provinces, Ukraine 26 oblasts).

- all-units name-local: 1346 → **1430**; subdivision name-local: 332 → **416**.
- Serbian districts in "<Adjective> управни округ" (Шумадијски управни округ; City of Belgrade = Град
  Београд; Kosovo districts in Serbia's de jure listing as closed-compound Косовскомитровачки/
  Косовскопоморавски — observational, G3). Bulgarian "Област <Name>" (Област Пловдив; Sofia City =
  Област София (столица); Софийска област adjectival). Ukrainian "<Name> область" (Київська область;
  Київ city; Автономна Республіка Крим de jure Ukrainian). All romanized.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining big non-Latin subdivision sets:
Khmer 24, Tunisia 24 (Arabic), Mongolia 22, Yemen 22, Myanmar 21, Maldives 20, Bhutan 20, Iran 31,
Iraq 18, Lao 17, Georgia/Armenia/Kazakhstan/etc. — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: North Macedonia 81 municipalities (1265 → 1346)

Continued the subdivision endonym front with all 81 North Macedonian municipalities (општини) in
Macedonian Cyrillic. 7 web-research subagents (Wikidata native labels). **81 Cyrillic endonyms added
with romanization.**

- all-units name-local: 1265 → **1346**; subdivision name-local: 251 → **332**.
- official "Општина <Name>" form (Општина Битола/Opština Bitola, Општина Тетово, Општина Ѓорче Петров
  with the Ѓ letter); the capital = Град Скопје/Grad Skopje (City of Skopje, not Општина). All romanized
  (ISO-9 Macedonian Latin) → searchable by Latin reading on /gov.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining big non-Latin subdivision sets:
Serbia 30, Bulgaria 28, Ukraine 26, Khmer 24, Tunisia 24 (Arabic), Mongolia 22, Yemen 22, Myanmar 21,
Maldives 20, Bhutan 20, Lao 17, Iran 31, Iraq 18 — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Thailand 77 provinces (1188 → 1265)

Continued the subdivision endonym front with all 77 Thai provinces (จังหวัด) in Thai script.
7 web-research subagents (Wikidata native labels). **77 Thai endonyms added with RTGS romanization.**

- all-units name-local: 1188 → **1265**; subdivision name-local: 174 → **251**.
- official จังหวัด<name> form (จังหวัดเชียงใหม่/Chiang Mai, จังหวัดภูเก็ต/Phuket, …); Bangkok =
  กรุงเทพมหานคร (special admin area, no จังหวัด prefix). All RTGS-romanized → searchable by Latin
  reading on /gov.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining big non-Latin subdivision sets:
North Macedonia 81, Serbia 30, Bulgaria 28, Ukraine 26, Khmer 24, Tunisia 24 (Arabic), Mongolia 22,
Yemen 22, Myanmar 21, Maldives 20, Bhutan 20, Lao 17 — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision name-local: Russia 85 federal subjects (1103 → 1188)

Continued the subdivision endonym front with the single largest non-Latin subdivision set: all 85
Russian federal subjects (republics / oblasts / krais / autonomous okrugs / federal cities). 7 web-
research subagents (Wikidata native labels). **85 Cyrillic endonyms added with romanization.**

- all-units name-local: 1103 → **1188**; subdivision name-local: 89 → **174**.
- standard administrative forms: republics Республика Татарстан / Чеченская Республика, oblasts
  …ская область, krais …ский край, autonomous okrugs Ямало-Ненецкий автономный округ, federal cities
  Москва / Санкт-Петербург. Captured the constitutional dual-names: Кемеровская область — Кузбасс and
  Ханты-Мансийский автономный округ — Югра. All romanized → searchable by Latin reading on /gov.
- honest note: Republic of Crimea (q15966495) + Sevastopol (ua-40) are internationally Ukrainian,
  Russia-administered since the 2014 annexation (not internationally recognized). The Cyrillic
  name-local is the linguistic endonym only — the atlas is an observational mirror (G3), not a
  sovereignty claim; both spellings are identical in Russian and Ukrainian.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN. Remaining big non-Latin subdivision sets:
Thailand 77, North Macedonia 81, Iran 31, Ukraine 26, Bulgaria 28, Serbia 30, … (future iterations).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis extends to SUBDIVISIONS: CN/KR/EG/GR (1014 → 1103)

Opened a new front for the endonym axis: SUBDIVISIONS of non-Latin jurisdictions had ZERO name-local
(only the high-tier ministries/courts carried endonyms). Began with the 4 highest-reference clusters.
6 web-research subagents (Wikidata native labels). **89 first-level-division endonyms added with
romanization** (China 33 provinces, Korea 15, Egypt 27 governorates, Greece 14 regions).

- all-units name-local: 1014 → **1103**; subdivision name-local: 0 → **89** (a brand-new tier).
- China provinces in 简体中文 with official suffixes (安徽省/Ānhuī Shěng, 新疆维吾尔自治区, 香港特别行政区);
  Korea in Hangul (서울특별시/Seoul Teukbyeolsi, 강원특별자치도 — reflects the 2023 Gangwon + 2024 Jeonbuk
  Special Self-Governing Province upgrades); Egypt governorates in Arabic (القاهرة/al-Qāhira); Greece
  regions in Greek (Περιφέρεια Αττικής; gr-69 = Άγιον Όρος autonomous monastic state). All romanized.
- the /gov map already renders nameRomanized + makes it searchable, so these 89 provinces are now
  findable by Latin reading too (e.g. "Ānhuī", "Gyeonggi", "al-Qāhira").

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN; index regen → 1103 with name-local.
Hundreds more non-Latin subdivisions remain (Russia 85, Thailand 77, North Macedonia 81, Iran 31,
Ukraine 26, …) — a long runway for future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — DATA-QUALITY: structural sweep — fix Brazil interior/justice slot collision

Extended the data-quality pass beyond subdivisions to ALL units: scanned for dangling parent refs
(0 found — clean) and for duplicate name-en within the same (country, level). One collision remained:
**gov.bra.interior AND gov.bra.justice were BOTH "Ministry of Justice and Public Security"** (both
pointing at gov.br/mj) — Brazil has no separate Interior Ministry, so the "interior" functional slot
had been mis-filled with a duplicate of Justice.

- **re-pointed gov.bra.interior** to the genuinely distinct ministry that fills Brazil's internal/
  regional-affairs function: **Ministry of Integration and Regional Development (MIDR / Ministério da
  Integração e do Desenvolvimento Regional)** — gov.br/mdr/pt-br, Wikidata Q10330386 (handles regional
  integration + civil protection / Secretaria Nacional de Proteção e Defesa Civil). Added the
  Portuguese name-local. gov.bra.justice stays the canonical MJSP. (1 web-research subagent confirmed.)
- **fixed its address**: the old hq row pointed at the Palácio da Justiça (the MJSP building, coord
  -15.7973/-47.8659) — wrong for MIDR. Re-set to "Esplanada dos Ministérios, Bloco E, Brasília (MIDR)"
  and DROPPED the Justice-building coord (G5 — did not fabricate a MIDR coord; honest null).

Verified: check_seed_integrity ✓; **duplicate name-en groups atlas-wide now 0**; dangling parent refs
0; run_tests.sh ALL GREEN. The atlas is now structurally clean: no QID/ISO subdivision duplicates, no
same-(country,level) name collisions, no dangling parents.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — DATA-QUALITY:全法域 QID/ISO duplicate sweep — 6 more removed (7093 → 7087)

Ran a SYSTEMATIC QID-vs-ISO duplicate scan across ALL jurisdictions (normalize name, strip the
level suffix, match a `.qNNN`-keyed subdivision to an ISO-3166-2-keyed one of the same place).
Found 6 more dual-entries beyond the Tanzania batch and removed the QID duplicates (each: unit def +
address row). **Re-scan now reports ZERO remaining QID/ISO subdivision duplicates atlas-wide.**

- **Azerbaijan**: gov.aze.adm1.q158903 (Shusha) ≡ az-sus (Shusha District) — both had the url+coord;
  ISO kept.
- **Libya** (5): q131323 Misrata ≡ ly-mi, q132409 Nalut ≡ ly-nl, q209393 Ghat ≡ ly-gt, q221503
  Zawiya ≡ ly-za, q3579 Tripoli ≡ ly-tb. ISO entries keep the coords.
- data note: the removed Tripoli QID carried a non-official `http://www.tripoli.info` URL (an .info
  city-info site, NOT a .gov.ly portal) — deliberately NOT transferred to the canonical ly-tb (which
  honestly stays url-less; Libyan districts largely have no official portal). Net accuracy gain.
- units 7093 → **7087**; addresses 1:1 preserved; no live OFFICIAL url lost.

Verified: check_seed_integrity ✓; run_tests.sh ALL GREEN; index regenerates 7,665 units +
validate_atlas --file ✓. The atlas is now duplicate-free across both the Tanzania (11) and this
6-unit sweep — 19 Wikidata-import artifacts removed total over the two cleanup PRs.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — DATA-QUALITY: remove 13 duplicate/artifact subdivisions (7106 → 7093 units)

Cleaned up the Wikidata-import artifacts flagged over the prior iterations. **Removed 13 bogus
subdivision unit records** (each: the :units definition + its :addresses row), leaving every
jurisdiction with its correct canonical first-level divisions.

- **11 Tanzania QID duplicates** removed: gov.tza.adm1.q110218 (Mwanza), q1960 (Dar es Salaam),
  q243319 (Morogoro), q244509 (Kigoma), q335548 (Mbeya), q643112 (Tabora), q646684 (Mtwara),
  q7296 ("Mount Kilimanjaro" — a MOUNTAIN, not a region), q735609 (Iringa), q818765 (Shinyanga),
  q829886 (Lindi). Each DUPLICATED a canonical ISO-3166-2 region (tz-18 Mwanza Region, tz-02 Dar es
  Salaam Region, …, tz-09 Kilimanjaro Region) — the .go.tz portals + names live on the ISO entries.
  Tanzania subdivisions: 37 → **26** (the correct count of mainland+Zanzibar regions).
- **gov.pak.adm1.q19807103** "Junagadh and Manavadar" — a former princely state claimed by Pakistan
  but India-administered since 1948; NOT a current Pakistani province. Removed.
- **gov.sau.adm1.q74063** "list of provinces of Saudi Arabia" — a Wikidata LIST item, never a real
  subdivision. Removed.
- units 7106 → **7093**; address records 7106 → 7093 (1:1 preserved); name-local 1013 unchanged;
  hq-coords 5670 → 5659 (the 11 dropped coords were on the removed duplicates; the canonical region
  entries are areas without a separate building seat).

Verified: check_seed_integrity --quiet ✓; run_tests.sh ALL GREEN; index regenerates to 7,671 units
(was 7,684) and validate_atlas --file ✓ (JP-authoritative-scope, parent-refs, summary all pass).
No live URLs lost (all were on the surviving ISO entries). Non-destructive to every real unit.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision official-url — Algeria wilayas + big-country mop-up (5949 → 5995)

The big federal countries (Mexico/Brazil/Russia/China/India/Turkey/Thailand/…) are now subdivision-
url-complete; the one large remaining gap was Algeria (51 wilayas). Plus a scattered mop-up of the
last 1-2-unit gaps in Turkey/Nigeria/UAE/Ukraine/Egypt/Venezuela/Pakistan/Saudi. 5 web-research
subagents. **46 official portals found + added; 15 honest nulls.**

- official-url: 5949 → **5995/7106**.
- **Algeria wilayas** (40 of 51): official wali (provincial governor's office) .dz portals
  (wilaya-<name>.dz / <name>.wilaya.dz / .gov.dz patterns). 11 nulls — mostly the NEW 2019 wilayas
  (Timimoun, Bordj Badji Mokhtar, In Salah, In Guezzam, Djanet, El M'Ghair) which only have tourism-
  directorate / commune / Facebook presence, plus 5 defunct/dead-domain older ones (Chlef, Annaba,
  Illizi, BBA, El Tarf). Rejected .mta.gov.dz tourism directorates + commune sites (wrong body).
- **mop-up** (6): Turkey Diyarbakır + Kilis valilik (.gov.tr); Nigeria Kano State; UAE Umm Al Quwain
  (uaq.ae — corrected, NOT uaq.gov.ae); Ukraine Luhansk Oblast military admin (loga.gov.ua); Egypt
  Beheira (behira.gov.eg — corrected spelling).
- **honest nulls + 2 flagged data artifacts (G5)**: Venezuela Federal Dependencies + Delta Amacuro
  (centrally administered / social-only); **gov.pak.adm1.q19807103 "Junagadh and Manavadar"** (a
  former princely state claimed by Pakistan but India-administered since 1948 — NOT a current
  Pakistani province) and **gov.sau.adm1.q74063 "list of provinces of Saudi Arabia"** (a Wikidata
  LIST item, not a subdivision) — both flagged for a future data-quality cleanup, alongside
  gov.tza.adm1.q7296 (Mount Kilimanjaro) noted earlier.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — subdivision official-url — partial-coverage jurisdictions (5905 → 5949)

Continued the subdivision official-url axis across 8 partially-covered jurisdictions. 8 web-research
subagents. **44 official portals found + added; 41 honest nulls** (this batch deliberately tested
several jurisdictions whose first-level divisions structurally have NO government portal — the nulls
are the finding, not a miss).

- official-url: 5905 → **5949/7106**.
- **Iraq governorates** (12/12): every محافظة diwan portal (anbar.iq, najaf.gov.iq, karbala.gov.iq …).
- **Cape Verde municipalities** (9/12): Câmara Municipal .cv portals (3 null = Facebook-only).
- **Uganda districts** (9/9): <district>.go.ug local-government portals.
- **Paraguay departments** (8/9): gobernación .gov.py portals (+ Asunción municipality for the Capital
  District; Ñeembucú via IDN punycode xn--eembucu-3za.gov.py).
- **Tunisia governorates** (4/12): only Tunis/Ben Arous/Béja/Jendouba run a gouvernorat-*.gov.tn site;
  the rest have none (rejected commune-*.gov.tn municipality sites — wrong tier).
- **Jordan** (2/11): only Amman (Greater Amman Municipality, metropolitan = governorate-scope) +
  Aqaba (ASEZA, governs the whole zone). The other 9 governorates are MoI-administered with no
  standalone portal; their seat-city municipalities are a DIFFERENT tier — left null (G5 accuracy,
  not attributed up-tier).
- **honest structural nulls**: Portugal districts (10/10 null — civil governments ABOLISHED 2011,
  districts are statistical/electoral only; did NOT substitute the Câmara Municipal of the capital);
  Philippine regions (10/10 null — administrative groupings not LGUs; the RDC is run by a national
  DEPDev/NEDA regional office, not a regional government). Negros Island Region re-created 2024.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — CONTACT axis: subdivision official-url — high-yield batch (5817 → 5905)

Resumed the official-url coverage axis at the SUBDIVISION tier (1,223 first-level-division gaps).
Targeted jurisdictions where each province/region/municipality demonstrably runs its OWN portal
(skipping the many developing-country provinces that genuinely have none — those are honest future
nulls). 7 web-research subagents. **88 official portals found and added; 4 honest nulls.**

- official-url: 5817 → **5905/7106**.
- **US states** (5): kentucky.gov, nebraska.gov, oklahoma.gov, oregon.gov, pr.gov.
- **Iran provinces** (17): ostandari governor's-office portals (ostan-XX.ir / hormozgan.ir /
  alborz.ir / sko.ir / nkhorasan.ir …) — data note: ostan-hm.ir is Hamadan NOT Hormozgan (corrected).
- **Montenegro municipalities** (15): every opština portal (bar.me … zeta.me; Tivat = opstinativat.me
  not tivat.me; Zeta migrated to zeta.me Aug 2025).
- **Tanzania regions** (17 of 19): Regional-Commissioner .go.tz portals (mwanza/kigoma/dodoma/…) —
  duplicate QID/ISO unit pairs both filled (q244509≡tz-08, q735609≡tz-04, q643112≡tz-24).
- **Cambodia provinces** (22): every <province>.gov.kh provincial-administration portal.
- **Panama** (12 of 14): gobernación pages under mingob.gob.pa (consolidated, no standalone domains).
- **4 honest nulls (G5)**: Tanzania Q7296 ("Mount Kilimanjaro" — a Wikidata data-quality artifact, a
  MOUNTAIN not a region) + Unguja South (social-media only); Panama Wargandí + Madugandí comarcas
  (corregimiento-comarcal, traditional-congress governed, no gobernación/site). Not fabricated.
- flagged data-quality artifact for a future cleanup: gov.tza.adm1.q7296 mislabels Mount Kilimanjaro
  as a subdivision (the real Kilimanjaro Region is tz-09).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — /gov FRONT-END: render endonyms + romanization + seat map links

Completed the publish-surface chain: the previous iteration put coords/endonyms/romanizations INTO
the index; this one makes the `/gov` atlas page actually USE them. Edited the apex Worker's `/gov`
HTML (`50-infra/etzhayyim-did-web/src/worker.ts`):

- **search now matches `nameRomanized`** — a Latin reader can find an endonym-named unit by typing
  "Kokkai" / "Verkhovna" / "Knesset" (previously only native-script name / English / id matched).
- **renders the romanization** (italic, after the endonym) when present.
- **adds a `geo:lat,lon` "map" link** for the 5,670 located seats — opens the user's OWN map app via
  the standard geo URI; NO third-party map/tile/script embedded (Charter ad-free / no-tracker / CSP
  default-src 'none' preserved — it's a plain top-level navigation link, not a fetch).
- stats line now reports "<N> endonyms · <N> located"; placeholder advertises endonym/romanization search.

Verified: worker `tsc --noEmit` clean; a node smoke-harness ran the inline render logic against
sample units → stats shows "2 endonyms · 1 located", output contains the Kokkai romanization hit and
the geo:24.7628,46.6403 map link. Additive, CSP-safe, no new dependencies.

The world atlas is now end-to-end: 7,106 units with addresses → 5,670 plottable seats + 1,013
endonyms (25 scripts) flow registry → index generator → /.well-known/gov-units.json → /gov UI,
each unit findable by its Latin reading and openable on the user's map.

run_tests.sh (ooyake) ALL GREEN; validate_atlas ✓ (unchanged from prior PR).

## 2026-06-05 — PUBLISH-SURFACE enrich: hq coords + endonyms into /gov atlas index

Pivoted from data-entry to data-exposure: the 5,670 building-level seat coordinates and 1,013
endonyms (+romanizations) we'd accumulated were NOT reaching the published `/gov` atlas index —
the generator emitted only id/name/nameEn/level/url/sourcing. Enriched the index so the rich data
actually surfaces.

- `50-infra/etzhayyim-did-web/scripts/gen-gov-atlas-index.mjs`:
  - now reads `:addresses` across every registry EDN and joins building-level `lat`/`lon` onto each
    unit record (5,670 units gain plottable coords — omitted entirely where no real seat, G5).
  - emits distinct `nameLocal` + `nameRomanized` fields (previously name-local was only folded into
    the display `name`; the romanization was dropped on the floor).
  - adds `withCoords` (5670) + `withNameLocal` (1013) summary counters to the index header.
- additive only — `validate_atlas.py` (id/level/sourcing/summary/JP-authoritative-scope) still
  PASSES; the published index stays all-`:representative` except the JP pref/city backbone (check #5).
- the `/gov` map can now plot real ministry/agency/court/library/archive seats worldwide and render
  each in its own script with a Latin reading.

Verified: generator → 7,684 units, 5,670 with hq coords, 1,013 with name-local; validate_atlas
--file ✓ all integrity checks passed; run_tests.sh ALL GREEN. (out/gov-units.json is a gitignored
build artifact; only the generator is committed.)

## 2026-06-05 — name-local axis: final non-Latin sweep IL/CY/BT/MV/AF (934 → 1013)

Closed the remaining sizeable non-Latin jurisdictions. 8 web-research subagents. **79 endonyms added
with romanization** (Israel 22 Hebrew, Cyprus 21 Greek, Bhutan 12 Dzongkha, Maldives 8 Dhivehi/Thaana,
Afghanistan 16 Dari). **all-units name-local crosses 1,000 → 1013.**

- scripts: Hebrew (הכנסת/HaKnesset, בית המשפט העליון), Greek-Cyprus (Βουλή των Αντιπροσώπων), Dzongkha
  Tibetan (ལྷན་རྒྱས་གཞུང་ཚོགས/Lhengye Zhungtshog), Dhivehi Thaana (ރައްޔިތުންގެ މަޖިލިސް/Rayyithunge
  Majlis, RTL), Dari Perso-Arabic (ستره محکمه, د افغانستان بانک) — all with romanization.
- **5 honest nulls (G5)**: Bhutan anticorruption + statistics (English-only sites, no published
  Dzongkha); Maldives MMA + meteorology + statistics (transliterated-English bodies, no independently
  verified Thaana) — not fabricated.
- honest notes: Israel agriculture renamed "…and Food Security" (2024) + energy reverted to "…and
  Infrastructure" (2023); Maldives ministry Dhivehi reflects the Muizzu-administration restructured
  "vuzaaraa" titles (broader scope than the short English labels); Da Afghanistan Bank's legal name is
  Pashto-form د افغانستان بانک in both languages.

**name-local axis ~complete for all non-Latin jurisdictions.** Started this axis at 78; now 1013
(13× growth) across ~25 scripts (Latin-diacritic, CJK, Hangul, all Cyrillic, Arabic, Persian, Urdu,
Hebrew, Greek, Armenian, Georgian, Bengali, Thai, Lao, Khmer, Burmese, Sinhala, Devanagari, Dzongkha,
Thaana, Amharic, Tigrinya). Residual gaps are Latin-script jurisdictions where name-local would
duplicate name-en (no value) plus a handful of small islands.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: SE/South Asia + Horn MM/KH/LA/NP/LK/ET/ER (832 → 934)

Continued the endonym axis into 7 distinct indigenous scripts. 10 web-research subagents.
**102 endonyms added with romanization** (Myanmar 18 Burmese, Cambodia 16 Khmer, Laos 8 Lao,
Nepal 22 Devanagari, Sri Lanka 19 Sinhala, Ethiopia 18 Amharic, Eritrea 1 + 4 honest nulls).

- all-units name-local: 832 → **934**.
- scripts newly on the atlas: Burmese (ပြည်ထောင်စုလွှတ်တော်/Pyidaungsu Hluttaw), Khmer
  (ក្រសួងមហាផ្ទៃ), Lao (ສະພາແຫ່ງຊາດ/Sapha Haengxat), Devanagari (नेपाल सरकार/Nepal Sarkar),
  Sinhala (ශ්‍රී ලංකා මහ බැංකුව), Amharic (የሕዝብ ተወካዮች ምክር ቤት/Ye-Hizb Tewekayoch) — all romanized.
- **4 honest nulls (G5)**: Eritrea agriculture/archives/finance/foreign — Eritrea has no
  constitutionally-designated official language and these bodies publish no established Tigrinya
  orthographic name (only the Bank of Eritrea ባንክ ኤርትራ is attested); not fabricated.
- honest currency notes (names match registry labels): Ethiopia statistics rebranded to Ethiopian
  Statistical Service (2021); Nepal CBS → National Statistics Office (2022 Act); Nepal Industry+Trade
  are the same merged ministry; Myanmar finance = Ministry of Planning and Finance; Cambodia
  constitutional body is the Constitutional Council (not a court).

**Approaching name-local completion** for all sizeable non-Latin jurisdictions. Remaining gaps are
scattered small/Pacific/sub-Saharan units (Bhutan Dzongkha, Maldives Thaana, Cyprus Greek, Israel
Hebrew agencies, etc.) — a final sweep next.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: Central Asia + Belarus KZ/KG/TJ/MN/BY (734 → 832)

Continued the endonym axis into Central-Asian + Mongolian + Belarusian Cyrillic. 8 web-research
subagents. **98 ministry/agency/court/legislature endonyms added with romanization** (Kazakhstan 22,
Kyrgyzstan 17, Tajikistan 12, Mongolia 21, Belarus 26).

- all-units name-local: 734 → **832**.
- scripts: Kazakh (Қазақстан Республикасының Үкіметі), Kyrgyz (Жогорку Кеңеши), Tajik (Маҷлиси Олӣ),
  Mongolian (Улсын Их Хурал/Ulsyn Ikh Khural), Belarusian-Russian (Совет Министров, Нацыянальны…) — all
  with romanization. (used an escaped-quote-safe insertion regex this round — no parse bug.)
- **1 data-quality en-name fix**: gov.kaz.culture "Culture and Sports" → Ministry of Culture and
  Information (current Kazakh body).
- honest currency notes captured (names match registry labels): Kazakhstan's standalone Anti-Corruption
  Agency dissolved 2025-06-30 into the National Security Committee; Mongolia education ministry now
  "Боловсролын яам" (science split out 2024); Mongolia labour officially "Family, Labour and Social
  Protection"; Kyrgyzstan agriculture reorganised to "Water Resources, Agriculture and Processing
  Industry"; Mongolia SWF = Chinggis Khaan National Wealth Fund (umbrella; Future Heritage = sub-fund).

Remaining non-Latin high-tier endonym gaps ~210 (Myanmar/Cambodia/Laos/Nepal/Sri Lanka, Eritrea/
Ethiopia, plus scattered sub-Saharan/Pacific non-Latin) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: Balkan Cyrillic + Caucasus BG/RS/MK/GE/AM (642 → 734)

Continued the endonym axis into Balkan Cyrillic + Caucasus scripts. 7 web-research subagents.
**92 ministry/agency/court/legislature endonyms added with romanization** (Bulgaria 26, Serbia 21,
North Macedonia 10, Georgia 18, Armenia 17).

- all-units name-local: 642 → **734**.
- scripts: Bulgarian/Serbian/Macedonian Cyrillic (Народно събрание, Влада Републике Србије, Собрание),
  Georgian (საქართველოს პარლამენტი/Sakartvelos parlamenti, უზენაესი სასამართლო), Armenian
  (Ազգային ժողով/Azgayin zhoghov, սահմանադրական դատարան) — all with romanization.
- **3 data-quality en-name fixes**: gov.geo.culture "Culture and Monument Protection" → Ministry of
  Culture (Georgia split Culture/Sport 1 Jan 2025); gov.geo.energy → Ministry of Economy and
  Sustainable Development (no standalone energy ministry); gov.arm.energy "Ministry of Energy
  Infrastructures and Natural Resources" (abolished 2019) → Ministry of Territorial Administration and
  Infrastructure.
- honest notes: Serbia Supreme Court of Cassation renamed Supreme Court (2023); Serbia organised-crime
  prosecutor dropped "Јавно" prefix post-2023 reform; both Georgia/Armenia energy folded into parent
  ministries.
- **fixed a self-inflicted parse bug**: gov.mkd.library's name-en contains escaped quotes
  (\"St. Kliment of Ohrid\"); the field-insertion regex split the string — repaired, integrity green.

Remaining non-Latin high-tier endonym gaps ~310 (Kazakhstan/Kyrgyzstan/Tajik Cyrillic, Mongolia,
Myanmar/Cambodia/Laos/Nepal/Sri Lanka, Eritrea/Ethiopia, Belarus) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: Bengali/Thai/Greek/Cyrillic BD/TH/GR/UA (543 → 642)

Continued the endonym axis into a 4-script cluster. 8 web-research subagents. **99 ministry/agency/
court/legislature endonyms added with romanization** (Bangladesh 26 Bengali, Thailand 25 Thai,
Greece 22 Greek, Ukraine 26 Cyrillic).

- all-units name-local: 543 → **642**.
- new scripts on the atlas: Bengali (জাতীয় সংসদ/Jatiya Sangsad, বাংলাদেশ ব্যাংক), Thai
  (กระทรวงการต่างประเทศ, ศาลฎีกา/San Dika), Greek (Βουλή των Ελλήνων, Άρειος Πάγος/Areios Pagos),
  Ukrainian Cyrillic (Верховна Рада, Кабінет Міністрів України) — all with romanization.
- **3 data-quality en-name fixes**: gov.grc.trade "Ministry for Trade" → Ministry of Development
  (Greece has no standalone trade ministry); gov.ukr.revenue "State Fiscal Service" (split 2019) →
  State Tax Service of Ukraine; gov.ukr.tourism (was duplicating "Ministry of Culture") → State
  Agency for Tourism Development of Ukraine (DART, a separate central executive body).
- honest notes captured (names match registry labels): Greece EETT is the telecom regulator not a
  competition authority; Ukraine culture ministry renamed back to plain Міністерство культури in Oct
  2025 (kept the labelled "…and Strategic Communications" form); Thai NACC = the commission proper.

Remaining non-Latin high-tier endonym gaps ~400 (Central Asia Cyrillic [Kazakhstan/Kyrgyzstan/Tajik],
Balkan Cyrillic [Serbia/Bulgaria/N.Macedonia/Mongolia], Caucasus [Georgia/Armenia], Myanmar/Cambodia/
Laos/Nepal/Sri Lanka, Eritrea/Ethiopia) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: Maghreb + Pakistan (453 → 543)

Continued the endonym axis into the Maghreb (Arabic) + Pakistan (Urdu). 8 web-research subagents.
**90 ministry/agency/court/legislature endonyms added with romanization** (Morocco 20, Algeria 19,
Tunisia 24, Pakistan 27 — 2 Pakistani bodies honestly null).

- all-units name-local: 453 → **543**.
- Arabic (Maghreb): بنك المغرب, المندوبية السامية للتخطيط (HCP), البرلمان الجزائري, مجلس نواب الشعب
  (Tunisia); Urdu (Nastaliq): حکومت پاکستان, وزارت خارجہ, عدالتِ عظمیٰ پاکستان, محکمہ موسمیات پاکستان.
- **3 data-quality en-name fixes**: gov.mar.supreme-court "Supreme Court of Morocco" → Court of
  Cassation (محكمة النقض, renamed by Law 58-11/2011); gov.dza.constitutional-court "Constitutional
  Council" → Constitutional Court (2020 revision); gov.pak.nhri "Human Rights Commission of Pakistan"
  (an NGO/HRCP) → National Commission for Human Rights (NCHR, the official Paris-Principles body).
- **2 honest nulls (G5)**: gov.pak.ombudsman (FOSPAH) and gov.pak.tourism (PTDC) operate under their
  English names with no established single official Urdu form — not fabricated.
- notes: Morocco merged Communications into the Youth/Culture/Communication ministry; Algeria interior
  label "Territorial Planning" reflects the prior cabinet (current site lists "…and Transport").

Remaining non-Latin high-tier endonym gaps ~499 (Bangladesh, Thai, Greek, Cyrillic neighbours,
Central Asia, SE Asia, sub-Saharan non-Latin) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: Levant/Persia IR/IQ/JO/SY/YE (368 → 453)

Continued the endonym axis into the Levant + Persia cluster. 7 web-research subagents.
**85 ministry/agency/court/legislature endonyms added with romanization** (Iran 22 [Persian],
Iraq 15, Jordan 14, Syria 22, Yemen 12).

- all-units name-local: 368 → **453**.
- Persian (Perso-Arabic): مجلس شورای اسلامی/Majles-e Shorā-ye Eslāmi, وزارت امور خارجه, دیوان عالی کشور;
  Arabic: مجلس النواب العراقي, هيئة النزاهة ومكافحة الفساد (Jordan), مصرف سورية المركزي, etc.
- **1 data-quality en-name fix**: gov.irq.supreme-court "Supreme Court of Iraq" → Federal Supreme Court
  of Iraq (المحكمة الاتحادية العليا, the constitutional apex).
- honest transition notes captured in romanization/source (not invented): Syria's 2024-25 transitional
  govt merged Economy+Foreign-Trade into Economy+Industry and Petroleum+Electricity into Energy — the
  stored name matches the registry English label; Iraq COSIT rebranded to Authority for Statistics &
  Geospatial Information Systems (canonical الجهاز المركزي للإحصاء kept to match en); Iran energy unit =
  Ministry of Petroleum (وزارت نفت).

Remaining non-Latin high-tier endonym gaps ~589 (Maghreb [Morocco/Algeria/Tunisia], Pakistan/Bangladesh,
Thai, Greek, Cyrillic neighbours, Central Asia, SE Asia) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: Arab core SA/AE/EG/QA/KW (272 → 368)

Continued the endonym axis into the Arabic-script cluster: the Gulf core + Egypt. 7 web-research
subagents. **96 ministry/agency/court/legislature Arabic names added with romanization** (Saudi 23,
UAE 16, Egypt 25, Qatar 16, Kuwait 16).

- all-units name-local: 272 → **368**.
- Arabic script with transliteration: وزارة الخارجية/Wizarat al-Kharijiyya, الهيئة العامة للإحصاء,
  صندوق الاستثمارات العامة (PIF), جهاز قطر للاستثمار (QIA), بنك الكويت المركزي, etc.
- **5 data-quality en-name fixes**: gov.sau.legislature "Government of Saudi Arabia" → Shura Council
  (مجلس الشورى); gov.are.legislature "Federal Supreme Council" (the rulers' council) → **Federal
  National Council** (المجلس الوطني الاتحادي, the actual legislature); gov.egy.finreg EFSA → Financial
  Regulatory Authority; gov.egy.statistics "Egypt Statistics" → CAPMAS; gov.qat.statistics "Ministry
  of Development Planning and Statistics" → Planning and Statistics Authority.
- honest data notes surfaced: Saudi ZATCA = merged zakat+tax+customs (2021); UAE archives Arabic word
  order reverses the English ("الأرشيف والمكتبة الوطنية"); Kuwait transport ministry = وزارة المواصلات.

Remaining non-Latin high-tier endonym gaps now ~674 (Iran, Iraq, Jordan, Syria, Tunisia, Morocco,
Algeria, Yemen [Arabic]; Thai, Bengali, Greek, Cyrillic neighbours, etc.) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: great-power ministries JP/CN/KR/RU (182 → 272)

Extended the endonym axis to high-tier institutions in non-Latin-script jurisdictions, starting with
the 4 most-referenced great-power administrations. 7 web-research subagents (Wikidata native labels).
**90 ministry/agency/court/legislature endonyms added with romanization** (Japan 11, China 24,
Korea 28, Russia 27).

- all-units name-local: 182 → **272**; JP 16→32, CN 2→27, KR 2→31, RU 2→30.
- scripts: Japanese Kanji (会計検査院/Kaikei Kensain, 国立国会図書館/…), Simplified Chinese
  (中华人民共和国外交部/…), Hangul (외교부/Oegyobu, 대법원/Daebeobwon), Cyrillic (Министерство
  обороны…/…, Росстат) — all with romanization.
- **4 data-quality en-name fixes** surfaced during research: gov.chn.anticorruption "ICAC" (a Hong
  Kong body) → National Supervisory Commission; gov.chn.finreg "China Banking Regulatory Commission"
  (dissolved 2023) → National Financial Regulatory Administration; gov.chn.meteorology "National
  Meteorological Centre" (a sub-unit) → China Meteorological Administration; gov.chn.prosecutor
  "Fourth Division of the People's Procuratorate of Beijing" (a wrong sub-division) → Supreme
  People's Procuratorate.
- honest note: gov.chn.electoral has no name-local — the PRC has no national electoral commission
  (local elections run by ad-hoc 选举委员会), so no endonym was invented.

770 high-tier endonym gaps remain across other non-Latin jurisdictions (Pakistan, Arab states, Thai,
Greek, Cyrillic neighbours, etc.) — future iterations.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — name-local axis: country endonyms (19 → 123)

New maturity axis: native-script / native-language official names (endonyms). name-local was only
78/7106 across the whole atlas. Filled the COUNTRY tier first (foundational): 12 web-research
subagents pulled Wikidata native labels for the 173 missing countries. **104 endonyms added**
(non-Latin scripts + diacritic/spelling variants); 69 skipped as identical to the English name
(English-official or coincident spelling — no value, not stored).

- countries with name-local: 19 → **123/192**; all units: 78 → 182; +68 romanizations.
- non-Latin scripts now carried with romanization: Arabic (مصر/Miṣr, السودان/as-Sūdān, …), Cyrillic
  (Україна/Ukraïna, Србија/Srbija, Монгол Улс/Mongol Uls, …), CJK/Hangul (조선/Chosŏn), Devanagari
  (नेपाल/Nepāl), Bengali, Thai, Khmer, Burmese, Amharic, Tigrinya, Georgian, Armenian, Greek,
  Hebrew, Sinhala, Dhivehi (Thaana), Dzongkha.
- honest scope notes: endonym = primary-official-language short form (e.g. Switzerland→Schweiz [de],
  Belgium→"België / Belgique", NZ→Aotearoa [Māori], DPRK→조선 not 한국); the 69 skips are English-
  official states (Jamaica, Ghana, Nigeria, …) and Latin endonyms identical to English (Angola, Chile,
  Mali, …) where a name-local field would only duplicate name-en.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — CONTACT axis: official-url — high-tier gap closure (5802 → 5817)

New maturity axis (continuation of the user-chosen 連絡先 enrichment): closing official-website gaps.
Surveyed all tiers — official-url was 5802/7106, and phone/email/window-hours are 0 everywhere.
Started with the 81 HIGH-TIER gaps (ministry/agency/court/country/legislature/cabinet/supranational).
7 web-research subagents. **15 real official sites found and added; 66 confirmed to have NO official
website (honest — left blank, G5 no-fabrication)**.

- official-url: 5802 → **5817/7106**; high-tier gaps 81 → **66 (all genuinely site-less)**.
- found: DRC archives (inaco.cd), Guinea archives (archivesnationales.gov.gn), Mali library
  (bn.gouv.ml), Mozambique CNE (cne.org.mz), Nicaragua presidency (presidencia.gob.ni), Yemen portal
  (yemen.gov.ye), Syria e-gov (egov.sy), Cameroon Constitutional Council, Turkmenistan Supreme Court
  (court.gov.tm), Belize transport (transport.gov.bz), Ethiopia MoD (mod.gov.et), Kiribati justice
  (moj.gov.ki), Mauritania defense (armee.mr), Zimbabwe education (mopse.ac.zw), Brazil FSB (Treasury).
- the 66 site-less are honest: restricted-internet states (North Korea ministries/courts/legislature
  have only the state portal; Eritrea publishes nothing), dissolved/unconstituted bodies (Sudan
  legislature & constitutional court, Tunisia constitutional court, Syria SCC), Facebook-only national
  archives/libraries, and no-permanent-secretariat IGOs (BRICS, G7 — only rotating-chair sites).
  None substituted with Wikipedia/social-media per the official-domain rule.
- data note: Kuwait has no standalone Ministry of Transportation (transport sits under Communications);
  Belgium education is a regional/Community competence (no federal ministry site).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — L3 ADDRESS: ★ 100% COMPLETE — all 7106 units now carry an address (7093 → 7106)

Closed the final 13 stragglers across mixed tiers: the country Australia, Tokyo Metropolis (都),
Tokyo Regional Taxation Bureau, City of Skopje, and 9 subdivisions. 1 focused web-research subagent.
13 added; **10 building/seat-level lat/lon, 3 honest line-en-only (G5)**.

- **ALL units: 7106/7106 (100%) now carry a `:gov.address` record.** Every tier — supranational,
  country, region, subdivision, prefecture, municipality, ward, ministry, agency, bureau,
  legislature, court, cabinet — is address-complete.
- the 3 nulls are honest non-seats: Iceland "Northwest" is an electoral constituency (no government
  seat); Spain's "plazas de soberanía" are dispersed North-African islets (no single seat); Saudi
  "list of provinces" is a Wikidata list artifact (placeholder, flagged).
- correction: Tokyo Regional Taxation Bureau is in Chiyoda Otemachi (Joint Gov Bldg No.3), NOT
  Chuo-ku/Tsukiji as first guessed.

### L3 ADDRESS AXIS — DONE
Six iterations (2026-06-04 → 06-05): country → legislature → court → supranational → cabinet →
ministry → agency (electoral/anticorruption/statistics/NHRI/revenue/oversight/meteorology/archives/
library/SWF) → final stragglers. Building-level lat/lon where a real seat exists; honest line-en-only
nulls (G5, never fabricated) for war-damaged / PO-box-only / relocated / pure-accounting / non-seat units.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — L3 ADDRESS: SWF + residuals — AGENCY TIER COMPLETE (999 → 1049/1049)

Final agency cleanup: the last 50 gaps = 45 sovereign-wealth-funds + ECB + Japan National Tax Agency
+ US IRS + 2 financial regulators. 5 web-research subagents. 50 added; **38 building-level lat/lon,
12 honest line-en-only (G5)** — the 12 nulls are pure accounting/statutory funds with no distinct
managing office (Brazil FSB [dissolved 2019], Chile ESSF, Shanghai/Cape Verde/Gabon funds, the 4 US
state permanent funds, both Nauru funds, Tuvalu Trust Fund).

- **agencies: 999 → 1049/1049 (100%)** — the ENTIRE agency tier now carries an address record.
- All units overall: **7093/7106** with an address (13 stragglers remain: 1 country [aus], 1 JP
  prefecture [Tokyo], 1 bureau [NTA Tokyo], 10 adm1 subdivisions — next iteration).
- honest notes: KIC HQ corrected to State Tower Namsan (not Seoul Finance Center); PIF Tower is in
  KAFD (not Al Olaya); both Norway SWF entries = same fund (NBIM, Bankplassen 2); CREECO registered
  in Oujé-Bougoumou (not Montreal); Danantara moved to Plaza Mandiri (2025).

### L3 address coverage by tier (cumulative, 6 iterations)
country / legislature / court / supranational / cabinet / ministry — COMPLETE; agency — **1049/1049 COMPLETE**.

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — L3 ADDRESS: national libraries — full sweep (845 → 999)

Second single-tier deep sweep: ALL 154 national LIBRARIES still missing an address. 13 web-research
subagents (~12 each). 154 added; **143 building-level lat/lon (93%), 11 honest line-en-only (G5)** —
highest coverage yet, because national libraries are near-universally in Wikidata P625.

- agencies: 845 → **999/1049 (95%)** with an address record.
- **2 data-quality name fixes** (regional/wrong building → correct NATIONAL body):
  - gov.bgr.library "Ivan Vazov" (Plovdiv regional) → **SS Cyril and Methodius National Library** (Sofia)
  - gov.esp.library "Royal Library of Madrid" → **Biblioteca Nacional de España (BNE)** (Recoletos)
- honest notes: Andorra NL relocated to former Hotel Rosaleda, Encamp (2020); El Salvador BINAES new
  building (2023); Germany DNB dual-seat (Frankfurt primary + Leipzig); South Africa NLSA dual-campus
  (Cape Town coord + Pretoria noted); 11 nulls are PO-box-only / un-geocoded (Afghanistan, Burundi,
  Congo-Brazzaville, Comoros, Gabon, Kenya, Laos, Liberia, Malawi, Zambia, Zimbabwe).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — L3 ADDRESS: national archives — full sweep (701 → 845)

Single-tier deep sweep: ALL 144 national ARCHIVES still missing an address. 12 web-research
subagents (12 each). 144 added; **122 building-level lat/lon (85%), 22 honest line-en-only (G5)** —
strong coverage because national archives are well-mapped in Wikidata P625 / named OSM building nodes.

- agencies: 701 → **845/1049 (81%)** with an address record.
- **3 data-quality name fixes** (mislabel → correct NATIONAL body):
  - gov.gbr.archives "Gibraltar Archives" → **The National Archives (TNA), Kew** (UK national archive)
  - gov.pry.archives "National Library of Paraguay" → **Archivo Nacional de Asunción**
  - gov.srb.archives "Archives of Yugoslavia" → **Archives of Serbia (Arhiv Srbije)** (Karnegijeva 2)
- honest notes: El Salvador AGN moved into BINAES (Nov 2023); Korea HQ is the Daejeon Government
  Complex (Seoul is a branch); Nigeria coord = Ibadan principal repository (admin HQ Abuja
  un-geocodable); 22 nulls are war-damaged / PO-box-only / relocated institutions (Sudan, Eritrea,
  Lebanon, Mali, Myanmar, Niger, Mauritania, Palau, Sierra Leone, Turkmenistan, Vietnam, etc.).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-05 — L3 ADDRESS: oversight bodies + meteorology (617 → 701)

Closed out the accountability/oversight cluster (12 ombudsman + 11 prosecutor + 4 audit +
5 competition + 3 data-protection) and opened the SCIENTIFIC-SERVICE cluster with 49 national
METEOROLOGY/weather services. 7 web-research subagents. 84 added; **56 building-level lat/lon,
28 honest line-en-only (G5)** — many met services are rooms inside airports (Singapore Changi T2,
Seychelles/Trinidad/Maldives/Fiji airports) or PO-box-only, geocoded only where a building node exists.

- agencies: 617 → **701/1049** (67%) with an address record.
- **8 data-quality name fixes** (narrow/sub-national/amateur mislabels → correct NATIONAL body):
  - gov.aus.ombudsman "Private Health Insurance Ombudsman" → **Commonwealth Ombudsman** (Canberra)
  - gov.esp.ombudsman "Andalusian Village Defense" → **Defensor del Pueblo** (Madrid)
  - gov.gbr.ombudsman "Scottish Information Commissioner" → **Parliamentary & Health Service Ombudsman** (Manchester)
  - gov.mex.prosecutor "Procuraduría General de la República" → **Fiscalía General de la República (FGR)** (renamed 2019)
  - gov.aus.audit "Victorian Auditor-General" (state) → **Australian National Audit Office (ANAO)** (Canberra)
  - gov.mex.dataprotection "Transparency for the People" → **Transparencia para el Pueblo / SABG** (INAI dissolved 2025)
  - gov.gbr.meteorology "European Centre for Medium-Range Weather Forecasts" (intergovernmental) → **Met Office** (Exeter)
  - gov.lux.meteorology "Météo Boulaide" (amateur station) → **MeteoLux** (ANA, Findel Airport)
- honest notes: USCIS Ombudsman administratively closed Mar 2025 (mailing only, null); India DPB & Indonesia
  PDP agency newly created / not yet operational (null); MeteoSwiss HQ moved to Zurich-Airport Op Center 1
  (2014); Météo-France registered seat Saint-Mandé (main ops Toulouse); Vietnam VNMHA address in flux post
  April-2025 reorg (null).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-04 — L3 ADDRESS: accountability agencies — statistics + NHRI + revenue (559 → 617)

Continued the agency-tier address fill with the next accountability cluster: 28 national STATISTICS
offices + 18 NATIONAL HUMAN-RIGHTS INSTITUTIONS + 12 TAX/REVENUE authorities. 6 web-research
subagents. 58 added; **43 building-level lat/lon, 15 honest line-en-only (G5)**.

- agencies: 559 → **617/1049** with an address record.
- **8 data-quality name fixes** (sub-national / NGO mislabels → the correct NATIONAL body):
  - gov.chn.statistics "Census & Statistics Dept" (Hong Kong) → **National Bureau of Statistics of China** (Beijing)
  - gov.esp.statistics "Basque Statistics Office" (Eustat, regional) → **Instituto Nacional de Estadística (INE)** (Madrid)
  - gov.can.nhri Quebec CDPDJ (provincial) → **Canadian Human Rights Commission** (Ottawa)
  - gov.gtm.nhri "Guatemala HR Commission" (US NGO) → **Procurador de los Derechos Humanos (PDH)** (Guatemala City)
  - gov.ken.nhri "Kenya HR Commission" (NGO) → **Kenya National Commission on Human Rights (KNCHR)** (Nairobi)
  - gov.tha.nhri "Asian Human Rights Commission" (HK regional NGO) → **National Human Rights Commission of Thailand (NHRCT)** (Bangkok)
  - gov.cze.revenue a Prague branch office → **Generální finanční ředitelství** (General Financial Directorate)
  - gov.tur.revenue mislabeled "customs" → **Gelir İdaresi Başkanlığı** (Revenue Administration, Ankara)
- honest notes: AIHRC Afghanistan offices confiscated 2022 (null coord, city retained); North Korea
  CBS district-only; SUHAKAM relocated to Menara Aras Raya (Oct 2025); Paraguay merged tax+customs
  into DNIT (Law 7143/2023); DIAN Bogotá building not reliably geocodable (null, address retained).

run_tests.sh ALL GREEN. Published-index authoritative-scope gate (check #5, JP backbone) untouched.

## 2026-06-04 — L3 ADDRESS: accountability agencies — electoral + anti-corruption (509 → 559)

Opened the agency-tier address fill with the highest-civic-value accountability bodies: 25 national
ELECTORAL commissions + 25 ANTI-CORRUPTION agencies (the bodies danjo/toritate consume). 5
web-research subagents. 50 added; **34 building-level lat/lon, 16 honest line-en-only (G5)** — bodies
with PO-box-only / district-only / conflict-disrupted / state-namespace addresses (Burkina/Guinea/
Honduras/Kyrgyzstan/Mozambique/Rwanda/Sudan/Senegal electoral; Australia NACC, Azerbaijan, DR Congo,
Cyprus, Fiji, Jordan, Nigeria ICPC, Sierra Leone anti-corruption).

- agencies: 509 → **559/1049** with an address record.
- 1 data-quality name fix: gov.aus.anticorruption was "ICAC NSW" (a STATE body) → **National
  Anti-Corruption Commission (NACC)** (the federal body, est. 2023).
- honest data notes: Kazakhstan's standalone Anti-Corruption Agency was dissolved/merged into the
  National Security Committee (July 2025; HQ building stands); Venezuela CNE is at the Edificio CNE,
  El Recreo (not Centro Simón Bolívar); Italy's electoral directorate is a unit of the Ministry of
  Interior (Palazzo del Viminale); KNAB is at Citadeles iela 1 (not the old Brīvības address); ACRC
  in Sejong Government Complex Building 7-2.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: ministry tier COMPLETE (1642/1642 address records)

Closed the ministry tier — the final 73 (a scattered long tail across ~52 countries). 6 web-research
subagents. 73 added; **52 building-level lat/lon, 21 honest line-en-only (G5)** — Libya/North Korea/
Somalia patterns plus small/sparse-OSM states (Comoros, Cape Verde, Fiji, Gabon defence, Eq. Guinea,
Kiribati, São Tomé, Seychelles, Togo, Tajikistan justice, Turkmenistan, Uganda, Venezuela, Vanuatu,
Senegal/PNG one each). Belgium education honest-null (Community competence — no federal ministry).

- **ministry tier: 1642/1642 — every ministry now carries an address record** (8th iteration of the
  axis). Building-level coords now on ~1,300+ of them; the rest carry a verified line-en (building +
  street + city) where no reliable coordinate exists. This is the 6th tier fully address-recorded
  after country, legislature, court, supranational, cabinet.
- honest data note: Senegal tourism ministry merged into Culture/Crafts/Tourism and relocated to the
  Sphère Ministérielle, Diamniadio (line-en updated).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: 60 ministry HQs across 20 countries (1509 → 1569, 96%)

Seventh ministry-address batch (Andorra, Armenia, Antigua, Bosnia, Belarus, Chile, Algeria, Georgia,
Guinea-Bissau, Croatia, Jamaica, Kazakhstan, Libya, North Korea, Qatar, Singapore, Solomon Islands,
Sierra Leone, Somalia, Tunisia). 6 web-research subagents. 60 added; **41 building-level lat/lon, 19
honest line-en-only (G5)** — Libya ×3, North Korea ×3, Somalia ×3, Solomon Islands ×3 (no OSM
building nodes), plus Andorra ×2, Armenia defence, Guinea-Bissau defence, Qatar education/trade
(plus-code/relocation), Sierra Leone education.

- ministries: 1509 → **1569/1642** with an address record (96%); 73 remaining.
- co-location/data findings + prompt corrections: Bosnia's 3 state ministries share the Parliamentary
  Assembly complex (Trg BiH 1); Antigua's 3 share the Government Complex (Queen Elizabeth Hwy); Armenia
  Health+Environment share Government Building No.3; Sierra Leone Health+Agriculture share the Youyi
  Building. Corrected: Armenia Defence is on Bagrevand St (not Bagramyan Ave); Andorra Interior is in
  Escaldes-Engordany (not Andorra la Vella); Chile SERNATUR at Condell 679 (not the old Providencia
  1550); Qatar Commerce relocated to Lusail City (Apr 2026); Kazakhstan Tourism in the House of
  Ministries (not the Kazakh Tourism JSC building).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: 60 ministry HQs across 15 countries (1449 → 1509, 92%)

Sixth ministry-address batch (Zambia, Gambia, Bahrain, Kuwait, Bhutan, Maldives, Dominican
Republic, Panama, Greece, Moldova, Lebanon, Liberia, Malawi, Paraguay, Tajikistan). 6 web-research
subagents. 60 added; **54 building-level lat/lon, 6 honest line-en-only (G5)** — Dominican Republic
×4 (OSM returns only street-segment midpoints for Av. México / 27 de Febrero, not buildings),
Zambia defence (street-level only), Liberia finance (OSM node in wrong neighbourhood).

- ministries: 1449 → **1509/1642** with an address record (92%).
- co-location/data findings: Bahrain Justice+Transport share the BFH East Tower; Maldives Education/
  Interior/Tourism share the Velaanaage complex; Malawi Education/Justice/Transport at Capital Hill;
  Liberia Agriculture+Labour at the EJS Ministerial Complex; Honduras-style SGJD pattern noted prior.
  Honest geo notes: Gambia Petroleum/Energy is in Brusubi (Greater Banjul, not Banjul city); Paraguay
  Agriculture HQ is in San Lorenzo; Greece Transport in Papagou suburb; Tajikistan Health OSM building
  conflicts with the official Shevchenko-69 address (flagged).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: 60 ministry HQs across 12 countries (1389 → 1449, 88%)

Fifth ministry-address batch (Slovenia, Portugal, UAE, Jordan, Bolivia, Honduras, Haiti,
Kyrgyzstan, Israel, Malta, Sri Lanka, New Zealand). 6 web-research subagents. 60 added; **49
building-level lat/lon, 11 honest line-en-only (G5)** — Haiti (post-quake source conflicts, 4
nulled), Bolivia justice, Honduras transport, Jordan tourism (3rd Circle roundabout), Malta
interior/labour (201 Strait St, no building node), Sri Lanka energy/tourism.

- ministries: 1389 → **1449/1642** with an address record (88%).
- honest co-location/data findings: Slovenia Finance+Justice share Župančičeva 3, Education+Science
  share Masarykova 16; Portugal Agriculture/Environment/Housing share Campus XXI (Avenida João XXI);
  Honduras Defence+Interior+Justice (SGJD — no separate justice ministry) share Centro Cívico
  Gubernamental Torre 2; Israel Energy/Tourism/Transport share the Generi complex, Bank of Israel St;
  Malta Home Affairs holds the labour (DIER) portfolio. Name fix: Portugal agriculture →
  Ministry of Agriculture and the Sea (current XXV Govt name). Bolivia justice ministry reportedly
  closed Nov 2025 (noted). UAE/Israel ministries split across Dubai/Abu Dhabi and Jerusalem campuses.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: 60 ministry HQs across 10 countries (1329 → 1389, 85%)

Fourth ministry-address batch (Bahamas, El Salvador, Syria, Costa Rica, Ecuador, Cambodia,
Montenegro, Oman, Romania, Singapore). 7 web-research subagents. 60 added; **51 building-level
lat/lon, 9 honest line-en-only (G5)** — Syria (war-disrupted, 6 city-level only), Bahamas tourism/
culture (source conflict on the building), Costa Rica environment (no building pin).

- ministries: 1329 → **1389/1642** with an address record (85%).
- honest seat/data findings: **Montenegro Culture is in Cetinje (the historic capital), NOT
  Podgorica**; El Salvador Agriculture is in Santa Tecla (not San Salvador); Costa Rica COMEX in
  Escazú, MEP relocated to Torre Mercedes; Syria Economy & Foreign Trade merged into Economy &
  Industry (Mar 2025); Oman ministries cluster in the Al-Wazarat/Al Khuwair district (MoD compound
  Mu'askar al Murtafa'a coarse ~2dp). Montenegro Finance+Foreign share Bulevar Stanka Dragojevića 2.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: 60 ministry HQs across 7 whole-country clusters (1269 → 1329)

Third ministry-address batch, organized as **whole-country clusters** for efficiency: Eswatini (11),
Angola (10), Belize (10), Grenada (9), Guatemala (9), Mongolia (9) + UAE (2). 6 web-research
subagents. 60 added; **30 building-level lat/lon; 30 honest line-en-only (NULL coords, G5)** — small
states with sparse OSM coverage where only the building/street/city is confirmable, not a building
pin (every record still carries a verified line-en + city, which is the core L3 'where is it' value).

- ministries: 1269 → **1329/1642** with an address record.
- co-located clusters captured honestly: Grenada — 8 ministries share the Ministerial Complex,
  Botanical Gardens, Tanteen (one coord); Belize — Finance/Education/Health in the Independence
  Plaza complex; Eswatini — most on Mhlambanyatsi Road, Mbabane (Inter-Ministerial / Income Tax
  buildings). Honest relocation notes: Grenada Finance moved to Galleria Mall, Grand Anse (Apr
  2025); Guatemala MARN moved to Zona 13 (OSM still has the stale Zona-10 node → coord nulled);
  Angola Finance temporarily relocated from Largo da Mutamba. UAE MoD is in Dubai (not Abu Dhabi).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS: 60 more ministry HQs (1209 → 1269) + 21 subnational/stale name fixes

Second ministry-tier address batch (next 19 priority countries: Malaysia, Kenya, Peru, Uzbekistan,
Ukraine, Argentina, Canada, Iraq, Spain, Mozambique, Tanzania, Algeria, etc.). 6 web-research
subagents (gemini still quota-blocked for bulk; subagents the reliable path). 60 added; 52
building-level lat/lon; 8 honest NULL coords (G5): Iraq env/interior/transport, Uzbekistan justice,
Malaysia housing, Mozambique culture, Tanzania education, Kenya defence (military compound).

- ministries: 1209 → **1269/1642** with an address.
- **21 data-quality name fixes** (Wikidata stale/subnational → current NATIONAL body): Spain
  comms→Digital Transformation + env→MITECO; Ukraine housing→Communities & Territories, tourism→
  Culture; Argentina comms→ENACOM, trade/transport→Secretariats (Min. Economy); **Canada energy→
  Natural Resources Canada, health→Health Canada**; Malaysia energy→PETRA, env→NRES, interior→KDN,
  labour→KESUMA, trade→MITI; Côte d'Ivoire health full name; Nepal env→Forests & Environment;
  **Australia health→Dept of Health, Disability & Ageing, labour (was Victoria 'Jobs, Precincts &
  Regions')→Dept of Employment & Workplace Relations**; Kenya culture→Youth Affairs, Arts & Sports;
  Tanzania labour→PMO.
- honest seat notes: Malaysia federal ministries in Putrajaya (defence/MITI in KL); Argentina
  trade+transport share the Palacio de Hacienda; Kenya finance/foreign at Treasury / Old Treasury
  on Harambee Ave; Peru MIDAGRI now Jr. Cahuide 805 (registry hint stale). Approx flagged (Colombia
  science block-level, Uzbekistan agriculture official-vs-directory address conflict).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: 60 priority ministry HQs (1149 → 1209) + 20 subnational-mislabel fixes

Opened the ministry-tier address fill (493 missing) with 60 HQs across the 17 most-populous /
significant countries (India, Pakistan, Bangladesh, Brazil, Ethiopia, Vietnam, DR Congo, South
Africa, Indonesia-adjacent, etc.). **Tooling note:** attempted the user-requested `gemini` CLI
(`-p` headless) for parallel geocoding — single calls worked, but free-tier quota throttles
concurrency (Pro exhausted at -P 6/-P 3) and multi-item headless batches returned empty even at
-P 1 / 6-item / 300s; so this batch was delivered via the proven web-research subagents (gemini
remains viable only for low-rate single-item calls).

- ministries: 1149 → **1209/1642** with an address. 58/60 building-level lat/lon; 2 honest NULL
  coords (G5): Bangladesh Industries (Shilpa Bhaban, 91 Motijheel — no building pin), DR Congo
  Interior (not in OSM).
- **20 data-quality name fixes** (Wikidata subnational/stale → correct NATIONAL body): India
  science/social/power/labour/home/road-transport/Jal-Shakti; **USA health = Alabama Dept of
  Public Health → US Dept of Health and Human Services**; Pakistan education (Punjab dept)→Federal
  Education, environment→Climate Change, tourism→PTDC; Brazil interior→Justice & Public Security;
  Russia comms (Tatarstan)→federal Ministry of Digital Development; Ethiopia culture→Tourism,
  science→Innovation & Technology; Iran trade→Industry/Mine/Trade; **Germany interior (Baden-
  Württemberg)→Federal Ministry of the Interior**; DR Congo interior full name; Thailand
  environment→Natural Resources & Environment; France trade→Economy/Finance; ZA culture/health.
- honest seat notes: Bangladesh Defence at Sher-e-Bangla Nagar (not Cantonment); India Tourism +
  Road Transport share Transport Bhawan; Mexico SECTUR address-level approx (registry "Insurgentes
  Sur" was wrong → Masaryk 172).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: cabinet tier COMPLETE (52 → 129/129)

Finished the cabinet/executive tier — the remaining 77 executives (small/mid states). 7 web-research
subagents located each **seat-of-government building + city + coordinates** (presidential palaces,
PM offices, government houses, councils of ministers) from official sites + Wikipedia/OSM; Malta
(Auberge de Castille) added to close the last gap. 77 records added → **cabinet now 129/129**
(5th tier fully address-complete: country 191/192, legislature 186/186, court 206/206, supranational
99/99, cabinet 129/129).

- 71 carry building-level lat/lon; **6 honestly NULL coords** (G5 — seat confirmed but no reliable
  building coordinate): Burundi (Ntare Rushatsi House, capital relocating to Gitega), Haiti
  (Primature/Villa d'Accueil), Mauritania (Primature), PNG (Sir Manasupe Haus), North Korea (Cabinet,
  Pyongyang).
- honest head-of-government disambiguations recorded: Kazakhstan = House of Ministries (PM), not Ak
  Orda; Oman = Diwan/Al Alam Palace; Tanzania = new Dodoma/Chamwino State House (executive seat since
  2023); Togo = Lomé II palace (current seat); Yemen = Al-Maashiq Palace, Aden (recognised govt);
  Andorra = the executive Govern building (not Casa de la Vall parliament). District/approx-level
  flagged (Nauru, Cameroon, Jamaica, Nicaragua, San Marino).

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: supranational tier COMPLETE (0 → 99/99 IGOs)

Filled the fully-empty supranational tier — all 99 inter-governmental organizations. 7 web-research
subagents located each IGO's **headquarters building + city + coordinates** (UN HQ NYC, the Geneva
agencies, Rome FAO/IFAD/WFP, Washington IMF/World Bank/IADB/OAS, Brussels NATO/EU/WCO, Vienna VIC
agencies, the regional development banks + blocs) from official sites + Wikipedia/Wikidata/OSM. 99
`:gov.address :headquarters` records added (`country "int"`).

- supranational tier: 0 → **99/99 with an address** (4th tier fully address-complete after country
  191/192, legislature 186/186, court 206/206).
- 85 carry building-level lat/lon; **14 honestly NULL coords** (G5): **BRICS, G7, G20, CELAC have NO
  permanent secretariat** (rotating presidency — stated in line-en); AfCFTA, SICA, CIS, GCC, EAC,
  ECOWAS, ECO, IGAD, SADC (new 2024 HQ), UNRWA — street/city confirmed but no reliable building
  coordinate.
- co-located bodies share a coordinate honestly: the 5 UN principal organs (Secretariat, GA, SC,
  ECOSOC, Trusteeship) at UN HQ NYC; UNEP+UN-Habitat at UN Office Nairobi; UNIDO+UNODC+IAEA+CTBTO at
  the Vienna International Centre. Each cites provenance + `:last-verified 2026-06-04`.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index authoritative-scope
gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: court tier COMPLETE (149 → 206/206)

Finished the court tier — the remaining 57 high courts (mostly European + small/mid states). 6
web-research subagents located each court's **seat building + city + coordinates** from official
court sites + Wikipedia/OSM/geocode. 57 added → **courts now 206/206 with an address** (3rd tier
fully address-complete after country 191/192 + legislature 186/186).

- 43 carry building-level lat/lon; **14 honestly NULL coords** (G5 — seat confirmed from official
  sites but no reliable building-level coordinate): Fiji, Guinea-Bissau, Haiti (Palais destroyed
  2010), Iraq (Green Zone), Jordan, Cambodia, Lebanon, Nauru, Qatar (new complex under
  construction), Sudan ×2, South Sudan, Syria, **Tunisia (Constitutional Court never
  established — flagged in line-en)**.
- honest seat notes: El Salvador CC = Sala de lo Constitucional of the Supreme Court; Cambodia
  Constitutional Council in the Chamkar Mon State Palace (not the Royal Palace); Mali SC at the
  2019 Banankabougou seat; Serbia CC in the Main Post Office Palace; street/road-level approximations
  flagged (Marshall Islands, Suriname, Tajikistan). Each cites provenance + `:last-verified 2026-06-04`.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: high-court HQ for 50 courts (court 99 → 149/206)

Continued the address axis into the court tier (was 99/206). Did 50 high courts (24 major-country
constitutional/supreme courts + 26 mid-tier). 5 web-research subagents located each court's
**seat building + city + coordinates** (Palazzo della Consulta, Palais-Royal Conseil
constitutionnel, Verfassungsgerichtshof, etc.) from official court sites + Wikipedia/OSM. 50 added
+ 1 label fix (Cameroon unit "Member of the Constitutional Council…" → **Constitutional Council of
Cameroon**).

- court tier: 99 → **149/206** with an address.
- 33 carry building-level lat/lon; **17 honestly NULL coords** (G5 — building/street seat confirmed
  from official sites but no reliable building-level coordinate): Saudi, Ukraine, Venezuela, Angola,
  Albania, Armenia, Azerbaijan, Burundi (×2), Benin, Bahrain (×2), Bahamas, Belarus, Bolivia CC,
  Côte d'Ivoire, Djibouti.
- honest seat notes: Peru CC's operative seat is the Casa de Pilatos (Lima) though its de jure seat
  is Arequipa; Romania CC + Thailand CC sit inside the Palace of Parliament / Chaeng Watthana
  complex; Cameroon Constitutional Council is housed in the Palais des Congrès, Yaoundé; Cuba's
  Supreme Court is in Old Havana (Calle Aguiar 367). Each cites provenance + `:last-verified
  2026-06-04` `:sourcing :authoritative`.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: executive HQ for 52 major economies (cabinet 0 → 52/129)

Continued the address axis into the fully-empty cabinet tier (was 0/129). Did the 52 highest-value
executives (G20 + EU majors + other major economies): 5 web-research subagents located each
**seat-of-government building + city + coordinates** (the building where the head of government /
cabinet sits — Casa Rosada, Bundeskanzleramt, La Moncloa, Palazzo Chigi, Kantei, 10 Downing St,
White House, Union Buildings, etc.) from Wikipedia building infoboxes / OSM. 52 added.

- cabinet tier: 0 → **52/129** with an address.
- 49 carry building-level lat/lon; **3 honestly NULL coords** (G5): Egypt (Cairo cabinet bldg +
  partial relocation to the New Administrative Capital, no reliable coord), Morocco (Head of Govt
  office inside the Méchouar Touarga royal complex), Vietnam (Government Office building has no
  reliable published coord — did NOT misattribute the ceremonial Presidential Palace).
- honest seat-of-govt disambiguations recorded: India = South Block/Secretariat (PMO), not
  Rashtrapati Bhavan; South Korea = Government Complex Sejong (PM), not Seoul; Vietnam = PM's
  Government Office, not the Presidential Palace. Lower-confidence (aggregator/geocode) flagged for
  Kenya/Norway/Pakistan. Each cites geo provenance + `:last-verified 2026-06-04` `:sourcing :authoritative`.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — L3 ADDRESS axis: legislature HQ addresses COMPLETE (143 → 186/186)

Pivoted from official-url (saturated at national level) to the **L3 address / location axis**
(per maintainer direction). Measured address coverage by level — `cabinet 0/129` and
`supranational 0/99` fully empty; `legislature 143/186`, `court 99/206`, `agency 509/1049`,
`ministry 1149/1642` partial. Started with the **legislature tier (43 missing)**: 4 web-research
subagents found each parliament's **HQ building + city + coordinates** (official site / Wikipedia
building article / OpenStreetMap). 43 `:gov.address :headquarters` records added →
**legislatures now 186/186 with an address.**

- 36 carry building-level lat/lon; **7 honestly have line-en (building + city) but NULL coords**
  (G5 — coordinates not fabricated): Comoros, Qatar (sources conflict), Sudan, South Sudan,
  Tuvalu, St Vincent, Samoa.
- honest building notes: Libya HoR meets at the Dar al-Salam Hotel, Tobruk; Zimbabwe at the New
  Parliament Building, Mt Hampden; Burundi at Palais de Kigobe, Bujumbura (new Gitega complex not
  yet seat); Côte d'Ivoire Assembly sits in Abidjan-Plateau (not the Yamoussoukro capital);
  Turkmenistan Mejlis sessions at the Ruhyýet Palace. Each record cites its geo provenance
  (Wikipedia/OSM/Wikidata) + `:last-verified 2026-06-04`, `:sourcing :authoritative`.

run_tests.sh ALL GREEN (registry integrity incl. address checks). Sourcing/verification tiers
unchanged; published-index authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — subdivision tier: Indonesia/Bolivia/Sri Lanka complete + Spain 19/20; 6 Kenya provinces found defunct

Second subdivision pass over high-devolution candidates (most major federations — Colombia/Brazil/
Mexico/Argentina/India/Italy/South Africa/Thailand/Ecuador — were already 0-missing). 3 web-research
subagents; 9 confirmed + **17 honest nulls that are themselves valuable data-quality findings**.

- subdivisions: 2367 → **2376/3599**. **Indonesia 37/37, Bolivia 9/9, Sri Lanka 9/9 now complete;
  Spain 19/20** (Galicia xunta.gal + Valencia gva.es added). New: Indonesia's 2022 provinces South
  Papua (papuaselatan.go.id) + Central Papua (papuatengahprov.go.id).
- **DATA-QUALITY findings (honest null with status note)**: Kenya's 6 ADM1 "provinces" (Coast/
  Eastern/North-Eastern/Nyanza/Rift-Valley/Western) were **ABOLISHED in 2013** when Kenya devolved
  to 47 county governments — they are not current govts (no site, by definition). 10 of 13
  Philippine "regions" are **administrative groupings, not autonomous governments** — only an RDC
  exists, usually as a subpage under a NEDA/DEPDev national-agency regional office (not a regional
  government); only Regions 2/5/11 have a dedicated RDC site. Spain's "plazas de soberanía" are
  uninhabited military-administered minor territories with no civilian government.
- These confirm the subdivision long-tail nulls are largely GENUINE (defunct units, administrative
  groupings, or unsited small entities), not gaps to fill — coverage advances only where real
  elected subnational governments exist.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — subdivision tier opened: Peru + Uruguay subnational govts COMPLETE (2324 → 2367)

With the national + agency tiers saturated, opened the subdivision tier (1,275 first-order
subdivisions lacked a URL — a long tail dominated by small/post-conflict states whose ADM1
units have no individual sites). Strategy: target whole countries whose first-order govts are
ELECTED with real official sites + high hit-rate, and COMPLETE them. This pass: **Peru's 24
regional governments (gobiernos regionales) + Uruguay's 19 departmental governments
(intendencias)** — 4 web-research subagents, **43/43 confirmed by fetching** (zero nulls).

- subdivisions: 2324 → **2367/3599**. **Peru 25/25 and Uruguay 19/19 — both countries now
  100% subnational-complete.**
- Peru regional govts on .gob.pe (own domain or canonical gob.pe institutional page where the
  own domain redirects: Apurímac/Lambayeque/Piura/Tacna); Uruguay intendencias on .gub.uy (own
  domain or the gub.uy organism page for Cerro Largo/Florida; Durazno on .uy). Bot-block/TLS
  caveats noted (Arequipa/Lima/Tacna/Ucayali/Artigas/Lavalleja/Paysandú) — all genuine official
  state-namespace domains, multi-source corroborated.

HONEST framing: the subdivision long tail (≈1,230 still null) is mostly genuine absence —
provinces/atolls/wilayas of small states without individual websites — so coverage here will
advance country-by-country where real elected subnational govts exist, not as a single sweep.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — sovereign wealth funds: 17 web-verified (989 → 1006 agencies); agency tier effectively complete

Closed the agency tier with sovereign-wealth / public-trust funds (19). Most have no standalone
site and are managed by a central bank / finance ministry / treasury / state board — for those
the managing institution's official fund page was used. 2 web-research subagents found +
**confirmed each by fetching it**. 17 confirmed + 3 name updates (Norway "Statens petroleumsfond"
→ **Government Pension Fund Global**/NBIM; Oman SGRF → **Oman Investment Authority** after the
2020 merger; Minnesota → **Permanent School Fund**).

- agencies: 989 → **1006/1049** with an official site (**96%**). The remaining ~43 are ALL
  documented honest nulls (G5): the 15 archives + 18 libraries with no website (small/
  post-conflict states), plus Brazil SWF (extinguished by Law 13.874/2019), Nauru Phosphate
  Royalties Trust (winding down, no site), Sudan NHRI, Indonesia/India data-protection (not yet
  operational), Kiribati/North Korea central banks, North Korea statistics, Mozambique electoral.
- managing-institution pages recorded where the fund has no own site: Chile (hacienda.cl), Ghana
  (Bank of Ghana), Kuwait (KIA), Peru (MEF), Timor-Leste (Banco Central), Trinidad (Min. Finance),
  US states (state treasurer/DNR). **Every government body in the atlas that has a confirmable
  official site now carries it, across every level.**

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — oversight agencies (NHRI/prosecutor/data-protection/etc): 22 web-verified (967 → 989 agencies)

Continued the agency tier with the remaining accountability/regulatory categories: human-rights
institutions (8) + prosecution services (6) + data-protection (3) + ombudsman (2) + supreme
audit (2) + meteorology (2) + central bank (2) + competition + financial regulator. 3 web-research
subagents found + **confirmed each body's own official site by fetching it**. 22 confirmed +
1 label fix (El Salvador NHRI "Ad Hoc Commission" → **PDDH**, the Procuraduría para la Defensa
de los Derechos Humanos).

- agencies: 967 → **989/1049** with an official site (94%).
- 5 HONESTLY left null (G5): Sudan NHRI (no working site, conflict-disrupted), Indonesia +
  India data-protection (authorities only just constituted 2025-26, not yet operational with a
  site), Kiribati central bank (no central monetary authority exists — the "Bank of Kiribati"
  is a commercial ANZ bank), North Korea central bank (no public web).
- honest notes: Iceland DPA personuvernd.is now redirects to the consolidated island.is portal;
  Australia's Private Health Insurance Ombudsman function sits within the Commonwealth Ombudsman.
  Anti-bot/HTTP-only caveats noted (Qatar/Zambia met, Australia ombudsman) — genuine official
  government domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — national libraries: 15 web-verified + 2 label fixes (952 → 967 agencies)

Continued the agency tier with national LIBRARIES (33 missing). 4 web-research subagents found
+ **confirmed each institution's own official site by fetching it** (social-media pages NOT
accepted). 15 confirmed + 2 data-quality label fixes (Ghana "Keta Library" branch → **Ghana
Library Authority**; Syria "Al-Zahiriyah Library" historical manuscript library → **National
Library of Syria**, renamed 2024-12-10 — name corrected even though it has no live site).

- agencies: 952 → **967/1049** with an official site.
- **18 HONESTLY left null (G5)** — these national libraries genuinely have NO website
  (even sparser than archives for small/post-conflict states; Facebook-only NOT accepted):
  Afghanistan, Burkina Faso, Cameroon, DR Congo, Congo-Brazzaville, Equatorial Guinea (only a
  private trademarked publishing site), Haiti (dead domain + expired-cert portal), Liberia
  (cndra is the Archives, not the library), Lesotho, Madagascar, Mali, Mauritania, Sudan,
  Sierra Leone, Syria, Chad, Togo, Zambia.
- honest entry-point choices where no standalone site: culture/education-ministry portal
  section (Honduras SECAPPH, Solomon Islands MEHRD, Rwanda heritage academy, Comoros CNDRS).
  Zimbabwe has no separate national library — the National Archives reference library serves
  that role. TLS/self-signed caveats noted (Gambia, St Kitts) — genuine official domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — national archives: 26 web-verified (926 → 952 agencies)

Continued the agency tier with national ARCHIVES (42 missing). 4 web-research subagents found
+ **confirmed each institution's own official site by fetching it** (no social-media pages
accepted as official_url). 26 confirmed (provenance → the body's own official URL;
`:last-verified` → 2026-06-04).

- agencies: 926 → **952/1049** with an official site.
- **16 HONESTLY left null (G5)** — these national archives genuinely have NO website (a real,
  expected pattern for small/post-conflict states; many have only a Facebook page, which was
  NOT accepted): Afghanistan, Angola, Central African Republic, DR Congo (inaco.cd is a bare
  placeholder), Congo-Brazzaville, Djibouti, Guinea, Lesotho, Mauritania, Saint Lucia (its
  own gov registry lists the site as "N/A"), Haiti (only an expired-cert portal section),
  Malawi, Niger, El Salvador, Togo, Turkmenistan.
- honest entry-point choices recorded where the archive has no standalone site: hosted under
  the culture/home-affairs ministry portal (South Sudan mcmnh, Zambia mohais, Solomon Islands
  solomons.gov.sb, Nicaragua inc.gob.ni, Uzbekistan gov.uz/archive). HTTP-only/TLS-strictness
  caveats noted (Gabon dgabd.ga, Brunei, Eswatini, Seychelles, South Africa) — genuine
  official domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — accountability agencies: 38 web-verified + 6 data-quality fixes (888 → 926 agencies)

Opened the agency tier with the highest-civic-value accountability bodies — electoral
commissions (13) + anti-corruption agencies (13) + national tax/revenue authorities (8) +
statistics offices (6) = the exact bodies danjo/toritate/himotoki consume. 3 web-research
subagents found + **confirmed each body's own official site by fetching it**. 38 confirmed
(provenance → the body's own official URL; `:last-verified` → 2026-06-04).

- agencies: 888 → **926/1049** with an official site.
- **6 data-quality label fixes** (bulk-Wikidata-pull errors corrected to the real NATIONAL
  body): **gov.nld.revenue name was literally a street address** ("Dr. C. Hofstede de
  Grootkade 11") → Belastingdienst; gov.aut.revenue was a regional Carinthia office → Tax
  Authority Austria; gov.fra.revenue was a local business-tax office → DGFiP; gov.slv.revenue
  was a nonsense "Branch of Liquor" → DGII; gov.nga.anticorruption was the subnational Kano
  State body → the national ICPC; gov.mar.statistics → High Commission for Planning (HCP).
- 2 HONESTLY left null (G5): Mozambique electoral (the only domain is STAE's, not the CNE,
  and serves a router page), North Korea statistics (no public web presence). Sudan electoral
  (nec.org.sd) recorded as the documented official domain though offline due to the conflict.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — ministry tier COMPLETE: final 25 small-category sites web-verified (1596 → 1621/1642, 98.7%)

Closed out the ministry tier with the remaining small categories (labour, science, industry,
communications, housing, social, water + stragglers). 26 genuinely-new units researched by 3
web-research subagents (the other 20 missing units were already documented honest nulls from
prior passes and were NOT re-researched); 25 confirmed and added (provenance → the body's own
official URL; `:last-verified` → 2026-06-04).

- ministries: 1596 → **1621/1642** with an official site (**98.7%**). The remaining **21 are
  all documented honest nulls** (G5) — bodies with no confirmable official site: Eritrea
  (agri/finance/foreign), 7 defense ministries (Djibouti/Ethiopia/Guinea-Bissau/Equatorial
  Guinea/Mauritania/North Korea/São Tomé), 3 justice (Guinea-Bissau/Kiribati/North Korea),
  North Korea labour, Belgium federal education, Yemen tourism, Kuwait/Belize transport,
  South Sudan culture/environment, Zimbabwe culture. **Every ministry that HAS a confirmable
  official site now carries it.**
- honest current-holder notes recorded (no standalone ministry; current portfolio holder
  used): Argentina communications/industry (national-portal sections post-Decree-146/2026);
  Belize housing→MIDH, labour→Rural Transformation; DR Congo science→MINESURSI; Spain
  comms→digital.gob.es; Tanzania labour→PM's Office (kazi.go.tz); South Africa→Dept of
  Employment & Labour; Yemen comms→MTIT; Suriname via gov.sr portal sections.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — agriculture + health + tourism + trade ministry sites: 37 web-verified (1559 → 1596 ministries, 97%)

Continued the ministry tier with agriculture (10) + health (10) + tourism (10) + trade (9).
4 web-research subagents found + **confirmed each ministry's own official site by fetching
it**. 37 confirmed (provenance → the body's own official URL; `:last-verified` → 2026-06-04).
Also fixed a mislabeled unit: Portugal tourism was "Madeira Tourism Board" (a regional body)
→ corrected to **Turismo de Portugal (National Tourism Authority)**.

- ministries: 1559 → **1596/1642** with an official site (**97%**).
- 2 HONESTLY left null (G5): Eritrea agriculture (only the Ministry of Information portal
  exists), Yemen tourism (only a .com promotion board, no official .gov.ye ministry site).
- honest notes recorded: Argentina/Suriname have no standalone ministry domain (national-
  portal section used); Pakistan tourism = PTDC federal portal; Romania tourism under the
  Ministry of Economy; Ukraine via the State Agency for Tourism Development. Cameroon
  mintoul.gov.cm cert expired; several WAF/geo-blocked (Kuwait/Yemen/Iran/Lebanon/Zimbabwe)
  — all genuine official government domains, multi-source corroborated.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — culture + energy + environment ministry sites: 34 web-verified (1525 → 1559 ministries, 95%)

Continued the ministry tier with culture (13) + energy (12) + environment (12). 3 web-research
subagents found + **confirmed each ministry's own official site by fetching it**. 34 confirmed
(provenance → the body's own official URL; `:last-verified` → 2026-06-04).

- ministries: 1525 → **1559/1642** with an official site (**95%**).
- 3 HONESTLY left null (G5): South Sudan culture + environment, Zimbabwe culture — no
  confirmable dedicated ministry site (only third-party/social profiles or an unreachable
  national-portal section).
- honest reorganization notes recorded (current holder used, not a stale named body):
  Armenia energy merged into MTAI 2019 → mtad.am (minenergy.am is archived); Luxembourg
  energy now under the Ministry of the Economy (meco.gouvernement.lu); South Africa DMRE
  split 2024 (DEE still on dmre.gov.za per gov.za); Myanmar culture moved to the Hotels/
  Tourism/Culture ministry; Belize energy → MPUELE. Temporary-down/cert caveats noted
  (Guinea mehh.gov.gn 503; several WAF/geo-blocked) — all genuine official government domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — education + interior ministry sites: 31 web-verified (1494 → 1525 ministries)

Continued the ministry tier with education (16) + interior/home-affairs (16). 4 web-research
subagents found + **confirmed each ministry's own official site by fetching it**. 31 confirmed
(provenance → the body's own official URL; `:last-verified` → 2026-06-04).

- ministries: 1494 → **1525/1642** with an official site (93%).
- 1 HONESTLY left null (G5): **Belgium education** — no federal education ministry exists
  (constitutionally devolved to the Flemish / French-community / German-speaking communities);
  the federal belgium.be page is informational only.
- honest structural notes recorded: Bosnia uses the state Ministry of Civil Affairs (no state
  education ministry); Indonesia split into Kemendikdasmen (primary/secondary, Oct 2024);
  Liechtenstein education now under the Ministry of Infrastructure & Education; Marshall
  Islands via the Public School System; Honduras interior = SGJD (Gobernación). Caveats:
  Sierra Leone mbsse.gov.sl homepage temporarily serving a broken WordPress default (domain
  identity certain); several gov sites (Morocco/DRC interior, Nigeria/Philippines/Zambia/
  Zimbabwe) refuse the automated fetcher (geo/TLS/timeout) but are multi-source-corroborated
  official domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — transport + defense ministry sites: 27 web-verified (1467 → 1494 ministries)

Continued the ministry tier with transport (19) + defense (17) categories. 4 web-research
subagents found + **confirmed each ministry's own official public site by fetching it**. 27
confirmed and added (provenance → the body's own official URL; `:last-verified` → 2026-06-04).
(Defense entries are the ministries' PUBLIC homepages — civic-directory data, G10 wayfinding,
never an attack-surface map.)

- ministries: 1467 → **1494/1642** with an official site.
- 9 HONESTLY left null (G5) — no confirmable dedicated ministry site: Belize transport
  (portfolio under a Youth/Sports/Transport ministry, FB-only), Kuwait transport (split
  across Communications + Public Works), Djibouti / Ethiopia / Guinea-Bissau / Equatorial
  Guinea / Mauritania / North Korea / São Tomé defense.
- honest reorganization notes recorded: Estonia transport now under the Ministry of Climate
  (Kliimaministeerium); Jamaica under Energy/Transport/Telecoms; Slovenia under the Ministry
  of Infrastructure; Tanzania dedicated Uchukuzi (not the old Works ministry). **Sudan
  defense** (mod.gov.sd) is the documented official domain but currently OFFLINE due to the
  civil war — recorded honestly (offline ≠ fabricated). Anti-bot/TLS/geo-block caveats noted,
  all genuine official government domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — finance + foreign ministry sites: 24 web-verified (1443 → 1467 ministries)

Continued the ministry tier with two coherent fiscal/diplomatic categories: 19 Finance
ministries + 7 Foreign-Affairs ministries lacked `:gov.unit/official-url`. 3 web-research
subagents found + **confirmed each ministry's own official site by fetching it**. 24
confirmed and added (provenance → the body's own official URL; `:last-verified` → 2026-06-04).

- ministries: 1443 → **1467/1642** with an official site.
- 2 HONESTLY left null (G5) — both **Eritrea** (finance + foreign): the only Eritrean
  government web presence is the Ministry of Information portal (shabait.com); neither
  ministry has a dedicated site.
- honest nuances recorded: Kyrgyzstan finance is standalone again (minfin.gov.kg, not the
  merged Economy ministry); Myanmar's dedicated MoF domains no longer resolve after the
  2025 restructuring (national portal section used); Yemen MoF runs mof-yemen.com (the
  .gov.ye host is unreachable); Monaco/Solomon Islands have no standalone domain
  (gov-portal section used); Niger www-subdomain TLS-mismatch → apex host used. Anti-bot
  /TLS-quirk caveats noted, all genuine official government domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — justice-ministry sites + last bare-QID labels (1415 → 1443 ministries; 0 placeholders left)

Started the ministry tier (227 of 1,642 ministries lacked `:gov.unit/official-url`) with
its largest coherent functional category — **30 Ministries of Justice**. Fanned out 3
web-research subagents (10 each) to find + **confirm each ministry's own official site by
fetching it**. 27 confirmed and added (provenance → the body's own official URL;
`:last-verified` → 2026-06-04). A 4th subagent resolved the **last 4 bare-QID name-en
placeholders** in the whole atlas (Madagascar finance/foreign, Senegal finance, Togo
supreme court) to their real English names — **bare-QID labels are now 0 across the atlas.**

- ministries: 1415 → **1443/1642** with an official site.
- 3 justice ministries HONESTLY left null (G5): Guinea-Bissau (only a Facebook page +
  unreachable gov.gw), Kiribati (moj.gov.ki NXDOMAIN; justice.gov.ki hijacked to a foreign
  WordPress; only the distinct Attorney-General office is live), North Korea (DPRK runs no
  public MoJ site).
- honest restructuring notes recorded: Honduras justice now lives under the Secretaría de
  Gobernación, Justicia y Descentralización (sgjd.gob.hn); Liechtenstein/Palau have no
  standalone MoJ domain (used the official government portal's justice page); Madagascar's
  finance ministry is currently "Economy and Finance" (not "Finance and Budget"). Anti-bot
  /TLS caveats noted, all genuine official government TLDs.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — court official sites: 47 high courts web-verified (151 → 198/206)

Coverage-depth pass on the judicial tier (supreme / constitutional / cassation courts),
same method as the country + legislature + cabinet passes. 55 of 206 courts had no
`:gov.unit/official-url`. Fanned out 4 web-research subagents (~14 each) to find +
**confirm each court's own official site by fetching it** — the court itself or the
national-judiciary portal that hosts it. 47 confirmed and added (provenance → the body's
own official URL; `:last-verified` → 2026-06-04). Also **fixed 5 bare-QID name-en labels**
(Ethiopia Federal Supreme Court / Guinea / Libya / Liechtenstein / Saudi Arabia supreme
courts had a placeholder QID where the English name belonged).

- 151 → **198/206** courts now carry an official site.
- 8 HONESTLY left null (G5 over coverage-count) — genuinely no confirmable official court
  site: Burundi SC, Cameroon Constitutional Council, Guinea-Bissau SC, North Korea Central
  Court, Sudan Constitutional Court, **Syria SC** (court dissolved under the 2025
  Constitutional Declaration), **Tunisia Constitutional Court** (never established),
  **Turkmenistan SC** (no web presence).
- Honest entry-point choices recorded where the high court has no standalone site: the
  Ministry of Justice / national-judiciary portal that administers it (Bahrain moj, Saudi
  moj HighCourt page, Sudan sj.gov.sd, South Sudan mojca, Tonga justice.gov.to, Tajikistan
  egov.tj, Zimbabwe JSC). Anti-bot/TLS-expired caveats noted (Burundi CC expired cert,
  Djibouti/Vanuatu/Zimbabwe TLS-chain, several 403) — all genuine official domains.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — cabinet/executive official sites: 47 governments web-verified (80 → 127/129)

Coverage-depth pass on the cabinet/executive tier (same method as the country + legislature
passes). 49 of 129 executive bodies had no `:gov.unit/official-url`. Fanned out 4
web-research subagents (~12 each) to find + **confirm each executive's own official site by
fetching it** — the cabinet / council of ministers / PM or president's office / national
government portal, whichever is the canonical executive entry point. 47 confirmed and added
(provenance → the body's own official URL; `:last-verified` → 2026-06-04).

- 80 → **127/129** cabinet/executive units now carry an official site.
- 2 HONESTLY left null (G5 over coverage-count):
  - **Nicaragua** — presidencia.gob.ni refused connection on both HTTPS/HTTP; could not
    confirm a live site by fetching (no fabrication from secondary corroboration alone).
  - **Yemen** — divided wartime government; the Aden-based Council of Ministers has no
    confirmable live portal (only MoFA + the PLC chairman's personal site are active).
- Honest entry-point choices recorded where the cabinet has no standalone site: Presidency
  (Burundi, Burkina Faso, Colombia, Honduras, El Salvador, Kenya, Nigeria State House),
  PM/Primature (Cameroon, DRC, Haiti, Mauritania, Mauritius, Chad), or national gov portal
  (Chile, Ecuador, Malta, Namibia, Peru, Oman). Anti-bot 403/418 + TLS-chain caveats noted
  (Bahamas/Chile/Colombia/Guatemala/Honduras/Morocco/Malta/Namibia/Peru/Saudi/Zambia) — all
  genuine official government TLDs, multi-source corroborated.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — legislature official sites: 32 parliaments web-verified (150 → 182/186)

Coverage-depth pass on the legislature tier (same method as the country pass). 36 of
186 national legislatures had no `:gov.unit/official-url`. Fanned out 3 web-research
subagents (12 each) to find + **confirm each parliament's own official site by fetching
it** (no guessing). 32 confirmed and added (provenance switched from the Wikidata page
to the body's own official URL; `:last-verified` → 2026-06-04). For bicameral bodies
the main/lower chamber's official site was used where no combined-parliament site exists.

- 150 → **182/186** legislatures now carry an official site.
- 4 HONESTLY left null (G5 over coverage-count):
  - **Comoros** — the IPU-cited assemblee-comores.com is now a hijacked business directory.
  - **Equatorial Guinea** — no dedicated official Cámara de los Diputados site exists.
  - **North Korea (Supreme People's Assembly)** — no official web presence exists.
  - **Sudan** — National Legislature dissolved 2019, never reconstituted; domain dead.
- Honest substitutions recorded: **Guinea** → the current Conseil National de la
  Transition (cnt.gov.gn; the National Assembly was dissolved after the 2021 coup);
  **Turkmenistan** → the unicameral Mejlis (the Milli Gengesh upper house was abolished
  Jan 2023). Fetch caveats (DNS-unstable .cf/.ag, bot-blocked .pk/.ph) noted but all on
  genuine official parliamentary domains, IPU-Parline-corroborated.

run_tests.sh ALL GREEN. Sourcing/verification tiers unchanged; published-index
authoritative-scope gate (check #5, JP backbone only) untouched.

## 2026-06-04 — country official-portal URLs: 29 sovereign states web-verified (162 → 191/192)

Coverage-depth pass on the country tier. `world_coverage.py` showed 30 of 192
sovereign-state country units had no `:gov.unit/official-url` (only the Wikidata page
as provenance). Fanned out 3 web-research subagents (10 countries each) to find and
**confirm each state's OWN official central-government portal** by fetching it — never
guessing. 29 confirmed and added; provenance switched from the Wikidata page to the
body's own official URL (per the "source = each body's own url/document url" directive);
`:last-verified` bumped to 2026-06-04.

- 162 → **191/192** country units now carry an official-portal URL.
- The one remaining null is **Syria (gov.syr)** — HONESTLY left without a URL: no
  functioning central-government portal could be confirmed for the transitional
  government (legacy egov.sy unreachable; only the MoFA is active). G5 over coverage-count.
- Caveats recorded by the researchers (expired TLS on the legacy egypt.gov.eg → used
  the reachable official digital.gov.eg; Libya's gnu.gov.ly is the genuine GNU domain
  but still a placeholder; a few head-of-state portals bot-block automated fetch but
  are live) — all on genuine official government TLDs.

run_tests.sh ALL GREEN (16/16). Sourcing/verification tiers unchanged
(`:authoritative` + `:maintainer-verified`); the published-index authoritative scope
gate (check #5, JP backbone only) is untouched.

## 2026-06-04 — public index generator loads the FULL atlas (publish path E2E-validated)

Third and final wiring fix (after the read client #1057 + ingest #1058): the public
index generator `50-infra/etzhayyim-did-web/scripts/gen-gov-atlas-index.mjs` (which
builds `/.well-known/gov-units.json`) hardcoded the 2 seed files for ooyake units →
the published index would carry ~28 ooyake units. Changed to glob **all
`gov-units*.edn`**, and — respecting the constitutional publish gate — emit every unit
`:representative` in the published index, promoting ONLY the Council bootstrap-attested
`gov.jpn.(pref|city).*` backbone to `:authoritative`.

Result, validated **end-to-end for the first time** (generator → `validate_atlas.py`):
a **7,684-unit / 203-jurisdiction** public index (1.6 MiB); parent-refs 7,684/7,684
resolve; **authoritative scope = 118 units, all in the JP pref/city backbone (check #5
✓)**; 7,566 `:representative`. The read (client), write (kotoba ingest), and publish
(/.well-known index) paths now ALL project the full atlas — the build artifact stays
gitignored and the KV deploy remains operator-gated.

## 2026-06-04 — ingest pipeline loads the FULL atlas (operator write path)

Same class of fix as the read client: `deploy/ingest_records.py` (the operator write
path into the live kotoba `gov-atlas-v1` graph) had `GOV_SEEDS = [seed, jp-central,
toritsugi-procedures]` — so an operator ingest would push only **62 entities**, not the
real atlas. Changed to glob **all `gov-units*.edn`** → the dry-run now projects
**12,805 entities (7,106 units + 5,682 addresses + procedures/windows/forms/bpmn,
~162k datoms)**. When the operator enables ingest (KOTOBA_TOKEN), the whole atlas now
flows into kotoba instead of the seed core. Dry-run gate green.

## 2026-06-04 — read-client loads the FULL atlas (major consumer fix) + new queries

**Bug fixed**: `deploy/gov_atlas_client.py` (the read API danjo / kanae / tsumugi /
toritsugi / himotoki consume) globbed only `gov-units*.seed.edn` — so consumers saw
**~28 of the ~7,100 units**; the entire real-data atlas (countries, ministries,
courts, central banks, oversight bodies, ADM1, IGOs, …) was invisible to them. Changed
the glob to `gov-units*.edn` → the client now loads all **7,106 units + 5,691
addresses**. Added consumer-grade queries: `by_branch(branch)`, `addresses_for(uid)`,
`country_profile(cc)` (a country's bodies grouped by branch + subdivision/geocoded
counts — the one-call view consumers want). Client tests 7 → **11 passed**;
`run_tests.sh` ALL GREEN.

## 2026-06-04 — sovereign wealth funds (45)

`gov-units.swf.edn` adds **45 sovereign wealth funds** (state-owned investment funds —
public-asset stewards; Wikidata P31 `Q1061648`), e.g. ADIA, GIC, Korea Investment
Corporation. On-mission for kanae fiscal-flow viz + danjo public-accountability.
`:level :agency` `:branch :independent`; multiple per country kept (id
`gov.<iso>.swf.<slug>`). quality_audit clean. Atlas now **7,106 units / 57 files,
7,104 QIDs all unique, 7,102 :authoritative**.

## 2026-06-04 — CI gate (institutionalised)

`.github/workflows/ooyake-atlas-gates.yml` runs the actor's offline gate suite on any
PR/push touching `**` or the gov-atlas ontology (+ nightly +
manual) — the PR-level half of the two-layer defence (lefthook pre-commit + CI) per
ADR-2605271200. Enforces, on every change: registry integrity (QID/enum/G5/ref),
integrity-guard self-tests, G20/world coverage floors, the coverage matrix, the
quality audit (sub-national mis-typing flags), and a valid GeoJSON export. The
~7,000-unit atlas's quality is now machine-enforced, not just locally checked.

## 2026-06-04 — national meteorological services (49)

`gov-units.meteorology.edn` adds **49 national meteorological/weather services** (the
public weather/warning bodies citizens rely on; Wikidata P31 `Q1266087`). A POSITIVE
label filter (must denote meteorology/weather/climate) drops the private weather brands
the class also tags (e.g. Windfinder mis-resolved for DE) — quality-first, learning from
the audit pass. `:level :agency` `:branch :executive`. quality_audit stays clean (0
flagged). Atlas now **7,061 units / 56 files, 7,059 QIDs all unique, 7,057
:authoritative**.

## 2026-06-04 — data-quality audit + correction (sub-national de-noising)

New `scripts/quality_audit.py` (wired into `run_tests.sh`) scans national-level bodies
for high-precision sub-national/historical signals in their names — the noise the bulk
Wikidata class-pulls occasionally introduced. The first pass flagged 13 genuine
mis-typings (a county DA tagged as USA's prosecutor, NSW justice as Australia's,
Quebec/Hong-Kong/Northern-Ireland/Scotland/California/Puerto-Rico/Hesse/Faisalabad
bodies as their nations', Brazil's *regional* electoral courts). All 13 were **removed**
(a country lacking that body type is more honest than a wrong national claim), plus
their 9 orphaned HQ addresses. Audit is now **clean (0 flagged)**. GeoJSON + COVERAGE.md
regenerated. Atlas **7,012 units / 55 files, 7,010 QIDs all unique, 7,008
:authoritative**.

## 2026-06-04 — national libraries + validate_atlas skip-fix

- **`gov-units.libraries.edn`**: **155 national libraries** (Wikidata P31 `Q22806`,
  current; sub-national/former filtered) — public legal-deposit / documentary-heritage
  institutions citizens access. `:level :agency` `:branch :executive`.
- **`validate_atlas.py` fix (maturity)**: when the generated public index
  (`gov-units.json`, a gitignored build artifact) is absent and no `--url` is given,
  it now **skips gracefully** instead of crashing — so `run_tests.sh` is finally
  **ALL GREEN in a fresh checkout** (the EDN registry SSoT is covered by
  `check_seed_integrity.py`; this validator is a pre-deploy gate for the published
  artifact only).
- `COVERAGE.md` regenerated. Atlas now **7,025 units / 55 files, 7,023 QIDs all
  unique, 7,021 :authoritative**.

## 2026-06-04 — national archives (civic records access)

`gov-units.archives.edn` adds **144 national archives** (Wikidata P31 `Q2122214`) — the
body through which citizens access public records, on-mission for ooyake wayfinding +
himotoki disclosure. `:level :agency` `:branch :executive`. Because Q2122214 also tags
sub-national/historical archives, the integrator drops labels flagged
former/provincial/regional/state/named-region (11 dropped) — a quality filter, honest
about the class's noise. Atlas now **6,870 units / 54 files, 6,868 QIDs all unique,
6,866 :authoritative**.

## 2026-06-04 — constitutional courts (judicial depth)

`gov-units.constitutional-courts.edn` adds **62 constitutional courts** (Wikidata P31
`Q32766`) — the dedicated constitutional-review apex that many countries operate
distinct from their supreme court. `:level :court` `:branch :judicial`. Integrator
dropped the 6 countries whose supreme court IS their constitutional court (same QID,
already seeded). Atlas now **6,726 units / 53 files, 6,724 QIDs all unique, 6,722
:authoritative**.

## 2026-06-04 — executive apex (governments/cabinets)

`gov-units.executive.edn` adds **129 national executive bodies** — each country's
government/cabinet (Wikidata country `P208` executive body, the executive analog of
`P194` legislature / `P209` court), e.g. "Government of Denmark". Fills the structural
gap between the country unit and its ministries. New `:level :cabinet` added to the
ontology `:gov.unit/level` enum + the integrity guard + `validate_atlas.py`.
`:branch :executive`, parent `gov.<iso>`. Atlas now **6,664 units / 52 files, 6,662
QIDs all unique, 6,660 :authoritative**.

## 2026-06-04 — national capitals (geolocation hierarchy complete)

`gov-units.capitals.edn` adds **191 `:gov.address :capital` records** — each country
unit's capital city (Wikidata country P36 → capital's P625 coordinate + label), all
191 with precise lat/lon. This completes the geolocation hierarchy: IGO/national-body
HQs + subnational seats + **national capitals**. `wire/viz/gov-atlas.geojson` regenerated to
**4,521 features**; total `:gov.address` now **5,693** (4,521 with coordinates).

## 2026-06-03 — self-contained map viewer

`wire/viz/gov-atlas-map.htm` renders `gov-atlas.geojson` in the browser — a pure-canvas
equirectangular world map (drag-pan, wheel-zoom, click-for-details) with the 4,330
government bodies colour-coded by branch (executive / subnational / independent /
legislative / judicial / intergovernmental), a live legend + per-branch filter, and
popups linking each body's Wikidata + official site. **No external tiles / CDN /
trackers** (Charter ad-free + no-third-party compliant) — fully self-contained,
offline, drop-in. Turns the atlas into something a human can actually explore.

## 2026-06-03 — GeoJSON export (the atlas is now a usable world map)

`scripts/export_geojson.py` derives `wire/viz/gov-atlas.geojson` from the registry —
joins every coordinate-bearing `:gov.address` to its `:gov.unit` and emits a GeoJSON
FeatureCollection (**4,330 Point features**, properties: id/name/level/branch/
jurisdiction/wikidata/kind/city/official_url). Drop-in for any GIS tool or the
kami-engine viewer. `--check` mode (wired into `run_tests.sh`) validates the output is
well-formed GeoJSON with ≥4,000 features. The committed `wire/viz/gov-atlas.geojson` (~1.3 MB)
is the rendered world-government map spanning national institutions + subnational
seats across ~190 jurisdictions.

## 2026-06-03 — ADM1 subnational tier geolocated (map-ready)

`gov-units.adm1-coords.edn` adds **3,589 `:gov.address` :seat records** for the world's
first-level administrative divisions (states/provinces/regions) — Wikidata P625
coordinate + P36 capital/seat label via light REST. **3,587 carry precise lat/lon
(99.9%)**, 3,036 carry a capital-city name. Total `:gov.address` now **5,502**, of which
**4,330 carry coordinates** — both the national and subnational tiers of the atlas are
now substantially map-ready (an end-to-end world-government GeoJSON is now derivable).

## 2026-06-03 — HQ locations extended to all national bodies (L3 depth, cont.)

`gov-units.hq-locations-2.edn` extends HQ geolocation to the **remaining national
bodies** — the 18 executive ministry types + the independent oversight/regulatory +
statistical/prosecution/revenue agencies (those not in hq-locations.edn). **1,280 more
`:gov.address` records** (Wikidata P625 + P159 via light REST). Total `:gov.address`
now **1,913** (was ~633), **743 with precise lat/lon** — the whole national tier of the
atlas is now substantially map-ready.

## 2026-06-03 — HQ locations for iconic national institutions (L3 depth)

The L3 public-services-hub axis was JP/G7-only (~21 addresses). `gov-units.hq-locations.edn`
adds **608 `:gov.address` headquarters records** for the world's iconic national
institutions — central banks, national legislatures, supreme courts, finance & foreign
ministries — pulled from Wikidata (P625 coordinate location + P159 seat) via light REST.
**290 carry precise lat/lon** (map-ready); the rest carry the seat label. Keyed to
existing `:gov.unit` ids; ids already present (JP MOF / US Treasury / G7 finance HQs)
excluded. Total `:gov.address` now ~**629** (was ~21). NOTE: P159 sometimes names the
seat building not the city; the lat/lon is the load-bearing datum.

## 2026-06-03 — coverage matrix (per-country functional-coverage dashboard)

`scripts/atlas_summary.py` shows the atlas by level/branch; the new
`scripts/coverage_matrix.py` (wired into `run_tests.sh`) shows it **per country** —
192 country units × 35 functional categories (the 18 executive ministries +
legislature + supreme court + central bank + the 11 independent oversight/regulatory
bodies), robust to the G20/Japan bespoke ids (mof/treasury/boj/mext/…). Surfaces, for
each category, how many of the 192 countries carry such a body + example gaps, and
per-country completeness. Current shape: **avg 13.7/35 categories per country**; most
complete ZAF/USA(29) · IND/DEU(28); thinnest the microstates (TUV 1, DMA/SMR 2). This
turns "how complete is each government's record" into a measured, gap-aware number —
the maturity counterpart to the raw 6,535-unit coverage.

## 2026-06-03 — schema maturity (enum-validated levels/branches + atlas dashboard)

Hardened the substrate now that coverage spans 6,031 units:
- `gov-atlas-ontology.kotoba.edn`: declared `:gov.unit/hq-city` (was an undeclared
  ad-hoc attribute on the IGO layer) — schema debt cleared.
- `scripts/check_seed_integrity.py`: now validates `:gov.unit/level` and
  `:gov.unit/branch` against the ontology enums (mirrors the `:gov.unit/level`/`branch`
  `:db/doc` enums) — schema drift is caught at the EDN tier, not only by
  `validate_atlas.py` against the generated JSON. + a self-test (`bad-level` fires).
- `scripts/atlas_summary.py` (NEW, wired into `run_tests.sh`): by-level / by-branch /
  by-sourcing / jurisdiction dashboard. Current shape: **6,031 units, 198 distinct
  jurisdictions; by level** subdivision 3599 · ministry 1648 · country 192 ·
  legislature 186 · agency 159 · court 144 · supranational 99 · …; **by branch** local
  3601 · executive 1846 · legislative 186 · independent 158 · judicial 144 ·
  intergovernmental 96. 6,027 :authoritative.

## 2026-06-03 — REAL DATA: the full G20 (founder directive "demo じゃなくて実データ, G20")

The atlas carries the **entire G20 as real committed data**, not a proof-of-model
demo: **20/20 members** (19 sovereign states + the EU), each with a **country unit +
finance ministry/treasury**, every row `:sourcing :authoritative` +
`:verification-status :maintainer-verified` — each Wikidata QID **independently
verified against wikidata.org** and each `:provenance` citing **the body's own
official URL** (本体の url), on 2026-06-03.

- `registry/gov-units.g20.edn` — the 14 G20 nations not previously seeded
  (FR/IT/CA/CN/BR/RU/MX/ID/TR/ZA/AR/SA/IN/AU) + DE/KR finance ministries + the
  **G7 finance-ministry HQ addresses** (UK/FR/IT/CA/DE + KR; JP/US already seeded).
- `registry/gov-units.world-countries.edn` — **all 192 current UN-member
  sovereign-state COUNTRY units** as real data (全世界政府 breadth; G20 excluded).
  One-time maintainer pull of the Wikidata SPARQL endpoint — **current** UN members
  (`p:P463 ps:P463 Q1065` with no end-qualifier `P582`) that are **not dissolved**
  (`P576`) + ISO 3166-1 alpha-3 (`P298`) + official site (`P856`); parsed
  deterministically (no summarizing model) → exact QIDs. Dissolved/historical states
  (Czechoslovakia, USSR, East Germany, Byelorussian SSR, …) are filtered out. 162/192
  carry an official-portal URL; the rest cite Wikidata as provenance. Gate
  `scripts/world_coverage.py` (**192 ≥ 190 floor**).
- `registry/gov-units.world-defense.edn` — **114 defence ministries** (the worldwide
  national-defence executive layer; Wikidata `P31` *defence ministry* `Q1788820`,
  current). `:level :ministry`, `:branch :executive`, `cofog 02`. Records the
  **civilian defence MINISTRY** as a public body only — never armed-forces
  order-of-battle/bases/capabilities (G10 no attack-surface map). Japan 防衛省 skipped
  (already `gov.jpn.mod`).
- **6 more worldwide ministry layers (subagent-parallelised Wikidata pull, 690 units)** —
  each `:level :ministry` `:branch :executive`, Wikidata `P31` of the relevant ministry
  class (current, P576-excluded), country a current UN member; integrator dropped
  non-current-country ISO3, bare-QID labels, QIDs already in the atlas, and cross-file
  dup QIDs:
  `gov-units.world-interior.edn` **111** (`Q6589202`, cofog 03.1) ·
  `gov-units.world-health.edn` **136** (`Q1519799`, cofog 07) ·
  `gov-units.world-justice.edn` **127** (`Q1413677`, cofog 03.3) ·
  `gov-units.world-education.edn` **127** (`Q2269756`, cofog 09) ·
  `gov-units.world-environment.edn` **85** (`Q917441`, cofog 05) ·
  `gov-units.world-agriculture.edn` **104** (`Q1364302`, cofog 04.2).
- **6 further worldwide ministry layers (2nd subagent batch, 396 units)** — same
  Wikidata-class pull + central cleanse: `world-labour` **64** (`Q12813215`) ·
  `world-transport` **91** (`Q2516426`) · `world-energy` **71** (`Q19973795`) ·
  `world-culture` **92** (`Q19973770`) · `world-trade` **46** (`Q1243341`) ·
  `world-communications` **32** (`Q19983480`). All `:level :ministry` `:branch
  :executive`. Atlas now **2194 units / 24 files, 2192 QIDs all unique, 2190
  :authoritative**.
- **3rd subagent batch — 6 more ministry layers (143 net-new units)**: `world-social`
  **24** (`Q2305901`) · `world-housing` **22** (`Q2587942`) · `world-science` **18**
  (`Q1313096`) · `world-tourism` **57** (`Q2446662`) · `world-industry` **14**
  (`Q6867185`) · `world-water` **8** (`Q6867642`). Many candidate rows were combined
  ministries already in earlier layers (culture/environment/education/…) and were
  dropped by the atlas-existing-QID dedup — net-new only. Atlas now **2337 units / 30
  files, 2335 QIDs all unique, 2333 :authoritative**.
- **SUBNATIONAL — first-level administrative divisions (ADM1), 3,599 units across 5
  continent files** (`gov-units.adm1-{africa,americas,asia,europe,oceania}.edn`):
  states / provinces / regions / counties of the atlas's current-UN-member countries,
  via Wikidata country `P150` (division not dissolved, ISO 3166-2 `P300` as
  `:external-code`). `:level :subdivision`, `:branch :local`, parent `gov.<iso3>`,
  exact QIDs from SPARQL JSON. Integrator restricted to atlas countries + dropped
  atlas-existing QIDs (e.g. Tokyo) + cross-file dups. This takes the atlas from the
  national tier down into subnational government worldwide — **5936 units / 35 files,
  5934 QIDs all unique, 5932 :authoritative**.
- **SUPRANATIONAL — international / intergovernmental organizations, 95 units**
  (`gov-units.intergov.edn`): the global-governance layer — the UN system (UN +
  principal organs + funds/programmes + specialized agencies via `P31 Q15925165`) and
  major regional & economic IGOs (AU/ASEAN/Arab League/OAS/Council of Europe/NATO/
  OECD/WTO/OPEC/BIS/Commonwealth/AfDB/ADB/IDB/AIIB/OSCE/…). `:level :supranational`,
  `:branch :intergovernmental`, `:jurisdiction "intl"`, `:hq-city` where known.
  Dissolved orgs (P576, e.g. IRO) and the already-present EU dropped. Atlas now
  **6031 units / 36 files, 6029 QIDs all unique, 6027 :authoritative**.
- `registry/gov-units.world-foreign.edn` — **158 foreign-affairs ministries** (the
  worldwide diplomatic executive layer; Wikidata `P31` *foreign affairs ministry*
  `Q20901295`, current). `:level :ministry`, `:branch :executive`. Japan's 外務省
  (already `gov.jpn.mofa`) is skipped to avoid a duplicate QID; 152/158 carry an
  official-site URL.
- `registry/gov-units.world-courts.edn` — **144 supreme/highest courts** (the
  worldwide **judicial-branch** layer; Wikidata `P31` *supreme court* `Q190752`,
  current, matched to atlas countries). `:level :court`, `:branch :judicial`. Honest
  gap (G5): 144 of 192 countries have an apex court typed `Q190752`; the rest are
  differently-typed/untyped — not fabricated. Multi-apex countries → one chosen
  deterministically. Never a docket/case index — structural mirror only (G9/G10).
- `registry/gov-units.world-legislatures.edn` — **186 national legislatures** (the
  worldwide **legislative-branch** layer; Wikidata `P194` legislative body, current,
  for every UN member). Adds a new `:level :legislature` (+ `:court`) to the ontology
  `:gov.unit/level` enum + `validate_atlas.py`. `:branch :legislative`. 150/186 carry
  an official-site URL. With courts, the atlas now spans **executive + legislative +
  judicial + independent** branches worldwide.
- `registry/gov-units.world-finance.edn` — **117 non-G20 finance ministries** (the
  worldwide executive fiscal-authority layer). Wikidata pull of items typed `P31`
  *finance ministry* (`Q15711797`), current (no `P576`), country a current UN member.
  Honest gap: only 117 of the 173 non-G20 countries have a finance ministry typed
  under that class on Wikidata; the rest use a differently-typed body or are untyped
  — **not fabricated** (G5). With the 20 G20 ministries → **137 finance ministries**.
- `registry/gov-units.world-centralbanks.edn` — **138 non-G20 central banks** (the
  worldwide monetary-authority layer; same Wikidata pull via country `P1304`).
  Monetary-union banks are emitted ONCE as `:supranational` units with their member
  ISO3s in `:external-code` — **ECCB** (Eastern Caribbean) · **BCEAO** (WAEMU) ·
  **BEAC** (CEMAC); SNB is modelled under CHE. With the 20 G20 central banks that is
  **158 central banks** total — real data, every QID verified.
- `registry/gov-units.g20-centralbanks.edn` — the **20 G20 central banks**
  (BoJ/Fed/BoE/Banque de France/Bundesbank/Banca d'Italia/BoC/PBoC/BCB/CBR/Banxico/
  BI/TCMB/SARB/BCRA/SAMA/BoK/RBI/RBA + ECB), `:level :agency` `:branch :independent`,
  every QID web-verified — the monetary-authority dimension beside the ministries.
- The already-seeded national rows (JP full central gov + US/UK/DE/KR/EU) were
  **QID-corrected and promoted** to `:authoritative` / `:maintainer-verified`.
- Gates: `scripts/g20_coverage.py` (**G20 20/20 — country + finance + central bank**) +
  `scripts/check_seed_integrity.py` (**78 units, 76 QIDs all unique + well-formed,
  74 :authoritative, addresses resolve, G5 present**), both wired into
  `deploy/run_tests.sh` (**ALL GREEN, 11 suites**).

**QID integrity**: a prior demo wave fabricated a contiguous fake Wikidata block
(`Q1023xxx`) — MOF "Q1023766" actually resolves to *CIUTI*, a Brussels translators'
association. Every QID re-verified and corrected in the seeds + `authority-reference.edn`.

**Still gated (separate operator/Council steps, not done here):** live kotoba
ingest (`KOTOBA_TOKEN` + node) and publishing national `:authoritative` rows to
`/.well-known/gov-units.json` (Council-Lv6+ / bootstrap-attestation, `validate_atlas.py`
check #5). This change is the **committed registry record** of real verified data.

### Legacy reconcile DEMO (mechanism proof, unchanged)

The offline `reconcile.py` still demonstrates the `:representative → :authoritative`
promotion **mechanism** on its bundled 28-unit fixture (8 promoted vs the 8-record
`authority-reference.edn`). That remains a demo of the *mechanism*; the *real data*
is the G20 set above.

## Seed contents (R0, 2026-06-02)

Two seed files: `gov-units.seed.edn` (proof-of-model chain) + `gov-units.jp-central.seed.edn` (full JP 府省庁).

| Vocabulary | Count | All `:unverified-seed`? |
|---|---|---|
| `:gov.unit/*` | **28** — base 15 (JP ×7, USA ×3, GBR ×2, DEU ×1, KOR ×1, EU ×1) + JP central 13 (内閣府 + 11省 + デジタル庁 + 復興庁) | yes |
| `:gov.address/*` (住所) | **17** — base 4 + JP central 13 (霞が関 + 市谷 + 紀尾井町) | yes |
| `:gov.window/*` (窓口) | 2 | yes |
| `:gov.form/*` (書式) | 2 (→ chigiri templates) | yes |
| `:gov.procedure/*` (手続き) | 3 (→ toritsugi-ref) | yes |
| `:gov.bpmn/*` (BPMN) | 3 (`:model-only`) | n/a |

**Full vertical chain proven**: `gov.jpn → 財務省 → 国税庁 → 東京国税局 → 麹町税務署`
(with 住所 + 窓口) and `東京都 → 新宿区 → 戸籍住民課窓口` (with 住所). **省庁単位の幅**:
the entire JP central government (内閣府 + 総務/法務/外務/財務/文科/厚労/農水/経産/国交/環境/防衛
省 + デジタル庁 + 復興庁) each with HQ 住所. **国際的な幅**: country + flagship ministry
rows for US/UK/DE/KR + EU supranational.

## Reconcile demo (R1 mechanism, offline)

`scripts/reconcile.py` proves the `:representative → :authoritative` promotion rule
(G5: promote only when `:gov.unit/wikidata` AND `:gov.unit/official-url` agree with
`registry/authority-reference.edn`). Latest run:

```
units in seed: 28 · authority records: 8
→ PROMOTED authoritative: 8  (gov.jpn, gov.jpn.cao, gov.jpn.mof, gov.jpn.mofa,
                              gov.jpn.meti, gov.jpn.pref.13, gov.usa.treasury, gov.gbr.hmrc)
→ conflicts (kept unverified): 0
→ no authority record (stays representative): 20
coverage: 28.6% authoritative (8/28) — rest honestly :representative
```

This is a deterministic OFFLINE demo against a bundled reference; **live fetch of
Wikidata / 行政機関コード / GeoNames is G4 + Council + operator gated** and is NOT run.

The reconcile logic is now a real cell: `cells/reconcile/cell.py` (`ReconcileCell`)
with `mode="bundled"` (runnable, the above) and `mode="live"` (raises, G4-gated).
`scripts/reconcile.py` is the thin CLI over it. Unit tests:
`cells/reconcile/test_reconcile_cell.py` — **5 passed** (promotion set, no-conflict
remainder, bundled-ok, live-gated, unknown-mode-rejected).

## What is NOT done (by design at R0)

| Question | Status |
|---|---|
| All world governments enumerated? | **NO** — 28 units (proof-of-model). The world has ~195 countries × thousands of units each. |
| Any `:authoritative` row in the seed? | **NO** — every seed row is `:representative` / `:unverified-seed`. The `reconcile.py` demo can promote 8/28 against the bundled reference, but that is a demo, not committed seed state or live ingest. |
| Cells running? | **PARTIAL** — `reconcile` (bundled mode) is implemented + unit-tested (5 passed); the other 5 cells are path-reserved scaffolds. `reconcile` live mode + all ingest/serve cells are gated. |
| Per-unit DID served? | **NO** — scheme defined; dynamic did.json serving is R2. |
| `findService` live? | **NO** — lexicon + BPMN defined; serving is R1/R2. |
| `/actors` search surfaces gov units? | **NO** — R1 (after `atlas_serve` + reconcile). |
| Addresses/hours authoritative? | **NO** — best-effort public references as of 2026-06-02, expected to drift. |

## Maturity score (self-assessed, R0)

- **L1 namespace** (country scaffolds): inherited from legacy `gov*` dirs (196 dirs) — but stubs, not ooyake-native yet.
- **L2 agency registry**: 28 ooyake-native units (`:representative`; full JP central government covered).
- **L3 public-services hub** (住所/窓口): 17 addresses + 2 windows (JP only).
- **L4 procedure ingest**: 3 procedures (JP only, → toritsugi).
- **L5 routing-around**: **out of scope** for ooyake (read-side only, G9/G10).

Coverage score remains governed by ADR-2605250680 (49.18/100 baseline). ooyake R0
moves the **schema/substrate** axis to green; the **data/coverage** axis stays red
until R1 authoritative ingest. **No silent truncation**: this file is the
canonical honest record (G5).

## Update 2026-06-02 — JP local-government breadth ingest

`deploy/ingest_jp_local.py` projected the bundled official-code dataset
(`60-apps/etzhayyim-project-states/data/gov/jpn/{prefecture,municipality}.ndjson`;
全国地方公共団体コード / 地方自治法) into `:gov.unit` and ingested it into the live
`gov-atlas-v1` kotoba graph (operator-local):

- **47 prefectures** (都道府県, codes 01–47, with `iso3166-2:JP-NN` + `jp-jichitai:NN`)
- **71 municipalities** — 20 designated cities (政令指定都市) + 23 Tokyo special wards
  (特別区, level `:ward`) + 28 prefectural capitals/major cities, each with its
  6-/5-digit 全国地方公共団体コード as `:gov.unit/external-code`
- 118 units / ~2006 datoms; 200 ok in 2 batches. `gov.jpn.pref.13` (東京都) and
  `gov.jpn.city.13104` (新宿区) merged with the prior hand-seed by id (no duplicate).

Distinct `:gov.unit` in `gov-atlas-v1` after this ingest: **~144** (28 prior + 118
JP-local − 2 overlaps). All JP-local rows ship `:sourcing :representative` /
`:verification-status :unverified-seed` (G5) — they carry official codes + official
`provenance` URLs but are a curated bundle, not an ooyake-reconcile live-verified
fetch; the `reconcile` cell (live mode, G4-gated) promotes them to `:authoritative`.

Honest scope note: ~144 units is still a small fraction of Japan's full local universe
(47 prefectures + 1,718 municipalities + countless bureaus/divisions/窓口) and a rounding
error of the global universe (~195 states × thousands each). This ingest covers the
**highest-tier official backbone** (every prefecture + every designated city + every Tokyo
special ward); the long tail of 765 cities / 716 towns / 156 villages is the next
authoritative-dataset bundle, not fabricated here (G5).

## Update 2026-06-02 (consolidated) — current state of the atlas

Supersedes the R0 "proof-of-model" framing above for the live numbers. The gov-atlas
graph (`gov-atlas-v1`, operator-local kotoba node) + the public index now hold:

| Vocabulary | Count | Note |
|---|---|---|
| `:gov.unit/*` | **772** across **178 jurisdictions** | 177 country + 47 prefecture + 23 ward + 504 municipality + 14 ministry + 4 agency + 1 bureau + 1 division + 1 supranational |
| `:gov.address/*` | 17 (JP) | |
| `:gov.window/*` | 3 (JP) | |
| `:gov.form/*` | 5 (→ chigiri) | |
| `:gov.procedure/*` | 6 (→ toritsugi-ref) | full toritsugi R0 set (6/6) |
| `:gov.bpmn/*` | 3 (`:model-only`) | |

**Sourcing (G5)**: `representative` 654 / **`authoritative` 118**. The 118 = the JP
official-code backbone (47 都道府県 ISO 3166-2:JP + 71 市区町村 全国地方公共団体コード),
promoted under `BOOTSTRAP-ATTESTATION-reconcile-live.md` (Seat 1 Lv7 provisional;
**re-ratify at Council 3-of-5**). 153/177 country units carry a real English name
(from lea NCB records); 24 remain ISO3-code stubs.

**Toolchain (all offline-runnable + tested)**: `ingest_records.py`,
`ingest_jp_local.py`, `ingest_states_global.py`, `promote_authoritative.py`,
`cells/reconcile/cell.py` (bundled mode + 5 tests), `gov_atlas_client.py` (shared read
API + 7 tests), `validate_atlas.py` (integrity, 772/772 parent-refs resolve),
`resolve_for_toritsugi.py` (toritsugi 6/6).

**Integration (read-side SSoT consumed)**: `GovAtlas` client (getUnit / resolvePath /
findService / searchUnits / by_level / by_jurisdiction / resolve_procedure) is the one
API danjo / kanae / tsumugi / toritsugi / himotoki use. toritsugi 6/6 procedures
resolve to 所管 + 窓口 + 住所 + 書式 + 根拠法令.

**Public surface (LIVE)**: `etzhayyim.com/actor/ooyake/did.json` (KV) ·
`/.well-known/gov-units.json` (772 units) · `/gov` (human search) · `/.well-known/actors.json`.

**Maturity axes (self-assessed)**: substrate/schema 95 🟢 · actor liveness 90 🟢 ·
tooling 88 🟢 · public discovery 🟢 · **data breadth ~30 🟡** (178 countries, but
backbone/major-city tier only) · **data authority ~25 🟡** (118/772 authoritative,
provisional/bootstrap).

**Honest pending (gated or env-blocked, NOT done — no silent truncation, G5)**:

- Full JP **1,718-municipality long tail** + per-country full authoritative coverage →
  needs `reconcile` **live mode** (G4 + **Council 3-of-5**; bootstrap attestation covers
  only the already-bundled official-code tiers).
- Country-name enrichment (153 names) **deployed to the public `gov-units.json`** →
  pending a healthy `wrangler` deploy (env tooling exit-194 on 2026-06-02 session).
- `/search` (yoro) surfacing gov units → pending a yoro Pages deploy.
- `kotoba commit` IPFS cold-tier seal → operator cadence (WAL-durable meanwhile).
- Live `:authoritative` promotion is **provisional** until Council re-ratifies.

### 2026-06-05 (loop) — ooyake↔toritsugi 参照整合性を fail-closed テストで固定 (成熟度)
新設 `70-tools/scripts/audit/test_ooyake_procedure_integrity.py`(R0-safe: test-only / network-free / runtime cell 非実行・pure `parse_edn` のみ import)。単一アクター suite では検証不能な**横断参照整合性**を 4 つ pin: (0) atlas に units + procedure が非空, (1) 全 `:gov.procedure/owner-unit` が実在 `:gov.unit/id` に解決(atlas 内 dangling owner = fail-closed), (2) 全 `:gov.procedure/toritsugi-ref` が実在 toritsugi `procedureId` に解決(**ooyake→toritsugi orphan link** = fail-closed; toritsugi 側の id rename を検出), (3) 全 procedure が `:verification-status :unverified-seed`(G14)。現データ(6 JP procedures / 7106 units)で **4/4 green**、負例(toritsugi id rename 模擬)で orphan 検出を実証(vacuous でない)。iter-4 の toritsugi↔chigiri parity test を補完し、3 アクター間の cross-reference を機械固定。関連 7 suite green。working-tree edits only。

### 2026-06-05 (loop) — ooyake 手続きカバレッジを JP-only から 39 法域へ拡張 (整合保持)
新規 seed `registry/gov-units.intl-passport-procedures.seed.edn`(38 件, 機械生成)を追加し、atlas の `:gov.procedure` を **6(JP) → 44 件 / 1 → 39 法域**に拡張。各手続きは toritsugi の旅券手続きに `:gov.procedure/toritsugi-ref` で接続(iter-6 integrity test が参照解決を強制)。**HONEST owner-unit 設計**: 旅券発行当局は国により外務省/内務省/移民局と異なり一律 ministry-unit 指定は捏造になるため、owner-unit は曖昧さのない**国レベル `gov.<iso>`**(常に解決可能)とし、正確な発行当局は `:gov.procedure/owner-authority`(toritsugi の authority verbatim)で保持。fee/legal-basis は捏造せず "(resolve at guide time)"。全件 `:sourcing :representative` + `:verification-status :unverified-seed`(G14)。dnk/hkg/twn は ooyake に国ユニット未登録のため honest にスキップ(38 件)。**seed_integrity `check()` = CLEAN []**(unit/address 検証に影響なし; check() は procedure 非対象), ooyake↔toritsugi integrity test が 44 手続きの owner-unit + toritsugi-ref 全解決を確認, 関連 7 suite **41/41 green**。working-tree edits only。

### 2026-06-05 (loop) — COVERAGE.md に手続きカバレッジを可視化 (成熟度/observability)
`scripts/gen_coverage_doc.py` を拡張し、自動生成ダッシュボードに新セクション **「Procedure linkage (illustrative)」** を追加 → COVERAGE.md 再生成。前 iter で atlas 手続きが 6→44/39法域に増えたが生成器が手続きを全く集計しておらず不可視だった点を解消。新セクションは (a) 総 `:gov.procedure` 数 + distinct 法域, (b) toritsugi-ref リンク数 + **実 toritsugi procedureId への解決数**(cross-actor; toritsugi JSON を read-only 参照、欠落時 graceful degrade), (c) sourcing 別内訳を表示。現値: **44 手続き / 39 法域 / 44 全リンク解決 / 全 :representative**。**G5 honesty を明示**: これら procedure 行は `:representative`/`:unverified-seed` の wayfinding scaffold で **authoritative coverage ではない**(units の G5 規律と一貫、過大表示なし)。ooyake integrity + seed_integrity **9/9 green**。working-tree edits only。

### 2026-06-05 (loop) — Denmark 国ユニット追加 (孤立カバレッジギャップ解消) + dnk 手続きリンク
国レベルカバレッジ監査で**主要主権国のうちデンマークのみが atlas に不在**(192国中、`gov.dnk` ABSENT)と判明 — 明確な主権国(EU/NATO/Nordic)の孤立ギャップ。`registry/gov-units.world-countries.edn` に `gov.dnk`(Wikidata **Q35**, denmark.dk, iso3166-1-alpha3:DNK, `:authoritative`/`:maintainer-verified`, 既存191国ユニットと同 tier・同形式)を追加 → **country units 192 → 193**。Q35 未使用を duplicate-qid guard で事前確認。`check_seed_integrity.check()` = **CLEAN []**(malformed/duplicate QID・G5 provenance 全 pass)。副次効果: 前 iter で `gov.dnk` 不在のため skip していた dnk 旅券手続きがリンク可能になり、`gen_intl_proc.py` 再生成で intl 手続き 38→39、**atlas 手続き 44→45 / 39→40 法域**(dnk: owner-unit `gov.dnk` + toritsugi-ref `pp-dnk-passport-application` 双方解決、integrity test 確認)。COVERAGE.md 再生成(193法域反映)。フル監査 `70-tools/scripts/audit/` **462 passed / 0 failed**。working-tree edits only。

### 2026-06-05 (loop) — atlas↔toritsugi 投影を旅券のみ→全手続きに一般化 (45→95 手続き)
旅券限定だった `:gov.procedure` 投影を **全 toritsugi 手続きの投影**に一般化。旧 `gov-units.intl-passport-procedures.seed.edn`(39 旅券)を `gov-units.intl-procedures.seed.edn`(**89 手続き**)で置換: passport / national-id / tax / social-security / civil-registration を含む non-JP toritsugi 手続きを全投影(id=`proc.<toritsugi-procedureId>` で一意)。**捏造なし**: toritsugi の実 `requiredDocuments` + `legalBasis`(存在時) + `channelType`→channel kw + provenance を持ち越し、owner-unit は honest に国レベル `gov.<iso>`、正確な発行当局は `owner-authority` verbatim。jpn(6, 手動投影済 proc.jpn.*)・eu-wide(4, 国ユニット無)・twn/hkg(各2, 国ユニット無)は honest スキップ。結果 **atlas 手続き 45 → 95 / 40 → 49 法域**(dangling owner=0 / orphan toritsugi-ref=0、integrity test 確認)。`check_seed_integrity.check()` = **CLEAN []**(check() は procedure 非対象だが units 健全性維持)。COVERAGE.md 再生成。フル監査 `70-tools/scripts/audit/` **462 passed / 0 failed**。AUTO-GENERATED ファイル(loop generator 再実行で再生成)。working-tree edits only。

### 2026-06-05 (loop) — 投影生成器をリポジトリへコミット (再現性) + eu-wide 投影
**再現性ギャップ解消**: atlas の `gov-units.intl-procedures.seed.edn` は "AUTO-GENERATED" と記すが生成器が一時領域にしか無かった問題を解消 — 正式スクリプト `scripts/gen_intl_procedures.py`(committed, repo-relative パス, docstring に honest owner-unit/skip 規律)を追加。誰でも `python3 scripts/gen_intl_procedures.py` で再生成可能に。**カバレッジ**: `eu-wide → gov.eu`(European Union supranational unit, 既存)マッピングを追加し、これまで国ユニット無で skip していた eu-wide 4 手続き(Single Digital Gateway / EHIC / GDPR DSAR 等)を投影 → atlas 手続き **95 → 99 / 49 → 50 法域**。skip は honest に jpn(6, 手動)・twn(2)・hkg(2)のみ。check() = **CLEAN []**、dangling owner=0 / orphan ref=0、eu-wide 4 件投影確認。COVERAGE.md 再生成。フル監査 **470 passed / 0 failed**。working-tree edits only。

### 2026-06-05 (loop) — atlas↔toritsugi 投影に freshness テスト追加 (drift 防止)
新設 `70-tools/scripts/audit/test_ooyake_intl_projection_fresh.py`(R0-safe; 生成器の pure helper を import、main() 非実行=disk 非書込)。AUTO-GENERATED な `gov-units.intl-procedures.seed.edn` の **stale 化を fail-closed 検出**: toritsugi 編集後に生成器再実行を忘れると committed 投影が silently drift する問題を pin。2 不変条件: (1) committed に投影された toritsugi-ref 集合が、生成器が今投影する集合と**完全一致**(missing=toritsugi 追加・未再生成 / ghost=toritsugi 削除・残存 を双方検出), (2) 各 row の owner-unit が生成器の割当(country-level gov.<iso> / eu-wide→gov.eu override)と一致。現 committed で **2/2 green**、負例(toritsugi 手続き追加模擬)で missing 検出を実証(vacuous でない)。これで iter-6 の参照整合性 + 本 freshness で、投影は「全 ref 解決」かつ「生成器と同期」が機械保証される。フル監査全 green。working-tree edits only。

### 2026-06-05 (loop) — gov-procedures publish surface に freshness テスト (drift 防止)
前段で apex Worker の手続き公開サーフェス(`/.well-known/gov-procedures.json` + `/actor/<gov-handle>/procedures.json`)を `gen-gov-procedures.py` → `gov-procedures.gen.ts`(157手続/51単位/50法域)で構築したが drift guard が無かった点を解消。新設 `70-tools/scripts/audit/test_gov_procedures_gen_fresh.py`(R0-safe; ooyake parse_edn 再利用・.gen.ts は regex 読取のみ)が **compiled Worker registry の stale 化を fail-closed 検出**: (1) committed .gen.ts の procedure id 集合が ooyake から今生成される集合と完全一致(missing=ooyake 追加・未再生成 / ghost=削除・残存), (2) GOV_PROCEDURES_TOTAL/_OWNER_COUNT/_JURISDICTION_COUNT が source と一致。現状 157/51/50 で **3/3 green**、負例(ooyake 追加模擬)で検出を実証。これで「ooyake→Worker 公開」も iter-14 の「ooyake→atlas 投影」と同様に生成器同期が機械保証。フル監査 **497 passed / 0 failed**。working-tree edits only。

### 2026-06-17 (loop) — manifest+lexicon charter-gate test (構造ゲート pin)
既存テスト(cell + procedure-integrity/projection-freshness audit)は seed-data 層を被覆していたが、**manifest G1–G12 ゲートセット + lexicon の構造的ゲート**は未 pin だった点を解消。新設 `methods/test_charter_gates.cljc`(**6 tests green**, standalone・network-free・R0 ceiling 不変)が固定: (1) manifest が厳密に G1–G12 を宣言。(2) **provenance 規律** — govUnit/address/procedure/window が provenance + sourcing + lastVerified 必須。(3) **sourcing = {authoritative, representative} のみ**(ooyake は自ら "official" を僭称せず、ミラーまたは representative)。(4) **G5 legal-basis** — procedure が legalBasis + verificationStatus 必須、verificationStatus = {unverified-seed, maintainer-verified, stale}(捏造 "official" tier 不在)。(5) **G3 mirror record** — govUnit が atlasDid + verificationStatus 必須(公的機関そのものでなくミラー)。(6) findService が verifyFirst 必須。`run_tests.sh` 新設(charter-gate + 4 cell suite、計 5/5 green)。working-tree edits only。

> **2026-06-17 substrate-native migration (ADR-2606160842):** the charter-gate test above was ported Python→Clojure (`methods/test_charter_gates.py` → `methods/test_charter_gates.cljc`, ns `ooyake.methods.test-charter-gates`, reads the lexicons via cheshire/edn) and the Python was pruned. Run via `./run_tests.sh` (now `exec bb`) or `kbb -M:test:charter` (all 34 charter suites; 244 tests / 924 assertions green). Assertions unchanged (1:1 port).
