# bangou 番号

**番号法 — whether you may hold a 個人番号 at all.**

Jurisdiction-keyed like `kotoba-lang/taxlaw` and `kotoba-lang/worklaw`,
dependency-free for the same reason, and with one property neither of them
has.

## The API does not take a 個人番号

Every function answers a question about a **purpose**. None accepts a number.

A library with `(valid? my-number)` in it has been handed the thing 第二十条
is about, and a caller who reached for it has already collected. So the
number never crosses this boundary — and a test asserts it, by flattening
every public arglist and checking no argument is named for one.

**What that costs:** this library cannot tell you whether a number is
well-formed. The twelfth digit is a check digit and its formula is delegated
to a 総務省令 this catalog could not locate — it is in neither 番号法 nor its
施行令 (第八条 there is about 準法定事務 criteria). A check digit written from
memory would silently accept invalid numbers or reject valid ones, so there
is no shape check here at all. Recorded in `:catalog/not-read` with what was
searched and when.

## The rule

番号法 第二十条, read 2026-08-19 from the e-Gov law API v2:

> 何人も、前条各号のいずれかに該当する場合を除き、特定個人情報（他人の個人番号を
> 含むものに限る。）を収集し、又は保管してはならない。

**何人も** — anyone, not only an administrative organ. The default is
prohibition and the exceptions are 第十九条's seventeen 号. So the question is
never *may I store this?* but *which 号 am I acting under?*, and this library
will not answer the first without the second.

## Four answers, none of them an unqualified yes

| answer | meaning |
|---|---|
| `:none` | uncatalogued jurisdiction. Not *no rule* — *nobody looked*. |
| `:not-declared` | no 号 named. **This is the answer the library exists to give**: 第二十条 prohibits by default, so a caller who cannot name a 号 has its answer already. |
| `:unknown-ground` | a 号 was named and 第十九条 has no such number. Different from naming nothing. |
| `:ground-named` | the 号 exists, and is named back with `:bangou/conditions-not-read? true`. |

`:ground-named` is **not permission**. This catalog read the seventeen
headlines, not their conditions.

`permitted?` is therefore **false for every input**, and that is not a stub:
nothing this catalog holds can establish permission, so a boolean that ever
said true would be asserting what was declined. It exists so a caller does
not write its own truthy check over the map and get a different answer.

## Who needs this

`cloud-itonami-isco-4313` (payroll) files 源泉徴収票, which carries a
個人番号; `cloud-itonami-isco-4311` (bookkeeping) touches 支払調書. Both are
第十九条第二号 territory — 個人番号関係事務実施者 — and neither may reach for
this library and receive a yes.
