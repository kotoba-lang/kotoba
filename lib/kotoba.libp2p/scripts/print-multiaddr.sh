#!/usr/bin/env bash
# print-multiaddr.sh — emit Multiaddrs that identify this Kubo node's
# libp2p endpoint, in the forms useful for ADR-2605241800 publication.
#
# Usage:
#   ./print-multiaddr.sh [format]
#
# Formats:
#   peer       (default) — /p2p/<peer-id>
#   dnsaddr            — /dnsaddr/etzhayyim.com/p2p/<peer-id>
#   all-local          — every /ip4/.../tcp/4001/p2p/<peer-id> the host listens on
#   all                — every form, separated by newlines

set -euo pipefail

FORMAT="${1:-peer}"
PEER_ID="$(ipfs id -f '<id>')"

case "${FORMAT}" in
  peer)
    echo "/p2p/${PEER_ID}"
    ;;
  dnsaddr)
    echo "/dnsaddr/etzhayyim.com/p2p/${PEER_ID}"
    ;;
  all-local)
    ipfs id -f '<addrs>' | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$'
    ;;
  all)
    echo "/p2p/${PEER_ID}"
    echo "/dnsaddr/etzhayyim.com/p2p/${PEER_ID}"
    ipfs id -f '<addrs>' | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$'
    ;;
  *)
    echo "Unknown format '${FORMAT}'. Choices: peer | dnsaddr | all-local | all" >&2
    exit 2
    ;;
esac
