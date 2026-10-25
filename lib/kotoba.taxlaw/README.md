# kotoba-taxlaw

**What a tax record must carry, by jurisdiction** — a
[kotoba-lang](https://github.com/kotoba-lang) capability library that answers
one question: in this jurisdiction, does this document support the treatment
being claimed for it?

> **Not tax advice.** This is a mechanism plus a small, cited rule set. It is
> deliberately incomplete, and its most important behaviour is what it does
> about that.

Sibling of [`kotoba-lang/worklaw`](https://github.com/kotoba-lang/worklaw),
and the same shape on purpose.

## The invariant: absence is never sufficiency

```clojure
(require '[kotoba.taxlaw :as taxlaw])

(taxlaw/credit-support [:atlantis] {:registration-number "T1234567890123"})
;; => {:taxlaw/coverage :none :taxlaw/unchecked [[:atlantis]]}
;;    no :taxlaw/supported? key at all — nobody checked

(taxlaw/credit-support [:jp] {:registration-number nil})
;; => {:taxlaw/coverage :checked :taxlaw/supported? false
;;     :taxlaw/reason :missing-registration-number ...}

(taxlaw/supported? [:atlantis] {:registration-number "T1234567890123"})
;; => false
```

`requires-qualified-invoice?` returns **nil**, not `false`, for an
uncatalogued jurisdiction — so a caller cannot read *we have no rule* as
*there is no requirement*. `supported?` is deliberately not
`(:taxlaw/supported? …)`: a caller who reaches for the convenient boolean
gets the conservative answer rather than the flattering one.

That distinction is the whole library. A bookkeeping actor that treated
silence as sufficiency would let a receipt nobody has seen the law about
support an input-tax credit.

## How much of the world is this? Ask, and supply the denominator

`world-coverage` **requires a universe and has no default**, and that is the
whole design. With three jurisdictions read and three known, the honest
arithmetic is `3/3`, and `100%` is what a reader takes away. The denominator
has to come from outside, because the thing being measured is precisely *what
this catalog does not know about* — the same shape as a citation checker whose
corpus is missing reporting zero problems.

`kotoba-lang/iso3166` is one place to get one (193 UN member states, and
portable as of 2026-08-18). This library does **not** depend on it: `deps.edn`
says it is deliberately dependency-free so that an actor needing to know what
a tax record must carry does not thereby acquire anything else — and a
universe is the caller's question anyway. A firm trading in four countries has
a universe of four, and `4/4` is true and useful where 193 would bury it. The
key spaces differ (`[:jp]` here, `"JPN"` there), so a caller bridging them
supplies the mapping visibly rather than this library guessing at one.

### Coverage has two dimensions and reporting one is the lie

`[:us]` is in the catalog with **one facet of ten**. Counting it as a
covered jurisdiction is true and misleading. So the answer carries both:

```clojure
(world-coverage #{[:jp] [:us] [:eu] [:de] [:fr] [:sg] [:gb]})
;; :taxlaw/read          [[:eu] [:jp] [:us]]        3 of 7 jurisdictions
;; :taxlaw/depth         {[:us] {:read 1 :of 8} …}
;; :taxlaw/facet-total   {:read 14 :of 70}          the figure that does not flatter
```

12/56 is lower than 3/7, which is the point of reporting it.

### Four buckets, and the one that matters is `:silent`

`depth` partitions the ten facets into `:read`, `:partly-read`,
`:out-of-scope` and `:silent`, and a test asserts they sum to `:of` for every
jurisdiction. That assertion earned itself immediately: the first version had
two buckets and `[:eu]` came back **3 + 6 = 9 out of 8**, because a facet can
be both — the EU's `:jurisdiction/electronic-transaction` was read from
Articles 218/246, and the sub-question *must the holder preserve the
electromagnetic record* is separately out of scope. Two buckets could not say
that, so they double-counted it.

**`:silent` is a facet nobody has thought about.** From every other view it is
identical to one deliberately left out — `credit-support` answers `:none` for
both, correctly, because neither is a pass. This is the view that tells them
apart, and the difference is whether there is a decision behind the absence.
All three catalogued jurisdictions currently have **zero** silent facets;
every absence is recorded.

## Three jurisdictions, and mostly what two of them do not say

| | read from source | notably absent |
|---|---|---|
| `[:jp]` | 消費税法, 所得税法, 電子帳簿保存法 + 施行規則, 法人税法施行規則, 消費税法施行令, 会社法 | — |
| `[:eu]` | Directive 2006/112/EC Art 215, 218, 226, 244, 246, 247 | **no retention period** |
| `[:us]` | 26 CFR § 1.6001-1(a), (e) | **no retention period, and no federal VAT at all** |

Both non-JP instruments were fetched and quoted verbatim on 2026-08-18. The
most valuable thing in each is an absence:

- **Article 247(1)**: *"Each Member State shall determine the period throughout
  which taxable persons must ensure the storage of invoices…"*
- **26 CFR § 1.6001-1(e)**: *"…retained so long as the contents thereof may
  become material in the administration of any internal revenue law."*

"EU: 10 years" and "US: 7 years" are folklore. Neither number appears in either
text, so `retention-years` is **nil** for both, and `:rule/period-set-by` says
where the answer actually lives (`:member-state` / `:materiality`). A test
asserts the US quote contains no digit-plus-"years" at all.

### Adding a jurisdiction must not widen a single pass

That is the whole risk of this change and it nearly went wrong. `credit-support`
gated on `covered?`, and `requires-qualified-invoice?` returns nil for a facet
the catalog does not carry — so `(or (not needs?) …)` evaluated to **true**.
The first jurisdiction added without an invoice rule would have flipped every
input-tax claim there from *held, nobody catalogued this* to *approved, no
registration number needed*, and **the diff that did it would have been a data
entry.** Measured 2026-08-18, before `[:us]` existed.

So coverage is now per **facet** (`facet-of`), and — one layer deeper, because
this bit immediately — per **question**. `[:eu]` carries a
`:jurisdiction/electronic-transaction` facet read from Articles 218 and 246, but
that facet says Member States must *accept* electronic invoices, which is not an
answer to *must the holder preserve the electromagnetic record as such*. With a
facet-presence gate, an EU electronic transaction kept on **paper** reported as
preserved. 電子帳簿保存法 第七条 and Article 218 share a facet key and point in
opposite directions.

`out-of-scope` records a facet left out **on purpose**, with the reason — the
United States has no federal VAT, so there is no federal analogue of 適格請求書,
and the sales taxes that exist are State law this catalog has not read. It still
answers `:taxlaw/coverage :none`, so a consumer that has never heard of
`:out-of-scope` holds exactly as it held before. **The reason is additive; the
refusal is not weakened.**

### What a `true` from `registration-number-valid?` means in the EU

Article 215 gives *"a prefix in accordance with ISO code 3166 — alpha 2"* and
nothing else — no length, no digit count, no Member State list. So the check is
the prefix shape, and the answer carries `:taxlaw/registration-format` naming
what was **not** checked: `:member-state-is-a-member`, `:body-format`,
`:check-digit`. `XX1` passes, and that limit is documented as real rather than
as a disclaimer. A pattern that also fixed a length would be enforcing one
Member State's rule against all of them.

### A citation nobody can check is not a citation that checked out

`tools/verify_citations.cljk` reads `:law/id` and checks it against the e-Gov
corpus. A Directive and a CFR section have no `:law/id`, so before this change
they **vanished from the run** and the summary read `10 / 10 in force` — true of
the ten it looked at, and read as true of the catalog. The verifier now prints a
`NO-CORPUS` line unconditionally, including the zero case, so *nothing outside
the corpus* stays distinguishable from *nobody looked outside the corpus*:

```
10 / 10 e-Gov-corpus statutes in force with matching titles
NO-CORPUS	 2 statute(s) cited that NO corpus in this workspace can check
  UNVERIFIED  26 CFR § 1.6001-1 Records
  UNVERIFIED  Council Directive 2006/112/EC on the common system of value added tax
```

A verbatim quote with a retrieval date is a **weaker** claim than the corpus
check: it says a fetch saw this text on a day, not that the instrument is in
force today.

### The retrieval URL is not the citation URL

`eur-lex.europa.eu/legal-content/…` answers **HTTP 202 with an empty body** to a
fetch, and `Accept: text/html` on CELLAR **404s**. What serves the text:

```bash
curl -sL -H "Accept: application/xhtml+xml" -H "Accept-Language: eng" \
  "http://publications.europa.eu/resource/celex/32006L0112"
```

Both URLs are recorded (`:source/url` for a human, `:source/retrieval-url` for a
fetch) because a later reader who tried the pretty one would conclude the source
was gone.

## Jurisdictions are paths, not codes

`[:jp]` today. A path leaves room for `[:jp :tokyo]` or `[:us :ca]` without
renaming anything. A bare keyword (`:jp`) is accepted too, because making
every actor convert at the call site is how a shared library stops being
used.

## Citations are checked against the corpus, not against HTTP

Every statute carries its **e-Gov law id**, and `tools/verify_citations.cljk`
resolves those ids against
[`kotoba-lang/jp.go.e-gov.elaws`](https://github.com/kotoba-lang/jp.go.e-gov.elaws)'s
`index/laws.edn` — 9,536 Japanese laws with status, title and content hashes.

This replaces an earlier check that fetched each URL and accepted HTTP 200.
Reachability is the weaker claim by some distance:

| | HTTP 200 | corpus index |
|---|---|---|
| the URL resolves | yes | — |
| the law exists under that id | inferred | stated |
| the title is what we said it is | no | **compared** |
| the law has been **repealed** | **invisible** | `:law.status/repealed` |

A repealed statute serves its page with a 200 like any other.

```bash
kbb --backend sci tools/verify_citations.cljk ../jp.go.e-gov.elaws
# CORPUS  …/index/laws.edn   9536 laws
# SCANNED 8
#   ok  132AC0000000048  :law.status/in-force  商法
#   …
# 8 / 8 in force with matching titles
# 4 of those are :superseded-revision — the corpus snapshot predates a
#    later revision of a law still in force. Not a bad citation.
```

**`:law.status/superseded-revision` is not repeal.** It means the corpus
snapshot predates a later revision of a law that is still in force. Four of
the eight statutes are in that state; the checker separates them from
`:repealed` / `:lapsed` / `:expired`, which fail.

### Exit codes are three-valued

| | |
|---|---|
| `0` | every cited statute exists, is in force, and its title matches |
| `1` | a citation is bad — absent, no longer in force, or retitled |
| `2` | **the run could not answer** — corpus not on disk, or index parsed to nothing |

`2` exists because a checker whose corpus is missing has learned nothing
about the citations, and reporting "0 problems" would make that
indistinguishable from having checked. An empty scan prints `SCANNED 0` and
refuses.

Measured 2026-08-17, all four discriminated:

| injected | result |
|---|---|
| cite a repealed law (`113DF0000000036` 旧刑法) | `FAIL … no longer in force: :law.status/repealed` |
| cite a law id that does not exist | exit 1, `not in corpus` |
| change a title, leave the URL working | exit 1, `title differs` |
| point at a directory with no corpus | exit 2, refuses |

## 電子帳簿保存法 第七条 — read, then enforced

The catalog carried an electronic-transaction rule that nothing consumed and
that nobody had read: `:rule/review :reachable-not-read`. Before wiring it
into a governor, the article was retrieved and quoted.

```
第七条  所得税（源泉徴収に係る所得税を除く。）及び法人税に係る保存義務者は、
        電子取引を行った場合には、財務省令で定めるところにより、当該電子取引の
        取引情報に係る電磁的記録を保存しなければならない。
```

Retrieved 2026-08-17 via `GET /api/2/law_data/410AC0000000025`, so
`:rule/review` is `:read-from-source` and `:rule/quote` carries the text.

**The article's scope is recorded, not widened.** It binds 保存義務者 for
income tax (excluding withholding) and corporation tax — `:rule/applies-to
#{:income-tax :corporation-tax}`. This library does not decide whether a
given holder is one; a caller who does not know has not established that it
is exempt.

```clojure
(taxlaw/record-preservation [:jp] {:origin :electronic-transaction
                                   :preservation :paper})
;; => {:taxlaw/coverage :checked :taxlaw/preserved? false
;;     :taxlaw/reason :electronic-record-not-preserved
;;     :taxlaw/provision "電子帳簿保存法 第七条" ...}
```

Three-valued like `credit-support`, with one more state that matters:
`:not-declared` — the document does not say how the transaction happened, so
nothing was asserted and nothing was checked. Printing an electronic
transaction and keeping the paper is the case the article addresses: the
obligation is to preserve the 電磁的記録 itself.

## 消費税額等 — 施行令 第七十条の十, and the ¥1 nobody notices

消費税法施行令 第七十条の十, read 2026-08-18 from
`GET /api/2/law_data/363CO0000000360`. The article settles three things that a
naive implementation gets wrong, and it is worth naming them because getting
any of them wrong produces an invoice that looks completely normal:

1. **The multiplication is on the per-rate subtotal, not per line.**
   「税率の異なるごとに区分して合計した金額に…を乗じて」— sum first, then
   multiply. Taxing each line and adding the results is a *third* method, and
   the article offers exactly two. `consumption-tax-amount` therefore takes
   `:subtotals`, not lines: **a caller holding lines has to group them, which
   is where the grouping decision belongs and where it can be seen.** A test
   shows a case where the two disagree by ¥2 on ¥999.
2. **The rounding happens once, on that one figure.**
3. **The article does not say which way to round.** 処理する, not 切り捨てる.

So neither the method (`:tax-exclusive` 第一号 / `:tax-inclusive` 第二号) nor
the rounding (`:floor` / `:ceil` / `:round-half-up`) is defaulted. Both are
`:not-declared`, with `:taxlaw/choices` naming what the caller may state. **A
library that picks one is wrong by ¥1 per rate, on every invoice, forever, and
nothing in its output says so.**

The four rate pairs are read off the text as exact integers — 税抜 10/100 and
8/100, 税込 10/110 and 8/108 — and no float ever holds a tax figure. 消費税額等
already includes the 地方消費税 by its own definition (施行令 第四十五条), so
there is no separate local-tax step.

Two refusals worth their own line: a tax category the article does not name is
refused rather than treated as 標準, and **a negative subtotal is refused
rather than rounded backwards** — `quot` truncates toward zero, so `:floor` on
a negative rounds *up* and does it silently. 返還インボイス is governed
elsewhere and this article is not it. Meanwhile an empty invoice returns a real
`0`, distinguishable from the `nil` that means *could not answer*.

## 検索要件 — two regimes, and neither of them is a plain duty

電子帳簿保存法施行規則, read 2026-08-18 from `GET /api/2/law_data/410M50000040043`
(revision `410M50000040043_20250401_507M60000040028`). A 帳簿 and an electronic
transaction record are governed by **different provisions with different search
requirements**, and treating them as one rule is the easy mistake here.

| | 帳簿 | 電子取引 |
|---|---|---|
| provision | 規則第五条第五項第一号ハ | 規則第四条第一項 → 第二条第六項第五号 |
| 記録項目 | 取引年月日、取引金額及び取引先 | 取引年月日**その他の日付**、取引金額及び取引先 |
| when it bites | only to claim 法第八条第四項 (優良帳簿, the 過少申告加算税 reduction) | always, less two exemptions |
| sales ceiling | none | 五千万円以下 |

Both require the same three things of the search itself: each 記録項目 usable
as a condition, a range on date or amount, and two or more conditions combined.

### ⚠ The invoice figure is not the return's national tax

消費税額等 includes 地方消費税 by its own definition, so the 十 in 施行令
第七十条の十 is the **combined** rate. 消費税法 第二十九条 sets the **national**
rate at 百分の七・八 (軽減 百分の六・二四), read verbatim on 2026-08-18.

A caller reaching for `consumption-tax-amount` as 課税標準額に対する消費税額
(第四十五条第一項第二号) **overstates the national tax by 10/7.8 — about 28% —
on every return**, and the return still adds up.

Found by a consumer, not by this suite: `cloud-itonami-isco-4311` hit it while
building a 消費税申告 and handled it by never calling the function. That is
right for that repo and not enough for this one — the next consumer will not
have read their report. So `:rule/is-not` carries it **in the data**, with
第二十九条 quoted, and a test asserts the quote contains 百分の七・八 and does
*not* contain 百分の十.

There is no function here that computes a return figure at all: 積上げ vs
割戻し (施行令 第六十二条 / 第四十六条) is a taxpayer election this catalog has
not read, and the absence is asserted rather than left for a reader to notice.

### `requires-book-search?` does not answer `true`

It answers `:claiming-preferential-treatment`. Ordinary electronic book
preservation under 法第四条第一項 carries **no** search requirement at all —
search is what you do to claim a benefit. A caller that wanted a boolean and
got a keyword has learned the real shape: whether the rule bites depends on a
decision the holder makes and this library does not observe.

`book-search` accordingly has four answers, and `:taxlaw/adequate?` is **nil**
when the holder is not claiming the benefit — not `true`. *The rule does not
reach you* and *you satisfy the rule* are different facts, and a caller that
needs the second must not be handed the first wearing its clothes.

### The two electronic-transaction exemptions, and what they make undecidable

規則第四条第一項 carves them out in the same sentence that imports the
requirement:

- being able to respond to 電磁的記録の提示等の要求 drops ロ (range) and ハ
  (combination), leaving イ;
- that **and** either 基準期間における売上高が五千万円以下 or being able to
  produce 取引年月日その他の日付及び取引先ごとに整理された書面 drops the whole
  of 第五号.

Both turn on facts about the holder. So `electronic-transaction-search` returns
`:not-declared` when the on-demand capability is unstated — but **not** merely
because a fact is missing. If the records can be produced on demand and イ is
satisfied, the answer is settled and the sales figure never mattered; the wider
exemption could only have helped and nothing needed helping. It refuses only
where the missing fact is the one that decides, and even then it still reports
`:taxlaw/missing` — *refusing to conclude is not refusing to inform.*

Fifteen mutations cover this pair (`kbb --backend sci tools/mutate.cljk`). Two survived the
first run and both were real gaps: nothing had exercised the tier where the
holder says it **cannot** produce on demand, so neither "all three are then
required" nor "being small is not by itself an exemption" was measured.

## 所得税法 第百八十三条第一項 / 第百九十条 — read, then enforced

The withholding facet exists because a payroll actor needed it. Same standing
rule, so the articles were retrieved first, via
`GET /api/2/law_data/340AC0000000033` on 2026-08-17 (revision
`340AC0000000033_20260812_508AC0000000064`, newer than the pinned corpus
snapshot — recorded in `:retrieved-revision`).

```
第百八十三条  居住者に対し国内において第二十八条第一項（給与所得）に規定する
             給与等（以下この章において「給与等」という。）の支払をする者は、
             その支払の際、その給与等について所得税を徴収し、その徴収の日の
             属する月の翌月十日までに、これを国に納付しなければならない。
```

**The scope is recorded, not widened**, and here that does real work. The
article reaches a payer of 給与等 **居住者に対し** **国内において** — and
nothing else. So `withholding-obligation` has a fourth state:

```clojure
(taxlaw/withholding-obligation [:jp] {:payment-kind :employment-income
                                      :recipient-residency :resident
                                      :paid-in :domestic})
;; => {:taxlaw/coverage :checked :taxlaw/accounted-for? false
;;     :taxlaw/reason :withholding-not-recorded
;;     :taxlaw/provision "所得税法 第百八十三条第一項"
;;     :taxlaw/amount-checked? false ...}

(taxlaw/withholding-obligation [:jp] {:payment-kind :employment-income
                                      :recipient-residency :non-resident
                                      :income-tax-withheld 0})
;; => {:taxlaw/coverage :out-of-scope
;;     :taxlaw/read-provision "所得税法 第百八十三条第一項" ...}
;;    no :taxlaw/accounted-for? key — and this is NOT a finding that no
;;    withholding obligation exists. Other provisions govern payments to
;;    non-residents; none of them was read.
```

**Silence is not the article's exclusion.** A payment that declares
employment income but says nothing about residency or place stays `:checked`.
Only an explicit `:non-resident` / `:overseas` reaches `:out-of-scope`,
because absence of a declaration is the unchecked case and the unchecked case
never buys an exemption.

**Presence is checked; the amount never is.** The article says 徴収し —
collect *the* income tax on that 給与等. How much that is comes from
所得税法 別表第二 / 別表第五, which were **not** read, so every result carries
`:taxlaw/amount-checked? false`. A recorded amount must not read as a correct
one, and a recorded **zero** is accepted for the same reason: this library
did not read the tables that would say otherwise.

`year-end-adjustment` (第百九十条) has the same four states, and takes its
three exclusions verbatim off the text — declaration not filed, not the
year's final payment, annual 給与等 above **二千万円** (`:rule/income-ceiling-yen
20000000`, the number in the article). Its quote is the operative opening
sentence only; the 各号 set out how the year's tax is computed and are
omitted, which `catalog-verification` records as `:quote-is-partial?` with a
`:quote-omits` note.

### A quote assertion a paraphrase can satisfy is not evidence

Measured 2026-08-17. This test was green:

```clojure
(is (str/includes? (:rule/quote r) "その支払の際、その給与等について所得税を徴収し"))
```

…and it stayed green under a mutation that rewrote the duty as
「所得税を徴収**してもよく**」 — a *shall* turned into a *may* — because
徴収し is a prefix of 徴収してもよく. Both quote tests now pin the whole
operative clause through the 義務, and both mutations redden.

## What was verified, and what was not

`catalog-verification` records this as data, because the two are different
claims:

- **existence / status / title** — all 8 statutes, against the corpus.
- **content** — four claims. The qualified-invoice registration-number
  format, read off the 国税庁 publication site
  (「"T"を除く13桁の半角数字」); 電子帳簿保存法 第七条; and 所得税法
  第百八十三条第一項 / 第百九十条 — each retrieved from the e-Gov law API and
  quoted, the last one partially and saying so. Everything else cites the
  instrument **without** quoting article text and is marked
  `:rule/review :reachable-not-read`.

  The rule is: **a claim this library enforces must be read, not merely
  cited.** Every read claim backs a rule a governor acts on; the
  `:reachable-not-read` entries back nothing that holds anything.
  `every-enforced-rule-was-read-not-merely-cited` asserts the direction that
  matters — each enforced facet carries `:read-from-source`, a provision, a
  quote and a retrieval date — so the rule is a test rather than a paragraph.

Two candidates were **dropped rather than cited**, recorded in
`:catalog/rejected` with reasons: `asb.or.jp` (connection timed out) and
中小企業の会計に関する基本要領 (403 to a plain client; 200 only with a
spoofed browser User-Agent — a citation this repo's own gate could not
verify). An absent citation that leaves no trace looks identical to one
nobody thought of.

## Scope

Japan, and within Japan what a bookkeeping, invoicing or payroll actor
actually has to gate on: whether input-tax credit requires a qualified
invoice, how long records must be kept, whether an electronic transaction's
record must be preserved as such, and whether an employer paying employment
income must withhold income tax and settle the year's over/under at the final
payment.

**Not a tax engine.** It computes no tax, files nothing, and renders no
opinion — see `:taxlaw/amount-checked?`.

## Consumers

| repo | uses it for |
|---|---|
| [`cloud-itonami/cloud-itonami-isco-4311`](https://github.com/cloud-itonami/cloud-itonami-isco-4311) | the **receiving** side — a journal entry claiming 仕入税額控除 must cite a document carrying a valid registration number |
| [`cloud-itonami/tehai`](https://github.com/cloud-itonami/tehai) | the **issuing** side — an invoice drafted for a client in a qualified-invoice jurisdiction must carry the issuer's registration number, or its recipient cannot credit it |
| [`cloud-itonami/cloud-itonami-isco-4313`](https://github.com/cloud-itonami/cloud-itonami-isco-4313) | the **paying** side — a payroll run for an employer in a jurisdiction requiring withholding must account for the income tax withheld |

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 24 tests / 255 assertions, all green (`kbb -M:test`) |
| Dependencies | none |
| Citation check | `kbb --backend sci tools/verify_citations.cljk`, three-valued, demonstrated in both directions |

Apache-2.0.
