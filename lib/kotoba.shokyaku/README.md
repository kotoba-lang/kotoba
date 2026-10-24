# shokyaku（償却）

**How a depreciable asset writes down, by jurisdiction.** A dependency-free
[kotoba-lang](https://github.com/kotoba-lang) capability library that answers:
in this jurisdiction, what is the most this asset may be depreciated this
year, and by which methods may it be depreciated at all?

> **Not tax advice.** This is a mechanism plus a small, cited rule set. It is
> deliberately incomplete, and its most important behaviour is what it does
> about that.

Sibling of [`taxlaw`](https://github.com/kotoba-lang/taxlaw) and
[`worklaw`](https://github.com/kotoba-lang/worklaw), and the same shape on
purpose: a jurisdiction is a path, coverage is per **facet**, an unchecked
facet is never a pass, and the convenient boolean gives the conservative
answer.

```clojure
(require '[kotoba.shokyaku :as sh])

(sh/depreciation-limit
 [:jp] {:asset-class :machinery
        :acquisition-cost-yen 1000000
        :acquired-on "2020-04-01"
        :placed-in-service-on "2020-10-15"
        :useful-life-years 5
        :method :straight-line
        :accumulated-depreciation-yen 0
        :fiscal-year-start "2020-04-01"
        :fiscal-year-end "2021-03-31"})
;; => {:shokyaku/coverage :checked
;;     :shokyaku/limit-yen 100000
;;     :shokyaku/prorated? true
;;     :shokyaku/months-in-service 6
;;     :shokyaku/months-in-fiscal-year 12
;;     :shokyaku/memorandum-yen 1
;;     :shokyaku/ceiling-yen 999999
;;     ...}
```

## The invariant: absence is never sufficiency

```clojure
(sh/covered? [:atlantis])                  ;; => false
(sh/requires-election? [:us])              ;; => nil, NOT false
(sh/depreciation-limit [:us] asset)        ;; => {:shokyaku/coverage :none}
(sh/within-limit? [:us] asset 1)           ;; => false
```

`requires-election?` returns **nil** rather than false for an uncatalogued
jurisdiction, so a caller cannot read *we have no rule* as *there is no
rule*. The United States depreciates assets — MACRS exists, IRC §168 exists.
This library has not read them, and that is a different fact from their
absence. There is no `[:us]` entry at all: cataloguing it with every facet
out of scope would be recording a decision nobody made.

## Coverage is per facet and per question

Being in the catalog says something was read about somewhere. It says nothing
about the facet you are asking after. Every entry point gates on `facet-of`,
never on `covered?`.

`taxlaw` measured why on 2026-08-18: `credit-support` gated on `covered?`,
and the underlying rule returned nil for a facet the catalog did not carry,
so `(or (not needs?) ...)` made the answer `true`. Adding a second
jurisdiction with no invoice rule would have turned every claim there from
*held, nobody catalogued this* into *approved, no requirement*.

The same shape here would be worse, because the thing on the other side is an
amount: a jurisdiction with no `:jurisdiction/residual-value` facet would
yield a memorandum value of nil, and an asset would depreciate to zero.

```clojure
(sh/depth [:jp])
;; => {:shokyaku/read 5 :shokyaku/partly-read 1
;;     :shokyaku/out-of-scope 1 :shokyaku/silent 0 :shokyaku/of 7
;;     :shokyaku/partly-read-facets [:jurisdiction/useful-life]}
```

Four disjoint buckets that sum to `:of`. **`:silent` is the one that
matters** — a silent facet and an out-of-scope one look identical from every
other view, and the difference is whether there is a decision behind the
absence. `:jurisdiction/useful-life` is `partly-read` because three ordinance
tables were read and three were not; `:jurisdiction/rounding` is
`out-of-scope` and appears in the universe precisely so a refusal cannot
vanish from the coverage view.

`world-coverage` takes the universe as an argument and **has no default** — a
catalog with one jurisdiction read and one known computes `1/1`, and the
denominator has to come from outside, because what is being measured is what
this catalog does not know about.

## What was read, verbatim

Every provision below was retrieved from the **e-Gov law API v2** on
2026-08-18, at the revision named, and quoted from that response — not from
memory and not from a secondary summary. All three instruments were
`CurrentEnforced` with `repeal_status: None` in the same responses.

| Instrument | e-Gov id | Revision served |
|---|---|---|
| 法人税法 | `340AC0000000034` | `..._20260812_508AC0000000064` |
| 法人税法施行令 | `340CO0000000097` | `..._20260731_508CO0000000094` |
| 減価償却資産の耐用年数等に関する省令 | `340M50000040015` | `..._20260522_508M60000040029` |

Provisions read verbatim: 法人税法 **第三十一条第一項**; 施行令 **第十三条**,
**第四十八条の二第一項・第五項**, **第五十六条**, **第五十八条**,
**第五十九条第一項第一号・第二項**, **第六十一条第一項第二号**. 施行令
**第四十八条** (the pre-2007 regime) was read and deliberately not
implemented.

`tools/verify_citations.cljk` resolves the three law ids against
`kotoba-lang/jp.go.e-gov.elaws` and **refuses to report a verdict (exit 2)**
when that corpus is absent, rather than reporting zero problems.

```
$ kbb --backend sci tools/verify_citations.cljk ../jp.go.e-gov.elaws
CORPUS  ../jp.go.e-gov.elaws/index/laws.edn  9536 laws
SCANNED  3
  ok   340AC0000000034  :law.status/superseded-revision  法人税法
  ok   340CO0000000097  :law.status/in-force             法人税法施行令
  ok   340M50000040015  :law.status/in-force             減価償却資産の耐用年数等に関する省令

3 / 3 e-Gov-corpus statutes in force with matching titles
TABLES-NOT-READ  4 ordinance table(s) fetched and deliberately NOT read
```

## The rates are read from the table, never computed

The 定額法 rate for a 3-year life is **〇・三三四**, not ⅓. For 7 years it is
**〇・一四三**, not 0.142857. And 別表第十 is *not* 別表第八 doubled, which
第四十八条の二第一項第一号イ（２）'s own wording invites you to assume:

| 耐用年数 | 別表第八 (定額法) | ×2 | 別表第十 (定率法) |
|---|---|---|---|
| 3 | 〇・三三四 | 〇・六六八 | **〇・六六七** |
| 6 | 〇・一六七 | 〇・三三四 | **〇・三三三** |
| 7 | 〇・一四三 | 〇・二八六 | 〇・二八六 |

The article describes how the Ministry built the table. The table is what
governs. Computing these instead of reading them is wrong in both directions
and looks right.

## Arithmetic is integer yen and exact fractions

Every amount is an integer number of yen. Every rate is `{:num n :scale s}` —
〇・三三四 is `{:num 334 :scale 1000}`, never `0.334`.

**This is portability, not fastidiousness.** ClojureScript has no distinct
floating-point type: `1.0` reads as `1`, `(integer? 1.0)` is `true`, and
`(str -0.0)` is `"0"`. A rate stored as a double would not round-trip under
both runtimes this library must satisfy, and depreciation is arithmetic on
money. A non-integer `:acquisition-cost-yen` is refused rather than
truncated.

## What it refuses, and why

| Refusal | Reason |
|---|---|
| **The method** | 定額法 / 定率法 are an election — 法 第三十一条第一項 computes the limit on 「その内国法人が当該資産について選定した償却の方法」. Nothing here defaults one; an undeclared method gets `:not-declared` **with the permitted choices named**. The article also provides for 「選定しなかつた場合」, and what applies then is a 政令 this library has not read — so an undeclared method has an answer in law and this catalog does not know it. |
| **端数処理 of the yen amount** | No provision stating it was read. The 省令 full text contains no 円未満, no 切り捨て and no 切り上げ; the 端数 rules that exist govern *months* (施行令 第五十九条第二項, up) and *years* (省令 第三条第三項, down). Every inexact division carries `:shokyaku/rounding :floor-not-in-statute` and `:shokyaku/dropped` — the remainder over its scale — so the floor is visibly this library's convention. |
| **改定取得価額** | 第四十八条の二第五項第二号イ defines it as the 取得価額 of the year 定率法 crossed below the 償却保証額 — history a single-year function does not see. Once the crossing happens the result is `:not-declared` until it is supplied. |
| **耐用年数 for most tangible assets** | See below. |
| **Assets acquired on or before 平成19年3月31日** | 施行令 第四十八条's regime (旧定額法/旧定率法) needs 残存価額 (別表第十一), the 95% ceiling of 第六十一条第一項第一号イ and the five-year run-out of 第六十一条第二項. Read, not implemented. Half a regime is worse than none of it. |
| **生産高比例法 / リース期間定額法 / 特別償却 / 減損** | Recorded in `:jurisdiction/out-of-scope`, each with its reason. |

### The 別表 that could not be read

別表第八・第九・第十 (the rate tables) and 別表第三・第五・第六 (the flat
耐用年数 tables) were extracted from the API response and embedded — 99, 99,
99, 18, 2 and 8 rows, **zero of them ambiguous**.

別表第一 (492 rows), 別表第二 (118) and 別表第四 (44) were **fetched, are
present in the response, and are still not read.** 細目 nests up to three
levels and the nesting is marked *only by an empty 耐用年数 cell* — a visual
convention the JSON does not carry. 種類 and 構造又は用途 carry `rowspan` and
are recoverable; 細目 does not. **81 of 492, 11 of 118 and 1 of 44 rows are
such sub-group headers.** Reading a 耐用年数 out of them means guessing which
parent a row hangs from.

So `useful-life` answers `:none` for a lathe, naming why:

```clojure
(sh/useful-life [:jp] {:kind "特許権"})   ;; => {:shokyaku/coverage :checked :shokyaku/years 8 ...}
(sh/useful-life [:jp] {:kind "旋盤"})     ;; => {:shokyaku/coverage :none ... "may well be in 別表第一…"}
```

**A 償却限度額 can still be computed for a lathe** — by passing
`:useful-life-years` in from wherever the caller actually got it. What must
not happen is this library inventing the number, and that is why the two are
separate facets.

A kind that appears in more than one 別表 is `:not-declared`, not a guess:
ソフトウエア is 3 or 5 years in 別表第三 and 3 years in 別表第六 (開発研究用),
which are different assets in the same words.

## Two figures that look familiar and are not what the article says

- **「everything leaves one yen behind」.** 第六十一条第一項第二号**ロ** caps
  坑道 and the 第十三条第八号 intangibles at 「その取得価額に相当する金額」 —
  the whole cost. **Software depreciates to zero, not to one yen.** The 1 yen
  is イ's, and applies to tangible and biological assets.
- **「構築物 can elect 定率法」.** 第四十八条の二第一項第一号 イ reaches assets
  acquired 平成28年3月31日以前 *excluding 建物*; ロ — everything else in 第一号
  — is 定額法 only. 建物附属設備 and 構築物 lost the 定率法 election on
  **平成28年4月1日**, and 建物 never had it under the current regime.

## Portability

`.cljc`, and portable in the way that can fail rather than the way that
cannot. A reader conditional whose `:cljs` branch nothing evaluates is the
appearance of portability.

```bash
kbb -M:test                                   # JVM
kbb --backend sci --classpath src:test test/run_portable.cljk   # nbb

# and from a FOREIGN working directory, which is the one that matters
cd /tmp/elsewhere && kbb --backend sci --classpath "$REPO/src:$REPO/test" "$REPO/test/run_portable.cljk"
```

All three: **33 tests, 517 assertions, 0 failures.**

The tables live in `resources/kotoba/shokyaku/tables.edn` (the source of
truth, and what a human edits) and are projected into
`src/kotoba/shokyaku/embedded.cljk` by `tools/gen-embedded.cljk`, gated by
`--check`. There is no runtime file access and no cwd assumption: a
`resources/` read relative to the process's working directory is right while
this library is the root project and wrong the moment it is a dependency —
measured in `kotoba-lang/technology` on 2026-08-18, where a registry came
back nil for all 159 of iso3166's assertions.

## Mutation testing

```bash
kbb --backend sci tools/check-mutations.cljk   # pre-flight: every :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # 15 mutations
```

**15 mutations, 15 killed, 0 survived.** The first blind run — mutations
written from the source before re-reading the suite — killed 11 and left 4.
Three were real gaps and now have tests:

- the 償却保証額 crossing is `<`, not `<=` (「満たない」 is *falls short of*;
  equal is not short, and no case put the two amounts exactly equal)
- an over-depreciated asset must yield `0`, not a negative limit
- a whole year of service must not be *reported* as prorated — the amount is
  unchanged at 12/12, so only the reporting differed

The fourth was an **equivalent mutant** and is recorded as such in
`tools/mutations.edn` rather than deleted, with the analysis: forcing
`first-year?` true cannot change an answer, because when 事業供用日 precedes
the fiscal-year start the months to the year end are necessarily ≥ the months
in the year, and the second guard already refuses to prorate. It is
retargeted at the part that *can* differ.

`tools/mutations.edn` states its **scope** in the header: it covers the
computation and its refusals, not the reporting views or the citation
metadata. A clean run means *every invariant listed there is measured*, not
*every invariant of this library*.

## License

Apache-2.0.
