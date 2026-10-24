# com-google-snappy

**Snappy, raw format — compression and decompression in portable `.cljc`.**
No JNI, no native library.

```clojure
(require '[snappy.core :as snappy])

(snappy/compress   [104 101 108 108 111])  ; => raw snappy, vector of bytes
(snappy/decompress bytes)                  ; => the original
(snappy/decompress bytes start end 500)    ; with the length a caller was promised
```

Origin plane: snappy is Google's, so the repo is named for where it comes from
(`google.com` → `com-google-snappy`), not for what it does here.

## The compressor actually compresses

A snappy stream made only of literals is valid, decodes correctly, and is
worthless — the output is *larger* than the input by the size of the tags. It
is also the shape a first attempt naturally takes, and this workspace already
has one codec that stopped there: `org-ietf-zstd`'s `compress` writes a
conformant frame of raw blocks and says so in its own docstring.

So this has a match finder — a hash table over 4-byte sequences, the same
shape the reference implementation uses. Measured against `cramjam`, on the
suite in `test/fixtures/verify_with_cramjam.py`:

| input | bytes | ours | cramjam |
|---|---:|---:|---:|
| 500-byte run | 500 | **28** | 28 |
| repeated text | 1,760 | **128** | 128 |
| overlapping run | 600 | **35** | 35 |
| mixed | 680 | **436** | 466 |
| far match | 70,200 | **3,317** | 3,319 |
| incompressible | 5,000 | 5,005 | 5,005 |

Not tuned, and it does not need to be: columnar data is repetitive, and
finding matches at all is most of the win.

## Raw, not framed

Parquet compresses each page body on its own and records both sizes in the
page header, so the stream framing that carries checksums and chunk
boundaries has no job there. **Avro's snappy is the framed variant** with a
trailing big-endian CRC-32C, which this does not produce — `org-apache-avro`
refuses that codec by name rather than emitting a frame every conformant
reader rejects.

## The one subtlety

A copy element may reference bytes it is **currently producing** — an offset
smaller than the length, which is how snappy encodes a repeating run. So
decompression copies a byte at a time from the output as it grows. Slicing
the source range up front is the natural-looking implementation and it
silently truncates every run longer than its own period.

## Portability

`.cljc` on the JVM and ClojureScript. The hash function is written with
constants whose products stay under 2^53, so it is exact on a JavaScript
double as well as a JVM long — the reference implementation's 32-bit multiply
relies on overflow that is defined in C and lossy in JS.

## Tests, and the oracle

```
kbb -M:test
kbb --backend sci --classpath "src:test:$(kbb -Spath)" test/run.cljk
kbb -M:lint

python3 -m venv .venv && .venv/bin/pip install cramjam
.venv/bin/python test/fixtures/verify_with_cramjam.py
```

The Clojure tests round-trip. That proves the compressor and the decompressor
agree, which two halves of one misunderstanding also do — and snappy makes
that failure quiet, because a stream with a wrong copy offset still decodes,
into different bytes.

So the oracle is `cramjam` in **both** directions: it decompresses what we
write, and we decompress what it writes. They fail independently — a
malformed element we happen to read back correctly, versus an element shape
we never emit and cannot read. It has been shown to fail: adding one to every
copy offset makes cramjam reject five of the nine cases with
`corrupt input (expected valid offset ...)`.

Every case runs through one `kbb -M` invocation. Starting a JVM costs
about twenty seconds here, and per-case invocation turned a thirty-second
check into one that could not finish in ten minutes.

## License

Apache-2.0
