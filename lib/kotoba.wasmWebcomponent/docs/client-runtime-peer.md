# Bounded peer host extension

AWAI-325: client-runtime.v1 accepts an explicit `transport: libp2p` endpoint.
This extends the canonical validator/broker; products must consume these exact
bytes and must not represent native peers with fabricated HTTPS origins.

Required endpoint keys: `transport`, `peer-id`, `addresses`, `protocol`, `action`,
`max-request-bytes`, `max-response-bytes`, `timeout-ms`. This first profile
accepts 1–4 unique literal IPv4 QUIC-v1, WebRTC Direct or TCP multiaddresses, each ending in the
same declared base58 PeerID. Port zero, unspecified/multicast addresses, DNS,
gateways and other transports are refused. WebRTC Direct requires an explicit
base64url multibase certificate hash. Hosts must parse the PeerID and multiaddress with libp2p, verify authenticated
remote identity, and use Noise/TLS for TCP; plaintext TCP is not supported.

Requests and JSON-compatible responses are capped at 1 MiB; deadlines at
60 seconds. The canonical consent host displays exact PeerID, addresses,
protocol, action, limits and data categories. Payload is snapshotted before
consent; denial/synthetic clicks do not invoke the host. Approved operations
still ask again. Peer routes never enter HTTP CSP `connect-src` and cannot
declare HTTP redirects or artifact options. No socket is provided by this JS.

The trusted shell captures `peerAdapters[service][operation]` at broker creation.
Handlers receive frozen `{operation, payload, signal}`. They must enforce exact
protocol/action, request shape, identity/address scope, native byte limits and
deadline, and stop active transport on cancellation. No other peer discovery,
automatic redial, provider, relay or HTTP fallback is authorized by one peer
operation. Browser WebRTC uses only declared Direct addresses with no external
STUN/HTTP discovery; NAT/relay/discovery profiles need separate declarations.

As with existing browser handlers, adapters belong to the verified host realm,
not arbitrary guest code. This extension does not turn trusted-page-v1 into a
sandbox. Restricted guests reach only bounded broker invocation. A native host
must independently bound transport resources; JavaScript response limits do
not protect a decoder that already allocated oversized native data.

Native QUIC authenticates transport identity; this does not establish account
identity, dango authorization, publisher admission, private-data E2EE or the
post-quantum envelope. Aozora's initial adapter is public-block connectivity
only. No private-data or Native/selfhost qualification is conferred.

## AWAI-3001 bounded snapshot and receive profile

A literal-IP address may explicitly name one authenticated relay PeerID and
`/p2p-circuit/p2p/<targetPeerID>`; target and relay must differ. No relay or
provider is selected implicitly. A new optional `scope` is admitted only with
`/awai/yataverse/1.0.0` and `sync-push`, `sync-pull`, `pin-query` or
`receive-snapshot`. It requires exact `snapshot-cid` (CIDv1 base32 syntax) and
`max-transfer-bytes` (1..256 MiB). Native hosts must parse/verify CIDs and enforce
this quota independently; response-message limits do not cover network traffic.

`receive-snapshot` additionally requires exact `listen-address` (literal IPv4
TCP/QUIC or one selected relay circuit, no unspecified address/port zero) and
`receive-ms` (1..21600000, at most six hours) and an explicit boolean
`allow-read-back`. False permits receiving/pin/query metadata only; true also
allows that same peer to fetch the same snapshot within the byte/time budget. Its `addresses` may be empty; the
endpoint PeerID identifies the only authorized incoming peer. The canonical
trusted dialog shows the full immutable scope before fresh approval. Starting a
receive operation creates one named, bounded host session; the operation deadline
bounds startup. The native host owns its separate timer, byte admission and
explicit Stop command after startup has returned. No automatic restart, renewal,
peer change, new snapshot or provider enrollment follows from that approval.

Android must show the active receive service and stop on notification Stop,
expiry, OS foreground-service timeout or host failure. This is not guaranteed
indefinite/background execution. Provider-side approval and sender-side approval
remain independent; a sender does not grant remote storage. Receipt signatures
are transport observations, not account/PQ/publication authority.
