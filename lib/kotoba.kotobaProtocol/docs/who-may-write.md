# Who may write

A hostname cannot authorize a write. Keys authorize writes.

- principal: `did:key`
- mutable name: key-derived IPNS
- consent: CACAO — a person or wallet agreeing once; a depth-1 self-mint is the
  default for an actor's own graph
- delegation: Biscuit — principal to principal, attenuated offline
- decision: the `authority` lattice (`covers?` / `meet`). One implementation
- admission: a governor rejects an intent before the actor reaches the log
- accountability: an intent naming an `:action` must hold the tier its policy
  requires ([Accountability tiers](accountability.md))

CreateLink-shaped overlay writes pass through this boundary before reaching a
datom log or DHT metadata. Authorization to add an overlay does not authorize a
block rewrite, so the target entry CID remains unchanged.

The model follows Inga's "an actor writes only its own chain" rule. It does not
adopt a Holochain conductor or unordered write surface; an ordered log gives a
Datalog join one current reference.

There is no live HTTP endpoint here. The executable seam is
`kotoba.protocol.govern/write-overlay`. Its default `decide` function does not
verify signatures—cryptography belongs to `org-chainagnostic-cacao`/`org-ietf-ed25519`—but the shape
still fails closed:

- own graph with no CACAO: allow as a depth-1 self-mint
- own graph with a depth other than 1: deny
- another actor's graph: deny with `:foreign-chain`
- hostname-shaped author: deny with `:not-a-key`
- missing governor function: deny rather than defaulting to allow

A denied intent never reaches the action log and cannot advance its parent CID.

## Delegation is Biscuit. The decision engine is not duplicated here

Root ADR-2608180200 makes Biscuit the delegation centre for this workspace and
moves CACAO from delegation down to human consent. One measured property decides
it:

- a macaroon chains with an HMAC, so **verifying needs the root secret**
- a Biscuit chains with public keys, so **verifying needs only the root public key**

These planes are verified at the edge — Workers, browsers, untrusted mirrors.
Putting a root secret in every one of those contradicts the rule that a server
must not hold what it must not leak (ADR-2608070400 D1). Biscuit removes the
conflict structurally: a verifier can check a credential it could not issue, and
so holds nothing worth stealing.

Attenuation needs no key at all, so a token handed to an agent can be narrowed to
one CID, one operation and five minutes **without asking the issuer**. That is
what makes per-agent least privilege practical rather than aspirational.

The decision itself is not re-implemented here, and not in Biscuit either. Scope
covering is `authority`'s `covers?` and `meet`; the named model is kotoba's
`lang/capability-semantics.edn` (`:cap/kind`, `:cap/resource`, `:cap/holder`).
Biscuit is the wire those travel on. CACAO and UCAN keep narrower named roles
rather than being removed.

### What the seam admits today

`kotoba.protocol.govern/decide` implements the CACAO self-mint shape above and
**nothing else** — it does not yet admit a grant carried by a Biscuit. That is a
gap in this seam, not a second delegation model. Recording it here is what keeps
the declared plane and its implementation from drifting apart quietly.

### Reads are a different question

Where an object is sealed (`kotoba.protocol.sealed`), a reader who cannot unwrap
the content key cannot read it, whatever the store chooses to serve. So on a
sealed plane this boundary governs **write and discovery**; confidentiality is
carried by the object itself, not by the permission check. That is why the choice
of storage provider is a durability question rather than a trust one
(ADR-2608301039).
