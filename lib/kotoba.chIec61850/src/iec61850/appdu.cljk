(ns iec61850.appdu
  "The Ethernet-layer envelope IEC 61850-8-1 (GOOSE) and 61850-9-2 (Sampled
  Values) share, below whatever BER PDU rides inside it. This namespace has
  no opinion on what that PDU is — `goose.cljc` supplies the goosePdu
  encoder/decoder and calls into this one for the frame around it.

  ```
  | dst MAC (6) | src MAC (6) | [802.1Q tag (4), optional] | EtherType (2) |
  | APPID (2) | Length (2) | Reserved1 (2) | Reserved2 (2) | APDU (Length-8) |
  ```

  `Length` is the size of everything from `APPID` through the end of the
  APDU **inclusive of the 8-octet APPID/Length/Reserved1/Reserved2 header
  itself** — not just the APDU. Reserved1's top bit doubles as a simulation
  flag in the Edition 2 amendment (mirroring the PDU-level `simulation`
  field so a receiver can filter simulated traffic without touching BER);
  the rest of both Reserved fields is conventionally zero and not otherwise
  interpreted here.

  Sources: EtherType values (0x88B8 GOOSE, 0x88BA Sampled Values) and this
  header shape are widely reproduced in open GOOSE/SV implementations
  (libiec61850, Wireshark's `packet-goose.c`/`packet-sv.c`) since IEC
  61850-8-1/9-2 Annex A itself is paywalled and not quoted here from
  memory.")

(def ethertype-goose 0x88B8)
(def ethertype-sv 0x88BA)

(defn- u16be [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd-u16be [bs off] (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
                                  (bit-and (nth bs (inc off)) 0xFF)))

(defn encode
  "`{:dst-mac [6 octets] :src-mac [6 octets] :vlan {:pcp :dei :vid} (optional)
  :ethertype :appid :reserved1 :reserved2 :apdu [octets]}` → the full frame
  as a vector of octets (no FCS — that is the NIC's job, not this
  library's).

  `:reserved1`/`:reserved2` default to 0. `Length` is computed, never taken
  from the caller, so it cannot be inconsistent with the `:apdu` actually
  written."
  [{:keys [dst-mac src-mac vlan ethertype appid reserved1 reserved2 apdu]
    :or {reserved1 0 reserved2 0}}]
  (when (not= 6 (count dst-mac))
    (throw (ex-info "dst-mac must be 6 octets" {:type :iec61850.appdu/bad-mac :which :dst})))
  (when (not= 6 (count src-mac))
    (throw (ex-info "src-mac must be 6 octets" {:type :iec61850.appdu/bad-mac :which :src})))
  (let [apdu (vec apdu)
        length (+ 8 (count apdu))
        vlan-octets (when vlan
                      (let [tci (bit-or (bit-shift-left (bit-and (:pcp vlan 0) 0x7) 13)
                                        (bit-shift-left (if (:dei vlan) 1 0) 12)
                                        (bit-and (:vid vlan 0) 0xFFF))]
                        (into [0x81 0x00] (u16be tci))))]
    (-> (vec dst-mac)
        (into src-mac)
        (into vlan-octets)
        (into (u16be ethertype))
        (into (u16be appid))
        (into (u16be length))
        (into (u16be reserved1))
        (into (u16be reserved2))
        (into apdu))))

(defn decode
  "The frame → `[:ok {:dst-mac :src-mac :vlan (or nil) :ethertype :appid
  :length :reserved1 :reserved2 :apdu [octets]}]`, or `[:error kw data]`.

  `:apdu` is sliced to exactly `Length - 8` octets — anything past that in
  the buffer (Ethernet's 60-octet minimum frame size routinely pads GOOSE
  frames, since a real goosePdu is often shorter) is dropped here rather
  than being handed to a BER decoder that would misreport it as trailing
  garbage inside the PDU."
  [bytes]
  (let [bs (vec bytes)
        n (count bs)]
    (cond
      (< n 14)
      [:error :iec61850.appdu/frame-too-short {:length n :minimum 14}]

      :else
      (let [dst (subvec bs 0 6)
            src (subvec bs 6 12)
            tagged? (and (= 0x81 (nth bs 12)) (= 0x00 (nth bs 13)))
            et-off (if tagged? 16 12)
            vlan (when tagged?
                   (let [tci (rd-u16be bs 14)]
                     {:pcp (bit-and (unsigned-bit-shift-right tci 13) 0x7)
                      :dei (pos? (bit-and tci 0x1000))
                      :vid (bit-and tci 0xFFF)}))]
        (if (< n (+ et-off 10))
          [:error :iec61850.appdu/frame-too-short {:length n :minimum (+ et-off 10)}]
          (let [ethertype (rd-u16be bs et-off)]
            (if (not (#{ethertype-goose ethertype-sv} ethertype))
              [:error :iec61850.appdu/bad-ethertype {:ethertype ethertype}]
              (let [appid (rd-u16be bs (+ et-off 2))
                    length (rd-u16be bs (+ et-off 4))
                    reserved1 (rd-u16be bs (+ et-off 6))
                    reserved2 (rd-u16be bs (+ et-off 8))
                    apdu-start (+ et-off 10)
                    apdu-end (+ et-off 2 length)] ; et-off+2 is where APPID starts; length counts from there
                (cond
                  (< length 8)
                  [:error :iec61850.appdu/length-too-small {:length length :minimum 8}]

                  (> apdu-end n)
                  [:error :iec61850.appdu/length-mismatch
                   {:declared length :available (- n (+ et-off 2))}]

                  :else
                  [:ok {:dst-mac dst :src-mac src :vlan vlan :ethertype ethertype
                        :appid appid :length length :reserved1 reserved1 :reserved2 reserved2
                        :apdu (subvec bs apdu-start apdu-end)}])))))))))
