# Routing

Routing answers **which peer should be contacted next for this key, name, or
peer?** It is content routing, not packet routing.

The implementation authority is `io-libp2p-specs-kad-dht`, including
`/ipfs/kad/1.0.0` and delegated HTTP routing. Being a DHT node and reading a
signed record through quorum are separate responsibilities.

| | Routing | Discovery |
|---|---|---|
| Question | Who should be queried next? | Who is indexed as serving the CID? |
| Example | Kad peer lookup | IPNI/provider record |

`GET /routing/v1/ipns/{k51}` performs naming resolution through a routing
surface; the returned object's identity is still its CID.

`GET /routing/v1/peers/{peer-id}` returns reachable addresses and protocols for
a peer. It is different from discovery's `GET /providers/{cid}`. The injected
live seam is `kotoba.protocol.route/lookup-live`, normally backed by
`kad.routing/find-peers`. If an adapter returns a different peer ID, the result
fails closed with `:peer-mismatch`.

This protocol does not claim that Kad signs provider advertisements. IPIP-0526
is historical and did not settle canonical signing bytes, so the contract does
not invent them.
