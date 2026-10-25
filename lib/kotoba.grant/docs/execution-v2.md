# V2 execution integration

The target-independent shape owner is `kotoba.core.execution`. Physical profiles
are in `kotoba.abi.target`; canonical content blocks are in
`kotoba.artifact.execution`. The authority issues a fresh invocation block,
selects immutable plan/policy/basis and permission ceilings, derives a permit
through `grant.execution-decision`, issues leases and signs the intent/leases.
Kototama verifies those blocks and signatures before admitting a host mechanism.

The pre-execution intent includes `invocation-cid`. It has no outcome or receipt.
A lease's existing `execution-identity-cid` field names this intent. Completion
creates a new identity CID from observed output and executor-signed receipts;
its existing v2 field set is unchanged. A fresh invocation permits another run
at the same basis; replay or a second intent for the same invocation is denied.

The v2 path is explicit. V1 descriptors, WIT, hashing, signatures and default
CLI admission remain compatible. Content verification is not authorization;
fixture coverage and main integration do not establish Q9 or production readiness.
