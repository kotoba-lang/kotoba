# Content-addressed app installation contract

Status: protocol contract, first implementation slice.

This contract describes the shared install behavior for apps launched through
`itonami.app`. It is intended for the Murakumo pilot and then every public app
domain. A hostname is a name for an app; it is not the app's content identity
or its execution host.

## Identity and authority

An app is identified by its reverse-DNS app ID and publisher DID. Its manifest
names an immutable bundle CID and may compose app-local cells, each with an
immutable dag-cbor DNA CID. A verified release descriptor binds the publisher,
monotonic release sequence, manifest CID, and decoded manifest.

The Awai/host adapter verifies the signed release, its chain predecessor, and
the manifest bytes before passing a normalized descriptor to
`kotoba.protocol.install`. This protocol namespace checks the descriptor's
shape and makes policy decisions; it does not verify signatures, DNSSEC, chain
history, or the bytes behind a CID. Those remain adapter responsibilities.

An external domain binding is a separate record that maps a DNS name to an app
ID, publisher, and release channel. Its owner signs the Awai binding, and the
domain publishes `awai-app=<domain/bind entry CID>` as a TXT record. The resolver
checks a fresh TXT answer for the exact binding CID, checks the binding expiry,
and matches the selected release and manifest to the same app, publisher, and
channel. The binding never replaces the app ID, publisher, release CID, or
bundle CID. Resolving a domain grants no app capability.

## Local install and update rules

The portable install lock contains the app ID, publisher, selected release
channel, sequence, release and manifest CIDs, bundle CID, cell-to-DNA-CID map,
and manifest-requested capabilities. It deliberately excludes a domain name,
local paths, and user approvals. Hosts must protect their local lock and keep
user approvals in host-owned state; downloading a lock is not user consent.

The host's full installation record can separately retain the last verified
domain-binding CID and local grants for audit and recovery. Those facts are
host-owned state; they do not change the portable release identity or travel as
authority inside an app bundle.

An update must preserve app ID, publisher, and selected channel, and advance the
verified release sequence. Switching channels is a separate explicit action.
New requested capabilities are reported as a consent delta. Effective
capabilities are the exact intersection of the current manifest requests,
explicit local approvals, and the host's supported set. No wildcard grants are
recognized.

The shared capability registry includes `awai.cell.read` and
`awai.cell.write` for host-mediated access to an app's declared Awai cells.
Reads return accepted entry projections. Writes submit an app-provided signed
entry envelope to the Awai validator; the host does not expose its cell signing
key or local bearer token. The host rechecks the protected install lock and
cell scope for every operation. `awai.cell.write` is classified as risky, so
hosts using the bridge trust policy withhold it from unverified manifests.

The registry also includes `awai.policy.evaluate` for explicit, local-only
evaluation of the Kotoba policy bound to the installed domain. The app may
choose a declared export and provide typed input values, but cannot choose a
policy ID; the host resolves that from its protected installation origin.
Evaluation is read-only and does not authorize a host effect, Awai write, or
payment. It is not classified as risky because the operation stays in the
verified local policy bundle and returns only the deterministic result.

Changing, adding, or removing a cell's DNA CID requires an explicit cell
migration receipt before the update can commit. This first slice returns
`:requires-cell-migration`; DNA migration execution and receipts belong to the
app runtime and are not implemented here.

## Offline launch

After installation, a host can launch the cached app when it has verified the
release, manifest, bundle, and every referenced DNA CID against their bytes.
The launch decision does not require a live domain, registry, or content
transport. Domain-binding freshness is returned as separate status and does
not change the installed app's local identity or grants.

The host still owns secure local state, content retrieval and byte verification,
cell genesis and membership, revocation handling, and execution isolation.
This contract does not claim those runtime paths are already deployed or
qualified. In particular, it does not provide a Cloudflare fallback: independent
Awai/IPFS retrieval and the `itonami.app` resolver/runtime must be implemented
and qualified by their owning repositories before any public domain moves.
