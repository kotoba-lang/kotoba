# yobidashi (呼び出し)

**Incoming-call standby without a push service.** Cellular-style paging,
rebuilt for a mesh:

- `yobidashi.schedule` — DRX-like listening slots derived from the device's
  page destination; the home node computes the same slot. `:lora` profile:
  60 ms window per 2.56 s cycle (~months on a 1000 mAh cell for paging alone).
- `yobidashi.ring` — the ring: ~180 bytes, encrypted to the device, signed by
  the home node, one LoRa frame. Device ack stops paging other devices. A
  28-byte BLE wake frame lets a LoRa companion wake the phone (no APNs/FCM).
- `yobidashi.invite` — caller-device-signed invite with the attachments a
  home node needs to decide offline (device cert, introductions, community
  claims, stamp).
- `yobidashi.home` — the home node: enroll (must hold a `:home` cert from the
  user's root), device location records, `handle-invite` → monban → page
  effects, `handle-ack`, `tick` re-paging into the next window until answered
  or expired to voicemail.

LoRa airtime for one ring: ~0.29 s at SF7, ~0.92 s at SF9 (125 kHz) — see
`denwa.bearer/airtime-ms` and `kiss.airtime`.

```sh
npm test
```
