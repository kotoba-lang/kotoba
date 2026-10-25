# Production transport and workload identity qualification

W4 combines TLS 1.3 mutual authentication, peer identity and certificate
binding, online revocation checks, short-lived SPIFFE workload identities,
hardware-custodied CA signing, overlap rotation, old-certificate revocation,
rollback denial, and the production evidence plane.

The shared gate fails closed when a TLS downgrade is attempted, either peer is
not mutually authenticated, the workload identity is stale or overlong, CA key
custody is exportable or unattested, rotation events are incomplete or
reordered, or evidence is local, replayed, unsigned, or artifact-unbound.

Passing fixtures do not qualify a production CA. W4 remains pending until the
deployed CA/HSM and workload identity authority produce independently verifiable
remote E4 receipts.
