# Kotoba-owned Awai logical-file / chunk-profile v1

AWAI-531. The executable authority is `src/awai/fs/logical_file.kotoba`:
Kotoba `:schemas` own the Native typed values, and the closed reader/writer
own their mapping to `schema/v1.json`'s logical data model. This is a first-party
format contract, not a new compiler, general CBOR codec or crypto implementation.
DAG-CBOR items come from `kotoba.ioIpld/ipld.dag-cbor-write`; CID and SHA-256
come from `kotoba.ioMultiformats`. Neither input bytes nor IDs contain device,
Pack index/offset, physical media, cache, queue or placement parameters.

## Frozen logical data model

A chunk profile is exactly `{"kind":"fixed","version":1,"leafSize":N}`.
`N` is 1..16777216. It is embedded unchanged when a file is created. A logical
file is exactly `{"chunks":[...],"format":"awai.logical-file","version":1,
"fileSize":N,"chunkProfile":PROFILE}`. Each chunk has exactly `cid` (an IPLD
link), `length` and `offset`. Links are CIDv1/raw/SHA2-256 with a 32-byte digest;
there are at most 1024 chunks, each positive length, all non-final lengths equal
the fixed leaf size, contiguous offsets from zero, and final end equal to size.
The empty file has zero chunks and size zero. The representational file bound
is 17179869184 bytes (1024 maximum-size leaves); it is not an I/O or performance
claim. Metadata encodings are at most 131072 bytes.

Both profile and file IDs are CIDv1/DAG-CBOR/SHA2-256 of their exact canonical
bytes. Map keys have canonical encoded-length/UTF8 order; integer heads and
CID varints are minimal; tag 42 contains `00 ++ binary CID`. The reader rejects
unknown fields/format/versions, duplicate/reordered keys, unsupported links,
indefinite/float/signed scalar aliases, nonminimal integers, extents, truncation
and trailing bytes. No rejected input yields a successful identity.

Native's `file` record holds version, size, a typed profile and a flat checked
chunk-row vector. Each row is `offset,length,CID[36]` (38 i64 values); this is
an internal ABI, not another wire codec or an offset on a storage medium.
`file-new`/`chunk-row` construct inputs; `refusal`, `encode`, `decode`, `file-cid`
and `bytes-cid` validate before success. `profile-encode`/`profile-decode`/
`profile-cid` do the same for the profile. `verify-leaf` compares supplied raw
bytes with an admitted row's length and existing Native CID/SHA primitive.
Linked block bytes still need verification at the real storage adapter.

Changing media/repacking cannot change these logical inputs or this ID. An
explicit rechunk/profile change produces another manifest/ID, even for a small
file whose leaf bytes happen to stay equal. No migration or rechunk operation
runs here. This new versioned logical-file root does not reinterpret the
legacy Otehon `{"leaves":[links...]}` Pack root or retroactively relabel its CIDs.
Filename/private-tree/query meaning stays with AWAI-173/174; ACL, dango, AEAD,
signatures, storage engines and device adapters are not reimplemented.

## One portable corpus, Native verdicts

`corpus/v1.json` freezes 11 logical-file/profile byte/CID goldens, 36 malformed
wire cases and the six existing Otehon indexless Pack vectors without changing
them. The reference is the independent pinned JS DAG-CBOR writer and
multiformats hash/CID library, run once locally; `corpus/provenance.json` records
versions, commands and the owning predecessor. `oracle/generate.mjs` regenerates
the new reference values with those exact packages and retains the frozen Pack
vectors. No reference runtime or host codec is in Native build/gates/runtime.

`test/stage_corpus.py` only turns frozen inputs/expected literals into `.kotoba`
fixtures. All byte comparison, encode/decode, CID, semantic rejection and leaf
verification predicates execute inside freshly built Native programs. Large
hex literals are split at the ordinary string bound; limits are not widened.
Each case gets a fresh process/output directory and complete source lock.
`test/native_gate.py` records the actual compiler, source, lock and artifact
hashes, rejects failed builds, and never reuses an older artifact after failure.

The Native gate runs 11 logical positives, 36 wire refusals, all six frozen
legacy Pack/CAR constructors, three primitive suites and three separately
built/executed wrong-golden, version-guard and link-codec mutants: 59 Native
executions per target. The primitive suites include the writer's six original
golden groups, input aliasing/70000-byte boundary, direct typed/leaf refusals
and Pack bounds/refusals. Mac ARM64 and Linux ARM64 local receipts are recorded;
the same gate runs on real macOS ARM64, Linux ARM64 and Linux x86_64 CI hosts.
Linux predicates are read from the structured Native result, never inferred
from the runner's process exit alone.

The Native writer's `append` now copies once into fresh storage: persistent
`conj` retained quadratic allocation history and trapped on the 1024-chunk
corpus. Output bytes and input immutability stay unchanged; no runtime or
logical corpus bound is reduced or widened. `multiformats.byte-cid` factors the
existing pure byte functions out of the text capability graph; `cid-hash`
retains its API by delegation, and SHA-256 remains the existing primitive.

`kotoba.ioIpldCar/ipld.car.pack` constructs the preserved indexless CARv2 profile
from ordered raw leaves using the existing codec/CID owners. Its explicitly
bounded Native admission is 65536 total encoded bytes and at most 1024 leaves;
the six frozen old vectors compare complete CAR bytes and root CID. This is a
constructor subset of Otehon's 16 MiB profile, not a replacement limit or a
standalone CAR reader/storage qualification. Logical-file roots remain separate.

Run on the declared actual host ISA with an Amu stage matching every required
file in `native-inputs.json` (immutable source/artifact pin):

```
python3 lib/kotoba.awaiFs/test/native_gate.py --amu AMU --target macos-arm64 --output NEW_OUTPUT
# Or --target linux-arm64 / linux-x86_64 on the corresponding Linux ISA.
```

Python only stages, hashes and observes processes. Amu builds the fixtures;
Native predicates own their verdicts. The private compile directory is the
explicit FD3 resource, child PATH has no hosted language executables, and
source/artifact drift refuses the gate. Oracle package downloads were not
needed: the local reference reused archived pinned packages.

This qualification is for the logical format/profile on the recorded host.
Native I/O, OS-cache-loss reboot, power loss, independent nodes/EC/repair,
private-tree/query semantics, signed authority, production acceptance and
performance thresholds remain separate. The maximum-size case is metadata
only; it does not allocate or verify a 16 GiB file. The legacy Pack vectors qualify only the constructor subset described above.
