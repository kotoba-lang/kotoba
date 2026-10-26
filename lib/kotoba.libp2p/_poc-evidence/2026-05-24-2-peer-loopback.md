PoC date: 2026-05-23T08:57:29Z
Kubo version: ipfs version 0.41.0
Host peer:     12D3KooWGRnHP5hHAxSnPQE5gopDqAzWkZ2NAFi2ZZ6o85FnAiEc
Consumer peer: 12D3KooWM7m3fhPBDnTLxfMj44oN1fGCfzjuifS9oxkbzE5z1bdX

## Protocol: /x/etzhayyim/xrpc/1.0

## Host listen:
/x/etzhayyim/xrpc/1.0 /p2p/12D3KooWGRnHP5hHAxSnPQE5gopDqAzWkZ2NAFi2ZZ6o85FnAiEc /ip4/127.0.0.1/tcp/18080

## Consumer forward:
/x/etzhayyim/xrpc/1.0 /ip4/127.0.0.1/tcp/29080 /p2p/12D3KooWGRnHP5hHAxSnPQE5gopDqAzWkZ2NAFi2ZZ6o85FnAiEc

## End-to-end round trip:
$ curl http://127.0.0.1:29080/echo-payload.json
{"$type":"com.etzhayyim.libp2p.echo","msg":"hello over libp2p","ts":"2026-05-24T17:50:00Z"}


Direct backend GET vs tunneled GET diff:
PASS — bytes identical
