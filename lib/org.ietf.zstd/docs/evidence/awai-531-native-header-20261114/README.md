# Native Zstd frame-header admission, 2026-11-14 JST

This is a bounded **header parser**, not decompression, Forest index access,
Native filesystem I/O, a complete Zstd profile, or production qualification.
The field sizes, little-endian encoding and window formula come from
[RFC 8878 section 3.1.1.1](https://www.rfc-editor.org/rfc/rfc8878.html#section-3.1.1.1).
The caller supplies maximum window and declared content size; an unknown content
size is reported as -1 and must still be bounded by a future decoder. Any
explicit dictionary-ID field, even ID zero, is conservatively rejected to match
this repository's existing `zstd.core` implementation. Checksums are reported,
not verified by this header-only unit.

The first six bytes of Awai's pinned Forest fixture (SHA-256
`87a1d2773c099ef49af8fc7b9b00b43123a4e83ab1bc3f1f2b3fca0278fb62df`)
are `28 b5 2f fd 00 58`: the parser reports a 2,097,152-byte window, unknown
content size, no checksum and header length 6; a 1,048,576-byte window limit
rejects it. The Native test also covers single-segment/empty, 1/2/4/8-byte
size forms, truncation, invalid bytes and magic, a reserved bit, dictionaries,
checksum flag, limit refusal and signed-64 overflow. These are selected vectors,
not an exhaustive or official conformance corpus.

On macOS arm64, the previously pinned Amu selfhost compiler and packager were
hash-checked. Compiler SHA-256
`369fc624cf5236b3f4a9dba2021bb057223bd1179736c882123506dee4fda082`,
packager SHA-256
`7691467cf64ec5116de3534579a8383b4b0b17198e12a21076145afbc4bce31e`.
The compiler used the exact staged Native source and `positive.ksl` with FD 3
open to the staging directory. Native compile/extract/packager succeeded; the
ad-hoc-signed positive Mach-O returned 0. An independently compiled negative
control changed only the expected Forest window from 2097152 to 2097151 and
returned 12. Both Native entry offsets were 3040. Relevant SHA-256:

- Native parser: `10944d6f4dfca40d10a19e3529f758740e7e87112c228ef129b385f6c0621cbb`
- Native test: `754ef787a4096b3c644cc280a28f2ccdb2e7dd232125f0b6f6b7157d071e5eea`
- Positive lock: `5ad6e2337aa5f31bd2490fa1a49a95d64bf2a44677049ec5ccac01ddbcaebf9f`
- Positive Mach-O: `e3974e0bb1e80e4b858fb5d0d8693fdedba3e090b305e24fdbfa371d43f9f0c9`
- Negative lock: `c9da5b1f82d577b91d29395b4600a8c1797fed70caa02e8343151d1c535ac130`
- Negative Mach-O: `7ae6e28b7ebad07d8d0ab151275a02ec34e0b9d12c7fb190b3d6a4ecda0b1fdc`

The independent local reference used Temurin 21.0.1 and Clojure CLI 1.12.5.1654.
The five existing `.cljk` source bytes were copied unchanged with `.cljc`
extensions to `.agent-output/zstd-oracle/zstd` for the host reader. Command:

```sh
clojure -Sdeps '{:paths [".agent-output/zstd-oracle"]}' -M -e '(require (quote [zstd.core :as z])) (let [f (deref (var zstd.core/read-frame-header)) a (f [40 181 47 253 0 88] 0) b (f [40 181 47 253 32 5] 0) d (try (f [40 181 47 253 33 0 5] 0) :accepted (catch Exception e (:reason (ex-data e))))] (prn {:forest a :single b :explicit-zero-dictionary d}))'
```

It returned Forest window 2097152, unknown size, checksum false, data-start 6;
single-segment window/content 5; and `:dictionary-required` for the explicit
zero dictionary field. The reference oracle is not a Native fallback or build
dependency. The full compressed-block decoder and Native I/O remain open.

The existing Awai native gate also ran locally on macOS arm64 with
`--target macos-arm64 --only zstd_header` against the pinned compiler and
packager. It compiled and ran the unmodified predicate (result 0) and the
independently compiled wrong-window negative control (result 12). Its receipt
covers only these two cases; it does not qualify the full corpus or Native
I/O. The CI matrix is configured to run them on macOS arm64 and Linux arm64
and x86-64; those platforms require their own CI results.

The copied reference source SHA-256 values, in bits/core/fse/huff/xxhash order:

```text
21d9f604f6be16b64ae85ca83bc084412fcd28ed9dd00962b94ef5976b9897ad
2463119ef0a6d2668ce6bc5704f5261869717601f6d32f6f07f7a76e025cbb4f
990d77600b670b6e195f04273e320a97d0218761f073bb5cd295397a19effa92
8af5d6687fe47e0cb1acc69605547a42075776dc974598215a779be13e6a1103
b604bb9e8ea01f851cc0c326ee6f0b187ffc36fdfe1d67237d5b1d40839c9748
```

## Block header admission

The Native module also parses the three-byte block header according to
[RFC 8878 section 3.1.1.2](https://www.rfc-editor.org/rfc/rfc8878.html#section-3.1.1.2),
rejecting invalid bytes, truncated headers, reserved type, negative window and
a size exceeding `min(window, 131072)`. It reports the separate stored payload
length for RLE. This is header admission only: it does not check payload
availability, decode raw/RLE/compressed bytes, verify decoded size or verify a
checksum. The caller must perform those checks before accepting output.

The actual Forest fixture starts `28 b5 2f fd 00 58 d9 01 00`: at offset 6,
the block parser reports last=1, raw type 0 and size 59. Native tests cover
this vector and RLE, compressed, size/window refusal and malformed headers.
The pinned macOS arm64 Awai gate passed the test (result 0), the existing wrong
window control (12), and an independently compiled wrong block-size control
(28). The updated three-platform CI must be checked on its own revision.
Parser SHA-256 `d27e62dc4d1f2aaf77220dafc41384eccd046cb3f6dd405fab928dbffdcc97f3`;
test SHA-256 `68363c1abf3a46a5e60087ca9bc548d17db6876bace5fc8f43489f960280fff6`.
After correcting the source preamble to mention both header types, parser
SHA-256 became `51f49522176b8442d1febe688897e34eb8c52c97d9860e8824d852409561d80d`;
the same three macOS Native gate cases were rerun and passed.

## Bounded raw and RLE payloads

The Native module now expands a single admitted raw or RLE block with a
caller-supplied output limit, refusing truncation, invalid input bytes and
compressed blocks. It does not assemble frames, decode compressed blocks,
verify frame checksums or perform I/O. In the actual Forest fixture, the
first raw block expands to the 59 CAR header bytes; the Native test compares
all bytes against the fixture. Additional tests cover RLE, truncated raw and
RLE input, output limits, invalid bytes and compressed-type refusal.

On macOS arm64 the pinned Native gate passed the positive case and separately
compiled wrong-window, wrong-block-size and wrong-raw-byte controls (results
0, 12, 28 and 42 respectively). Exact-head Linux and macOS CI remain to be
checked. Parser SHA-256
`f81baf23321de07b020c1ef9fc2aadf796dc1c94be76c52341a4dbea0e05e8fe`,
test SHA-256
`f97ef9e2a26c6f549a74b60cda64f2bcebcbc288929db13e80800e5775b097bb`.

## Compressed-block raw literals

The second frame of the same Forest fixture begins a compressed block. Its
raw literals section starts at absolute offset 77 with header `74 12`, which
declares 295 bytes; those bytes have SHA-256
`a2521f5f723cb192bdac6c1cd080b95e50f7439539dee3e835744981b77936c2`.
Native code now reads raw and RLE literal sections with an explicit containing
block end and output cap, returns the sequence-section offset, and refuses
truncation, invalid bytes, overlarge output and unsupported Huffman literals.
The caller must also supply the applicable remaining block/window budget.
The test compares all 295 fixture literals, not just the header. A separate
literal-byte mutation causes native result 52; positive, window, block-size,
raw-byte and literal-byte controls returned 0, 12, 28, 42 and 52 on macOS
arm64. The test checks 1/2/3-byte headers, RLE, end bounds and refusals.

This still cannot decode the fixture's sequences or whole compressed block,
and does not implement frame assembly, checksums, Forest index or Native I/O.
Exact-head CI remains separate. Native source SHA-256
`cff144c8b5452c480fe7cab02bb824db90b89d60dd0fc45859a0cf0f41d9567d`;
test SHA-256
`59cd525564e2467ceaff9d916310cf5f3fa0359489ca19bfb599f69132348743`.

## Sequence header and reverse bit reader

The second fixture frame's sequence section begins at absolute offset 374
with bytes `10 00`: 16 sequences, all three modes predefined. The Native
parser admits bounded sequence counts and modes, rejects truncated headers,
reserved mode bits and caller count-limit excess, and supports all three
sequence-count widths. A stateless reverse bit reader validates the marker
and bounds, reports its bit position, and exposes zero extension to the caller
rather than treating it as end-of-stream validation. Its fixture-derived last
byte `a6` has initial bit position 1 and the next five bits produce 9.

The local pinned macOS Native gate passed positive and five separately
compiled controls, including changed sequence count (result 62). This is not
an FSE table decoder or proof of sequence-stream termination, and does not yet
produce a complete compressed block. Source SHA-256
`570877357bb7c47e325499dcbbe82d9ab50a7497e139aa15ed7a0804ccf47fc7`;
test SHA-256
`243b2a2f4ebeacca2c6ad370b3bfc7888f4a44626a4d74885d399e64961de6da`.

## Native FSE table construction

The Native builder takes bounded normalized counts and accuracy log 5..9,
reserves low-probability states, spreads positive weights, and emits flat
`[symbol, bits, new-state]` triples. It rejects invalid totals, counts and
unfilled states. The test compares every state of the three RFC 8878
predefined literal-length, match-length and offset tables (64, 64 and 32
states) against the attached local oracle output. The first changed expected
table entry produces result 78 in a separately compiled negative control.
The macOS Native gate passed positive and all six controls; exact-head CI is
separate. This does not validate arbitrary FSE table-description decoding,
bitstream termination, sequence execution or full decompression.

One-time reference on 2026-11-14 JST: Clojure CLI 1.12.5.1654, Temurin
21.0.1; existing `zstd.fse` and `zstd.bits` bytes were copied unchanged as
`.cljc` for the JVM reader, with respective SHA-256
`990d77600b670b6e195f04273e320a97d0218761f073bb5cd295397a19effa92` and
`21d9f604f6be16b64ae85ca83c084412fcd28ed9dd00962b94ef5976b9897ad`.
Command, using the staging directory described above:

```sh
clojure -Sdeps '{:paths [".agent-output/zstd-oracle"]}' -M -e '(require (quote [zstd.fse :as f])) (doseq [x [f/literal-length-default f/match-length-default f/offset-default]] (prn (vec (mapcat (juxt :symbol :nb-bits :new-state) (f/build-table (:counts x) (:accuracy-log x))))))'
```

Output `fse-predefined-oracle.edn` SHA-256
`2413c4cd468508f9b5d83e29476bc3af2a76bee5e9701a7691a551497303ff57`.
This local oracle is neither a Native fallback nor a build dependency.
Native source SHA-256
`fb771feb8904b0c4835dc66907d39982b000fe4c96cbb704b9d8b222498f9a88`,
test SHA-256
`b70fc998a9c4387053280bff9ca928e46df5b04d938aa1968ae4b95bdc3ed9f5`.

## Predefined sequence decoding

Native now connects the three predefined FSE tables to the bounded reverse
bit reader and emits `[literal-length, match-length, offset-value]` triples.
For the actual Forest fixture's second frame (sequence bytes 374..421), all
16 triples match the one-time reference `forest-sequences-oracle.edn`, SHA-256
`ecf19622cf55390d42d8182128cd6c37bc581e3fafce5c31517c50be9974ebbf`.
The pinned macOS Native gate passed the positive case and seven independently
compiled controls; changing the first expected triple yields result 85.
Tests include truncation, count limits, invalid marker, trailing bits and
explicit rejection of non-predefined modes. This is a conservative supported
subset: it requires exact consumption of the bitstream and does not claim to
accept every valid frame. It does not execute sequences, apply repeat offsets,
verify checksums or implement I/O.

Reference command on 2026-11-14 JST, Clojure CLI 1.12.5.1654 / Temurin 21.0.1,
using the copied unchanged `.cljc` reference sources recorded above (the
fixture is `part-0.forest.car.zst`, SHA-256
`87a1d2773c099ef49af8fc7b9b00b43123a4e83ab1bc3f1f2b3fca0278fb62df`):

```sh
clojure -Sdeps '{:paths [".agent-output/zstd-oracle"]}' -M -e '(require (quote [zstd.core :as z])) (let [f (deref (var zstd.core/read-sequences)) b (mapv #(bit-and 255 %) (java.nio.file.Files/readAllBytes (java.nio.file.Paths/get "/Users/junkawasaki/github/wt/codex/awai-532-streaming-pack/nixos/otehon/storage/test/fixtures/crosspack/part-0.forest.car.zst" (make-array String 0))))] (prn (vec (mapcat identity (:sequences (f b 374 422 {}))))))' > .agent-output/forest-sequences-oracle-20261114.edn
```

Native source SHA-256
`0bedf2a9f1db277fa1dbc03a0a44d79b770d6a13e2b32aeb600ed19404c0e69e`;
test SHA-256
`0ac3e0eacd3b3907583d116683cb4bc8408161c1a6e466a42454adc8122d0b51`.
This local reference is not a Native fallback or a CI dependency.

## Sequence execution for the actual compressed block

Native now executes the decoded triples with bounded output, literal copy,
overlapping match copy, window/history checks and repeat-offset updates. On
the actual fixture's second frame, the extracted literals and 16 decoded
sequences produce 65,575 bytes with SHA-256
`3a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435`
and repeat offsets `[8165 256 1]`, matching the local reference. The Native
test hashes all output bytes with the repository's pure Native SHA-256 and
checks overlapping copy, prior-block history, direct and repeat offsets,
invalid history/offset and output limits. The pinned macOS Native gate passed
the positive test plus eight independently compiled controls; changing the
expected output digest returns 94. Exact-head CI remains separate.

The one-time reference on 2026-11-14 JST used the same Clojure CLI 1.12.5.1654,
Temurin 21.0.1, reference source copies and pinned fixture documented above:

```sh
clojure -Sdeps '{:paths [".agent-output/zstd-oracle"]}' -M -e '(require (quote [zstd.core :as z])) (let [f (deref (var zstd.core/decode-block!)) b (mapv #(bit-and 255 %) (java.nio.file.Files/readAllBytes (java.nio.file.Paths/get "/Users/junkawasaki/github/wt/codex/awai-532-streaming-pack/nixos/otehon/storage/test/fixtures/crosspack/part-0.forest.car.zst" (make-array String 0)))) out (volatile! []) reps (volatile! [1 4 8])] (f b 77 422 out {:huffman nil :tables {} :reps-v reps}) (let [bytes (byte-array (map unchecked-byte @out)) hash (.digest (java.security.MessageDigest/getInstance "SHA-256") bytes)] (prn {:size (count @out) :sha256 (apply str (map #(format "%02x" (bit-and 255 %)) hash)) :reps @reps})))' > .agent-output/forest-block-oracle-20261114.edn
```

The recorded `forest-block-oracle.edn` SHA-256 is
`511f1ad0d896b106847f97b08a10c821b1d6d5da714a3e2f4c8a2eb70592c604`.
Native source SHA-256
`873daa94115cc46d3ce25417bee9b4dfec891baf3f61400acfc4857c8da6c01b`;
test SHA-256
`308e2ab818c4c0ddf3d9e6bc003bae6fbfeb586bbe5010b5e025b9443d696954`.
This is a single predefined-mode block with raw literals, not generic Zstd,
whole-frame assembly, checksum validation, Forest index access or Native I/O.
The JVM oracle remains a local reference, not a build or runtime dependency.
