# Native full1MiB application schema — JUN-757

Eight gzip files preserve original native receipts: one normal schema run,
five faults, and both-role encrypted receive regressions. All complete their
entire respective corpus. Failed/refused/timed out probes never count as passes.

native-snapshots.tar.gz preserves2174 individually gzipped native memory dumps.
All members were reopened/decompressed and hash-matched. Schema checkpoints
compare all1MiB+1 input,8193 private work and65537 output bytes to independent
public expectations. Both NIC regressions compare all session/IO/log/8MiB-pool
bytes across38 refusal calls per role. GDB only acknowledges test receipts.

The initial header-mask fault was not detected by the old corpus; it is
retained as failed. Explicit known-but-opposite-direction header vectors were
added, and every final schema run repeats all87 cases. Wipe fault detection is
an independent complete-work-byte mismatch (native return assertions alone
remain zero), not a native trap. The limit fault detects loss of full capacity.

These are data component and receive regression proofs, not actual schema
dispatch, installed Mac/6600H apps, pending256/controller/service/port/socket
policy, fresh trusted consent, nativeSSH, isolation or OS/L1 production readiness.
See ../../native-application-message.md for contracts and remaining scope.
