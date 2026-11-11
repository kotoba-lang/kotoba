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

The current Mac ARM gate runs the 47 corpus cases plus the original writer's
six golden groups, an input-alias/70000-byte boundary, direct typed input and
leaf-digest refusals, and three separately built/executed wrong-golden,
version-guard and link-codec mutants (52 Native executions). The Native writer's
`append` now copies once into fresh storage: persistent `conj` retained quadratic
allocation history and trapped on the 1024-chunk corpus. Output bytes and input
immutability stay unchanged; no runtime or corpus bound is reduced or widened.

Run on Mac ARM64 with an exact Amu checkout/stage matching
`scripts/native-ci-inputs.json`:

```
python3 lib/kotoba.awaiFs/test/native_gate.py --amu AMU --output NEW_OUTPUT
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
only; it does not allocate or verify a 16 GiB file. The preserved legacy Pack
vectors remain a separate Native constructor qualification until executed.
