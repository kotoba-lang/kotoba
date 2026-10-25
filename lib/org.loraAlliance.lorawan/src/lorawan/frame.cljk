(ns lorawan.frame
  "A LoRaWAN data-frame `PHYPayload`, end to end: `lorawan.phy` (framing) +
  `lorawan.mic` (integrity) + `lorawan.crypt` (FRMPayload confidentiality),
  for the four data `FType`s — `:unconfirmed-data-up/-down`,
  `:confirmed-data-up/-down`. Join frames are `lorawan.join`'s job, not
  this namespace's — a Join-Request/Accept has neither an `FHDR` nor an
  `FPort`-selected session key, so folding them into the same encode/
  decode pair would mean every call site re-deriving \"is this actually a
  data frame\" from the very MHDR byte this dispatch exists to check once.

  §4.3.3 Table 11 selects the FRMPayload key by `FPort`: `NwkSKey` for
  port 0 (MAC commands as payload), `AppSKey` for 1..255. Callers pass
  both keys; this namespace picks the right one per frame.

  As `lorawan.mic` documents, every function here takes the **full 32-bit
  frame counter** explicitly — reconstructing it from the 16-bit wire
  `FCnt` is a Network Server's job this stateless codec does not do."
  (:require [lorawan.crypt :as crypt]
            [lorawan.mic :as mic]
            [lorawan.phy :as phy]))

(def uplink-ftypes #{:unconfirmed-data-up :confirmed-data-up})
(def downlink-ftypes #{:unconfirmed-data-down :confirmed-data-down})

(defn- ftype->dir [ftype]
  (cond (uplink-ftypes ftype) mic/dir-uplink
        (downlink-ftypes ftype) mic/dir-downlink
        :else nil))

(defn- frm-key [fport nwk-s-key app-s-key]
  (if (or (nil? fport) (zero? fport)) nwk-s-key app-s-key))

(defn- first-error [& results] (first (filter #(= :error (:status %)) results)))

(defn encode-data-frame
  "`opts` — `:ftype` (one of the four data types), `:dev-addr`, `:fcnt32`
  (full 32-bit counter; the wire `FCnt` is `(mod fcnt32 0x10000)`,
  computed here), `:fctrl` (a map for `phy/encode-fctrl`, minus
  `:fopts-len` which is derived from `:fopts`), `:fopts` (already-encoded
  MAC-command bytes, unencrypted per §5), `:fport`, `:payload` (plaintext
  — `nil`/`[]` for a payload-less frame, in which case `:fport` is
  ignored, matching `phy/encode-macpayload`), `:nwk-s-key`, `:app-s-key`.

  Flat rather than nested `if`s on purpose — every intermediate step
  (`fctrl`, `FHDR`, the encrypted payload, `MACPayload`, the MIC) is bound
  first, and `first-error` picks out whichever one actually failed, so
  adding or reordering a step never means re-threading five levels of
  `(if (= :error …) … (let […] …))`."
  [{:keys [ftype dev-addr fcnt32 fctrl fopts fport payload nwk-s-key app-s-key]}]
  (let [fopts (or fopts [])
        payload (or payload [])
        dir (ftype->dir ftype)]
    (if (nil? dir)
      {:status :error :reason :lorawan/not-a-data-frame :ftype ftype}
      (let [mhdr (phy/encode-mhdr ftype)
            fctrl-r (phy/encode-fctrl (if (= dir mic/dir-uplink) :uplink :downlink)
                                       (assoc fctrl :fopts-len (count fopts)))
            fhdr-r (if (= :error (:status fctrl-r))
                     fctrl-r
                     (phy/encode-fhdr {:dev-addr dev-addr :fctrl-byte (:byte fctrl-r)
                                        :fcnt (mod fcnt32 0x10000) :fopts fopts}))
            key (frm-key fport nwk-s-key app-s-key)
            enc-r (cond
                    (= :error (:status fhdr-r)) fhdr-r
                    (seq payload) (crypt/crypt-frm-payload key dir dev-addr fcnt32 payload)
                    :else {:status :ok :bytes []})
            macpayload (when (not= :error (:status enc-r))
                         (phy/encode-macpayload (:bytes fhdr-r) {:fport fport :frm-payload (:bytes enc-r)}))
            mp-err (when (map? macpayload) macpayload) ; encode-macpayload's own error shape
            mic-r (when (and (nil? mp-err) (not= :error (:status enc-r)))
                    (mic/data-frame-mic nwk-s-key dir dev-addr fcnt32 (into [(:byte mhdr)] macpayload)))]
        (or (first-error fctrl-r fhdr-r enc-r) mp-err (first-error mic-r)
            (phy/encode-phypayload (:byte mhdr) macpayload (:mic mic-r)))))))

(defn decode-data-frame
  "`fcnt32` is the caller-reconstructed full 32-bit counter to check the
  MIC and decrypt against (see the namespace docstring). Verifies the MIC
  **before** decrypting — a MIC failure returns `{:status :error :reason
  :lorawan/mic-mismatch}` without ever touching `FRMPayload`, so a
  forged/corrupted frame never reaches the decrypt step at all."
  [bs {:keys [fcnt32 nwk-s-key app-s-key]}]
  (let [phy-r (phy/decode-phypayload bs)
        ftype (get-in phy-r [:mhdr :ftype])
        dir (when (not= :error (:status phy-r)) (ftype->dir ftype))
        not-data-frame (when (and (not= :error (:status phy-r)) (nil? dir))
                          {:status :error :reason :lorawan/not-a-data-frame :ftype ftype})
        mp (when (and (nil? not-data-frame) (not= :error (:status phy-r)))
             (phy/decode-macpayload (if (= dir mic/dir-uplink) :uplink :downlink) (:body phy-r) 0))
        mic-ok? (when (and mp (not= :error (:status mp)))
                  (mic/verify-data-frame-mic nwk-s-key dir (:dev-addr mp) fcnt32
                                              (into [(nth bs 0)] (:body phy-r)) (:mic phy-r)))
        mic-err (when (false? mic-ok?) {:status :error :reason :lorawan/mic-mismatch})
        dec-r (when (true? mic-ok?)
                (let [key (frm-key (:fport mp) nwk-s-key app-s-key)]
                  (if (seq (:frm-payload mp))
                    (crypt/crypt-frm-payload key dir (:dev-addr mp) fcnt32 (:frm-payload mp))
                    {:status :ok :bytes []})))]
    (or (first-error phy-r) not-data-frame (first-error mp) mic-err (first-error dec-r)
        {:status :ok :ftype ftype :dev-addr (:dev-addr mp) :fctrl (:fctrl mp)
         :fcnt (:fcnt mp) :fopts (:fopts mp) :fport (:fport mp) :payload (:bytes dec-r)})))
