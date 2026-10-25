# Information-flow residual risk and non-claims

The stack enforces explicit classification labels at its documented admission,
storage, disclosure and network egress boundaries. Structured audit data is
redacted before persistence. These controls reduce accidental and direct
application-layer disclosure.

They do not claim elimination of covert or side channels. In particular, the
current implementation does not provide constant-time whole-program execution,
termination-insensitive noninterference, cache or branch-predictor isolation,
traffic-flow confidentiality, packet-size hiding, timing-channel elimination,
power/EM resistance, or protection from a fully compromised host kernel.

Secrets must therefore remain inside the narrowest available capability and
hardware boundary. Deployments handling restricted data must additionally use
workload isolation, traffic padding where justified, rate limits, remote audit
sinks, and platform-specific side-channel qualification. Logs are evidence, not
a secret transport; callers must pass structured fields and must not encode
secrets into arbitrary identifiers or timing.
