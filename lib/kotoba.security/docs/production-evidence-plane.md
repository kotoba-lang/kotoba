# Production evidence plane

The shared verifier in `kotoba.security.evidence-plane` admits E4 evidence only
when a production receipt is fresh, authority-signed, artifact- and
control-bound, part of an ordered hash chain, absent from durable replay state,
stored by a qualified remote immutable adapter, and covered by an independently
signed log head.

Storage and signing remain injected provider boundaries. Passing unit fixtures
prove verifier behavior, not production operation. A deployment must qualify
the remote append-only provider and authorities, retain consumed nonces outside
the submitted batch, and archive the signed head before any repo moves from E3
to E4.

The machine-readable policy is
[`production-evidence-plane.edn`](../policy/production-evidence-plane.edn).
Local files, simulations, self-asserted storage booleans, and unsigned CI output
must never be presented as E4 evidence.
