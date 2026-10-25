# kakeibo 家計簿

**Statement rows to a double-entry ledger, deterministically.** The expense
half of a personal-finance plane: normalize what a bank export says, refuse to
double-count it when windows overlap, categorize it by rule, and post it into
`kotoba-lang/banking`'s double-entry ledger.

Portable `.cljc`. No network, no filesystem, no clock, no model. Same inputs,
same output — which is what makes it honest to run as a deterministic
`tamaki exec` tick whose receipt means something.

```text
statement-fetch          kakeibo                          banking
(browser, handoff auth)  ─────────────────────────────    (double-entry)
   downloads a           rows → tx → dedup → category  →  balanced postings
   document                         ↘ rollup → report
```

## Where it sits

| repo | owns |
|---|---|
| [`statement-fetch`](https://github.com/kotoba-lang/statement-fetch) | getting the document out of a bank's web UI, where **authentication is a `:handoff` step that compiles to no argv** — the agent structurally cannot type a password |
| **`kakeibo`** | rows → canonical transactions → de-duplication → categories → ledger postings → rollups |
| [`banking`](https://github.com/kotoba-lang/banking) | the ledger contract: `entry`, `posting`, balanced-posting validation, minor-unit amounts |

## Use

```clojure
(require '[kakeibo.core :as kakeibo])

(kakeibo/ingest
  {:mapping  (read-edn "resources/mappings/jp-rakuten-bank.transaction-detail-ja.edn")
   :rows     [{"取引日" "2026/7/1" "入出金先内容" "まいばすスーパー"
               "入金金額" "" "出金金額" "3,240"}]
   :rules    (read-edn "resources/rules/example-categories.edn")
   :existing previous-transactions})   ; optional
```

`kakeibo.core` is the only namespace a consumer should require. The stage
namespaces stay public for testing, but an app assembling the pipeline itself
is how two consumers end up de-duplicating differently and disagreeing about
how much was spent.

As a tick:

```sh
kbb --backend sci --classpath "src:bin:resources:../banking/src" bin/kakeibo.cljk ingest \
  --mapping resources/mappings/jp-rakuten-bank.transaction-detail-ja.edn \
  --rules   resources/rules/example-categories.edn \
  --rows    data/2026-07.rows.edn \
  --existing out/previous.result.edn \
  --out     out/2026-07.result.edn \
  --budget  data/budget.edn --budget-period 2026-07
```

Exit 0 when the ingest is clean, **1 when any row was rejected or any
transaction was unpostable**, 2 on a usage or file error. A tick that partially
failed must not look like a success. `--existing` accepts either a transaction
vector or a whole previous `--out` result.

## The four properties that matter

**1. Money is exact.** Amounts are signed integers in the currency's minor
unit — the same convention `banking` and `card` use. Digits are folded with
`(+ (* 10 acc) d)`, so no float and no host interop is involved and the result
is identical on the JVM, in ClojureScript and under a Kotoba/Wasm host. A value
carrying more precision than the currency has (`12.345` in USD) is rejected,
never truncated.

**2. Nothing is dropped quietly.** Every count has a corresponding list:
`:kakeibo/read` reconciles against `:kakeibo/txs` + `:kakeibo/rejected` +
`:kakeibo/suppressed`, and each rejection carries its reason and the original
row. A statement line silently read as zero understates spending while nothing
surfaces the loss. A budgeted category with no observed transaction is
`:unobserved`, **never `0`** — a report that renders "not ingested yet"
identically to "spent nothing" reads as good news.

**3. Overlapping windows do not double-count.** This is the problem an
aggregator actually has to solve. You re-fetch the last 90 days every week, so
the same purchase arrives many times; but two identical coffees on the same day
really are two transactions. A transaction's key is the institution's own
reference when there is one, else
`account | date | amount | normalized description`; within a batch, same-key
transactions are numbered by occurrence; merging batches keeps **the highest
occurrence count any single batch reported, not the sum**. Two windows that each
saw two coffees yield two. A window that genuinely saw three yields three. A
later short window cannot erase what a longer one saw.

**4. No model runs in the money path.** Categories come from ordered rules
(first match wins) and every category is traceable to the `:rule/id` that
produced it. An unmatched transaction stays visibly `:uncategorized` and shows
up in `kakeibo.category/coverage` — the working list for the next rule — rather
than being assigned a plausible bucket. A language model asked to categorize a
statement line produces a confident answer with no way for anything downstream
to tell a correct one from an invented one, and these numbers land in a ledger.
An unknown predicate key in a rule fails closed, so a typo cannot silently
widen a rule to everything below it.

## What this does not do

- **It does not extract rows from a PDF.** `statement-fetch` downloads the
  document; turning a PDF into a table is a host capability. Feed `kakeibo`
  rows from a CSV export, or from whatever extracted the table.
- **It is not a MoneyForward-style connector.** There is no scraping, no
  credential handling, no account linking here. Retrieval lives in
  `statement-fetch`, and its authentication handoff exists precisely so that no
  code path leads from a flow definition to a keystroke carrying a credential.
- **`account-balances` reports movement, not balances.** kakeibo sees statement
  windows, not an account's whole history; calling the net of a window a
  "balance" would overstate what the data supports.
- **It does not know the calendar.** Dates are range-checked (month 1-12, day
  1-31) and normalized to ISO, but `2026-02-30` is not rejected here.
- Column *labels* in `resources/mappings/` are marked
  `:mapping/unverified true` until confirmed against a real export, following
  `statement-fetch`'s `:step/unverified` convention. `validate-mapping` can
  detect a missing column; it cannot detect a wrong label, and a wrong label
  produces plausible-looking transactions.

## Privacy

Statement exports and ingest output are personal financial data and are
gitignored (`/data/`, `/out/`, `*.statement.edn`, `*.ledger.edn`). What lives
in this repository is structure only: institution mappings carry column labels,
not account numbers, balances or payees; fixtures under `test/` are invented.

## Issue topology

[`roadmaps/itonami-kaikei.edn`](roadmaps/itonami-kaikei.edn) is the canonical
machine-readable roadmap. It owns issue state, dependency edges, projects,
outcomes, stable issue IDs, the Datomic/DataScript schema, and the Datalog
queries used to inspect the graph. Radicle issues are a public collaboration
projection of those entities; they do not own the dependency graph.

`kakeibo.topology/datoms` converts the roadmap into transaction data with
`:issue/blocked-by` lookup refs. `topological-order` fails closed on cycles or
missing blockers, while `runnable` returns only open nodes whose blockers are
`:integrated` or `:closed`. Tamaki reads this same file before assigning work,
so actor execution and graph visualization can share one topology rather than
maintaining parallel blocker lists.

## Test

```sh
npm test
# or
kbb --backend sci --classpath "src:test:resources:../banking/src" test/run_tests.cljk
```

nbb is the gate — ClojureScript-on-Node is this repository's first-class
runtime, per the workspace runtime priority (kotoba wasm > clojurewasm >
ClojureScript > nbb, JVM last). `kotoba-lang/banking` must be checked out as a
sibling directory; CI checks it out explicitly.
