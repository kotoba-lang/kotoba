(ns j1939.identifier
  "The 29-bit extended CAN identifier SAE J1939-21 packs onto, and the
  Parameter Group Number (PGN) that identifier encodes.

  Bit layout, MSB to LSB, 29 bits total (clause 5.2):

    28..26  Priority          3 bits, 0 = highest
    25      EDP (Extended Data Page)  1 bit — reserved for a future third
                                       page; every PGN in the current
                                       standard has EDP = 0
    24      DP  (Data Page)   1 bit — selects between the two data pages
                                       PGNs are currently assigned from
    23..16  PF  (PDU Format)  8 bits
    15..8   PS  (PDU Specific) 8 bits — a destination address or a group
                                       extension, see below
     7..0   SA  (Source Address) 8 bits

  **The PDU1/PDU2 split is the thing every from-scratch implementation
  gets subtly wrong first, the way org-modbus's README singles out the
  reflected CRC polynomial.** `PS` means two completely different things
  depending on `PF`:

    PF < 240 (0xF0)   PDU1, \"peer-to-peer\": PS is a DESTINATION ADDRESS.
                       The PGN this identifier carries does NOT include PS
                       — two frames with the same PF but different PS (one
                       addressed to ECU 0x03, one to ECU 0x21) carry the
                       SAME PGN, just aimed at different receivers.
    PF >= 240 (0xF0)  PDU2, \"broadcast\": PS is a GROUP EXTENSION and IS
                       part of the PGN. There is no destination address in
                       a PDU2 frame — every PDU2 message is a broadcast to
                       every node on the bus.

  Getting this backwards — always folding PS into the PGN, or always
  treating it as a destination — produces a PGN lookup that is right for
  half of all messages and silently wrong for the other half, which is
  exactly the kind of bug that survives testing against one ECU and fails
  in the field against a different message set.")

;; ── the 29-bit identifier ────────────────────────────────────────────────────
;; A 29-bit unsigned value never sets bit 31 or 30, so it stays inside the
;; range JavaScript's 32-bit signed bitwise operators are exact for — no
;; byte-at-a-time decomposition is needed here the way ptp.timestamp needs
;; one for its 48/64-bit fields.

(def max-id "2^29 - 1." 0x1FFFFFFF)

(defn pack-identifier
  "`{:priority :edp :dp :pf :ps :source-address}` -> `[:ok id]`, a 29-bit
  unsigned integer. `:priority` 0..7, `:edp`/`:dp` 0 or 1, `:pf`/`:ps`/
  `:source-address` 0..255."
  [{:keys [priority edp dp pf ps source-address]}]
  (cond
    (not (<= 0 priority 7)) [:error :j1939/priority-out-of-range priority]
    (not (#{0 1} edp)) [:error :j1939/edp-not-a-bit edp]
    (not (#{0 1} dp)) [:error :j1939/dp-not-a-bit dp]
    (not (<= 0 pf 255)) [:error :j1939/pf-out-of-range pf]
    (not (<= 0 ps 255)) [:error :j1939/ps-out-of-range ps]
    (not (<= 0 source-address 255)) [:error :j1939/source-address-out-of-range source-address]
    :else
    [:ok (bit-or (bit-shift-left (bit-and priority 0x7) 26)
                 (bit-shift-left (bit-and edp 0x1) 25)
                 (bit-shift-left (bit-and dp 0x1) 24)
                 (bit-shift-left (bit-and pf 0xFF) 16)
                 (bit-shift-left (bit-and ps 0xFF) 8)
                 (bit-and source-address 0xFF))]))

(defn unpack-identifier
  "29-bit unsigned integer -> `[:ok {:priority :edp :dp :pf :ps :source-address}]`."
  [id]
  (if-not (<= 0 id max-id)
    [:error :j1939/id-out-of-range id]
    [:ok {:priority (bit-and (unsigned-bit-shift-right id 26) 0x7)
          :edp (bit-and (unsigned-bit-shift-right id 25) 0x1)
          :dp (bit-and (unsigned-bit-shift-right id 24) 0x1)
          :pf (bit-and (unsigned-bit-shift-right id 16) 0xFF)
          :ps (bit-and (unsigned-bit-shift-right id 8) 0xFF)
          :source-address (bit-and id 0xFF)}]))

;; ── PDU1 / PDU2 ──────────────────────────────────────────────────────────────

(def pdu1-pf-limit "PF values 0..239 are PDU1; 240..255 are PDU2." 240)

(defn pdu1?
  "true when PS is a destination address (PF < 240)."
  [{:keys [pf]}]
  (< pf pdu1-pf-limit))

(defn destination-address
  "The destination address a PDU1 frame is aimed at, or `:broadcast` for a
  PDU2 frame (which has none — every PDU2 message goes to every node).
  0xFF as a PDU1 destination means \"global\" (also, in effect, a
  broadcast) per clause 5.2.3; this function reports it as-is (255) rather
  than collapsing it into `:broadcast`, so a caller can still tell a PDU1
  global message apart from a PDU2 one if that distinction matters to it."
  [{:keys [pf ps] :as fields}]
  (if (pdu1? fields) ps :broadcast))

;; ── PGN, clause 5.2 ──────────────────────────────────────────────────────────
;; The Parameter Group Number is an 18-bit quantity: EDP<<17 | DP<<16 |
;; PF<<8 | (PS if PF>=240, else 0). It is the PF<240 case — PS zeroed out
;; of the PGN because it is a destination address, not group data — that
;; the docstring above is about.

(defn pgn-of
  "`{:edp :dp :pf :ps}` -> the PGN those fields encode, an integer 0..0x3FFFF."
  [{:keys [edp dp pf ps]}]
  (let [base (bit-or (bit-shift-left (bit-and edp 0x1) 17)
                      (bit-shift-left (bit-and dp 0x1) 16)
                      (bit-shift-left (bit-and pf 0xFF) 8))]
    (if (< pf pdu1-pf-limit)
      base
      (bit-or base (bit-and ps 0xFF)))))

(defn identifier->pgn
  "29-bit identifier -> `[:ok pgn]` directly, composing `unpack-identifier`
  and `pgn-of`."
  [id]
  (let [[st fields] (unpack-identifier id)]
    (if (= :error st)
      [:error fields]
      [:ok (pgn-of fields)])))

(defn pgn->fields
  "The inverse of `pgn-of`, for building an outgoing identifier: a PGN
  (plus, for a PDU1 PGN, the destination address to send it to — ignored
  for a PDU2 PGN, whose low byte already IS the group extension) ->
  `{:edp :dp :pf :ps}`. `dest-address` defaults to 0xFF (global/broadcast)
  when the PGN is PDU1 and no destination is given."
  ([pgn] (pgn->fields pgn 0xFF))
  ([pgn dest-address]
   (let [edp (bit-and (unsigned-bit-shift-right pgn 17) 0x1)
         dp (bit-and (unsigned-bit-shift-right pgn 16) 0x1)
         pf (bit-and (unsigned-bit-shift-right pgn 8) 0xFF)]
     {:edp edp :dp dp :pf pf
      :ps (if (< pf pdu1-pf-limit) (bit-and dest-address 0xFF) (bit-and pgn 0xFF))})))
