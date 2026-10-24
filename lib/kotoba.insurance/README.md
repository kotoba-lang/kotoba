# kotoba-insurance

[![CI](https://github.com/kotoba-lang/insurance/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/insurance/actions/workflows/ci.yml)

**Policies, premiums and claims in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
`cloud-itonami` insurance vertical (ISIC 6511 life insurance, 6512 non-life
insurance, 6520 reinsurance, 6530 pension funding, 6621 risk and damage
evaluation, 6622 insurance agents/brokers, 6629 other insurance auxiliary):
policy records (life/non-life), premium-quote arithmetic, claim records and
underwriting-decision records.

No network, no I/O, and **no real actuarial tables** — an operator supplies
their own licensed rate table; this library only combines a supplied rate
with policy facts. Amounts are plain numbers in the smallest currency unit.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 216 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.insurance :as ins])

(ins/policy "P1" "Alice" :life 100000 "2026-01-01" "2036-01-01")
(ins/policy-active-on? policy "2026-06-01")           ; => true/false
(ins/premium-quote policy 5 :loading 0.1)             ; rate-per-mille + loading -> premium amount
(ins/claim "C1" "P1" "Alice" "2026-06-01" 5000)
(ins/claim-in-force? claim policy)                    ; loss occurred while coverage was active?
(ins/underwriting-decision "P1" :approve :risk-score 0.2)
```

## Operator console (UI/UX)

A read-only HTML dashboard renders policies, premium quotes and claims for
an operator. Built on [`kotoba-lang/html`](https://github.com/kotoba-lang/html)
(Hiccup→HTML) + [`kotoba-lang/css`](https://github.com/kotoba-lang/css)
(EDN→CSS). Pure data → markup; the console never exposes a write surface (no
`<form>`/`<button>`) — binding, endorsement and claim payout stay behind the
governor.

```clojure
(require '[kotoba.insurance.ui :as ui])

(ui/dashboard
  {:policies [(ins/policy "P1" "Alice" :life 100000 "2026-01-01" "2036-01-01")]
   :claims   [(ins/claim "C1" "P1" "Alice" "2026-06-01" 5000 :status :paid)]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Japan health-insurance identifiers

Format and check-digit validation for the 保険者番号 (health-insurer
number, an 8-digit 法別番号(2) + 都道府県番号(2) + 保険者別番号(3) +
検証番号(1)) and the 医療機関コード (medical-institution code, a 10-digit
都道府県番号(2) + 点数表番号(1) + 郡市区番号(2) + 医療機関(薬局)番号(4) +
検証番号(1)) printed on Japanese health-insurance cards / claims forms, per
MHLW notification 別添２『保険者番号、公費負担者番号、公費負担医療の受給者
番号並びに医療機関コード及び薬局コード設定要領』(primary source verified
2026-07-08: https://www.mhlw.go.jp/content/12400000/001275316.pdf, dated
2024-07-12; archived at
[`kotoba-lang/emr-claims-primary-sources`](https://github.com/kotoba-lang/emr-claims-primary-sources)
alongside a 2008 predecessor notification independently confirming the
same 保険者番号 worked example — see ADR-2607084100). No real 法別番号 or
医療機関 registry, no diagnosis codes, no claims-adjustment logic — pure
shape/check-digit recomputation only.

```clojure
(require '[kotoba.insurance.jp :as jp])

(jp/valid-hokensha-bangou? "06130488")        ; => true  (MHLW worked example)
(jp/parse-hokensha-bangou "06130488")         ; => {:hokensha/houbetsu-bangou "06" ...}
(jp/validate-hokensha-bangou "0613048")       ; => {:insurance/valid? false :insurance/error :not-8-digits}
```

### 都道府県番号 (prefecture code)

The 2-digit 都道府県番号 shared by both 保険者番号 and 医療機関コード is
embedded as a 94-entry constant table: the 47 primary codes ("01"-"47",
JIS X 0401) plus the 47 alternate codes ("51"-"97", each primary code +
50) that 別添２ documents for use once a prefecture's primary-code range of
保険者別番号/医療機関(薬局)番号 numbers is exhausted. Both ranges are
equally valid, currently-issuable codes. Stable, public, decades-old data,
unlike the tens-of-thousands-of-rows 診療行為/薬剤/傷病名 masters that this
codebase deliberately does not embed elsewhere (see the iryo actor's
master-honesty ADR-2606074000).

```clojure
(jp/valid-todoufuken-bangou? "13") ; => true
(jp/todoufuken-name "13")          ; => "東京都"
(jp/todoufuken-name "63")          ; => "東京都" (alternate code, 13 + 50)
```

### 医療機関コード (medical-institution code) — full check-digit validation

A 医療機関コード is 10 digits: 都道府県番号(2) + 点数表番号(1) +
郡市区番号(2) + 医療機関(薬局)番号(4) + 検証番号(1), per 別添２ 第４. The
検証番号 algorithm is the *same* alternating-2/1 fold-mod10 formula as
保険者番号's, applied to the 9-digit body — verified against 別添２ 第４-５'s
own worked example (都道府県番号=34, 点数表番号=1, 郡市区番号=07,
医療機関番号=1236 → 検証番号=2, full code `3410712362`).

点数表番号 decodes to a category per 第４-５(１)「点数表番号は医科１、
歯科３、薬局４とするものとする」— only these three digits are implemented;
secondary sources additionally describe "2" (健診等機関) and "6" (訪問看護)
but the primary source consulted does not document either, so they are
deliberately left unmapped (`tensuhyou-bangou-category` returns `nil`)
rather than guessed at.

医療機関(薬局)番号 numeric ranges are validated per 第４-３: 医科
1,000-2,999 / 歯科 3,000-3,999 / 薬局 4,000-4,999. The ただし書き exclusion
(a 4-digit number whose middle two or last two digits read "90" is a
permanent 欠番/unassigned number) is exposed as a separate predicate,
`iryokikan-kikan-bangou-ketsuban?`, rather than folded into the main
validator.

```clojure
(jp/parse-iryokikan-bangou "3410712362")
;; => {:iryokikan/todoufuken-bangou "34" :iryokikan/tensuhyou-bangou "1"
;;     :iryokikan/gunshiku-bangou "07" :iryokikan/kikan-bangou "1236"
;;     :iryokikan/kenshou-bangou "2"}
(jp/iryokikan-bangou-check-digit "341071236")         ; => 2  (MHLW worked example)
(jp/valid-iryokikan-bangou? "3410712362")             ; => true
(jp/tensuhyou-bangou-category "1")                    ; => :medical
(jp/valid-iryokikan-kikan-bangou-range? "1" "1236")   ; => true (医科 1000-2999)
(jp/validate-iryokikan-bangou "3410712362")
;; => {:insurance/valid? true :iryokikan/category :medical ...}
(jp/validate-iryokikan-bangou "341071236X")
;; => {:insurance/valid? false :insurance/error :not-10-digits}
```

**Known gap, not implemented.** A secondary source (Wikipedia,
「処方箋発行医療機関コード」) describes a legacy exception for some
医療機関コード issued in 埼玉県・千葉県・東京都・神奈川県 before Japan's
1976 unification onto the current 10-digit scheme (descending from a 1967
7-digit scheme), whose 検証番号 is said to be computed over the bare
7-digit 医療機関コード body alone (郡市区番号+医療機関番号+検証番号),
omitting 都道府県番号 and 点数表番号 from the check-digit input entirely.
Neither primary source consulted for this library documents that
exception, so it is **not implemented** here — `iryokikan-bangou-check-digit`
and `valid-iryokikan-bangou?` always use the full 9-digit body. A caller
working with pre-1976 legacy codes from those four prefectures should not
trust this library's check-digit result.

## US insurance/claims identifiers

Structural validation for two identifiers used in US health-insurance claims
practice, researched from primary sources 2026-07-08 (archived at
[`kotoba-lang/emr-claims-primary-sources`](https://github.com/kotoba-lang/emr-claims-primary-sources)
where a primary source exists). Unlike `kotoba.insurance.jp`, **neither
identifier here gets a check-digit function** — for both, the research
itself determined there is nothing to implement beyond shape, for two very
different reasons documented in full in `kotoba.insurance.us`'s namespace
docstring:

```clojure
(require '[kotoba.insurance.us :as us])

(us/valid-naic-company-code? "19232")         ; => true  (Allstate's real NAIC company code)
(us/validate-naic-company-code "1923")        ; => {:insurance/valid? false :insurance/error :not-5-digits}

(us/valid-payer-id-shape? "WX867")            ; => true  (real-world clearinghouse example)
(us/validate-payer-id-shape "WX-867")         ; => {:insurance/valid? false :insurance/error :non-alphanumeric}
```

### NAIC company code — 5-digit numeric, confirmed no check digit

Per NAIC's own official Glossary of Insurance Terms
(https://content.naic.org/glossary-insurance-terms, retrieved 2026-07-08):
"Company Code - a five-digit identifying number assigned by NAIC, assigned
to all insurance companies filing financial data with NAIC." Independently
corroborated by HL7 Terminology's registered `NAICCompanyCodes` NamingSystem
(OID `2.16.840.1.113883.6.300`), which cites the same source. **No
check-digit algorithm is documented anywhere in either source** — a
full-text search of the glossary page's raw HTML for "check digit" returns
zero hits — so `valid-naic-company-code?` / `validate-naic-company-code`
check only the 5-decimal-digit shape (leading zeros significant). A
secondary-source claim (found only as search-result summaries, never
confirmed against a fully-readable primary document) that codes below
10000 map to a legacy combined property/casualty-statement category is
**not implemented** — the one candidate NAIC PDF fetched to check this
came back as an undecodable compressed/font-subset stream, not readable
text.

### Payer ID — no universal registry; X12 structural envelope only

A Payer ID routes an electronic claim (ASC X12 837, loop 2010BB, `NM108`
"PI" / `NM109`) to the correct payer via a clearinghouse. **There is no
single official registry or issuing authority** — every clearinghouse
(Availity, Change Healthcare, Stedi, Jopari, Data Dimensions, Carisk, etc.)
assigns Payer IDs independently, the same payer often has different IDs at
different clearinghouses, and real-world values vary in both length and
alphanumeric shape (5-character codes like `WX867`/`35076` alongside
9-digit TIN-like values such as AHCCCS's `866004791`) — see
https://blog.daisybill.com/how-to-e-bill-clearinghouse-payer-ids (retrieved
2026-07-08). The one structural constraint traceable to an accredited
standards body is ASC X12 data element 67 ("Identification Code"), which
`NM109` uses: type `AN`, length 2-80 ("AN 2/80") — corroborated here via
three independent third-party EDI-standard reference mirrors of the X12
element dictionary (x12.org's own TR3 implementation guides are a paid
subscription product and did not serve this detail on direct fetch).
`valid-payer-id-shape?` / `validate-payer-id-shape` therefore check only
that 2-80 character, alphanumeric-only envelope (the alphanumeric-only
restriction matches every real-world example found but is not itself a
documented X12 rule) — **a true result is not a claim that the value is a
real, currently-issued Payer ID for any specific clearinghouse.**

## EU/EEA European Health Insurance Card (EHIC) identifiers

Structural validation only, researched from primary sources 2026-07-08
(archived at
[`kotoba-lang/emr-claims-primary-sources`](https://github.com/kotoba-lang/emr-claims-primary-sources)'s
`eu-ehic/` directory). **Headline finding: there is no single EU-wide
standardized "EHIC number."** Per Decision No S2 of 12 June 2009 concerning
the technical specifications of the European Health Insurance Card
(Administrative Commission for the Coordination of Social Security
Systems; CELEX 32010D0424(09), OJ C 106, 24.4.2010, p.26-39 — retrieved via
a real Chrome browser session, since EUR-Lex WAF-blocks automated
`curl`/`WebFetch` on both its modern and legacy endpoints), the card's
personal identification number field is explicitly defined as "the
personal identification number detail used by the issuing Member State" —
a nation-specific value with no documented cross-Member-State digit count
or check digit. This is corroborated operationally by a separate European
Commission report (Pacolet & De Wispelaere 2016) whose footnote records
Luxembourg reissuing every EHIC in 2014 due to "a change of the composition
of the national personal identification number."

```clojure
(require '[kotoba.insurance.eu :as eu])

(eu/valid-issuing-state-code? "UK")                       ; => true (documented GB exception)
(eu/valid-personal-identification-number-shape? "90010112345") ; => true (≤ 20 chars, no algorithm)
(eu/valid-institution-identification-number-shape? "1234567")  ; => true (4-10 chars)
(eu/parse-card-identification-number "AB1867XXXX0000001234")
;; => {:eu/issuer-identifier "AB1867XXXX" :eu/serial-number "0000001234"}
```

What *is* EU-standardized, and implemented here as structural-only checks
(no registry lookups, no check digits — none are documented):

- **Issuing state ID number** (Field 2) — 2 characters, nominally ISO
  3166-1 alpha-2 with the Decision's own documented "UK instead of GB"
  exception. Only the 2-uppercase-letter shape is validated; full ISO
  3166-1 membership is not (scope decision, see `kotoba.insurance.eu`
  docstring).
- **Personal identification number** (Field 6) — up to 20 characters, the
  only EU-standardized fact about this otherwise nation-specific value.
- **Identification number of the institution** (Field 7, part 2) — 4 to 10
  characters, nationally assigned ("see national code list of competent
  institutions"), no documented algorithm.
- **Logical identification number of the card** (Field 8) — the one
  precisely specified identifier: exactly 20 characters, a 10-character
  EN-1867-registered issuer identifier (treated as opaque — EN 1867 itself
  is a non-free standard, not fetched) plus a 10-digit numeric serial
  number.

**Known gap, not implemented.** Section 3.5's printing-character-set clause
("Compliance with EN 1387 ... Latin alphabet Nos 1-4 (ISO 8859-1 to 4)")
applies to every field above, but is not enforced — EN 1387 is itself a
non-free standard, and approximating it as a portable regex across
JVM/ClojureScript/SCI/GraalVM would trade a sourced length check for an
invented charset check. Decision No S1 of 12 June 2009 (issuance-procedure
rules, not the data model) and the date-of-birth/expiry-date fields
(`DD/MM/YYYY`, general dates rather than insurance identifiers) are also
out of scope for this namespace — see `kotoba.insurance.eu`'s namespace
docstring for the full field-by-field sourcing.

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for policies and claims.

```clojure
(require '[kotoba.insurance.export :as ex])

(ex/policies->csv policies)
(ex/claims->csv claims)
(ex/claims->json claims)
```

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
