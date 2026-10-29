# Native broker connection and fixed-roster quorum register

AWAI-98 adds a bounded native protocol beside the C0 authority/store profile.
The production compiler is unchanged: this profile needs the explicit Amu
FS35/CLI38 project compiler candidate documented in `authority-and-store.md`.
No deployment, browser consent activation or full conductor migration follows
from importing these modules.

## Authority and component boundary

`hata.broker` consumes the existing host FS provider; it embeds no VM, loader,
network engine or new system capability. Its first application adapter is a
bounded managed object, `object-store.put-block` at `awai://object`. The object
bytes and their consumption record share one atomic signed snapshot. This
specific property does not apply to sending mail, payments, arbitrary HTTP or
another sink that commits separately.

The adapter calls `kototama.effect-origins/eligible?`, extracted verbatim from
the existing `kototama.admission/eligible?` body. The old public function delegates
to that kernel with the same arguments. Catalog, declared effects, definition
world, intents, grants, policy, runtime world and available mechanisms must all
agree. No LLM, request or certificate can supply these host-owned facts. The
remaining legacy admission closure is preserved, including its unsupported
Native dependencies; this extraction is not whole-component Q9 qualification.

The host also owns policy, trusted time, roster, checkpoint seed, voter seeds,
filesystem grants and process launch. Every voter needs a different key and a
private directory. Apps receive neither signing seeds nor `:fs/app-data`.
Origins alone authenticate no user: actual dispatch additionally verifies the
C0 signatures, current credential/revocation policy, body digest and reserved
resource costs. The five-byte fixture reserves 5,000 storage-byte-seconds;
ingress/egress, logical operation fuel and working memory must cover the body.
Cryptographic verification overhead and bounded provider journal overhead are
host-provisioned. This is not a measured CPU instruction billing schedule.

## Signed register protocol

The fixed configuration is 168 i64 words:

```text
[version=1 generation domain4 voters=4 threshold=3 voter-public-keys128 writer-public-key32]
```

All five keys must be distinct canonical prime-order Ed25519 keys. Generation,
domain and keys are hashed into the roster identity. There is no roster change
API. Signatures use distinct tagged messages and canonical little-endian i64
encoding. A proposal is an 85-word descriptor followed by its value:

```text
[version=1 sequence epoch kind parent4 value-hash4 domain4 writer-key-hash4
 value-length writer-signature64 value...]
```

Sequence is 1..256, epoch is positive and nondecreasing, kind is 1..3 and the
value has 1..53,660 words. The writer signs the roster and descriptor header;
the header commits the value hash. Voters sign the roster-bound entry ID.
A certificate contains `[1 vote-count (voter-index signature64)...]`; only
three or four distinct, authentic roster members qualify. Kind 1 is a retained
checkpoint, kind 2 a provider fence and kind 3 a reserved dispatch claim.

`replica/create` refuses an existing or incomplete initial state. Each operation
uses the host's existing cooperative lock on an unchanged `quorum.lock` inode.
The local signed state commits the roster, committed sequence/epoch/head,
current descriptor/certificate and one outstanding descriptor. `vote` requires
the next sequence and exact committed parent. It first persists the hashed
value block, fsyncs it and its directory, then atomically replaces and fsyncs the
signed vote state. Only after this succeeds does it return a signature. A
restart cannot produce another vote for that parent. `commit` requires a valid
certificate, retained data and the same parent CAS, then advances the head and
clears the outstanding vote. `current` rechecks retained value hashes and QC.
Duplicate vote/commit calls are safe; failures never return a successful ACK.

With at most one Byzantine storage voter, two groups of three among four share
at least one honest voter, whose durable unique vote prevents conflicting
certificates. This assumes honest voters retain their acknowledged data and
vote state, exclusive custody of keys and files, and no privileged rollback.
The trusted checkpoint writer remains responsible for legal business-state
transitions: voters authenticate its data and register ordering, not a complete
replay of C0 business logic. A certificate collected before it reaches any
committed replica is not an automatically discoverable latest head. A caller
must retain its ACK/certificate or obtain a fresh quorum read (below) before
relying on a head; `replica/current` alone is not a read protocol.

This is a safety-focused, bounded, fixed-roster register, not a complete BFT
consensus service. Split votes can halt it. Do not erase outstanding votes,
lower the threshold or fall back to a local journal to restore availability.
View changes, automatic leader recovery, certified genesis provisioning,
reconfiguration, log pruning and anti-rollback recovery remain separate work.
An acknowledged history has at most 256 positions. A voter may retain both its
own voted value and a different certified value at a position; interrupted
pre-ACK writes may leave additional orphan blocks. A host-provisioned disk
quota is required; the sequence bound alone is not a disk quota. Disk-full is
refusal, never a reset. Automatic orphan collection remains unimplemented.

## Fresh read (AWAI-103)

A reader chooses a nonce and asks replicas to attest. `replica/attest`, under
the replica lock, signs with that replica's voter key the reader's nonce, its
current snapshot and, when it holds one, its pending vote (re-issued for the
one descriptor it already voted; a replica never votes twice at a seq):

```text
Attestation = [1 index nonce4 state-len vote-len] snapshot vote(0|65) signature64
```

`read/latest` needs three valid attestations from distinct replicas. A
certificate has three voters; any three responders share at least two of them
and at most one replica is faulty, so an honest responder holds a certified
entry either committed or as its pending vote. The latest certified head is
therefore the highest committed sequence K seen, or K+1 when a responder at K
holds a pending vote. The result is one of:

| status | meaning | the reader may |
|---|---|---|
| 1 | committed head K with its certificate | rely on K |
| 2 | three pending votes for K+1 assemble a certificate that was never distributed | distribute it (`commit`), then rely on K+1 |
| 3 | one or two pending votes for K+1 | collect the missing vote or wait; never act on K or K+1 |
| 4 | nothing certified or pending (genesis) | create the first entry |
| 0 | refused | retry with a new nonce |

Refusal covers fewer than three distinct valid attestations, two different
certified heads at one sequence (more than one fault), a nonce other than the
reader's (a replayed signed snapshot), another roster, any changed word, a
pending vote by another index, for another sequence or on another parent.
Invalid attestations are dropped, so one faulty replica cannot forge a head but
can make a read wait. `replica/block` returns a retained value only when it
matches the descriptor's length and value hash; any replica that holds it can
supply a missing value.

The writer stays trusted: one writer signature per descriptor. An equivocating
writer is bounded only by one vote per replica and sequence, and can split votes
so that a read stays at status 3. View and roster changes are AWAI-104.

## Writer restore (AWAI-103)

A new writer starts from an empty C0 base. `broker/restore` takes the head a
fresh read returned, verifies its certificate on the full request (value
included) and that its epoch is the policy's, and passes the value to
`store/restore`. That store checks that the value parses as C0 state bound to
this policy's epoch, domain and operation, with each stable request id at most
once, writes a durable `restored` marker and only then publishes the state.

A restored store is inactive: `submit` and `complete` return
`rejected:inactive`; `recover` (the epoch bump) is allowed. The writer recovers
to a new epoch, certifies a fence entry and installs it at the sink.
`broker/activate` then reads a durable copy of the sink's sealed state and calls
`store/activate` only when that state shows the new epoch at or past the fence
entry. The previous writer is refused by the sink's epoch fence.

Legality of the transitions before the restored head rests on the trusted
writer's signatures; the restore checks shape and binding, not replayed
business history. No privileged rollback resistance is claimed without an
external witness or anchor.

## Broker fence, consume and reconcile

1. Replicate a kind-2 C0 snapshot under a quorum certificate. Install this fence
   at the actual provider. Activation/handover is complete only after its
   durable ACK; a QC alone does not magically fence an unreachable provider.
2. C0 `store/submit` verifies authority and reserves all six resources before
   effects. Replicate that full reserved blob as a kind-3 entry. The adapter
   finds the exact pending request and exact authority proof in this value.
3. `broker/execute` checks the certificate, installed epoch, next sequence and
   parent, body, fresh authority, costs and all host-owned origin facts. Under
   `broker.lock`, it writes the bytes and the stable principal/request-ID
   consumption record in one signed pending/fsync/rename/directory-fsync update.
   Body size is at most 256 bytes, with at most 64 retained request records.
   There is no eviction that would silently re-enable an old request.
4. A retry returns the recorded result without another effect. A certified
   duplicate at the next register position advances the provider head without
   reapplying bytes. Conflicting request/body hashes are refused. Success rows
   expire for reads, while consumption records remain. An expired latest
   object does not expose an older one.
5. Host-only `abandon` consumes an unresolved certified claim as terminal
   UNKNOWN without exposing an object. It still requires the exact reserved
   proof/body, checkpoint authority and QC, but not fresh expired/revoked
   application credentials or an execution grant. This allows conservative
   recovery without authorizing a new application effect.
6. `settle` reconciles an observed success into local C0 `store/complete` using
   its current CAS token. It does not hold a broker lock while obtaining the
   store lock: the native FS mechanism supports one cooperative lock per
   process. UNKNOWN never becomes success through this path.
7. Replicate the subsequent completion snapshot as a kind-1 entry. Host-only
   `checkpoint` verifies its QC, same installed epoch and next parent/sequence,
   then advances the provider head without an application effect. Its retry is
   idempotent. This prevents completion records from creating a gap before
   the next claim/fence. The caller orchestrates these steps; there is no
   automatic background coordinator or checkpoint-writer failover.

The sink is a single trusted persistence authority, not four interchangeable
copies of a signing key. Do not clone its seed/state to independent hosts and
claim provider failover or exactly-once effects. Generic distributed C0 state
issuance, network ingress, a fresh quorum read, independent sink fencing and
business-state replay are not implemented by these functions.

## Caller results

All vectors are canonical i64 words. Seeds/identity arguments are host-only.
`object` is a host inspection API, not an unauthenticated network read endpoint.
A service exposing reads still needs its own declared read operation and
authorization; this adapter does not publish such an endpoint.

| API | Successful result | Refusal/retry result |
|---|---|---|
| `replica/create` | `[3]` | `[0]` invalid/existing or `[11]` busy |
| `replica/vote` | `[1 voter-index signature64]` | `[10]` conflicting vote, `[11]` busy, `[12]` stale parent/sequence, `[0]` invalid/storage failure |
| `replica/commit` | `[2]`, `[4]` already committed | `[11]` busy, `[12]` stale parent/sequence, `[0]` invalid/storage failure |
| `replica/current` | `[request-length qc-length request... qc...]` | empty vector if absent/corrupt |
| `broker/install` | `[1]`, `[2]` already installed | `[0]` invalid, busy, stale or uncertain persistence |
| `broker/checkpoint` | `[1]`, `[2]` already consumed | `[0]` invalid, busy, wrong epoch or parent/sequence |
| `broker/execute` | `[1]` first effect, `[2]` recorded success | `[3]` terminal UNKNOWN, `[0]` refused/uncertain |
| `broker/abandon` | `[3]` terminal UNKNOWN | `[2]` already succeeded, `[0]` refused/uncertain |
| `broker/object` | retained bytes | empty vector if absent/expired/invalid |
| `broker/settle` | existing C0 `committed:<token>` | existing typed refusal/uncertain string |

A failed ACK may follow an uncertain durable write. Retry the same identity and
entry or read verified state; never infer that the operation did not happen and
mint another request ID. `abandon` is a recovery outcome, not an application
success receipt. The C0 token inside a dispatch command identifies its original
local reservation and is not substituted for the quorum parent CAS.

## Verification and scope

Run the exact source-locked gate on Linux x86_64 with the declared experimental
compiler and matching native runner:

```sh
python3 lib/kotoba.hata/scripts/check-broker-native.py \
  --compiler /absolute/path/candidate-F3.elf \
  --compiler-sha256 498c64b7a0338300e1acfafe0d436b6ac1fe1ef8c1c8706d0dc0c5e54f42cbfc \
  --runner /absolute/path/candidate-runner.elf --output /new/private/evidence
```

On Apple Silicon (JUN-593) the same gate runs with the Mac root compiler and a
Mac packager whose `fs2-cli-stdio-general` runtime answers these wire-35 text
requests (kotoba-lang/amu#1687):

```sh
python3 lib/kotoba.hata/scripts/check-broker-native.py \
  --compiler /absolute/path/amu-full-root.macho --compiler-sha256 <sha256> \
  --packager /absolute/path/kotoba-packager-root.macho --packager-sha256 <sha256> \
  --output /new/private/evidence
```

There FD 3 is the output directory and each scope directory reaches the guest
as `/<relative path>`; main's result is the exit status, compared modulo 256
(Linux reads the full i64 `:result`). Measured 2026-10-29 on an M1 Max:
`PASS_NATIVE_BROKER_QUORUM`, the same 97 guest calls in the same order as the
Linux x86_64 CI evidence (run 40854047278), and all 96 results equal modulo
256, including the non-durable-vote mutant (-17, exit 239). The fresh-read verdicts
(`read_native`) are miscompiled on the Mac by the current Mac compiler
(JUN-595: a multi-module compile reads a wrong vector element; the same code as
one module is correct); until it is fixed they are qualified on Linux x86_64
only.

The Python observer stages explicit closed source files, hashes artifacts,
launches Native processes and transports opaque bytes. Proposal construction,
signing, certificate assembly, origin/authority checks, persistence decisions
and semantic test verdicts execute in the Kotoba guest. PATH has no hosted
language executable. The expected failure from a deliberately non-durable-vote
mutation must be detected by the same Native no-equivocation verdict. A reader
that ignores pending votes must be detected by the fresh-read verdict 3003.

The fixture uses four separate private directories and fresh Native processes
on one physical Linux host. It does not qualify independent-host crash domains,
network transport, Byzantine host isolation, live traffic, production key
custody or a deployed Awai Network. Public deterministic fixture seeds must
never be enrolled in a real network.
