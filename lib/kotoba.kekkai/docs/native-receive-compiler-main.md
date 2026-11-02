# Receive profile on the main-derived pool compiler — JUN-757

The receive checker requires an explicit `--compiler-profile`; a digest or
profile mismatch refuses. `pool-v4-35f-reference` retains the immutable3eb3f373
candidate as historical reference. `pool-v4-main-2f842` selects the efec3448
candidate from Amu2f8429d78 after the main merge. Neither is a silent fallback.
The current root is snapshotted and digest-checked before testing so concurrent
changes to a compiler checkout cannot change an in-flight producer.

The existing42-module responder corpus is unchanged:2081 packets, one1MiB
message in2048 reversed parts,38 whole-owner refusals,41 older guards and8
header probes. Normal and channel-fault runs are freshly executed under the
new producer. Their entire kernel/EFI files match the previously executed
normal/channel files, not merely a text segment or selected outputs.

For the codec/private-wipe/busy controls, the separate compiler-parity checker
stages each source-locked, previously executed fault corpus and uses native
Amu discovery/checking/compilation/packaging. Two kernel and two EFI generations
must match each other and the complete earlier executed files byte-for-byte.
It records `freshRuntimeExecution=false`: those three are producer/artifact
parity results carrying the earlier full runtime evidence, not three new boots.
All source bodies, runtime, code/stack/grant bounds and message quotas remain.

Fresh whole-owner snapshots are retained independently; dynamic allocation
details need not match across boots. Every refusal still requires identical
session/IO/log/8MiB-pool bytes before and after its own call. GDB writes only
the dedicated observation acknowledgement, never protocol or consent state.

Source-bound qualification is in
`evidence/native-receive-compiler-main-20261103/receipt.json`. It binds the
explicit producer, unchanged graph, full artifact identities, two fresh
runtime receipts and three parity receipts to the earlier executed controls.
This qualifies this responder diagnostic on the main-derived candidate. It
does not change Amu's global adoption/release flags or qualify initiator
composition, all network quota/concurrency combinations, product protection,
native Mac backend, Mac/6600H app installation/live peers, schema/pending
context/directed socket policy/fresh consent, native SSH or whole OS/L1 release.
