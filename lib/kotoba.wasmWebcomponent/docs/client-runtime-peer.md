# Bounded peer host extension

AWAI-325: client-runtime.v1 accepts an explicit `transport: libp2p` endpoint.
This extends the canonical validator/broker; products must consume these exact
bytes and must not represent native peers with fabricated HTTPS origins.

Required endpoint keys: `transport`, `peer-id`, `addresses`, `protocol`, `action`,
`max-request-bytes`, `max-response-bytes`, `timeout-ms`. This first profile
accepts 1–4 unique literal IPv4/UDP QUIC-v1 or WebRTC Direct multiaddresses, each ending in the
same declared base58 PeerID. Port zero, unspecified/multicast addresses, DNS,
gateways and other transports are refused. WebRTC Direct requires an explicit
base64url multibase certificate hash. Hosts must also parse and validate the
PeerID and multiaddress with libp2p and verify authenticated remote identity.

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
