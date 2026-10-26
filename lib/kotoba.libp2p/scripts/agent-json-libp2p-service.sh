#!/usr/bin/env bash
# agent-json-libp2p-service.sh — print a JSON fragment suitable for
# splicing into an IPFS-pinned agent.json `service[]` array (per
# ADR-2605241800 §D1). Two entries are emitted:
#
#   1. /p2p/<this-node-peer-id>                     ← primary
#   2. /dnsaddr/etzhayyim.com/p2p/<this-node-peer-id>  ← cold-boot fallback
#
# The fragment is a JSON array; consumers may concatenate to an
# existing service[] array or substitute wholesale.
#
# Usage:
#   ./agent-json-libp2p-service.sh [protocol-version]
#
# Output: JSON array on stdout.

set -euo pipefail

VERSION="${1:-1.0}"
PROTOCOL="/x/etzhayyim/xrpc/${VERSION}"
PEER_ID="$(ipfs id -f '<id>')"

cat <<EOF
[
  {
    "id": "#xrpc-libp2p-primary",
    "type": "AtprotoXrpc",
    "serviceEndpoint": "/p2p/${PEER_ID}",
    "x-libp2p-protocol": "${PROTOCOL}"
  },
  {
    "id": "#xrpc-libp2p-bootstrap",
    "type": "AtprotoXrpc",
    "serviceEndpoint": "/dnsaddr/etzhayyim.com/p2p/${PEER_ID}",
    "x-libp2p-protocol": "${PROTOCOL}",
    "x-rationale": "DNS-anchored fallback for cold clients; resolved via libp2p dnsaddr + Mainline DHT"
  }
]
EOF
