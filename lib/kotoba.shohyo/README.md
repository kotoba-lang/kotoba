# kotoba-shohyo 諸表

**A trial balance folded into 貸借対照表 and 損益計算書.**

諸表 is the set of financial statements — read the name as *the statements*.
Not `kotoba-lang/kessai` (決済, settlement): one is what you report, the
other is money moving.

## What it refuses to do

**It does not guess what an account is.**

`bookkeeping.trial-balance` says of itself that it proves arithmetic, not
classification: an account is whatever string an entry named. Turning
`"cash"` into an asset because it is spelled that way would put
classification back where nobody declared it. So a **chart is an argument**,
and an account missing from it is named rather than dropped.

That is the whole design:

> A balance sheet that omits an account still balances. It is wrong, it looks
> right, and nothing about the output says which.

```clojure
(shohyo/statements chart (assoc balances ["mystery" "JPY"] {:balance 42}))
;; => {:shohyo/coverage :incomplete
;;     :shohyo/unclassified ["mystery"]
;;     :shohyo/by-currency {...}}   ; the numbers are still there
(shohyo/complete? …) ;; => false
```

`:incomplete` still carries the figures — refusing to show anything helps
nobody — but a caller that renders without reading `:shohyo/coverage` is
rendering a statement short by known accounts.

## Where it sits

```text
bookkeeping.posting ─┐
kakeibo.ledger      ─┼─▶ kotoba.banking ─▶ trial balance ─▶ kotoba.shohyo
                     ┘      (postings)        (balances)      (BS / PL)
```

Balances arrive as plain `{[account currency] {:balance n}}` — what
`bookkeeping.trial-balance/balances` produces — so this folds a trial balance
from anything, and `banking` stays the double-entry contract rather than
becoming a reporting engine. Zero dependencies.

## Boundary with kanjō 勘定

`cloud-itonami/kanjo` reads statements a listed company **disclosed** (EDGAR /
EDINET XBRL) and normalizes JP-GAAP, US-GAAP and IFRS onto one canonical
vocabulary. This library goes the other way: it **produces** a statement from
your own ledger.

They meet at that vocabulary. A chart may tag an account with a `:concept`,
and the accepted concepts are exactly kanjō's 16 — so an internally-produced
statement and an externally-read filing are comparable line for line.

The vocabulary is **vendored** (`resources/kanjo-canonical-concepts.edn`,
from kanjo @ `9834c1ff`) rather than depended on: kanjō is an actor and this
is a library, and a library depending on an actor has the arrow backwards.
The copy is what makes the alignment machine-checked instead of a claim in
prose, and the workspace already runs a `verify-vendored-copies` detector
over copies that name their upstream.

`concept-ok?` returns **nil**, not false, when the vocabulary cannot be
loaded — *this concept is unknown* and *nobody could check* are different
answers.

## Sign convention

Balances arrive debit-positive, as a trial balance produces. Assets and
expenses are debit-normal and appear as given; liabilities, equity and
revenue are credit-normal and are presented negated, so a statement reads the
way an accountant expects. The raw figure stays on each line as `:balance`,
so nothing is lost.

## The accounting equation is checked, not assumed

資産 = 負債 + 純資産 + 当期純利益, per currency. A fold that quietly
disagreed with the identity would still print two tidy columns.
`out-of-balance` names the currency and the difference, because a boolean is
not enough for whoever has to fix it.

Currencies never mix. Netting them would hide, one layer up, exactly the bug
this plane already shipped once at the entry level — a cross-currency journal
entry that "balanced" because nobody compared currencies.

`complete?` requires **both** full classification and the equation, and is
false for an empty ledger: an empty balance sheet balances trivially and says
nothing. Conservative in the same way as `worklaw/compliant?` and
`taxlaw/supported?`.

## 会社計算規則 — the JP statement structure, read from the regulation

`kotoba.shohyo` is jurisdiction-neutral: five account types and the
accounting equation. `kotoba.shohyo.jp` adds what a Japanese statement
actually looks like, and none of it is convention —— 会社計算規則
(418M60000010013, revision `..._20250331_507M60000010014`, retrieved
2026-08-18 from the e-Gov law API) states it, and `jp/provisions` quotes
every article implemented.

| | |
|---|---|
| 第七十三条 | 貸借対照表 = 資産 / 負債 / 純資産 |
| 第七十四条 | 資産の部 = 流動資産 / 固定資産 / 繰延資産; 固定資産 **contains** 有形 / 無形 / 投資その他 |
| 第七十六条 | 純資産の部 = 株主資本 / 評価・換算差額等 / 株式引受権 / 新株予約権; 株主資本 **contains** six, 自己株式 as a **控除項目**; 資本剰余金 and 利益剰余金 each contain two; 評価・換算差額等 contains five, of which two are 連結貸借対照表に限る |
| 第八十八条 | 損益計算書 = the seven 区分, in the article's order |
| 第八十九〜九十二条 | the 段階利益 ladder: 売上総 → 営業 → 経常 → 税引前 |
| 第九十三条 | 法人税等 and 法人税等調整額, 「税引前当期純利益金額…の次に」 |
| 第九十四条 | 当期純損益金額 — the fifth rung, with the same 零未満 sign flip |

### Two more rules a naive implementation gets wrong

**自己株式 is a 控除項目** (第七十六条第二項後段: 「第五号に掲げる項目は、
控除項目とする」). A chart that adds it into 株主資本 overstates equity by
twice the treasury holding — and **the accounting equation still holds**, so
`out-of-balance` never sees it. `deduction?` answers this per section rather
than leaving it to the caller's memory.

**法人税等調整額 is signed** (第九十三条第一項第二号 calls it a 調整額). Every
other section total is a natural positive magnitude, but a 税効果 credit is a
negative charge and *raises* 当期純利益; forcing it positive moves the figure
by twice the adjustment.

### A container section is not a classification

第七十四条第二項, 第七十六条第二項, 第四項, 第五項 and 第七項 all say
区分／細分しなければならない. An account parked directly on 固定資産 or
株主資本 is therefore **not classified yet**, and `section-problems` says so.
`:subdivided-by` marks the containers whose subdivision the regulation
*mandates*, as distinct from 第七十六条第六項 and 第八項, which say
ことができる and are left alone.

`subsections` returns them **in the article's 号 order, not map order** —
`bs-sections` has more than eight entries, so it is a hash-map whose seq
order is unspecified, and a subdivision listed back in hash order reads as if
the regulation numbered it that way. Measured: the test caught exactly this
before the sort was added.

### The rule a naive implementation gets wrong

第八十九条第二項, repeated identically in 第九十条, 第九十一条 and 第九十二条:

> 前項の規定にかかわらず、売上総損益金額が零未満である場合には、零から
> 売上総損益金額を減じて得た額を売上総損失金額として表示しなければならない。

A negative 売上総損益金額 is **not** a negative 売上総利益金額. It is a
**positive 売上総損失金額** — a different label and a sign flip. Printing
`-500` under 売上総利益 is the obvious implementation and is not what the
article says, so each rung returns a `:label`, not only a number. The signed
figure survives in `:shohyo.jp/concepts`, keyed by kanjō's names, so nothing
is lost for a caller that wants to compare with a filing.

Zero is a profit, not a loss: 零未満 is the condition, and zero is not below
zero.

**A missing section is not zero.** An absent 売上原価 is an unstated cost,
and treating it as zero would report a gross profit equal to sales, so the
ladder answers `:not-declared` and names every section it lacks.

Measured, all seven mutations red: present a loss as a negative profit (7),
relabel without flipping the sign (2), treat zero as a loss (1), compute the
ladder with sections missing (1 — **by NPE rather than by assertion, which is
weaker evidence and is recorded as such**), add 営業外費用 instead of
subtracting it (2), let a section contradict its article's account type (1),
flatten 固定資産's three subdivisions into peers (2).

## IAS 1 — the IFRS statement structure, and what could and could not be read

`kotoba.shohyo.ifrs` does for IAS 1 *Presentation of Financial Statements*
what `kotoba.shohyo.jp` does for 会社計算規則. **The core stays neutral and
knows about neither**: the module is the caller's choice.

### What was read

IFRS standards are copyrighted and behind registration, so the honest
expectation was that none of this could be quoted. Both of these turned out
to be public, and both were fetched on 2026-08-18:

| | |
|---|---|
| IFRS Foundation, IAS 1 (issued 2021, Part A), PDF | HTTP **200**, 246 388 bytes, no DRM |
| Commission Regulation (EC) No 1126/2008, consolidated at 2023-01-01, CELEX `02008R1126-20230101`, via CELLAR | HTTP **200**, 11 362 077 bytes |

They agree word for word on every paragraph quoted, which is why
`provisions` marks all eight `:read-from-source`: IAS 1.31, 1.32, 1.54, 1.56,
1.57, 1.60, 1.61, 1.82.

Three things were fetched and **not** used, and `catalog-verification`
records each with what it returned, because a citation nobody attempted and
one that failed look identical afterwards:

- the human-facing `eur-lex.europa.eu/legal-content/…` URL — **HTTP 202,
  empty body**. That is an async renderer saying *not this way*, not *no such
  text*; the CELLAR resource URL served the same act in full.
- `02008R1126-20240101` — **404**. 2023-01-01 is the consolidation that exists.
- `32008R1126`, the **un**consolidated 1126/2008 — **HTTP 200**, read, and
  rejected. It carries IAS 1 as revised in *2003*, whose paragraph 54 is a
  sentence about financial institutions and whose balance-sheet list is
  paragraph 68. Quoting IAS 1.54 from it would have been the wrong text under
  the right number.

### What was not read, and what that costs

IAS 1.54 and 1.82 fix the scope of particular items by pointing at other
standards — IFRS 17, IFRS 9 §5.5, IFRS 5, IAS 12, IAS 41 — and none of those
were read. Neither were IAS 1.66–76, the criteria that decide whether an
asset actually *is* current.

taxlaw's rule applies and is enforced in the code path, not in prose:
`requirable?` refuses to let any item whose scope is `:reachable-not-read`
make a statement conformant. A chart may still declare one — dropping it
silently is the bug this library exists to refuse — and the answer is then
`:scope-not-read`, naming the item.

`unread-provisions` prints the whole list, because a reader who cannot see
what was unread has to take the conformant answer on trust.

### The rule a naive implementation gets wrong

IAS 1.54 lists twenty items, so the obvious implementation is a checklist.
The standard says twice that it is not one:

> **57** This Standard does not prescribe the order or format in which an
> entity presents items. Paragraph 54 simply lists items that are
> sufficiently different in nature or function to warrant separate
> presentation …
>
> **31** … An entity need not provide a specific disclosure required by an
> IFRS if the information resulting from that disclosure is not material.
> This is the case even if the IFRS contains a list of specific requirements
> or describes them as minimum requirements.

A checklist reports every entity on earth non-conformant for having no
biological assets. **Materiality is the entity's judgement, not this
library's**: an item is required when the chart declares an account for it,
and missing when no line in that currency's statement carries it. Missing
items are **named** with their paragraph letter, never counted.

### The second rule a naive implementation gets wrong

IAS 1.60 lets an entity present in order of liquidity instead of
current/non-current. The obvious reading is that this turns the whole
section off. IAS 1.61 opens by saying it does not:

> **61 Whichever method of presentation is adopted**, an entity shall
> disclose the amount expected to be recovered or settled after more than
> twelve months for each asset and liability line item that combines
> amounts …

So the twelve-month disclosure is checked under **both** methods, and only
the per-line classification is switched off by the exception. And an
*undeclared* method is not a pass: defaulting to `:liquidity` would switch a
check off by default, and defaulting to the other would invent the entity's
choice.

### Three answers, one of which is a pass

| `:shohyo.ifrs/coverage` | |
|---|---|
| `:unread` | no paragraph is `:read-from-source` — nothing may be asserted |
| `:not-declared` | no account declares an `:ias1/item` |
| `:checked` | answered per currency, and **still need not be conformant** |

`presented?` is false for all but the last, the way `shohyo/complete?`,
`taxlaw/supported?` and `worklaw/compliant?` are — the convenient boolean
gives the conservative answer, not the flattering one. `:unread` and
`:not-declared` carry no `:shohyo.ifrs/conformant?` key at all, so a caller
reaching past the boolean gets nil.

Also read and enforced: **IAS 1.56** (deferred tax is never current) and the
item/type conflicts that would put a payable in the asset half. And **IAS
1.82(e)** and **(f)–(i)** are kept in the table marked `:deleted` rather than
omitted — *the Board removed this* and *we never implemented this* are
different facts, and a list that drops them cannot say which.

**IAS 1.32 (offsetting) is quoted and enforces nothing**, recorded as such in
`catalog-verification`. Offsetting happens upstream of a trial balance and
leaves no trace in the data that arrives. A cited article that silently backs
no check reads exactly like one that does.

### The one thing the core learned

`statements` now carries each chart entry onto its line as `:declared`. The
core still knows five account types and an equation and no jurisdiction — it
forwards whatever the caller declared and lets a module recognise its own
key, so this is an extension point rather than a hook for one framework.

It has to travel on the **line**, not be re-joined from the chart: the
statement is per currency and the chart is not. An account declared for a
required item but carrying no balance in USD is absent from the USD statement
while still present in the chart, and a module that asked the chart would
call that statement whole.

## 連結会計 — a group, and the two things that balance while being wrong

`kotoba.shohyo.renketsu` folds a group's member statements into
連結貸借対照表 and 連結損益計算書. The core stays single-entity and knows
nothing about groups: **consolidation composes `statements` results**, and
the only thing the core learned is `fold-lines` (below).

The library's founding sentence, with a group in it:

> A consolidated balance sheet that omits a subsidiary still balances. So
> does one that fails to eliminate an intercompany receivable against its
> payable. Both are wrong, both look right, and a total finds neither.

Measured, in this repo's own test:

```clojure
(renketsu/consolidate (dissoc group :renketsu/intercompany))
;; the equation holds — :difference 0, :holds? true
;; consolidated assets 400, where the right answer is 250
;; :shohyo.renketsu/eliminations :unpaired
;;   [{:entity "P" :account "due-from-s"      :currency "JPY" :balance  100 …}
;;    {:entity "P" :account "investment-in-s" :currency "JPY" :balance   50 …}
;;    {:entity "S" :account "due-to-p"        :currency "JPY" :balance -100 …}]
```

### How an unmatched intercompany balance is made unmissable

A caller who declares *no* eliminations would otherwise pass cleanly: nothing
failed, because nothing was attempted. So the claim moves to where it can be
checked — **the chart** tags an account `:renketsu/counterparty`, the core
forwards the whole chart entry onto the line as `:declared` without knowing
what the key means, and any such line still standing after the declared pairs
are applied is named with its entity, currency and amount. Named, never
counted: `3 eliminations failed` sends someone hunting; `S / due-to-p / JPY /
−100` hands them the row.

The elimination test is that a pair's **debit-positive balances sum to zero**.
One test covers both shapes 第六十八条 contemplates — a receivable +100
against a payable −100, revenue −100 against an expense +100 — and it is also
what makes elimination safe: removing a set of lines whose debit-positive
balances sum to zero cannot move 資産 = 負債 + 純資産 + 当期純利益. A pair
that does *not* sum to zero is **not partially applied**; the residual is
named and both legs stay, because deciding which leg is right is a judgement
about the transaction and not something a trial balance answers.

### What was read, verbatim

Four texts from the e-Gov law API on 2026-08-18, each pinned to the revision
it was read at — `会社計算規則 第六十三条` alone does not say which of eleven
amendments:

| law | id | revision | bytes |
|---|---|---|---|
| 会社法 | 417AC0000000086 | `..._20260812_508AC0000000064` | 3 034 237 |
| 会社計算規則 | 418M60000010013 | `..._20250331_507M60000010014` | 857 066 |
| 会社法施行規則 | 418M60000010012 | `..._20240401_506M60000010011` | 1 461 146 |
| 連結財務諸表規則 | 351M50000040028 | `..._20260331_508M60000002028` | 949 702 |

Fifteen provisions are quoted in `provisions`, all `:read-from-source`. Ten
back a check; five are quoted and marked `:enforced? false`, because a cited
article that silently backs no check reads exactly like one that does.

### The thing everybody quotes that the regulation does not say

Every textbook says consolidation eliminates 内部取引高 and 債権債務.
**Neither phrase occurs in 会社計算規則.** Measured, with its denominator, so
that an absence nobody counted cannot be mistaken for one nobody looked for:

| | 内部取引 | 未実現 | 債権債務 |
|---|---|---|---|
| 会社計算規則, 180 articles | 0 | 0 | 0 |
| 連結財務諸表規則, 399 main articles | 0 | 0 | 1 |

That single hit is 第十五条の四の二 — a 関連当事者 **note**, not an
elimination rule. What the regulation actually says is 第六十八条, and only
投資と資本 is named; everything else is
「その他必要とされる連結会社相互間の項目の相殺消去」. The itemised vocabulary
is 企業会計基準第22号's, an ASBJ standard that is not on e-Gov and **was not
read** — which is why 未実現損益 is refused rather than approximated.

### The rule a naive implementation gets wrong

第六十三条第一項ただし書 and 第二項 are **two different modalities**:

> 一項 …ただし、次のいずれかに該当する子会社は、連結の範囲に**含めないものとする**。
>
> 二項 …重要性の乏しいものは、連結の範囲から**除くことができる**。

第一項's two grounds (支配が一時的 / 著しく誤らせるおそれ) are an instruction
**not to include**. 第二項's materiality ground is a **permission** to
exclude. One `:excludable?` flag for both lets a caller consolidate a
subsidiary the regulation forbids consolidating, and the statement balances
anyway. So `exclusion-grounds` carries `:modality`, and a mandatory ground
declared alongside `:included` is a scope problem.

### The second rule: control is not a percentage

会社法施行規則 第三条第三項 opens its own definition with an exception —
「（財務上又は事業上の関係からみて…支配していないことが明らかであると認められる
場合を除く。）」 — so a holding over 百分の五十 is not **sufficient**; and
第三号 reaches 「自己の計算において議決権を所有していない場合を含み」, i.e.
**zero** voting rights, where 自己所有等議決権数 exceeds half. So a holding is
not **necessary** either.

None of 緊密な関係, 同意している者, 支配する契約等 or
「支配していることが推測される事実」 is in a trial balance. **A library cannot
observe control.** `:renketsu/control` is a required declaration, a declared
`:renketsu/voting-rights` does not substitute for it (and is quoted back in
the problem detail, so nobody thinks it was overlooked), and an unstated scope
is its own answer.

### What it computes, and what it refuses

| computes | |
|---|---|
| the group's 貸借対照表 / 損益計算書 | per currency, from the members' folded lines |
| the accounting equation on the **group** | per currency; `out-of-balance` answers where |
| intercompany elimination | where the caller supplies the pairing and the legs offset |
| whether a 非支配株主持分 **arises** | exact integer comparison of a declared holding |
| whether 資本連結 left anything standing | any subsidiary equity line still there is named |

| refuses | why |
|---|---|
| deriving 連結の範囲 | 支配 is a determination (会社法施行規則 第三条第三項); the evidence is not in a trial balance |
| 未実現損益 | needs, per item still on hand, the price it moved at and the cost it moved from — a closing balance is neither. And 企業会計基準第22号 was not read |
| the **amount** of 非支配株主持分 | needs the subsidiary's equity at acquisition and the carrying amount of the investment |
| 資本連結 as a computation | same figures; it is offered as an ordinary declared pair instead, and a residual on one is named as のれん-or-NCI |
| currency translation | 第七十六条第九項第二号 presumes rates and states none; the rates are 「外貨建取引等会計処理基準」's, unread |
| 持分法 (第六十九条) | needs the investee's own statements |
| 連結株主資本等変動計算書 / 連結注記表 | 連結計算書類 is four documents (第六十一条第一項); this produces two |

Each refusal is a named reason, listed in `catalog/out-of-scope` rather than
left to be inferred from silence.

### Currencies still do not merge

The members' lines are grouped by currency **before** folding, so a group
reporting in JPY and USD gets two statements side by side and never one total.
`translation` then says so out loud and refuses conformance, rather than
inventing a rate. Asserted directly, because a sibling library shipped exactly
this bug the same day by summing ¥100,000 and $500 into 100500:

```clojure
(totals r "JPY")  ;; :assets 350
(totals r "USD")  ;; :assets 500
;; and no total anywhere is 850
```

A holding is `[numerator denominator]`, two integers, and **nothing divides**:
ClojureScript has no distinct float type — `1.0` reads as `1` — and money is
arithmetic.

### Four answers, one of which is a pass

| `:shohyo.renketsu/coverage` | |
|---|---|
| `:unread` | no provision is `:read-from-source` — nothing may be asserted |
| `:scope-not-declared` | no members; 連結の範囲 was never stated |
| `:unusable-scope` | the declaration does not parse, and no figures are produced |
| `:checked` | answered, per currency, and **still need not be conformant** |

`consolidated?` is false for all but the last, like `complete?`,
`presented?` and `taxlaw/supported?`. The first three carry no
`:shohyo.renketsu/conformant?` key at all.

**It is reachable.** An earlier draft refused 資本連結 unconditionally, which
made the boolean false for every group with a subsidiary in it — and a
predicate no input can turn true tells nobody anything, the same objection as
a check that never goes red. It is now answered from the data: no subsidiary
equity standing, every pair offsetting, one currency, wholly owned, members
complete, 未実現損益 addressed.

### The one thing the core learned

`fold-lines` — given already-classified lines in one currency, return
`{:bs :pl :totals :equation}`. `statements` now calls it, and so does the
group fold. **Not a special case for consolidation**: it knows nothing about
entities and will not say whether the lines handed to it belong together, the
way the chart is the caller's argument. Anything holding lines from more than
one fold — a group's members, a restated period, a segment — needs the same
totals and the same equation, and a second implementation of
資産 = 負債 + 純資産 + 当期純利益 is a second thing to drift.

### Mutations — `kotoba.shohyo.renketsu` and `fold-lines`

**This section covers only those.** The 24 for `kotoba.shohyo.ifrs` and the
14 + 7 for the core and `kotoba.shohyo.jp` are separate runs; a green table
here says nothing about them, and a reader who adds the numbers up is quoting
the wrong denominator.

Measured, 35 + 16 = **51 applied, 51 red, 0 survivors**. That was not the
first run. Two blind rounds, both written from the source without consulting
the tests, produced **three survivors, and all three were real**:

| survivor | what it exposed |
|---|---|
| `:ownership-denominator-may-be-zero` | `[0 0]` was refused by `(pos? d)` **and by nothing else** — the existing `[1 0]` case is caught by `numerator <= denominator` instead, so that clause had never been exercised. It matters: `wholly-owned?` answers **true** for `[0 0]`, being an exact integer identity, so a subsidiary declared `[0 0]` would have consolidated with no 非支配株主持分 arising from a holding that is not a holding. |
| `:the-nci-scan-includes-the-parent` | no test had ever put an `:renketsu/ownership` on the parent, so the `not= id parent` guard was unexercised. The guard is not an implementation detail: 非支配株主 under 第七十六条第一項第二号ホ are the minority **in a subsidiary**, and a parent's own outside shareholders are 株主資本 — every listed parent has them and none is a 非支配株主. |
| `:the-group-is-complete-with-unclassified-accounts` | the consolidated result is documented as being shaped like a single-entity one so `shohyo/complete?` composes onto it — and leaving its coverage `:complete` while a member was short survived the whole suite, because the group was still non-conformant for a *different* reason. A caller reaching for `complete?` instead of `consolidated?` would have been told a group short by a known account was whole. |

The other 48 died first time, including the ones that matter most:
`:currencies-are-folded-together` (which reddens exactly
`nothing-is-ever-added-across-currencies`, and nothing else — a precise kill,
not a broad one), `:eliminated-lines-are-not-removed`,
`:mandatory-exclusion-may-be-included`, `:a-residual-eliminates-anyway`,
`:unpaired-counterparty-lines-are-not-named`,
`:the-consolidated-equation-is-not-checked` and
`:an-unread-provision-still-asserts`.

### The portable runner

`test/run_portable.cljk` did not exist; the repo's portability was a claim
about a file extension. It now runs the whole suite under nbb and **exits
non-zero** — `cljs.test/run-tests` prints and returns, so a runner that only
printed would report a red suite with exit 0 to every shell, harness and gate
that reads one.

It also compares the suite list against `test/` on disk. The quiet way this
runner breaks is that someone adds `foo_test.cljc` and does not add it here:
the ClojureScript run silently stops covering it while `kbb -M:test`,
which discovers namespaces by scanning, keeps passing. The *other* direction —
a namespace listed but not loaded — is not guarded, because nbb throws
`No namespace: … found` before anything runs, and guarding the direction that
cannot happen while leaving the one that can is how a check becomes
decoration. Both live paths were demonstrated red before landing, as was the
`COULD NOT LOOK` answer for being run from the wrong directory, which is its
own exit rather than a clean scan.

## `kotoba.shohyo.genka` — 売上原価の内訳, and where the authority runs out

会社計算規則 names 売上原価 as one of the seven 区分 and says nothing about
what is inside it. A manufacturer's chart therefore has nowhere to put
期首材料棚卸高, 労務費 or 仕掛品. Measured 2026-08-20 against a live
MoneyForward chart for one 製造業 株式会社: **35 of 200 accounts across 10
categories** came back `:unknown-section` for exactly this reason.

`genka` is the one namespace here whose authority runs out partway down, and
it is built to say so:

| | backed by | in the code |
|---|---|---|
| the three 科目 of 売上原価, third a **控除科目** | 財務諸表等規則 第七十五条第一項 — **law, read** | `:genka/coverage :checked`, article quoted |
| that 当期製品製造原価 carries an attached 明細書 | 第七十五条第二項 — **law, read** | `:requires-schedule` |
| 材料費 / 労務費 / 経費 inside that 明細書 | 原価計算基準 (企業会計審議会 1962) — **not a 法令, not read** | `:source :observed`, `:genka/coverage :checked-arithmetic-only` |

材料費 and 労務費 occur **zero** times in the full text of 財務諸表等規則; the
three-way split is not in the regulation. So `cost-of-goods-manufactured`
produces the figure — refusing to produce it helps nobody — and carries
`:genka/authority` with `:shape-read? false` **in the returned map**, not in a
var a caller has to go and find. Every other number in this library is backed
by a quoted article, and a caller must be able to tell this one apart without
looking it up.

The 控除科目 trap appears twice more here. 第七十五条第一項第三号 makes
期末棚卸高 a deduction in the same sentence that names the other two items,
and 期末仕掛品棚卸高 and 他勘定振替高 sit the same way inside the 明細書.
Adding any of the three overstates the cost by twice that item — **and the
accounting equation still holds**, so `out-of-balance` never sees it. This is
the same shape as 自己株式 under 会社計算規則 第七十六条第二項.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 124 tests / 641 assertions green under **both** `kbb -M:test` and `kbb --backend sci --classpath src:test test/run_portable.cljk` |
| Dependencies | none |
| Mutations | 14 + 7 + 24 + 51 + 4 + 4 applied, all red |

Measured, every mutation red: dropping unclassified accounts silently (3),
returning an empty unclassified list (2), letting a typo'd account type
through (3), not checking the equation (3), aggregating across currencies
(17), answering `false` when the vocabulary is unloadable (1), presenting
credit-normal accounts unnegated (9).

> A first run of that harness printed `0 failures` seven times **without
> applying a single mutation** — a shell function that did not pass its
> arguments through. The mutation step is only worth anything if you can see
> that it ran; `applied` is now printed per mutation.

### Mutations — `kotoba.shohyo.ifrs` only

`kbb --backend sci tools/check-mutations.cljk` then `kbb --backend sci tools/mutate.cljk`. **This table
covers only the IFRS module and the one line it added to the core.** The
fourteen and seven mutations recorded above for the core and for
`kotoba.shohyo.jp` are separate runs; a green table here says nothing about
them.

Measured, 24 applied, **24 red, 0 survivors**. That was not the first run.
The first was **5 survivors and 1 unmeasured**, and every one was a real
finding:

| survivor | what it exposed |
|---|---|
| `:unread-paragraph-is-requirable` | every item in the table is `:read-from-source`, so `requirable?`'s read clause had never been exercised. Now downgraded under `with-redefs`. |
| `:liabilities-need-no-classification` | the test named *asset-or-liability* only ever dropped an **asset**'s classification. Now both, and both together. |
| `:not-declared-swallows-unverifiable` | a chart declaring **only** unread-scope items reported `:not-declared`, hiding the finding. *You tagged nothing* and *you tagged something nobody can verify* are different answers. |
| `:unread-list-counts-instead-of-naming` | the assertion was that `:affects` is non-empty, and `"1"` is non-empty — the same *counted, not named* failure this library refuses everywhere else. Written deliberately without looking at the tests, and it landed. |
| `:no-currency-is-a-pass` | **not a test gap.** The `(seq verdicts)` guard it targeted was unreachable — coverage is `:checked` only when a line declared an item, and lines live inside `by-currency`. The dead guard is gone and the id now targets the live invariant, that *every* currency must conform. |
| `:undeclared-method-passes` (unmeasured) | the replacement inserted a second `:holds?` into one map literal, so the file stopped **reading**. A mutation that breaks the reader demonstrates the reader. Re-aimed at a token that parses. |

Apache-2.0.
