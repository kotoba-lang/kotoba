# org-apache-arrow

**An Arrow IPC reader and writer in portable `.cljc`**, providing
[`columnar`](https://github.com/kotoba-lang/columnar)'s `IColumnSource`. No
Rust, no JNI, no native library, no generated FlatBuffers bindings — the
format is decoded from, and encoded to, bytes.

```clojure
(require '[arrow.source :as ar] '[arrow.write :as aw] '[columnar.plan :as plan])

(plan/scan (ar/open bytes) {:columns ["price"] :predicates [[:= "price" 120]]})
;; => {:rows [{::plan/row 4 "price" 120}] :chunks-read 3 :chunks-skipped 0}

;; …and back out again: a query result becomes an object other systems open
(aw/of-columns (aw/columns-of-rows [["price" :int64]] rows))
;; => Arrow IPC file bytes
```

Origin plane: the format is Apache's, so the repo is named for where it comes
from (`arrow.apache.org` → `org-apache-arrow`), not for what it does here.

## Why this repo exists

`columnar` was written as the seam a file format plugs into, and until now
exactly one format was plugged into it. With a sample size of one, *"the seam
is not Parquet-shaped"* was a claim about code that had never been asked the
question.

Arrow IPC is the right second format precisely because it is **not** a second
Parquet. Its metadata is FlatBuffers rather than Thrift compact, and its data
layer is *simpler* than Parquet's — uncompressed by default, no encoding
layer, just a validity bitmap beside a values buffer. So the pressure it puts
on the seam comes from a different direction.

**The answer: `columnar` did not change.** The protocol was implemented as
written. What did change is one thing, described below.

## What Arrow records, and what it does not

| question | Parquet | Arrow IPC |
|---|---|---|
| rows per chunk | footer | batch metadata |
| nulls per column chunk | footer statistics | `FieldNode.null_count` |
| **min / max per column chunk** | footer statistics | **not recorded** |

Arrow has no column statistics. That is a property of the format, not a gap in
this reader, and it is the most interesting thing about plugging it in:
`columnar.source` documents `-chunk-stats` returning `nil`-or-unbounded as
*"the source makes no claim"*, and `columnar.stats` states as its first rule
that **absent statistics never permit a skip**. Both were written before there
was a format that exercised them.

So an Arrow source reports `:rows` and `:nulls` and no bounds, and the
consequences are visible rather than hidden:

```clojure
(agg/aggregate s {:agg :count})            ;; {:value 9 :from :statistics :read 0}
(agg/aggregate s {:agg :count-non-null …}) ;; {:value 2 :from :statistics :read 0}
(agg/aggregate s {:agg :max :column "price"})
;; {:value 230 :from :scan :read 3}   <- Parquet answers this with :read 0
```

A format that records less plugs in by **reporting** less, not by growing a
special case. That is the property this repo was written to check.

### The one thing that did move

`IByteSource` — the range-reading seam — lived in `parquet.bytes`. A second
format needing the identical protocol made it shared rather than Parquet's, so
it is now **`columnar.bytes`**, beside `IColumnSource`, which is the other
half of the same seam. Two things that can substitute for each other are one
thing (ADR-2607299700).

## Metadata survives buffers this reader cannot decode

The single most useful property, and the same one `org-apache-parquet` holds
for statistics. Body compression is a property of the **buffers**; batch
lengths and null counts live in the **metadata**, which is never compressed.

So an lz4-compressed file still answers `count`, still answers
`count-non-null`, and still prunes all-null chunks, reading nothing but
message headers — while `-read-column` refuses it and **names the codec**.

`lz4.arrow` is the fixture that holds that line. It replaced `compressed.arrow`
(zstd) when zstd became decodable, for the reason `org-apache-parquet` keeps
`delta.parquet`: when a codec lands, the file that had been proving "metadata
is readable from what we cannot decode" quietly stops proving it, and the
property needs a witness the reader still cannot undo.

**ZSTD body compression decodes**, through the same `org-ietf-zstd` the Parquet
reader uses. Arrow compresses per *buffer* rather than per body, each with an
int64 length prefix — and a prefix of `-1` means that buffer was stored raw
because compressing would have made it bigger, which is the normal path for
small validity and offsets buffers.

## What it decodes, and what it refuses by name

```
decoded
  int8 / int16 / int32 / int64      uint8 / uint16 / uint32 / uint64
  float32 / float64                 bool (bit-packed)
  utf8 / large_utf8                 binary / large_binary
  null
  multiple record batches, each a prunable chunk
  the pre-0.15 envelope (no continuation marker) as well as the current one

refused, by name
  body compression:  lz4_frame  (zstd decodes, through org-ietf-zstd)
  dictionary-encoded fields
  nested:  list / large_list / struct / map / union / fixed_size_list
           run-end-encoded, and the view types
  decimal / date / time / timestamp / interval / duration
```

A refused *type* still lists in the schema — refusing to name a file's columns
is a worse failure than refusing to decode one of them — and a refused *layout*
throws when the source is opened rather than when the bad column is asked for,
because an unknown buffer count desynchronises every column after it.

## Writing

`arrow.write` takes `columnar.vector` columns — the engine's currency, so a
`plan/scan` result materialises without transposing through rows — and emits
IPC file bytes. Each batch becomes one record batch, which is one prunable
chunk when the result is read back.

```clojure
(aw/file {:fields  [{:name "price" :type :int64 :nullable? true}]
          :batches [[(cvec/column :int64 [1 2 3])]
                    [(cvec/column :int64 [4 5 6])]]})
```

`arrow.build` is the FlatBuffers **builder** underneath, and it is much the
harder direction: a table points at its vtable with a negative offset and a
vector stores its length before its elements, so the buffer is built from the
end toward the front. The working representation is therefore a reversed
accumulator where "offset" means distance from the end.

### Our own tests cannot prove the output is valid Arrow

This matters enough to state plainly. `arrow.writer-test` shares a code base
with the reader, so the failures that matter most — a wrong vtable, a body
length that forgot its padding, a buffer that is not 8-byte aligned — would
round-trip through it **cleanly**, because both halves would share the
misunderstanding.

So CI writes files with `arrow.emit-for-python` and hands them to pyarrow's
`validate(full=True)`, which walks offsets and buffer bounds rather than
trusting the metadata. Six cases: multi-column with every supported type,
multi-batch, all-null, no-nulls (the zero-length validity buffer), an empty
batch, and unicode. That step is the writer's real correctness gate; the
in-repo suite covers values, nulls, chunking and materialisation.

## Reads are ranges

Opening a file costs the footer: a 10-byte tail, then the footer FlatBuffer it
points at. Every batch offset, batch row count and column name comes out of
that, so pruning a 40 GB object costs the footer and nothing more.

Reading a column fetches that column's buffers at their own offsets and
lengths — not the batch body. There is a test that asserts it by metering the
transport, because an assertion on the *answer* cannot tell a projected read
apart from reading everything and slicing.

### Borrowed buffers: zero CPU materialisation, one GPU upload

`arrow.source/column-buffer-views` exposes an uncompressed projected column's
validity/value or validity/offset/data buffers as bounded
`columnar.bytes/IByteView` values. A vector, direct JVM `ByteBuffer`, or
JavaScript `Uint8Array` keeps the same backing storage while Arrow narrows it;
row values are not decoded into Clojure collections. A CPU vectorized host can
consume the native view directly, and a GPU host can perform its required
device upload without an intermediate Arrow-to-row-to-tensor copy.

The boundary is intentionally precise: network ingress may own a response
buffer, GPU upload is normally one host-to-device copy, and compressed Arrow
buffers require a decompression allocation. The borrowed-buffer API rejects
compressed batches rather than calling that path zero-copy.

## Portability, and 64-bit integers

Portable `.cljc`: the JVM and ClojureScript, with the Worker (cljs) being the
runtime this actually deploys on.

`arrow.flatbuffers/i64` is **exact or nothing**. The obvious accumulation with
`Math/pow` puts the top two bytes of a 64-bit value past double precision and
returns a quietly rounded answer — on the JVM as well as in ClojureScript. So
the JVM path is exact integer arithmetic, and the ClojureScript path *refuses*
a magnitude it cannot represent rather than rounding it. A reader that returns
a plausible wrong number is worse than one that says it cannot represent this
value, because nothing downstream can tell.

The fixtures carry `2**62 + 1` and a negative int64 for exactly this reason.

## Fixtures

Written by pyarrow (`test/fixtures/generate.py`), and so are the expectations:
`ground-truth.edn` is emitted by the same script from the files it just wrote.
A fixture this repo generated itself would test the decoder against its own
misunderstanding of the format, and expectations transcribed by hand would
drift from the fixtures the first time either was regenerated.

The fixture table is deliberately **the same nine rows, four columns and three
batch boundaries** that `org-apache-parquet` uses. Both readers are asserted
against the same reference writer's values, so the two formats' decoded output
is comparable without either repo depending on the other.

```
python3 -m venv .venv && .venv/bin/pip install pyarrow
.venv/bin/python test/fixtures/generate.py
```

CI regenerates them and fails on a diff: the fixtures must stay byte-identical
to what the reference writer produces, or the suite is testing this repo
against its own past misunderstanding rather than against Arrow.

## Tests

```
kbb -M:test                                             # JVM
kbb --backend sci --classpath "src:test:$(kbb -Spath)" test/run.cljk  # cljs, interpreted
kbb -M:cljs -m cljs.main --target node -m arrow.cljs-runner
kbb -M:lint
```

The ClojureScript runs are not a duplicate of the JVM one: the int64 refusal is
a claim only they can check, and `test/arrow/lake_e2e_test.cljk` is JVM-only on
purpose.

`lake_e2e_test` runs the whole chain — catalog → authorization → triple
pattern → buffer range — over a real Arrow file, against `kotobase-lake` as a
test-only dependency. It is the end that can prove the lake's scan seam took a
second format without changing, including the part that is not free: the
identical query that skips two of three row groups on Parquet reads all three
record batches here, and the test asserts that rather than glossing it.

## License

Apache-2.0.
