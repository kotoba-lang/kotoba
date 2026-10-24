# org-apache-avro

**An Avro Object Container File reader and writer in portable `.cljc`.** No
JNI, no native library, no code generation — the format is decoded from, and
encoded to, bytes.

```clojure
(require '[avro.file :as avro])

(avro/file-schema bytes)   ; the schema the file carries
(avro/schema-json bytes)   ; ...as the JSON text it is stored as
(avro/records bytes)       ; => [{"price" 10 "region" "east" ...} ...]
(avro/record-count bytes)  ; from block headers alone

(avro/write {:schema {"type" "record" "name" "Sale"
                      "fields" [{"name" "price" "type" "long"}]}
             :records [{"price" 10}]
             :codec "deflate"})   ; => the bytes of a container file
```

Origin plane: the format is Apache's, so the repo is named for where it comes
from (`avro.apache.org` → `org-apache-avro`), not for what it does here.

## Avro is self-describing, and that is the whole point

Unlike CSV, an Avro file **states its own field names and types**: the schema
travels as JSON inside the header. A reader needs no declared schema from the
caller, and none can disagree with the bytes.

That matters because **Avro writes no type tags**. The bytes of a `long` and
the bytes of a string's length are the same zigzag varint, and which one a
position holds is known only from the schema. A decoder that is wrong about
the schema does not fail — it produces plausible values and then
desynchronises. The only schema guaranteed to agree with the bytes is the one
shipped beside them, which is why `records` reads it from the file rather than
accepting one.

## It is `:materialize`, not `:scan`, and that is a property of the format

Avro is row-oriented. There is no footer, no per-column statistics, and no way
to read one column without reading the records around it. So it has nothing to
give `columnar`'s `IColumnSource` — **this repo does not depend on `columnar`
at all**, because depending on the engine would advertise a capability the
format does not have.

## The record count survives a codec this reader cannot undo

The Avro analogue of Parquet's statistics being readable from a file whose
pages are not, and the reason a partial reader earns its keep.

A block header is `(record-count, byte-size)` and is **never compressed**. So
`blocks` walks the file header-to-header using the declared sizes, verifying
every sync marker, without decompressing anything — and `record-count` and
`file-schema` answer on a file whose blocks `records` refuses.

`snappy.avro` is the fixture holding that line. Avro frames snappy with a
4-byte big-endian CRC-32C suffix that this workspace's raw-block snappy
decoder does not carry, so wiring it in would decode most blocks and corrupt
the checksum on all of them. Refused by name instead.

## The sync marker is checked

Every block ends with a copy of the header's 16-byte marker. A reader that
skips the comparison walks off the end of a truncated block and decodes the
next block's length as a record — **producing values**, which is the failure
mode worth one comparison per block to avoid. There is a test that flips a bit
in the last marker.

## Writing

`write` takes the schema as JSON — a string used verbatim, or data encoded
with `json.core/encode` — and **encodes the records with the same schema it
writes into the file**. That is the writing half of the property this format
is built around: a reader takes the schema from the bytes, so a writer and a
reader cannot be handed disagreeing ones.

Encoding has one decision decoding does not have to make. Reading a union is
told its branch by an index in the bytes; writing one has to choose from the
value, and Avro offers the writer no help — a union of bytes-or-array is two
schemas that both accept a sequence. `write` takes the first branch that
accepts the value and **refuses when none does**, rather than defaulting to
branch 0: a value written under the wrong branch produces a file that decodes
without error into the wrong thing, which is the encoder's version of the
desynchronisation described above. The union that appears in real data, and in
every Iceberg manifest, is the nullable one, which is never ambiguous.

Three other things it refuses rather than guesses: a `fixed` of the wrong
length (it would consume the next field's bytes on the way back in), a value
outside an `enum`'s symbols, and a **missing record field whose schema cannot
be null** — Avro has no way to say "absent", so filling one in would write a
value the caller never supplied. A missing field whose schema is nullable is
written as null, which is the one case where the format can say what happened.

Blocks default to 1000 records. Blocks are what let a reader walk or skip a
file without decoding it, so one giant block gives it nothing to walk. `:sync`
overrides the random marker for a caller that needs the same input to produce
the same bytes.

## What it decodes, and what it refuses by name

```
types
  null / boolean / int / long / float / double / bytes / string
  record (including self-referential)   union (the nullable case)
  array / map (including negative-count blocks, which carry a byte size)
  enum / fixed

codecs
  read    null / deflate (RAW, no gzip header) / zstandard
  write   null / deflate / zstandard — but zstandard does NOT compress:
          org-ietf-zstd writes conformant frames of raw blocks and has no
          encoder, so the codec name is available and the bytes are not
          smaller. Present so a caller who must emit that name can.

refused, by name
  snappy — Avro's CRC-32C framing, see above
  bzip2 / xz
  logical types are CARRIED but not applied: a timestamp stays the number it
  was written as, because turning it into a date would pick a representation
  this workspace has not chosen, and a reader that guesses is worse than one
  that hands back the number
```

An unknown *named* type in a schema throws rather than being treated as a
primitive — a schema referencing an undefined type would otherwise decode as
though the field were a string and consume the wrong bytes.

## Fixtures

Written by fastavro (`test/fixtures/generate.py`), and so are the
expectations: `ground-truth.edn` is emitted by the same script from the files
it just wrote. A fixture this repo generated itself would test the decoder
against its own misunderstanding — and for a format with no type tags, that
misunderstanding is invisible.

`multi-block.avro` uses a tiny sync interval on purpose: a single-block file
cannot tell a correct block walk from one that never moved.

The oracle points **both** ways. `generate.py` has fastavro write files this
repo reads. `verify_written.py` has this repo write files fastavro reads —
which is the direction that catches a nonconformant writer, because a
round-trip inside this repo proves only that the writer and reader agree with
each other, and two halves of one misunderstanding do that perfectly.

```
python3 -m venv .venv && .venv/bin/pip install fastavro
.venv/bin/python test/fixtures/verify_written.py
```

It runs the writer itself, so there is no fixture to go stale, and it has been
shown to fail: removing the zero terminator from an array block makes fastavro
refuse the file and the script exit 1.

## Portability, and 64-bit integers

Portable `.cljc`: the JVM and ClojureScript.

Avro writes `int` and `long` with the same encoding and distinguishes them
only in the schema, so a decoder cannot tell from the bytes which was meant.
Both produce a long, and on ClojureScript a magnitude past `MAX_SAFE_INTEGER`
is **refused rather than rounded** — the same rule `org-apache-parquet` and
`org-apache-arrow` apply.

The refusal lands differently here, though, and it is worth knowing before it
surprises you: **Avro decodes a record at a time**, so one out-of-range field
makes the *whole record* undecodable rather than just that field. Parquet and
Arrow read columns independently, so there only the offending column refuses.
That is a consequence of row-orientation, not a choice — and it is why
`big-ints.avro` is its own fixture instead of a column in the main one.

## Tests

```
kbb -M:test
kbb --backend sci --classpath "src:test:$(kbb -Spath)" test/run.cljk
kbb -M:cljs -m cljs.main --target node -m avro.cljs-runner
kbb -M:lint
```

## License

Apache-2.0.
