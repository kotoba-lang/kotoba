# denwa (電話)

**A telephone that needs no telephone company** — calls, paging, identity and
spam control over a mesh of LoRa radios, Wi-Fi, community LTE cells or the
Internet, written entirely in kotoba, cryptography included.

`denwa` is the top of the stack: call signalling, voice frames, the jitter
buffer, G.711 μ-law, and bearer/codec selection. It ships the end-to-end test
that runs every layer together.

## The stack

| repo | role | replaces, in a carrier network |
|---|---|---|
| [tsunagi](../tsunagi) | overlay: self-certifying addresses, announces, routing, links, store-and-forward | the core network |
| [nafuda](../nafuda) | root/device keys, revocation, guardian recovery, contact cards, community names | the numbering plan, SIM, HLR subscriber data |
| [monban](../monban) | call admission: contacts, vouches, introductions, community quota, PoW stamps, credit postage, blocklists | spam filtering (which carriers mostly don't do) |
| [yobidashi](../yobidashi) | paging slots, encrypted rings, the home node | paging channel, HLR/VLR, push notification services |
| **denwa** | call state, media, jitter buffer, codecs, bearer choice | the switch and the media plane |
| [kowane](../kowane) | LPC vocoder, 2400 / 1200 bit/s | narrowband codecs |
| [kiss](../kiss) | KISS framing to a LoRa modem, 920 MHz airtime governor | the radio interface |
| [shamir](../shamir) | GF(256) secret sharing for key backup | — |

Underneath: `org-ietf-x25519`, `org-ietf-ed25519`, `org-ietf-chacha20-poly1305`,
`org-nist-sha2`, `org-ietf-hpke`, `moyai-ledger` — all first-party kotoba.

## A call, end to end (`test/denwa/e2e_test.cljk`)

```
alice-phone ─── relay ─── bob-phone
                  │
               bob-home
```

1. Nodes announce; the relay learns paths.
2. Alice opens a link to Bob's **home node** and sends a signed invite (split
   into resource parts; it carries her device certificate).
3. The home node verifies the certificate, runs **monban** (Alice is a
   contact → ring), and sends a **ring** through the relay into Bob's
   listening slot.
4. Bob's phone verifies the ring was signed by his own home node, acks it,
   and **dials back** to Alice's callback destination. Alice checks that the
   answering device is certified by the root she meant to call.
5. Voice: LPC-2400 frames, 6 bytes per 20 ms, through the link into Bob's
   jitter buffer.

## Call modes by bearer

| bearer | mode | codec |
|---|---|---|
| Wi-Fi / mesh / LTE / Internet | full duplex | PCMU, 20–40 ms |
| LoRa (SF7/125 kHz, duty-limited) | push-to-talk | LPC-1200, 200 ms |

## Not done yet

- Radio/BLE/serial **drivers** (host I/O): the libraries are pure; a host
  binds `tsunagi.transport` effects to a UDP socket, a KISS serial port or a
  BLE characteristic.
- Audio capture/playback (host I/O).
- Constant-time X25519/Ed25519.
- PSTN / emergency-call gateway (needs a licensed operator).
- iOS: BLE-accessory wake is the path; APNs only as optional fallback.

```sh
npm test
```
