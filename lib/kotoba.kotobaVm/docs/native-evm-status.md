# AWAI-81 native Paris candidate

The selected native closure now implements account/frame execution, all nine
Paris precompiles, Ethereum transactions and secure MPT stateRoot calculation,
plus a bounded Cell/Inga adapter and durable native publication. It remains
experimental, unselected and unreleased. `evmConformant` is false: the pinned
official Paris full-state census is complete, but its resource envelope and the
public runtime are not qualified.

## Measured gates

The current canonical checked-module build executes 1,986 assertions in one loaderless
AArch64 Linux ELF. The independent Geth oracle is v1.16.7, commit
`b9f3a3d964ed3d31e710ec7dd66da9181477ecb2`. It generates reference fixtures;
it is not linked into the implementation or used as a runtime fallback.

| Gate | Assertions | Scope |
| --- | ---: | --- |
| Original arithmetic/frame/Cell/Inga closure | 204 | Historical bounded baseline |
| Canonical RLP | 73 | 28 official valid, 26 official invalid, additional canonical/integer checks |
| Account state / CREATE addresses | 20 | Updates, storage, CREATE and EIP-1014 vectors |
| Montgomery fields | 120 | secp256k1 field/order and BN128 field arithmetic |
| Recovery / G1 operations | 40 | Official ECRECOVER, BN128 add/multiply outputs |
| RIPEMD160 / BLAKE2F | 22 | Hash vectors, compression and malformed inputs |
| MODEXP | 94 | 47 official cases: arbitrary-width/even moduli and EIP-2565 gas |
| Frame manager | 32 | CALL families, CREATE families, context, gas, rollback and low-160-bit precompile dispatch |
| Geth frame differential | 245 | 30 frames: gas, output, world, logs/refund, STOP stack and stateRoot |
| Transaction envelopes | 225 | 15 legacy/2930/1559 cases and signing/hash/intrinsic fields |
| Transaction negative controls | 57 | Signature, chain, parity, quantity widths and canonical RLP |
| Geth transaction differential | 360 | 60 cases: admission, nonce, value, fees, refund, output/logs and stateRoot |
| Ethereum Cell/Inga binding | 6 | Exact replay result, duplicate, stale state, nonce/grant and fork/rollback |
| Precompile dispatcher | 488 | 123 cases across addresses 1–9, including gas and failures |

The earlier resource candidate was rebuilt by the measured Amu full-31 source closure
(`F1 = F2 = F3`, SHA-256
`ea15b258f2b2dffd72e7aeaade0410c69c4e5d2be314e30ee7ce375449242642`).
The current v45 source passes 1,986 project assertions, 38 core/memory/world/
deployment bounds, 7 large byte bounds, 10 field-parser bounds, and 8
Geth-root-checked state bounds. The latter exercise 4,096 storage slots,
2,048 accounts and 65,536 bytes of pre-existing code, each with a one-unit-over
refusal, plus a 32-account world above the former 1 MiB limit. A corpus-specific
native driver compares official expected state roots and logs hashes. Official
transaction exception entries check the native invalid-envelope status; the
upstream state-test runner does not distinguish exception subtypes.
The [v39 resource evidence](evidence/awai81-native-paris-resource-20261025/README.md)
preserves the earlier module closures and selected boundary fixtures. The
[v45 sparse-frame evidence](evidence/awai81-native-paris-sparse-20261025/README.md)
pins the current source closures, selected official cases and process receipts.

Native profile refusals (8/10/11) are never normalized into an EVM exception
by the Geth comparison. Geth's decoder/sender can accept oversized big-integer
quantities; the negative oracle separately applies the Paris value/fee width
checks from `core/state_transition.go`. Decoding, signature validity and
transaction admission are recorded as distinct checks.

The [follow-on receipt](evidence/awai81-native-paris-20261024/receipt.json)
pins every source, fixture, compiler, linked container and final ELF. The
[source lock](evidence/awai81-native-paris-20261024/project.lock) covers the
complete module closure. Build and final execution use Amu selfhost/native,
with PATH empty of tools, no network, host EVM/crypto, JVM, Node or C loader.
Transient Python/OpenSSL/CGO-disabled Go tools produced independent fixtures
and orchestrated processes; they are not product tooling or implementation.

## Execution and Ethereum state

`native-execution` layers explicit account/block/message context over the
256-bit frame core. It implements CALL, CALLCODE, DELEGATECALL, STATICCALL,
CREATE, CREATE2, LOG and Paris SELFDESTRUCT, including EIP-150 forwarding,
stipend, reentrancy storage synchronization, revert snapshots, return-data
bounds, code deposit and EIP-161 pruning. The differential gate found and
fixed empty-account EXTCODEHASH and successful CREATE code-deposit gas.
A colliding CREATE never executes its init code.

`native-precompile` implements ECRECOVER (including high-s acceptance),
SHA256, RIPEMD160, identity, MODEXP, BN128 addition/multiplication/pairing and
BLAKE2F. Public signature recovery uses native Montgomery/Jacobian arithmetic;
pairing validates G2 curve/subgroup membership and uses native Fp2/Fp12 and
Miller/final exponentiation. There is no signing API or foreign crypto.

`native-transaction` admits canonical legacy, EIP-2930 and EIP-1559 envelopes,
binds chain ID, checks EIP-2 low-s and recovers the sender. `native-transition`
checks sender code/nonce/balance and fee limits, applies intrinsic/access-list
gas, transaction rollback, nonce consumption, refunds, base-fee burn and
coinbase reward. Policy refusals preserve the entire pre-transaction state.

`native-trie` computes Ethereum secure account/storage trie roots with exact
Keccak and RLP, including compact paths, extension/branch/leaf nodes and
embedded versus hashed node references. IPLD bytes/CIDs do not replace an
Ethereum transaction hash or stateRoot. Proof generation, block/receipt trie
roots, RPC and `eth_getProof` are not implemented by this candidate.

The resource implementation stores EVM stack words as 16 little-endian limbs,
reuses bounded frame workspaces and computes deep recursive calls inside scalar
regions. Logical EVM memory and calldata sizes are distinct from materialized
byte prefixes; zero-padding reads preserve EVM semantics without allocating a
large empty prefix on every nested call. Shallow child frames own their scalar
buffers, and the root retries a whole transaction when its buffer needs to
grow, so a child cannot reexecute separately and multiply work through a deep
CALL tree. The private retry code never becomes a public transaction status.
The current bounds include 2,048 accounts, 4,096 storage slots per account,
65,536 bytes of pre-existing code and calldata, 32 MiB of frame memory,
16 MiB of internal serialized world state,
100 million frame steps, signed-64-bit gas, 16 domain requests, and 32 Mi
scalar words for the shared call-tree staging buffer. Deployment retains the
Paris 24,576-byte code limit. These are admission limits of this candidate,
not universal EVM limits. Host fuel in the local gates is unmetered.

Amu [#1568](https://github.com/kotoba-lang/amu/pull/1568) carries the
measured AArch64 scalar depth expansion needed by these deep frames. Its
follow-on expands the AArch64 static string pool to 1 GiB. The full-31
selfhost source reaches a fixed point at R2 = R3. The v45 checked module and
packed Paris driver were compiled with R2; the byte-identical R2/R3 image is
pinned in the v45 evidence.
The x86 pool and AArch64 vector-item limit are unchanged.
The concurrent public-root integration in Amu #1560 advanced separately;
combined-tree compiler and public-root qualification remain open.

## Cell authority, finality and persistence

The historical `native-domain` still has a private SHA256 storage commitment
and domain nonce. The separate `native-ethereum-domain` executes actual
Ethereum transactions over accounts and uses Ethereum stateRoot. Its grant
binds the complete prescribed context (domain, Cell/key, Inga anchor, genesis
world and EVM block context); its Cell signature binds nonce, prior root,
transaction bytes and grant. Requests have real raw/SHA256 CIDv1 identities.
Ethereum account nonces and the Cell request counter remain separate.

A complete certified prefix is checked before execution. Only finalized
proposals run. Duplicate request CIDs produce one saved receipt. Rejected
Cell requests and invalid Ethereum envelopes have domain refusal receipts;
they are not Ethereum block inclusion receipts. Saved receipts include gas,
transaction hash, output and logs. Shared Grant subsystem integration and
atomic cross-domain calls are not claimed.

The filesystem provider is proposed in [Amu #1560](https://github.com/kotoba-lang/amu/pull/1560).
`native-store` verifies a persisted context/checkpoint/proof/catalog/result
before recovery. Publication acquires a scope-bound native kernel flock,
checks the expected durable checkpoint, writes and fsyncs a pending envelope,
renames it over the state file, then fsyncs the directory before success.
State, nonce, receipts and checkpoint are replaced together. Corruption,
competing publishers, stale comparisons and conflicting finalized branches
fail closed. The lock file is never renamed or removed by the protocol.

The v45 [process-crash receipt](evidence/awai81-native-paris-sparse-20261025/durable-store/receipt.json)
records 41 successful process assertions. Five native SIGKILL windows cover
partial pending data, completed write, file fsync, rename, and directory
fsync. Independent restarts recover the old/new complete state as appropriate;
retry and duplicate publication preserve the same result. Competing native
publishers are refused while the killed process holds the lock. A separate
native filesystem gate passes 9 acquisition/reentry/unlock/scope/symlink checks.

Inga [#31](https://github.com/kotoba-lang/inga/pull/31) implements the native
validator side: signed proposals/votes/new-view messages, canonical quorum
certificates, timeout certificates, lock checks and durable vote intent before
signing. Selected gates pass 15 helper assertions, 30 replica assertions,
51 durable vote-store process checks across five SIGKILL windows, four native
TCP replicas at quorum three with a stopped scheduled leader and restart, and
24 independently OpenSSL-verified native signatures. The separate native
Ethereum consumer takes their actual certified prefix, Cell signatures and
raw transaction: four durable stores pass 34 checks through finality height
two, restart, repeated publication and stale-proof refusal. This exercises
the consensus-to-state boundary; a public node service and delivery protocol
are not qualified.

These gates exercise process crashes and logical atomic visibility. Physical
power loss, a malicious writer holding raw filesystem capability, storage
rollback outside the trusted checkpoint and distributed exactly-once delivery
remain open. Directory-fsync or unlock failure after publication is reported
as uncertain, not as a clean rollback.

## Open qualification gates

- Full official Paris conformance and broader independent client differential.
  The pinned v13.3 census attempted all 19,807 cases on one v45 native ELF:
  19,799 passed the official stateRoot/logs comparison and an independent
  BlockchainTests gasUsed check; three `vmPerformance/loopMul` cases
  (00596–00598) hit the explicit 100-million-step frame policy, and five
  cases (05687–05689, 10327, 10540) exceeded the run's per-case wall time.
  There were no semantic or gasUsed mismatches among completed passes, no
  missing IDs and no duplicate results. Cases 10327 and 05687 also produced
  no result after 45 minutes each at 6 GiB and a 64 MiB stack on the same
  v45 ELF. These eight non-passes prevent full conformance; the
  [audited ledger](evidence/awai81-native-paris-sparse-20261025/full-v45-audit.json)
  keeps policy refusals separate from host timeouts.
- Native allocation/stack/fuel qualification throughout the allowed envelope,
  beyond the selected stress and boundary cases above.
- Whole historical public API/package/CLI migration, external complex host ABI,
  cross-platform execution, the newer combined Amu root, release/controller
  integration and native CI.
- Multiple Cell/domain policy, shared Grant admission, a public consensus node,
  network delivery/acknowledgement and physical power-loss tests.

No existing service, default engine, route, RPC endpoint or production state
was changed. FEVM and full Ethereum state/proof equivalence are unqualified.
AWAI-81 remains open until its remaining acceptance criteria are met.
