# importer

**The contract for keeping up with an external service** — the kernel behind
repositories like `cloud-itonami/m365-ingest`, in the sense a connector is not:
a connector answers one question now, an importer holds a cursor, a credential
and a corpus, and keeps answering after nobody asked.

Portable `.cljc` (JVM, ClojureScript, nbb, SCI). One dependency,
[`kotoba-lang/connector`](https://github.com/kotoba-lang/connector), and only
`importer.connector` uses it. No I/O: every function returns a value and the
host performs the request.

## Why it is not a connector

A connector is request-shaped and stateless, so N bots calling it N times is
fine — each call is independent. An importer is cursor-shaped and stateful. If
each bot linked this library and ran its own sync, one tenant would have N
cursors racing over one delta stream, N copies of the credential, and one
throttle budget split N ways — and every bot would report that it was up to
date, because from inside a cursor there is nothing to see.

So the shape is **one resident writer per tenant, and many readers**, which is
the same answer AGENTS.md gives about splitting a kotobase ref under write
load: put a single writer in front rather than getting good at losing races.

| | connector | importer |
|---|---|---|
| unit | one **API** | one **tenant grant** |
| state | none | cursor, watermark, phase |
| Google | 3 repos (Gmail, Drive, Calendar — 3 APIs, 1 client) | **1** actor, 3 cursor families |
| Microsoft | 1 repo (Graph is one API over many services) | **1** actor, a folder tree of deltas |

That asymmetry is the reason Google Workspace and Microsoft 365 are two
importers rather than one parameterised one, and it is measured rather than
assumed: the cursors genuinely differ in kind, not just in endpoint.

## The three failures this exists to prevent

Each is a namespace, not a comment.

**A cursor that moves past records the sink did not take.** The next delta call
starts after the new token, so no later run will ever mention those records
again. The hole is permanent, silent, and invisible to every check that asks
the importer how it is doing. `importer.cursor/advance` therefore does not take
a token — it takes the plan's count and the sink's own report, and refuses when
they disagree.

**A promotion from backfill to incremental before the backfill is exhausted.**
The importer starts following a delta from now, every subsequent run is green,
and everything older was never read. `importer.cursor/promote` refuses.

**An empty answer that cannot be told from an unimported mailbox.** A bot asks
`did the customer reply?`, gets `[]`, and acts. `importer.coverage/answer` is
the only constructor of a corpus result and there is no arity that takes rows
alone, so absence of rows is only ever evidence of absence where coverage says
the stream was read.

## Namespaces

| | |
|---|---|
| `importer.outcome` | `:synced` / `:failed` / `:unmeasured`, and no `ok?` |
| `importer.model` | source descriptor: streams, cursor styles, retention, governance |
| `importer.cursor` | the watermark and the rule for when it may move |
| `importer.plan` | one page as a value; `commit` is persist-then-move |
| `importer.receipt` | evidence, and `silent-hole?` computed from it alone |
| `importer.coverage` | what an answer covers, attached to the answer |
| `importer.schema` | one canonical shape for both providers |
| `importer.normalize` | addresses and provider-independent message identity |
| `importer.ports` | `ISink`, `IBlobs` — host-injected |
| `importer.connector` | the corpus as a read-only connector, with no provider scope |

## What the corpus connector buys structurally

`connector.validate` treats a scope declared on a provider that has no scope
mechanism as an **error**, and the corpus profile is `bearer`. So a `corpus_*`
tool **cannot** declare a Google or Microsoft scope — not by convention, but
because `connector.provider/provider` throws at load time. N bots read a
tenant's mail and none of them holds `gmail.readonly`.

## Confirm it

```bash
kbb --backend sci --classpath "src:test:../connector/src" run-tests.cljk   # 39 tests, 111 assertions
kbb --backend sci --classpath "src:../connector/src" mutate.cljk           # 12 mutations, ~3 min
```

`mutate.cljk` breaks each invariant in a scratch copy and requires the suite to
go red **and** to name the test that pins it. A green suite proves the code
passes its tests; it does not prove the tests would notice if the code stopped
being right.

It has already earned its keep. On its first run all mutations
"survived" — which was not eleven weak tests but one broken runner. Under nbb
`clojure.test/run-tests` returns `nil`, so the usual spelling

```clojure
(let [{:keys [fail error]} (t/run-tests 'ns)]
  (js/process.exit (if (pos? (+ fail error)) 1 0)))
```

destructures nil twice, adds them to zero, and exits **0 with failures on the
screen**. Measured 2026-08-30 against an unmodified `com-google-gmail`: four
failures, exit 0. The exit code here comes from the `:end-run-tests` report
hook instead.

## Related

- `kotoba-lang/connector` — the request-shaped plane this one sits beside
- `kotoba-lang/mail-archive` — the Gmail-only precedent for the blob store and
  the dual-backend query parity
- `cloud-itonami/m365-ingest`, `cloud-itonami/actor-google-workspace-ingest` —
  the actors that run this
- ADR-2608301500 — why the plane is shaped this way
