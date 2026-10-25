# kotoba-lang/org-lora-alliance-lorawan

**LoRaWAN L2 1.0.4 Specification (LoRa Alliance, TS001-1.0.4, © 2020) —
MHDR/FHDR/MACPayload framing, Join-Request/Join-Accept, the MIC (AES-CMAC,
RFC 4493) and FRMPayload encryption scheme, and five representative MAC
commands — in portable `.cljc`.**

## Surface

```clojure
(require '[lorawan.frame :as frame] '[lorawan.join :as join])

(frame/encode-data-frame
  {:ftype :unconfirmed-data-up :dev-addr 0x26011BDA :fcnt32 5
   :fctrl {:adr true} :fport 1 :payload [0xDE 0xAD 0xBE 0xEF]
   :nwk-s-key nwk-key :app-s-key app-key})
;=> {:status :ok :bytes [...]}

(frame/decode-data-frame wire-bytes {:fcnt32 5 :nwk-s-key nwk-key :app-s-key app-key})
;=> {:status :ok :dev-addr 0x26011BDA :fport 1 :payload [0xDE 0xAD 0xBE 0xEF] ...}
```

| namespace | |
|---|---|
| `lorawan.bytes` | little-endian byte helpers — the one place the wire's byte-order convention lives |
| `lorawan.phy` | §4 — MHDR, FCtrl, FHDR, MACPayload, PHYPayload framing (structural only, no crypto) |
| `lorawan.cmac` | AES-CMAC (RFC 4493), built on `org-nist-aes`'s forward cipher — no second cipher |
| `lorawan.mic` | §4.4/§6.2.5/§6.2.6 — the B0/Ai-prefixed CMAC for data frames, Join-Request, Join-Accept |
| `lorawan.crypt` | §4.3.3 FRMPayload keystream encryption; Join-Accept **decode**-side decryption |
| `lorawan.join` | §6.2 — Join-Request (encode+decode), Join-Accept (**decode only**, see below), session-key derivation |
| `lorawan.frame` | end-to-end data-frame encode/decode: framing + MIC + FRMPayload crypto together |
| `lorawan.mac-command` | §5 — the full CID registry, real codecs for `LinkCheck`/`LinkADR`/`DutyCycle`/`RXParamSetup`/`DevStatus` |

Bytes are `Sequential` collections of ints in 0..255, in and out (this
workspace's `org-modbus` convention).

## The little-endian trap this whole library is built around

LoRaWAN's own "Document Conventions" (PDF page 8, before §1
Introduction — verified by full-text extraction of the spec PDF, not
recalled from memory):

> The octet order for all multi-octet fields SHALL be little endian.
> EUI are 8-octet fields and SHALL be transmitted as little endian.

Every multi-byte field — `DevAddr`, `DevEUI`, `JoinEUI`, `DevNonce`,
`JoinNonce`, `NetID`, `FCnt` — goes on the wire **least-significant byte
first**. A `DevAddr` configured as the conventionally-written hex string
`26011BDA` appears on the wire as the four octets `DA 1B 01 26`. This is
the single most common source of bugs in LoRaWAN implementations — for
the same reason `org-modbus` singles out its reflected CRC polynomial: it
*looks* correct (the value round-trips against itself) and disagrees with
every other implementation. `lorawan.bytes/le-n`/`le->int` are the only
place that convention lives.

## Real crypto, reused not reinvented

`kotoba-lang/org-nist-aes` provides the AES-128 forward cipher and
nothing else (by its own design — GCM/CTR/CMAC never need the inverse
cipher). Everything here is built *on top of* that one primitive:

- **AES-CMAC (RFC 4493)** for the MIC — `lorawan.cmac`, verified against
  RFC 4493 §4's own published test vectors (key
  `2b7e151628aed2a6abf7158809cf4f3c`, four messages of 0/16/40/64 bytes,
  fetched from rfc-editor.org).
- **FRMPayload encryption** (§4.3.3) is an AES-CTR-shaped keystream —
  encrypt a counter block, XOR — so encrypt and decrypt are the *same
  operation*; both directions are fully implemented and reused.
- **Join-Accept encryption** (§6.2.6) is the one place this library needs
  the AES-128 *inverse* cipher, and only in one direction. The spec's own
  words: "An AES decrypt operation in ECB mode encrypts the Join-Accept
  frame so that the end-device can use an AES *encrypt* operation to
  decrypt the frame. This way, an end-device has to implement only AES
  encrypt but not AES decrypt." **`decode-join-accept` (the end-device's
  role) is fully implemented and reuses `org-nist-aes` as-is.
  `encrypt-join-accept` (a join server's role) does not exist here** — it
  needs the true AES-128 inverse cipher (InvSubBytes, InvShiftRows,
  InvMixColumns, the key schedule read backwards), which neither
  `org-nist-aes` nor this library implements. A real, bounded gap, not a
  hidden one — see `lorawan.crypt`'s docstring.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule —
`:lorawan/mic-mismatch`, `:lorawan/frame-too-short`,
`:lorawan/buffer-underrun`, `:lorawan/bad-fopts-len`,
`:lorawan/fopts-len-mismatch`, `:lorawan/missing-fport`,
`:lorawan/bad-join-request-length`, `:lorawan/bad-join-accept-length`,
`:lorawan/wrong-ftype`, `:lorawan/not-a-data-frame`,
`:lorawan/mac-command-field-out-of-range` among them. **Those keywords
are contract.** The full 32-bit frame counter (not the 16-bit wire
`FCnt`) is an explicit argument to every MIC/crypto function — see
`lorawan.mic`'s docstring for why reconstructing it from traffic is a
Network Server's job this stateless codec does not do.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb -M:oracle                                                      # + independent JVM AES cross-check
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

**LoRaWAN's own spec text gives no worked byte-level examples** for a MIC,
an encrypted frame, or a Join-Accept (unlike Modbus's §6) — only the
algorithms. Correctness rests on:

1. **RFC 4493's own published CMAC test vectors** for the one piece that
   *does* have a canonical answer.
2. **An independent JVM AES oracle** (`oracle/lorawan/join_oracle_test.cljk`,
   `javax.crypto`, same pattern as `org-nist-aes`'s own `:oracle` alias):
   builds a Join-Accept the way a join server would — CMAC with this
   library, then cipher with the JVM's `Cipher` in `DECRYPT_MODE` — and
   confirms this library's `decode-join-accept` (which internally does AES
   *encrypt*) recovers the original fields. Two unrelated implementations
   of the inverse-cipher direction, so getting it backwards in *either*
   one shows up as a mismatch, not a pass.
3. Self-consistency (`decode(encode(x)) == x`) over a 200-iteration
   randomised sweep of full data frames (deterministic LCG, reproducible
   across the JVM/ClojureScript hosts) plus a from-scratch alternate
   reimplementation of §4.3.3's algorithm, agreed against independently.
4. Negative tests asserting the *specific* named reason keyword — most
   importantly `:lorawan/mic-mismatch`, checked with a discrimination
   proof: flip one payload byte (leaving the MIC alone), confirm the MIC
   check fails *before* decryption ever runs, restore, re-verify green.
5. Hand-derived bitfield layouts (MHDR's FType/Major nibble split, LoRaWAN
   little-endian DevAddr, `LinkADRReq`'s DataRate/TXPower nibble packing,
   `DevStatusAns`'s 6-bit signed SNR) checked against the spec's own
   tables, not just round-tripped against themselves.

Where a value is hand-derived rather than published, it's commented
`constructed, not a published spec vector`.

## Not here

**Encoding a Join-Accept** (a join server's role) — see above; needs the
AES-128 inverse cipher.

**14 of LoRaWAN's ~19 MAC commands.** `NewChannelReq`, `RXTimingSetupReq`,
`TXParamSetupReq`, `DlChannelReq`, `DeviceTimeReq` and the Class B set
(§9–12) are in the spec's CID registry (`lorawan.mac-command/cid->name`
has the full table) but not individually codec'd — the five implemented
(`LinkCheck`, `LinkADR`, `DutyCycle`, `RXParamSetup`, `DevStatus`)
establish the CID-dispatch and bitfield-packing pattern; the rest is
low-risk, high-volume table transcription that would not demonstrate
anything new. `lorawan.mac-command`'s docstring names this explicitly.

**Radio, timing, regional parameters, ADR algorithm state, Class B/C.**
This is a MAC-frame codec — encode fields to bytes, decode bytes back to
fields, compute and verify the MIC, encrypt/decrypt FRMPayload. No radio,
no sockets, no threads, no `[RP002]` regional channel plans, no receive-
window timing, no beacon slot randomization (§9–11).

## License

Apache License 2.0.
