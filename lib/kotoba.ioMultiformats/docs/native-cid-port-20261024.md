# Native CID and exact byte hashing

The native implementation uses canonical `.kotoba` and the Amu measured
compiler. It does not execute the historical host codecs or crypto providers.
Frozen public vectors remain the independent expected bytes/CIDs.

`multiformats.cid` validates canonical base32 tail bits, minimally encoded
unsigned varints, version 1 and the complete multihash framing. Declared
digest length must consume the remaining input exactly. Its typed parser
reports distinct errors; `cid-valid?` and `cid->bytes` use that parser.
Assembly refuses malformed digest hex and negative codecs rather than
coercing them into a plausible identifier.

Native varints cover every nonnegative i64, up to 9 bytes/63 bits. There is
no JavaScript number/53-bit prerequisite. This follows the
[multiformats unsigned-varint specification](https://github.com/multiformats/unsigned-varint).
Minimal headers and exact digest consumption follow the maintained
[IPFS CID specification](https://specs.ipfs.tech/cid/).

`multiformats.sha256` adopts Amu's pure byte SHA-256 algorithm from its
source-lock lineage. It hashes supplied byte vectors without UTF-8 coercion,
ambient reads or a host crypto provider. `cid-hash` adds raw-byte and DAG-CBOR
byte entry points. Existing text capability entry points remain explicit.

The native source-locked ARM CID fixture preserves all six existing positive
groups and exercises malformed encodings, digest length, minimality and
values above 2^53. This is candidate evidence; full public multiformats,
Definition CID, owning-main/lock/CI integration and x86 qualification remain
open until their native corpora and required callers pass.

## Reproduction

On native ARM Linux, run `python3 test/native_gate.py --compiler PATH
--compiler-sha256 SHA256 --amu AMU_CHECKOUT --output NEW_DIRECTORY` with a
measured Amu compiler. Python stages exact source locks and observes native
process exits; the canonical Kotoba fixtures implement all checks. The
2026-10-24 receipt uses the existing Amu main root with SHA-256
`f782f3f2a8298c39feeedf873896c9858535a8e371786337632cc60f9e971b9f`.
Both the CID and million-byte SHA-256 fixtures pass without granting the
hash capability. No CI workflow or branch protection is replaced by this gate.
