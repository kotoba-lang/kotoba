# ADR-0124: K16 direct HTTPS stops on FIN and retries a bounded node POST

## Status

Accepted (2026-08-30)

## Context

The physical K16 reached `TEST DIRECT HTTPS` after admitting the exact
10,934,860,704-byte model and executing the frozen first-token path.  Its TLS
ClientHello reached `api.murakumo.cloud`, but the server closed after the
handshake flight.  The one-buffer RTL8125 pump acknowledged that FIN as though
it were an ordinary empty data segment and entered another 200,000,000-iteration
receive budget.  The screen therefore remained at `TEST DIRECT HTTPS` and no
signed result POST was observed.

The signed HTTP request may occupy all 1,024 configured bytes.  A protected
HTTP record plus ClientFinished can require 1,104 bytes, while the physical
path supplied a 512-byte stack buffer.  That overflow had not yet been reached
because the handshake stopped first, but it would make a later success unsafe.

## Decision

The physical direct path now:

- acknowledges a peer FIN and fails that attempt immediately;
- uses a 10,000,000-iteration receive budget instead of 200,000,000;
- gives a signed node result up to three TLS attempts, each with fresh RDRAND
  ClientHello/X25519 material, a distinct local port and a distinct TCP ISN;
- retains one attempt for the fixed transport-only qualification profile; and
- holds ClientFinished plus the maximum protected HTTP record in a static
  1,152-byte buffer with a compile-time size assertion.

Attempt count and the TLS stage are included in serial evidence.  Success still
requires an admitted HTTP 2xx response; a retry is not itself success.

## Evidence boundary

The earlier physical run proves model-path-to-TLS reachability, not a Murakumo
POST, node registration or inference speed.  These changes remain physical-K16
unverified until a new one-shot image returns code 8160 and Murakumo records the
signed result.
