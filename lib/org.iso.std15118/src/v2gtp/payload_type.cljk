(ns v2gtp.payload-type
  "Known values of the V2GTP header's PayloadType field (2 bytes, big-endian,
  header offset 2..3) — how a V2GTP frame's Payload should be interpreted.

  Cited to the Eclipse RISE-V2G reference implementation
  (`SwitchEV/RISE-V2G`, `V2GTPMessage.java` javadoc: 'The type of the
  payload (EXI encoded message, SDP request or response)') and to the
  value table as it's independently reproduced by multiple public
  implementers/analyses of ISO 15118-2 (V2GInjector's Scapy layer;
  academic/CTF writeups on the protocol) — **not** to a section number in
  the ISO 15118-2:2014 standard text itself, which this library does not
  have paid access to. If the exact numeric values below turn out to be
  wrong in some published-standard-vs-reference-implementation edge case,
  that is a fact about this citation gap, which is why it's stated this
  plainly rather than attributed to a spec clause this library hasn't
  read.")

(def known
  {0x8001 :exi-encoded-v2g-message
   0x9000 :sdp-request
   0x9001 :sdp-response})

(defn name-of
  "`known`'s name for `payload-type`, or `:manufacturer-specific`
  (0xA000..0xFFFF is that range per the same sources) or `:reserved` for
  anything else. Every 16-bit value has *some* answer — a PayloadType this
  library doesn't recognize by name is not, on its own, malformed."
  [payload-type]
  (cond
    (contains? known payload-type) (get known payload-type)
    (<= 0xA000 payload-type 0xFFFF) :manufacturer-specific
    :else :reserved))
