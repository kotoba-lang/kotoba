(ns afdx.vl
  "The Virtual Link Identifier, as it is embedded in an AFDX frame's
  destination MAC address.

  **Provenance / confidence note.** ARINC 664 Part 7 itself (the AFDX
  network profile, sold at aviation-ia.com) has not been read by this
  implementation. The convention below — destination MAC address
  `03:00:00:00:HH:LL` where `HH:LL` is the 16-bit Virtual Link ID,
  big-endian, for a multicast VL destination — is reconstructed from
  publicly available AFDX overview papers and tutorials (the kind
  published alongside academic AFDX network-calculus / schedulability
  research, and by AFDX switch/test-equipment vendors) that describe
  this exact prefix-plus-VL-ID scheme. It is the single lowest-confidence
  structural claim in this whole library, lower than the frame layout in
  `afdx.frame` (which mostly rests on the freely published Ethernet/
  IPv4/UDP RFCs) or the sequence-number wrap rule in `afdx.sequence`
  (which is corroborated by more independent public sources). If you are
  wiring this against a real AFDX network, verify the destination MAC
  convention against that network's actual configuration table (ES
  Config Table / ICD) rather than trusting this namespace.

  16-bit VL IDs are accepted across the full 0..0xFFFF range here; real
  AFDX network configurations restrict the usable range further (and
  reserve some values), but that restriction is switch/network-design
  policy, not a wire-format constraint this codec enforces.")

(def mac-prefix [0x03 0x00 0x00 0x00])

(defn vl-id->dst-mac
  "16-bit Virtual Link ID (0..0xFFFF) -> `[:ok [6 octets]]` destination
  MAC address, or `[:error :afdx/vl-id-out-of-range n]`."
  [vl-id]
  (if (<= 0 vl-id 0xFFFF)
    [:ok (into mac-prefix [(bit-and (unsigned-bit-shift-right vl-id 8) 0xFF)
                           (bit-and vl-id 0xFF)])]
    [:error :afdx/vl-id-out-of-range vl-id]))

(defn dst-mac->vl-id
  "The inverse: a 6-octet destination MAC -> `[:ok vl-id]` if it carries
  the `03:00:00:00` AFDX multicast prefix, else `[:error
  :afdx/not-a-vl-mac mac]`."
  [mac]
  (let [mac (vec mac)]
    (if (and (= 6 (count mac)) (= mac-prefix (subvec mac 0 4)))
      [:ok (bit-or (bit-shift-left (nth mac 4) 8) (nth mac 5))]
      [:error :afdx/not-a-vl-mac mac])))
