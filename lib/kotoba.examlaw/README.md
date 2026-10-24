# kotoba-examlaw

**What a tax authority must have done before it may examine — by jurisdiction.**
A [kotoba-lang](https://github.com/kotoba-lang) capability library that answers
one question: in this jurisdiction, does the record establish what the law
requires before this examination step may be taken?

> **Not legal advice, and not a tax administration system.** This is a
> mechanism plus a small, cited rule set. It is deliberately incomplete, and
> its most important behaviour is what it does about that.

Sibling of [`kotoba-lang/taxlaw`](https://github.com/kotoba-lang/taxlaw) and
[`kotoba-lang/worklaw`](https://github.com/kotoba-lang/worklaw), and the same
shape on purpose — with one inversion that is the reason it is a separate
library rather than a namespace inside `taxlaw`.

## The invariant, inverted: absence is never authority

`taxlaw` and `worklaw` are keyed on a **private party's obligation**, so their
conservative direction is to withhold a pass: *absence is never sufficiency*.
This library is keyed on a **state power**. The conservative direction
therefore flips.

```clojure
(require '[kotoba.examlaw :as law])

(law/examination [:atlantis] :exam/field-visit
                 {:advance-notice-given? true :identification-carried? true})
;; => {:examlaw/coverage :none
;;     :examlaw/unchecked [[:atlantis]]
;;     :examlaw/reason :jurisdiction-not-in-catalog
;;     :examlaw/requirements []}
;;    no :examlaw/authority key at all — nobody read this country's procedure code

(law/authorized? *1)   ;; => false
```

A caller cannot read *we have not read this country's procedure code* as *the
officer may proceed*. `authorized?` is deliberately **not**
`(empty? (:examlaw/unmet result))`; a caller who reaches for the convenient
boolean gets the conservative answer rather than the flattering one.

Replacing `authorized?` with `(empty? unmet)` turns **39 assertions** red,
including the two tests that exist only to state this property. Measured, not
estimated — see the last section.

## This library never authorizes an exercise of examination power

That is a test, not a paragraph:

```clojure
(deftest never-authorizes-an-exercise-of-examination-power ...)
```

It builds the record most favourable to the authority that this library knows
how to read — every notice given, every safeguard honoured, no criminal
referral, ninety days where forty-five are needed — and asserts that
`authorized?` is **false** for every examination power in every catalogued
jurisdiction, and that `disposition` is
`:requires-official-determination`.

It holds because every examination power in every catalogued jurisdiction
begins with a condition the statute commits to a named official's own finding
— 国税通則法第七十四条の二's *調査について必要があるとき*, 26 U.S.C.
§7602(a)'s *for the purpose of ascertaining the correctness of any return*.
Those are marked `:req/kind :official-determination` and are never
machine-satisfiable. The library reports **what a human must decide**; it does
not decide it.

A property this strong is worth nothing if it is vacuous, so a second test
asserts `authorized?` *can* be true — for `:exam/close-examination`, which is
administrative rather than an exercise of power.

**The property earned itself immediately.** On first run it failed for
`[:us] :exam/contact-third-party`, because that action's requirement list had
the §7602(c) notice arithmetic but not §7602(a)'s purpose or §7602(c)(1)'s
*"unless there is an intent at the time such notice is issued"*. With a
perfect notice record the library said the contact could go ahead. Two
requirements were missing from the catalog and the property found them.

## Three-valued, because two values cannot say "the record does not say"

`:met` / `:unmet` / `:unverified` are three different answers and collapsing
the third into either of the others is a bug in a specific direction.

```clojure
(law/eval-clause [:all [:fact-true :a] [:fact-true :b]] {:a true})
;; => :unknown        NOT :no — nobody wrote down whether b happened
```

This bit during development. 26 U.S.C. §7605(b) says only one inspection per
taxable year *"unless the taxpayer requests otherwise or unless the Secretary
… notifies the taxpayer in writing"*. The first version of the test asserted
that a silent record makes a second inspection `:blocked`. That is the
stronger claim, and the evidence does not support it: a record that does not
mention the taxpayer's request is not a record that the taxpayer did not make
one. The library reports `:unverified` and `authorized?` stays false either
way — but only `:unmet` asserts that the law was broken, and this library
should not assert that from silence. The test was wrong; the code was right.

A record that *positively denies* both exceptions is a different matter, and
that one is `:blocked`.

## Four dispositions, and the fourth is not called `:permitted`

| | |
|---|---|
| `:no-catalog` | nothing here was checked |
| `:blocked` | a catalogued requirement is positively unmet |
| `:requires-official-determination` | a statute commits something to an official's finding, or the record does not establish a requirement |
| `:no-catalogued-requirement-unmet` | every catalogued requirement the record speaks to is satisfied |

The fourth is a statement about **this catalog**, which has read three
jurisdictions on fourteen facets. It is not a statement about the law, and it
is not a decision an official has made. Naming it `:permitted` would invite
exactly the reading it must not have.

## Jurisdictions are paths, not codes

`[:jp]`, `[:us]`, `[:eu]`, `[:eu :de]`, `[:eu :es]`. Rules attach at a level,
and a path is checked against **every** level that has them.

```clojure
(law/levels [:eu :de])          ;; => [[:eu] [:eu :de]]
```

A German field audit is governed by German law. The same officer sitting in a
Spanish joint audit is additionally capped by Directive 2011/16/EU, and
`examination` returns the union of both levels' requirements.

Two merge rules, and **a test found each of them by failing**:

- **A parent contributes only the facets it actually read.** The Union marks
  thirteen facets `:out-of-scope` because it has no examination power — that is
  a statement about the Union, not about Germany. Propagating it would report
  German re-examination law as deliberately out of scope when nobody has read
  it. So `:out-of-scope` and `:silent` stop at the level that declared them.
- **A child's `:silent` does not overwrite a parent's `:read`.** Germany's own
  entry is silent on cross-border because the Directive is where that law
  lives; the merged view must still read `:read`, sourced from `[:eu]`. A
  child's `:out-of-scope` *does* win, because that is a decision rather than an
  absence.

And a level that is not catalogued is unchecked **at its own level**:

```clojure
(law/examination [:eu :fr] :exam/field-visit {})
;; => {:examlaw/coverage :none :examlaw/unchecked [[:eu :fr]] …}
```

`[:eu]` being catalogued must never make France look covered.

## Five jurisdictions, and the pairs that point in opposite directions

| | read from source |
|---|---|
| `[:jp]` | 国税通則法 第74条の2・74条の7・74条の8・74条の9・74条の10・74条の11・74条の13・128条 |
| `[:us]` | 26 U.S.C. §7602(a)(b)(c)(d), §7605(a)(b), §7521(a)(b)(d) |
| `[:eu]` | Directive 2011/16/EU Art 11(1), 12(1), 12a(1), 12a(2) |
| `[:eu :de]` | Abgabenordnung §§ 193, 196, 197, 198, 199, 200(3), 201, 202 |
| `[:eu :es]` | Ley 58/2003 arts. 34.1.f, 141, 142.2, 147.2, 148.3, 150.1, 151.2, 151.3, 152.2, 156.1, 157.1, 157.2 |

Every quote was fetched from the official publisher on 2026-08-22 — e-Gov 法令
API for the Act (revision `337AC0000000066_20260624_508AC0000000046`), govinfo
for the 2023 edition of the Code, EUR-Lex for the 2024-01-01 consolidation,
gesetze-im-internet.de for the consolidated AO XML, and the BOE consolidated
XML of Ley 58/2003 (`fecha_actualizacion 20260626132602`) — and is a byte-exact
span of what that endpoint returned. A test asserts that
`:source/elided?` matches whether the quote actually contains an ellipsis, so
a silently shortened quote fails the build. It caught one on first run.

**A checker that learned one of these jurisdictions and answered for another
would be confidently wrong, four times:**

- **Criminal purpose.** 国税通則法第七十四条の八: the questioning-and-inspection
  power *「犯罪捜査のために認められたものと解してはならない」*. 26 U.S.C.
  §7602(b): the purposes *"include the purpose of inquiring into any offense
  connected with the administration or enforcement of the internal revenue
  laws."* Same fact — an officer inspecting books while suspecting an offense
  — **blocked in Japan, permitted in the United States.** (The US then blocks
  the *summons* once a Justice Department referral is in effect, §7602(d) —
  a different line in a different place.)
- **Re-examination.** §7605(b) makes one inspection per taxable year the
  default and requires a written notice to exceed it. 国税通則法第七十四条の十一
  第五項 permits further questioning *「新たに得られた情報に照らし非違があると
  認めるとき」* — an official's finding, not a written notice. **The defaults
  are opposite.**
- **Advance notice.** AO § 197(1) requires the audit order, the expected start
  and *die Namen der Prüfer* to be announced *angemessene Zeit vor Beginn*.
  LGT art 151.2: *"la inspección podrá personarse **sin previa comunicación**"*.
  Same continent, same Directive, opposite defaults — and for the identical
  conduct Germany has to reach for the § 197(1) exception while Spain needs
  nothing at all.
- **Who may be field-audited.** AO § 193 is an **admissibility gate**: a field
  audit is available against business, agricultural and professional taxpayers
  and § 147a cases, and against anyone else only on one of three enumerated
  conditions. Neither §7602(a) nor 74条の2 names a class of taxpayer at all —
  they gate on the officer's purpose or finding of necessity. A checker keyed
  on the Japanese or US shape would let a German audit of an ordinary employee
  through; `examlaw` returns `:blocked`.
- **Criminal purpose has a third answer.** 74条の8 forbids reading the power as
  a criminal-investigation power; §7602(b) says the opposite in as many words;
  AO § 201(2) does neither — it **reserves** the criminal assessment to a
  separate procedure and requires that the taxpayer be told so. Two data points
  looked like a binary. The third showed it was not.

### Four questions nobody had asked

Germany and Spain each answer something the first three jurisdictions were
never asked, so the facet universe grew from fourteen to eighteen:

| facet | who revealed it |
|---|---|
| `:exam/impartiality` | AO § 199(1) — *zugunsten wie zuungunsten des Steuerpflichtigen zu prüfen* |
| `:exam/duration-limit` | LGT art 150.1 — twelve months, extendable once by twelve, extension *motivado* |
| `:exam/premises-entry` | LGT art 142.2 and AO § 200(3) |
| `:exam/commencement-information` | LGT art 147.2, and it re-filed US §7521(b)(1), which had been wrongly shelved under `:exam/representation` |

**Every one of them made Japan and the United States score lower**, because
each is a question about them that nobody has answered. Coverage falling on new
knowledge is the correct direction; a denominator that only ever grew with the
numerator would be measuring effort rather than ignorance.

### Two more ways to not be a pass

- **`:conduct-duty`** — a duty on the officer's own conduct that no record can
  establish. AO § 199(1) is the case that forced it: examining *for and against*
  the taxpayer is a legal obligation, not a discretionary finding, and calling
  it `:official-determination` would have mislabelled it. With a complete German
  record it is the only thing left standing, and it holds `authorized?` at false.
- **`:unread-instrument`** — the statute routes the answer somewhere this catalog
  has not been. LGT art 142.2 sends a constitutionally protected domicile to
  art 113; 国税通則法第七十四条の九第一項第七号 sends the seventh notice item to
  政令. Both are reported, neither is `:unmet`, and neither is ever a pass.

The most valuable entries are absences that were searched for:

- **The United States has no general advance-notice-of-examination statute.**
  §7602(c) is notice of contacting *third parties*; §7521(b)(1) is an
  explanation given *"before or at an initial interview"* — and *at* is not
  *before*, and an interview is not the examination. Reading either as a
  general advance-notice rule would manufacture a taxpayer protection Congress
  did not enact. The facet is recorded `:read`, not `:silent`: someone looked.
- **国税通則法第七十四条の九第一項 lists seven items, not eleven.** Six are
  substantive and the seventh delegates to 政令. The figure quoted in practice
  counts items added by 国税通則法施行令第三十条の四, which this catalog has
  **not read**. Both figures are right about different instruments.
  `jp-notice-items` carries all three numbers and names the gap.
- **第百二十七条 is not the refusal penalty.** It punishes an official who
  leaks a secret learned on duty. Refusing an examination is 第百二十八条第二号.
  This was reached for first, from recollection, and it was wrong — so it is
  recorded, because the wrong article is the one a reader arrives with.
- **France and Italy are absent for retrieval reasons, not priority ones.** By
  economic size France should have been read before Spain. Légifrance returned
  **HTTP 403**; its bulk API needs a credential this workspace does not hold.
  Bot protection was not circumvented and no secondary source was substituted —
  one article paraphrased from a textbook would be indistinguishable in the data
  from the byte-exact spans around it. Normattiva was worse: **HTTP 200, 373 KB,
  and no law in it** — 9.5 KB of extractable site chrome. A pipeline that checks
  status codes would have recorded that as a successful fetch. It was caught by
  asserting on the presence of an article heading in the extracted text instead.

## The European Union has no power to examine anyone, and saying so is the entry

`[:eu]` is in the catalog and every examination action returns `:no-catalog`:

```clojure
(law/examination [:eu] :exam/field-visit {})
;; => {:examlaw/coverage :none :examlaw/reason :action-not-catalogued-here …}
```

Not because nobody looked — because someone looked and there is nothing to
read. Every cooperation article routes the actual power back to a Member
State: Article 11(1) *"in accordance with the procedural arrangements laid
down by the latter"*, Article 12a(2) *"in accordance with the laws and
procedural requirements of the Member State where the activities of a joint
audit take place."* The `:out-of-scope` entry carries that reason. Inventing
an EU-level examination power would be the most consequential error this
library could make.

Article 12a was also **measured, not inferred**: it is absent from the
2023-01-01 consolidation and present in the 2024-01-01 one. Both were fetched.
A catalog pinned to the wrong consolidation would report that joint audits do
not exist.

### Cross-border is the one place two jurisdictions must both be read

Article 12a(2): *"officials of another Member State shall not exercise any
powers that would exceed the scope of the powers granted to them under the
laws of their Member State."* The ceiling is the **lower** of two — so
`joint-audit` takes two jurisdictions and refuses if either is missing:

```clojure
(law/joint-audit [:eu :es] [:eu :fr] :exam/inspect-books facts)
;; => {:examlaw/coverage :none
;;     :examlaw/unchecked [[:eu :fr]]
;;     :examlaw/reason :cross-border-needs-both-jurisdictions}

(law/joint-audit [:eu :es] [:eu :de] :exam/inspect-books complete-record)
;; => {:examlaw/coverage :checked
;;     :examlaw/disposition :requires-official-determination}
```

Until Germany and Spain were read, **the second call could not return anything
but `:no-catalog`** — the Directive was catalogued and inert, because it is a
rule about two Member States and there were none. That is why the two of them
were read before larger economies outside the Union.

An intersection with an unread set is not the unread set. Reporting the host's
rules alone would silently drop the home-state cap that the Article exists to
impose. `:eu/home-power-ceiling` is marked `:req/kind :two-jurisdiction` so it
can never be satisfied from a single-jurisdiction call.

## How much of the world is this? Ask, and supply the denominator

`world-coverage` **requires a universe and has no default**, for the same
reason `taxlaw`'s does. The thing being measured is precisely what this
catalog does not know about, so the denominator has to come from outside it.

```clojure
(law/world-coverage #{[:jp] [:us] [:eu] [:de] [:fr] [:sg] [:br]})
(law/world-coverage #{[:jp] [:us] [:eu] [:eu :de] [:eu :es]
                      [:eu :fr] [:eu :it] [:gb] [:cn] [:in] [:br] [:kr]})
;; :examlaw/jurisdiction-fraction  [5 12]
;; :examlaw/facet-total            [43 216]   the figure that does not flatter
```

`43/216` is lower than `5/12`, and that is the point. The first draft of this
README wrote its facet total from memory and the number was wrong — which is
the same failure mode the library is built to prevent, one level up. Every
figure here is printed by the code.

| | `:read` | `:partly-read` | `:out-of-scope` | `:silent` | of |
|---|---|---|---|---|---|
| `[:jp]` | 11 | 1 | 0 | 6 | 18 |
| `[:us]` | 8 | 0 | 2 | 8 | 18 |
| `[:eu]` | 1 | 0 | 13 | 4 | 18 |
| `[:eu :de]` | 10 | 2 | 0 | 6 | 18 |
| `[:eu :es]` | 8 | 2 | 2 | 6 | 18 |

`[:eu :de]`'s tenth `:read` facet is `:exam/cross-border`, supplied by `[:eu]`;
`:facet/from` on each entry records which level it came from.
 `depth` partitions the
fourteen facets per jurisdiction into `:read`, `:partly-read`, `:out-of-scope`
and `:silent`, and a test asserts they sum to `:of` for every jurisdiction.

**`:silent` is a facet nobody has thought about**; `:out-of-scope` is one left
out on purpose, with the reason recorded. From every other view they are
identical — both answer `:no-catalog`, correctly, because neither is a pass.
This is the view that tells them apart, and the difference is whether there is
a decision behind the absence. United States closing procedure is `:silent`.
United States notice contents is `:out-of-scope`, because there is no general
advance notice for it to have contents.

A test makes this bidirectional: every facet marked `:out-of-scope` must
resolve to a recorded reason, and every recorded reason must belong to a facet
actually marked `:out-of-scope`. It found a defect on first run — `[:jp]`
carried a reason for `:exam/cross-border` saying the treaty instruments had
*not been read*, which is a silent facet, not a deliberate exclusion. The
reason moved to a `:facet/note` and the facet stayed `:silent`. `[:eu]`'s
thirteen out-of-scope facets share one `:out-of-scope-default` rather than
thirteen copies of the same sentence, and the test resolves through it.

`kotoba-lang/iso3166` is one place to get a universe of 193. This library does
**not** depend on it, deliberately: a library that shipped its own denominator
would be answering the one question the caller has to ask.

## What this is not

- **Not a tax administration system, and not a case-management system.** It
  selects nobody, opens nothing, assesses nothing and issues nothing. It has
  no store, no clock and no network.
- **Not a targeting or audit-selection tool.** There is no facility for
  scoring, ranking or shortlisting taxpayers, and adding one would require
  editing this repository — no input can reach such a thing at runtime.
- **Not legal advice.** Every claim here cites an instrument that can be
  fetched and checked. Route licensed work to counsel.

The nearest neighbours in this workspace, and the boundary with each:
`kotoba-lang/taxlaw` answers what a *taxpayer's document* must carry;
`cloud-itonami/cloud-itonami-isco-3352` is a tax-office documentation and
logistics robot with a structural no-enforcement-authority guarantee. This
library is the third thing: the *procedural preconditions on the state's own
power*, as a catalog, with a denominator.

## Run the tests

```bash
kbb --backend sci --classpath "src:test" run-tests.cljk    # primary
kbb -M:test                              # JVM compat path, same file
```

24 tests, 670 assertions. The suite has been shown to fail in both directions,
by actually breaking the library and reading the count:

| change | result |
|---|---|
| unmodified | 0 failures |
| `authorized?` → `(empty? (:examlaw/unmet result))` | **39 failures** |
| `eval-clause` `:fact-true` on an absent key → `:no` | **14 failures** |
| a child's `:silent` overwrites a parent's `:read` | **1 failure** |
| only the most specific level supplies requirements | **2 failures** |
| `:unread-instrument` removed from `disposition` | **2 failures** |
| `:conduct-duty` removed from `disposition` | **3 failures** |
| `:two-jurisdiction` removed from `disposition` | **3 failures** |

Every break was reverted and the suite returns to 0.

**The last three rows are here because the first attempt at them stayed
green.** Every catalogued examination action carries several
non-machine-satisfiable requirements at once, so deleting any single bucket
from `disposition` changed no catalog-driven answer. The buckets are now
tested one at a time against a synthetic result, which is the only way to see
which one did the work. A test that has only ever been green is not evidence
that it discriminates.
