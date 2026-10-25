(ns lorawan.mic
  "LoRaWAN L2 1.0.4 §4.4 \"Message Integrity Code (MIC)\" for data frames,
  and the equivalent MIC computations §6.2.5/§6.2.6 define for Join-Request
  and Join-Accept. All three are `AES-128-CMAC(key, prefix-block | msg)[0..3]`
  — `lorawan.cmac` does the CMAC; this namespace only builds the
  spec-defined prefix block and the message each frame type CMACs over.

  ## The full 32-bit frame counter, not the 16-bit wire `FCnt`

  §4.4's `B0` block (Table 13) and §4.3.3's `Ai` block (Table 12) both
  carry a 4-byte `FCntUp`/`FCntDown` — the end-device's/network's full
  32-bit counter — not the 16-bit `FCnt` that actually goes on the wire in
  `FHDR` (§4.3.1.5: \"the `FCnt` field SHALL correspond to the
  least-significant 16 bits\"). Reconstructing the high 16 bits from
  observed traffic is a Network Server's job — \"the server must infer the
  16 most-significant bits … by observing the traffic\" (§4.3.1.5's own
  note) — and this is a stateless codec with no traffic to observe. Every
  function here takes the full 32-bit counter as an explicit argument; it
  is the caller's job to track and supply it."
  (:require [lorawan.bytes :as b]
            [lorawan.cmac :as cmac]))

(def dir-uplink 0)
(def dir-downlink 1)

(defn- b0-block
  "§4.4 Table 13: `0x49 | 4×0x00 | Dir | DevAddr | FCntUp-or-Down | 0x00 |
  len(msg)`. `len-msg` must fit in one byte (`MACPayload` is capped at 250
  or so octets by every region's `RP002` max-payload table, so this is not
  a realistic ceiling in practice, but it's checked rather than silently
  truncated)."
  [dir dev-addr fcnt32 len-msg]
  (if (> len-msg 255)
    {:status :error :reason :lorawan/mic-message-too-long :length len-msg}
    {:status :ok
     :bytes (-> [0x49] (into (repeat 4 0)) (conj dir)
                (into (b/le-n dev-addr 4)) (into (b/le-n fcnt32 4))
                (conj 0) (conj len-msg))}))

(defn data-frame-mic
  "`msg` is `MHDR | FHDR | FPort | FRMPayload` (§4.4) — the already-
  encrypted `FRMPayload`, per §4.3.3's own ordering note (\"it SHALL be
  encrypted before the MIC is calculated\"). Returns `{:status :ok :mic
  […4 bytes…]}`."
  [nwk-s-key dir dev-addr fcnt32 msg]
  (let [b0 (b0-block dir dev-addr fcnt32 (count msg))]
    (if (= :error (:status b0)) b0
        (let [r (cmac/cmac nwk-s-key (into (:bytes b0) msg))]
          (if (= :error (:status r)) r
              {:status :ok :mic (subvec (:mac r) 0 4)})))))

(defn verify-data-frame-mic
  "`true`/`false` — not the MIC bytes, so a caller can't accidentally
  compare a `false` against a truthy non-boolean and get the wrong
  answer. Named `:lorawan/mic-mismatch` at the call site
  (`lorawan.frame`), not here — this function only computes and compares."
  [nwk-s-key dir dev-addr fcnt32 msg received-mic]
  (let [r (data-frame-mic nwk-s-key dir dev-addr fcnt32 msg)]
    (and (= :ok (:status r)) (= (:mic r) (vec received-mic)))))

;; ── Join-Request — §6.2.5 ────────────────────────────────────────────────────

(defn join-request-mic
  "`CMAC = aes128_cmac(AppKey, MHDR | JoinEUI | DevEUI | DevNonce)`.
  `join-eui`/`dev-eui` are 8-byte EUIs (little-endian, per the document-
  wide rule `lorawan.bytes` cites), `dev-nonce` a 16-bit counter."
  [app-key mhdr-byte join-eui dev-eui dev-nonce]
  (let [msg (-> [mhdr-byte] (into (b/le-n join-eui 8)) (into (b/le-n dev-eui 8))
                (into (b/le-n dev-nonce 2)))
        r (cmac/cmac app-key msg)]
    (if (= :error (:status r)) r {:status :ok :mic (subvec (:mac r) 0 4)})))

;; ── Join-Accept — §6.2.6 ─────────────────────────────────────────────────────

(defn join-accept-mic
  "`CMAC = aes128_cmac(AppKey, MHDR | JoinNonce | NetID | DevAddr |
  DLSettings | RXDelay | CFList)`. `cf-list` is the optional 16-byte
  region-specific blob (§6.2.6, `[RP002]`) — passed through as opaque
  bytes, `[]` when absent."
  [app-key mhdr-byte join-nonce net-id dev-addr dl-settings rx-delay cf-list]
  (let [msg (-> [mhdr-byte]
                (into (b/le-n join-nonce 3)) (into (b/le-n net-id 3))
                (into (b/le-n dev-addr 4)) (conj dl-settings) (conj rx-delay)
                (into cf-list))
        r (cmac/cmac app-key msg)]
    (if (= :error (:status r)) r {:status :ok :mic (subvec (:mac r) 0 4)})))
