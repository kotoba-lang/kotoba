# org-apache-iceberg

**Apache Iceberg v2 table metadata, written in portable `.cljc`.** No JVM
Iceberg library, no pyiceberg — the manifests, manifest lists and
`metadata.json` are produced from data.

```clojure
(require '[iceberg.schema :as s] '[iceberg.table :as table])

(def out
  (table/append {:location "s3://warehouse/prices"
                 :schema (s/schema [(s/field 1 "id" :string)
                                    (s/field 2 "n" :long)])
                 :data-files [{:file-path "s3://warehouse/prices/data/part-0.parquet"
                               :record-count 3 :file-size-bytes 700}]}))

(:files out)          ; {path bytes} — the manifest and the manifest list
(:metadata-json out)  ; the metadata.json to write, then point a catalog at
```

Origin plane: the format is Apache's, so the repo is named for where it comes
from (`iceberg.apache.org` → `org-apache-iceberg`), not for what it does here.

## Why this exists

A table format answers *which files is this table made of* without listing a
directory, and *which of them can this query skip* without opening one. This
workspace already had every piece except the answer: `org-apache-parquet`
writes data files, `columnar` executes over them, `tana` gives them a
content-addressed table plane. What was missing was the ability to say it in
**Iceberg's** words, which is what a Cloudflare R2 Data Catalog, DuckDB or
Spark will read.

Until 2026-08-29 that was blocked on one thing: Iceberg manifests are Avro
files, and `org-apache-avro` could only read. It can write now, which is what
made this repository possible.

`tana` is the other answer to the same question and is not superseded by this
one — it is content-addressed and signed, which Iceberg is not, and it is not
readable by anything outside this workspace, which Iceberg is. Choosing
between them is a deployment decision, not a correctness one.

## Field ids are the schema

Every field in an Iceberg schema carries an integer id, and readers resolve by
id rather than by name — that is what makes renaming a column metadata-only.
The ids in the manifest schemas are **assigned by the specification**:
`file_path` is 100, `record_count` is 103, `manifest_path` is 500. They are
not this repo's to choose, they are written into the Avro schema as `field-id`
attributes, and `test/iceberg/table_test.cljk` pins every one of them.

Changing `file_path` from 100 to 199 does not produce a corrupt file. It
produces a file that parses cleanly and that pyiceberg then refuses with
`100: file_path ... is non-optional, and not part of the file schema` —
measured, and the reason those pins exist.

## Two things a first attempt gets wrong, both measured

**An array must declare `element-id`.** The `partitions` array in a manifest
list carries `element-id: 508`. Without it a reader has no id for the element
type and refuses: `Cannot convert array-type, missing element-id`.

**A table whose data files carry no field ids needs a name mapping.** Parquet
written by an ordinary writer has column *names* and no Iceberg ids. Iceberg
resolves by id, finds none, and — correctly — refuses rather than matching by
position, which would silently swap two columns of the same type. The fix is
`schema.name-mapping.default`, which this sets from the schema unless the
caller overrides it.

## What it writes, and what it does not

```
writes
  metadata.json (v2)      schema, one unpartitioned spec, snapshots, refs
  manifest list (Avro)    one entry per manifest
  manifest (Avro)         one entry per data file, status ADDED
  append commits          carrying previous snapshots forward

does not write
  deletes / upserts       position and equality delete files
  partitioning            the spec is present and empty; no transforms
  schema evolution        one schema, no id reassignment
  column statistics       lower/upper bounds, value counts — see below
  the catalog step        this produces bytes and performs no I/O

absent, not stubbed. A call for one of these is missing, not silently a no-op.
```

## Statistics, when the caller has measured them

`data-file` takes `:lower-bounds`, `:upper-bounds`, `:null-counts`,
`:value-counts` and `:column-sizes`, keyed by Iceberg field id. All optional,
and **omitted means unknown, which is a truthful answer** — a reader handles it
by reading every file instead of pruning. A bound that is wrong in the
narrowing direction is not truthful: it deletes rows from a query's answer with
no error anywhere. So nothing here is estimated; the numbers come from a caller
that measured them, typically `parquet.footer/parse`, which reports per-chunk
statistics for the file it just wrote.

Bounds are compared **as bytes** by a reader, so `bound-bytes` is not an
implementation detail. Little-endian for the numerics, raw UTF-8 for strings.
Writing a long big-endian produces a file that parses, whose bounds decode to
enormous numbers, and whose pruning drops rows silently — measured: lower bound
1 came back as 72057594037927936.

**The catalog commit is not here.** An Iceberg commit is atomic because
something compare-and-sets the pointer to `metadata.json`; that is a REST call
against a catalog, needs credentials, and is the caller's. This namespace
stops at bytes, which is also why the part that must be exactly right is
testable without a network.

## Tests, and the oracle

```
kbb -M:test
kbb --backend sci --classpath "src:test:$(kbb -Spath)" test/run.cljk
kbb -M:lint

python3 -m venv .venv && .venv/bin/pip install "pyiceberg[pyarrow]"
.venv/bin/python test/fixtures/verify_with_pyiceberg.py
```

The Clojure tests pin structure. They cannot tell whether a real Iceberg
reader accepts the bytes, and round-tripping through this repo's own code
would only prove it agrees with itself — which two halves of one
misunderstanding also do.

So the oracle is pyiceberg reading a table this repo wrote: schema, snapshot,
`plan_files`, and the row values out of the Parquet the plan points at. The
data file is written by pyarrow on purpose, to keep this a test of the table
format layer rather than of two things at once. It has been shown to fail —
see the field-id paragraph above.

## License

Apache-2.0
