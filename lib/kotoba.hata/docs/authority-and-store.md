# C0 authority and durable admission (AWAI-96)

`hata.authority` verifies native Ed25519 responsibility attestations, service
grants, coupons and actor signatures before calling the existing
[post-verification reservation machine](accountable-admission.md).
`hata.store` retains that evidence with signed, atomic checkpoints and a
cooperative kernel file lock. These are internal trusted-host components;
there is no public wire decoder, enrollment endpoint or effect dispatcher.

## Qualification and integration

The shared native CI exercises authority with its existing pinned Amu image.
For the complete durable-store gate it separately derives a source-pinned
experimental FS35/CLI38 project compiler from
[Amu PR #1597](https://github.com/kotoba-lang/amu/pull/1597), tracked by AWAI-97. The previous pinned compiler refuses
capability-bearing projects with E7101. It must continue to refuse rather
than silently falling back to a hosted compiler or flattening source modules.

The candidate compiler is derived from the complete 47-module Amu lineage,
with F1 = F2 = F3 on native x86 Linux. Its existing project/refusal corpus and
declared FS35/CLI38 normal, missing-declaration, ungranted-wire and
scope/symlink refusal probes are separate from full public product/root/ARM
adoption. The [checked-in native evidence](evidence/authority-store-20261026.json)
records exact compiler, runner,
source-lock, source and payload hashes. A candidate pass does not mean that
the normal compiler release, merged main or a deployed service includes it.

Run the unchanged canonical modules and importing native tests with:

```text
python3 lib/kotoba.hata/scripts/check-authority-native.py \
  --compiler /absolute/path/to/qualified-native-compiler \
  --compiler-sha256 <exact-image-sha256> \
  --runner /absolute/path/to/same-toolchain-native-runner \
  --output /absolute/private/new-output-directory
```

`--case authority` runs the pure verifier and signature-bypass control;
`--case store` runs the store alone for iteration. Only the default `all`
case can emit `PASS_NATIVE_AUTHORITY_STORE`. Python stages bytes, hashes,
starts native processes and injects filesystem/process faults. All crypto,
admission, state transitions and test assertions execute in Kotoba.

## Trust and accountability

C0 uses a locally accepted registrar key. Its signature attests that the
principal commitment represents an accountable member and that this actor
may represent that member. Identity proofing, secure retention of the
principal-to-person mapping, appeal and evidence disclosure remain registrar
operations. A valid signature proves the accepted key's statement; it does
not independently prove that the registrar checked a real person correctly.
No actual member identity or production signing secret is used by these tests.

The host selects policy keys, revocation state, trusted current time and the
private filesystem grant. Applications and LLMs cannot select these inputs,
call completion/recovery, receive the checkpoint seed or create a file grant.
An LLM may propose a request; it is never a signature verifier or sanction,
identity-opening or permission authority. This code grants no LLM privileges.

Keys for the registrar, service and checkpoint writer must be distinct.
Actor and configured public keys must be canonical nonidentity prime-order
Ed25519 points. The existing native Ed25519 implementation performs signature
verification and signing; SHA-256 commits canonical bytes. Existing RFC 8032
and SHA-512 vectors are retained. This bounded qualification is not a full
cryptographic audit or a constant-time implementation claim.

## Fixed internal frames

All entries are signed i64 words. A canonical message is the exact ASCII
domain-separation tag, one NUL byte, then each word encoded as eight
little-endian two's-complement bytes. A digest is the four little-endian i64
limbs of the complete SHA-256 output. Signatures/public keys use one byte
per word and reject words outside 0..255. These frames are an internal ABI,
not a CBOR, DID, VC, wallet or existing Awai wire-format compatibility claim.

The request `r` is the existing 50-word admission frame. Auth `q` has 297 words:

| Offset | Width | Meaning |
|---|---:|---|
| 0 | 1 | version 1 |
| 1 | 4 | stable logical request ID, nonzero |
| 5 | 32 | actor public key |
| 37 | 64 | registrar responsibility/delegation signature |
| 101 | 64 | service grant signature |
| 165 | 64 | service coupon signature |
| 229 | 64 | actor request signature |
| 293 | 4 | SHA-256 commitment to the exact canonical body |

`r[22..25]` commits to the stable ID, `r[0..21]`, `r[26..49]` and the body
commitment, using `awai.c0.request-commitment.v1`. The actor key's SHA-256
must equal `r[30..33]`; the authenticated grant message digest must equal
`r[34..37]`. The body is bounded to 1 MiB. Ingress cost must cover at least
2776 bytes of these internal frames plus the body. Other costs and actual
work still require the effect broker's own authenticated metering checks.

`payload-matches?(r,q,body)` checks byte validity, actual byte length and the
body commitment. A broker **must** call it on the actual canonical body before
dispatch, and bind the same operation, destination and data labels to the
authenticated operation/body. Admission commits to a body but carries no
body and does not execute it. A caller-supplied digest is not proof that the
effect broker received those bytes.

Policy has a 112-word header and up to 64 five-word revocation entries:

| Offset | Meaning |
|---|---|
| 0..7 | version 1, writer epoch, policy generation, status not-before, status exclusive expiry, revocation generation, allow bots (0/1), revocation count |
| 8..11 | domain commitment |
| 12..15 | operation commitment |
| 16..47 | registrar key |
| 48..79 | service grant/coupon key |
| 80..111 | checkpoint key |
| 112.. | kind + four-word commitment: principal (1), actor (2), grant (3), coupon (4) |

Status lifetime is at most 3600 time units. The host must refresh this trusted
snapshot and supply an advancing trusted time; it is not fetched or signed
by an untrusted caller. Requests outside that snapshot, scope, epoch, policy,
class/delegation or credential lifetime fail closed. A fresh snapshot with
the same generation may add revocations. Changing revocation generation
invalidates earlier credential/grant signatures until they are reissued.

The signed statements use distinct tags:

| Tag | Signed words |
|---|---|
| `awai.c0.credential.v1` | revocation generation; request not-before, member expiry, policy, actor class and delegation expiry; domain; principal and actor commitments |
| `awai.c0.grant.v1` | revocation generation; r[1..7]; domain/operation; principal/actor; six grant ceilings |
| `awai.c0.coupon.v1` | stable ID and all 50 request words |
| `awai.c0.request-signature.v1` | stable ID and all 50 request words |

`verify(p,r,q,now)` returns 0 for authenticated frames. Refusal codes are
30 (frame/cost), 31 (policy), 32 (scope/time/class), 33 (revoked), 34 (actor
key binding), 35 (grant commitment), 36 (request/body commitment), 37
(credential signature), 38 (grant signature), 39 (coupon signature), and
40 (actor signature). `admit` then applies **all** existing admission shape,
budget, retention, monotonicity, duplicate and capacity checks. Authentication
alone is not a reservation or an execution permit. Grant ceilings are per
request; the admission machine also enforces the service's six global
remaining budgets. Wallet balances, deposits and slashing are not implemented.

## Durable checkpoint protocol

The base is a host-controlled private absolute directory beneath wire 35's
granted root. This profile restricts base characters to ASCII alphanumeric,
underscore, dash and single slash; dot segments and `_SEP` command separators are
refused. The host filesystem provider independently enforces its grant and
symlink boundaries. The directory and lock inode must not be writable by
untrusted actors. The lock file is never renamed or removed by this protocol.

`create(base,config,policy,seed)` initializes only an absent store, while
holding `awai-admission.lock` with nonblocking kernel flock. An existing
state **or pending** file prevents silent reset. `load` atomically reads
`awai-admission.state`, validates its layout/scope/policy and signature, and
returns empty for absent or invalid content. Ordinary I/O capability failures
may trap. Empty is never permission to initialize over existing files.

The on-disk envelope is `AWAI-C0-STORE-V1` + LF, lowercase hex blob, LF,
lowercase hex Ed25519 signature. Each i64 occupies 16 hex characters;
decoding is strict and bounded to 1 MiB. The blob is:

```text
[1, state-word-count, record-count, 781, admission-state..., records...]
record = [trusted-admission-time, r(50), q(297), policy-length, padded-policy(432)]
```

The checkpoint token is SHA-256 over
`awai.c0.checkpoint-token.v1` and the complete blob. The Ed25519 signature
covers `awai.c0.checkpoint-signature.v1` and that token. Records retain the
accepted policy, proofs and time even after credentials expire or are revoked.
The writer is trusted: a signed checkpoint attests its state. Loading does
not independently replay all historical proofs or reconstruct all transitions.

Each mutation requires the caller's four-word expected checkpoint token.
Under the unchanged kernel lock, the service reloads and verifies the current
checkpoint, compares that token, applies one transition, signs the next blob,
writes `awai-admission.pending`, fsyncs it, atomically renames it to `.state`,
and fsyncs the base directory. Only then can it return `committed:<token>`.
An uncertain rename, directory fsync or unlock result is not a dispatch permit.
Resolve uncertainty by reopening/recovering, never by blindly executing again.
A leftover pending file is never promoted on restart.

`submit` takes `[now,expected-token(4),r(50),q(297)]` (352 words).
Before taking the lock it checks real signatures; under the lock it checks
the current checkpoint and principal + stable ID journal. The same logical
ID and envelope returns the existing row status with no spend or new commit;
a changed coupon/body/actor/epoch with that ID is a conflict. The store has
one domain/operation. Deploying multiple independent journals for the same
domain would require a shared replay index; this implementation does not
provide cross-journal or cross-service idempotency.

`complete` takes `[now,expected-token(4),request-digest(4),outcome,result(4)]`.
`recover` takes `[now,expected-token(4),new-epoch]`. Both are host-only, require
the current policy writer epoch and use the existing transition machine.
Recovery advances the epoch, marks every pending row UNKNOWN and refunds
nothing. An old writer cannot complete under its previous epoch. Future
requests require newly bound signatures, but an old stable ID cannot execute
again. UNKNOWN is terminal and must be reconciled with the external sink.

The journal is bounded at 64 rows and **does not evict or reset**. A full
journal stops accepting work. Policy-generation/key migration, checkpoint
compaction and retention-safe garbage collection are not implemented.
Starting a new journal to evade retention or replay protection is forbidden.

## Limits of this proof

This is a trusted-host, single-filesystem C0 service. Cooperative flock and
token comparison prevent simultaneous/stale participating writers. They do
not stop a privileged host, a stolen signing key, lock inode replacement,
or restoration of a valid older snapshot when no independent newest-token
anchor exists. Same-key signed rollback/equivocation needs an external
monotonic witness/quorum and key custody. No such guarantee is claimed here.

Native fault tests kill a writer after partial write, full write, file fsync,
rename and directory fsync; restart must expose the old or new valid state,
release the lock, reserve at most once and recover pending work to UNKNOWN.
They test process death, not sudden power loss or filesystem/controller
failure. Two-process races, bad signatures, corruption, stable-ID conflicts,
old epochs and host grant refusals are separate checks. There is no distributed
consensus/finality, threshold identity opening (C1), transport/IP concealment,
effect dispatch fence, production key management or live network deployment.
