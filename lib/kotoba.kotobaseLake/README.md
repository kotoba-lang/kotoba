# kotobase-lake

**The catalog that lets kotobase accept any file, of any format, and still
find it again.**

The object plane below this (`kotobase-storage`'s `IObjectStore`) already
accepts anything — bytes are opaque to a store keyed by digest, so
format-agnosticism is free down there. What is not free is discovery. A store
you can only read by a CID you already hold is not a lake; it is a cache with
good manners.

This library is the metadata face. It turns an ingest into datoms on the
kotobase datom plane, so that every query surface over that plane — Datalog,
SQL (`org-postgresql-wire`), SPARQL, openCypher, GraphQL, Gremlin — can ask
what landed, who landed it, and what it claimed to be, without a second index
and without teaching any of them about files.

```clojure
(require '[kotobase.lake.catalog :as cat]
         '[kotobase.lake.sniff :as sniff])

(cat/admit {:cid "bafkreiabc…" :size 8_412_337
            :tenant "acme" :ingested-at "2026-08-04T09:00:00Z"
            :declared-media-type "text/csv" :filename "quarterly.csv"
            :source-uri "s3://drop/quarterly.csv"
            :prefix (sniff/prefix first-512-bytes)})
;; => {:admitted? true
;;     :object-id "obj:bafkreiabc…"
;;     :claim-id  "claim:acme|bafkreiabc…|2026-08-04T09:00:00Z"
;;     :declared-vs-observed :conflict          ; it is a PDF
;;     :observed {:format :pdf :media-type "application/pdf"}
;;     :quads #{…}}
```

Note what that did **not** do: it did not reject the file for being a PDF
wearing a `.csv` name. It wrote the contradiction down and admitted it.

## Three claims this library makes

### 1. Format is recorded, never enforced

`admit` refuses for exactly four reasons — no CID, no size, no tenant, no
ingest timestamp — and each one is *the record would be meaningless*, not *we
dislike these bytes*. There is no format on the refusal list and no allowlist
to add one to. Unknown format, zero-length body, absent filename, absent
media type, and a declared type that flatly contradicts the magic bytes all
admit.

The contradiction is the interesting case. It is recorded as
`:claim/declared-vs-observed "conflict"` and left for the reader to judge,
because refusing it would mean the lake turns away precisely the objects most
worth investigating. `cat/conflicting-claims` is how you find them later.

### 2. Two entities, and the cut between them is the whole design

| entity | id | holds | true for |
|---|---|---|---|
| object | `obj:<cid>` | `cid`, `size` | ever, for everyone |
| claim | `claim:<tenant>\|<cid>\|<ingested-at>` | declared type, filename, source URI, tenant, actor, **and what a sniffer observed** | one ingest event, by one observer |

`cid` and `size` are functions of the bytes alone. Nothing can change them,
and two tenants landing the same PDF land the *same object* — dedup is not a
feature added here, it is what content addressing already did.

Everything else is a function of the bytes **and an observer**. A declared
media type is a producer's assertion and may be false. A sniff result is this
library's assertion and changes when `sniff/rules` changes. Putting either on
the object entity would state as timeless something that is not, and would
let a classifier upgrade silently rewrite history. So they sit on the claim,
beside who claimed it and when, with `:claim/sniffer-version` recording which
classifier spoke — including when it spoke to say nothing.

Re-ingesting the same (tenant, CID, timestamp) produces byte-identical quads.
A retried upload or a re-run backfill does not accumulate a second
indistinguishable claim.

### 3. Parsing is deferred, and its failures are per-object

`kotobase.lake.reader` is where bytes finally get parsed, long after they were
accepted:

- **No reader is not a failure.** An unregistered type still leaves the object
  landed, catalogued, retrievable and joinable. A lake where an unparseable
  object is a *hole in the query* is a schema-on-write system that has not
  admitted it yet.
- **A decoder that throws does not fail the query.** Malformed input is the
  normal state of real data; `decode` catches, reports `:decoder-threw` with
  the message, and the scan continues over the objects that did parse.
- **The type is a hypothesis.** `candidate-types` yields declared first,
  observed second, and `decode` tries them in order. Neither was authoritative
  at write time and neither becomes authoritative here — what settles it is
  which decoder succeeded, reported as `:via`.

`reader/source` puts decoded rows and catalog facts in one
`datom.source/IPatternSource`, so a single query can ask for rows *and* their
provenance.

### …but decoding is not querying in place

`reader/decode` reads the whole object and returns all of its rows. That is
right for a 4 KB JSON blob and useless for a 40 GB Parquet file.
`kotobase.lake.tabular` is the other half: the object stays where it is and an
engine that already knows how to read it answers **one pattern at a time**.

A triple pattern turns out to be exactly what a columnar file is built to
serve — a projection and a filter:

| pattern | what the engine is asked for |
|---|---|
| `[?row "price" nil]` | the `price` column, and nothing else |
| `[?row "price" 42]` | …plus skip row groups whose min/max cannot contain 42 |
| `[nil nil nil]` | everything, honestly expensively |

**This namespace does not speak SQL.** `ITabularEngine` receives a *request*
(`{:columns :row :filters}`) and owns the dialect. So a predicate is checked
against the file's real columns before it can leave, values travel as data,
and a pattern — which is attacker-controlled in a multi-tenant deployment —
never becomes an identifier in a statement. It also makes the pushdown
testable without an engine: a fake that records requests proves the column was
projected, which an answer-only test cannot, because a source that reads every
row and filters in memory returns the identical set.

Two shapes, because **a table row is not a set of facts**:

- `wide-source` — one subject per row, one column per predicate. This is what
  real analytics files look like, and it can hold **at most one value per
  (subject, predicate)**. There is no cell for `alice likes tea` *and*
  `alice likes coffee`.
- `long-source` — one datom per row, in `s`/`p`/`o` columns. Expresses
  anything.

That limit is why `datom.source.conformance` runs against `long-source`: its
corpus contains exactly that multi-valued pair, so a wide table cannot
represent the suite. `wide-source` gets its own corpus, plus a test pinning
the limitation so it is documented rather than discovered.

### Getting one, for a catalogued object

`kotobase.lake.acquire/source-for` is where the catalog, the reader registry
and a tenant meet — and therefore the only place authorization can happen.

**A tenant with no holding gets the same answer as a nonexistent object.**
Exactly the rule the grant endpoint applies to reads (ADR-2608012600 D4), for
the same reason: objects are keyed globally by CID because dedup is what
content addressing already did, so tenant scope lives in `:holding/*` and
never in the key. "Exists, but not yours" is a sentence this system must not
say — CIDs are guessable for any content a caller can construct, so telling
the two apart turns the catalog into a membership oracle over every tenant's
data. The test asserts the two refusals are `=`, not merely both falsey; a
stray `:reason` key would leak exactly as well as a status code.

Authorization happens **at acquisition, not at every scan**. A source is
scanned many times by a planner; checking a tenant on every `-scan` would put
a policy decision on the hot path and produce a source that is *sometimes*
readable, which nothing downstream is built for.

Nothing is fetched before the gate: the handle carries `read-range` — a
capability — rather than bytes, and it reaches a reader only after the check
passes. An unauthorized caller costs one catalog lookup and no transfer.

Readers declare `:scan` or `:materialize`, and asking for a scanning reader
never yields a materializing one. Substituting silently would turn a range
read into a full download at exactly the moment the file got big enough to
matter.

A NULL cell yields **no datom**. EAV has no way to say "the value is nil", and
inventing one would make `[nil "note" nil]` return a row for every object that
has no note.

## What the sniffer will and will not tell you

`kotobase.lake.sniff` reads a bounded prefix, never parses, and returns `nil`
for anything it does not recognise. All three properties are structural:
`classify` takes the prefix, so there is no argument through which a caller
could hand it a gigabyte, and every rule is a byte comparison at a fixed
offset, so nothing here can throw on malformed input.

**`nil` is the normal answer, and that is the point.** CSV, TSV, JSON, NDJSON,
EDN, YAML, plain text and every log format have no magic bytes at all, at any
bound. This is not a gap to close later — it is the reason a declared media
type has to survive as a *claim* rather than be replaced by what was observed.
For a large share of real data, observation has nothing to say.

`prefix-bytes` is 512 rather than 64 so that `tar` (`ustar` at offset 257) is
reachable. ISO 9660 puts `CD001` at offset 32769 and is therefore
**undetectable here by construction** — stated rather than discovered, because
a bound whose cost is unknown is a bound nobody can evaluate. There is a test
asserting exactly this.

A compression or container format is not a disagreement with the payload's
type: a `:gzip` observation against a `text/csv` claim is scored `:enveloped`,
not `:conflict`. Scoring it as a mismatch would flag most of the compressed
data any lake ever receives.

## A table is N files

`kotobase.lake.table` is what makes this a lake rather than a very careful
single-file reader. A table is a set of objects under a prefix —
`region=east/part-0.parquet` and a thousand siblings — and a query over it
must not open a thousand footers to answer a question about three files.

**The manifest is datoms**, one attribute per column, on the same plane as
everything else:

```
member/table             table:acme|sales
member/object            obj:bafk…
member/rows              1000
member/partition/region  "east"
member/min/price         10
member/max/price         30
```

So "which files did this tenant land last week, and what is the price range in
them" is one query, not a directory walk plus a thousand reads. A blob of EDN
under a single attribute would be a manifest the query plane cannot see into.

**Pruning a file is the same operation as pruning a row group.** File
statistics have the shape `columnar.stats/skip?` already reads, so it is
literally the same function one level up — including the rule that matters
most: *absent statistics never permit a skip*. A manifest entry with no bounds
for a column means that file gets opened. Slower, and never a missing row.

**Partition columns are not in the files.** `region=east/part-0.parquet` has no
`region` column; the value is in the path. Two things follow:

1. A predicate on a partition column prunes **without opening anything** — no
   footer, no range read. The cheapest pruning in the system, and the reason
   partitioning exists.
2. A query that *asks for* a partition column is answered from the manifest,
   because no file contains it. Row counts are there and subjects derive from
   the object id, so those datoms are synthesised without a byte of any file.

**Members open lazily, per scan.** `open-member` is called for survivors only,
inside `-scan`. Constructing sources up front and merging them is the natural
shape and would defeat the whole namespace: the pruning would be perfect and
every file would already be open.

`members` returns a deterministic order. The manifest is a set, so without
sorting, the order files are opened in — and rows come back in, when a caller
imposes none — is whatever the collection iterates in today.

## One encoding, because two would look like a refusal

`admit` produces quads; a kotobase graph stores documents.
`kotobase.lake.docs` is that conversion, and it holds **both directions** —
`quads->docs` for the ingest path, `from-state` for the query path.

```clojure
(docs/admitted->docs (catalog/admit descriptor))
;; => {"obj:bafkrei…"           {"object/cid" "bafkrei…" "object/size" 2427}
;;     "claim:did:key:z…|baf…"  {"claim/tenant" "did:key:z…" …}}
```

They are one namespace because a writer and a reader that disagreed would
make `acquire/holds?` false for an object that is right there — and that is
byte-identical to the answer the gate gives someone who may not have it.
A misencoded catalog does not fail; it becomes invisible.

That argument only holds while both sides load the same code, so the
encoding lives here rather than beside either one. The reader's Worker
(`net-kotobase/lake`) re-exports it; the ingest path requires it directly.
`docs_test.cljc` asserts the end state rather than the round trip:
documents produced from an admission, hydrated back, open `acquire/holds?`
for the tenant that ingested and for nobody else — a round trip alone stays
green when both directions agree on an encoding the gate cannot read.

## Where this sits

```
query surfaces      Datalog · SQL · SPARQL · openCypher · GraphQL · Gremlin
                                        │
datom plane         datalog.index / arrangement ─── kotobase-lake (this repo)
                                        │                    catalog quads
kotobase-storage    IBlockStore(CID) · IRefStore(CAS) · IObjectStore(bytes)
                                        │
providers           S3/R2 · B2 · IPFS · PostgreSQL · SQLite · D1
```

The catalog lives on the datom plane; the bytes never do. That split is
`kotobase`'s, not this library's (ADR-2608039970: *"byte を datom 面に載せない"*)
— metadata is datoms, bodies go to the block and large-object planes. This
repo is what makes the metadata side rich enough that the split costs nothing
at query time.

Keep the catalog in **one ref**. Datalog join reach in kotobase is exactly one
ref chain (ADR-260726), so a catalog sharded across refs is a catalog you
cannot ask cross-object questions of — which is most of the questions.

## Scope, honestly

This library is the **catalog and the read-side seam**. It is not the transport.

Landing arbitrary files at arbitrary size also needs the object plane's G1
work in ADR-2608012600 (accepted, `com-junkawasaki/root`): presigned
direct-to-storage transfer instead of proxying through a Worker, per-tenant
scoping on the archive path, authenticated reads, and `REMOVE`. Until that
lands, the live `PUT /ipfs/:cid` path proxies the body and caps at 4 MiB, and
`GET /ipfs/:cid` is an unauthenticated gateway. Neither is a property of this
catalog, and neither is fixed by it.

Also out of scope on purpose: fetching bytes (a Promise on a Worker, not on
the JVM — a portable zero-dep library that owned both would force one shape on
the other), columnar layout, predicate pushdown, and partition statistics. See
the *base is the datom plane* discussion in ADR-2608039970 for why the
analytic-scan story is a separate question from the accept-anything one.

## Test

```sh
kbb -M:test                                              # JVM
kbb --backend sci --classpath "src:test:$(kbb -Spath)" test/run.cljk
kbb -M:cljs -m cljs.main --target node -m kotobase.lake.cljs-runner
kbb -M:lint
```

All of them, as CI runs them. The ClojureScript halves are not duplicates of
the JVM run, and that is not a theoretical claim: **the first green JVM run of
this suite was sitting on top of a cljs-only defect.** `(int \c)` is the code
point on the JVM but `(int "%")` is `0` in ClojureScript, so every ASCII magic
byte string compiled to all-zeros and matched any zero-filled buffer — a
512-byte tar fixture classified as PDF. 15 of 118 assertions failed under nbb
while the JVM reported none. The fix was to make `sniff/ascii-bytes` public,
because the same one-liner had been copied into the test helpers, which is how
it got two chances to be wrong and no chances to be caught.

nbb is the fast gate; `cljs.main` is the compiled one, and neither stands in
for the other.
