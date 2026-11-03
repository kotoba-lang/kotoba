# Native session dependency discovery — JUN-757

The ARM session gate failed before building its session image when shared
`noise.native` acquired a `noise.blake2s-native` dependency. The observer's
old four-file Noise inventory omitted the new owner, and its Python regex
closure raised `KeyError`. That was a staging failure, not a session refusal
or a successful broker gate.

`scripts/check-session-native.py` now stages its explicit source inventory,
including the canonical BLAKE2s owner, then asks the pinned native Amu
`modules` command to discover the entry's graph. Python does not parse
namespace or require forms. It validates native output paths against the
staged byte snapshot and passes only those exact bytes to the existing
source-locked builder. Each returned path and namespace must be unique,
the entry must be included, and a changed or out-of-inventory file refuses.
The receipt records both the33-file inventory and the selected32-file graph;
the unused audit source is staged but excluded from the lock. KSL1 requires
the exact graph, so adding every staged file to its lock would be incorrect.

The protocol driver below its source-staging call, guest modules, runtime
grants, expected outcomes and nine existing controls are unchanged. This is
a dependency-staging repair, not a new broker or a relaxation of a check.

Local qualification uses the same immutable Amu commit as the ARM CI step,
`65359a092b6c552b5adf436a0c359bc91d1676d3`, root image SHA256
`8ebb44c5d6babf3a02ef7d1785291b9741f1f7c410a9ee8dce9185c95d6bd34d`.
An isolated Linux ARM container runs the complete existing observer with
network disabled and native traffic confined to loopback. Native discovery,
check, compilation and packaging succeed; three replicas exchange votes,
commit/attest and a fenced effect. Wrong identity, replay, unauthenticated
connections, tampered body, duplicate effect, budgets and missing-clock
retry refusal retain their actual native checks. Both planned retries are
observed. Same-container replicas do not prove independent operators or
infrastructure, a live L1 deployment, or an installed Kekkai app.

A separate source-discovery control omits the required BLAKE2s file. Native
Amu reports E6002 for the missing module; the observer stops before a session
build. That is an expected discovery refusal, distinct from the nine
protocol-runtime controls. An earlier Mac candidate check with a33-file
lock terminated with SIGTRAP and remains an unsuccessful probe; its precise
trap cause was not diagnosed. It is not counted as a passing negative control.

The [source-bound receipt](evidence/session-source-discovery-20261102/receipt.json)
binds the driver, selected source bytes, compiler/runner, native observations
and local reproduction. Only public receipts, source pins and result/log
hashes are published. Generated coordinator/replica identity directories and
their key material remain private in the isolated test workspace. This
qualification does not replace exact-head CI or qualify unrelated library
consumers, kernel profiles, physical peers or production release readiness.
