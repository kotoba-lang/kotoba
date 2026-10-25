# kotoba-lang/org-ietf-ospf

**An OSPFv2 wire codec — the 24-octet packet header, all five packet types,
and the 20-octet LSA header — in portable `.cljc`, with no dependencies.
[RFC 2328](https://www.rfc-editor.org/rfc/rfc2328.txt), with the packet
checksum per [RFC 1071](https://www.rfc-editor.org/rfc/rfc1071.txt).**

Self-contained: no sibling-repo git dependency, no Maven deps at the top
level, no ASN.1/BER, no shared crypto. Bytes are `Sequential` collections of
ints in 0..255, in and out.

## Surface

```clojure
(require '[ospf.packet :as packet])

(def enc (packet/encode
           {:type :hello
            :header {:router-id 0x0A000001 :area-id 0 :autype 0}
            :body {:network-mask 0xFFFFFF00 :hello-interval 10 :options 0x02
                   :rtr-pri 1 :router-dead-interval 40
                   :designated-router 0x0A000001
                   :backup-designated-router 0x0A000002
                   :neighbors [0x0A000003 0x0A000004]}}))

(packet/decode (:bytes enc))
;=> [:ok {:header {:version 2 :type :hello :packet-length 52 ...}
;         :body {:network-mask 4294967040 ... :neighbors [167772163 167772164]}}]
```

| namespace | |
|---|---|
| `ospf.packet` | full packet `encode` / `decode` — header + body + RFC 1071 checksum |
| `ospf.header` | the 24-octet common header, Appendix A.3.1 |
| `ospf.hello` | Hello, packet type 1, Appendix A.3.2 |
| `ospf.dd` | Database Description, type 2, Appendix A.3.3 |
| `ospf.lsr` | Link State Request, type 3, Appendix A.3.4 |
| `ospf.lsu` | Link State Update, type 4, Appendix A.3.5 |
| `ospf.lsack` | Link State Acknowledgment, type 5, Appendix A.3.6 |
| `ospf.lsa` | the 20-octet LSA header, Appendix A.4.1, and §13.1's recency rule |
| `ospf.checksum` | the RFC 1071 Internet checksum, two independent implementations |
| `ospf.bytes` | big-endian u16 / u32 / **signed** i32 field packing |

## Four details that are usually got wrong

**The packet checksum excludes the Authentication field.** RFC 2328
Appendix A.3.1: "the standard IP checksum of the entire contents of the
packet, starting with the OSPF packet header but *excluding the 64-bit
authentication field*." It covers header octets 0–15 (Version # through
AuType) plus the whole body — never octets 16–23. Including them produces a
checksum that is self-consistent and rejected by every router.

**The DD flags octet is drawn `0 0 0 0 0 I M MS`.** Reading Appendix A.3.3's
diagram left-to-right, I is **bit 2** (0x04), M is bit 1 (0x02), MS is bit 0
(0x01). Assuming the more common convention — first-named flag at the LSB —
puts I and MS in each other's positions, and produces DD packets whose
Init/Master semantics are exactly inverted.

**The LS sequence number is a *signed* 32-bit integer.** RFC 2328 §12.1.6:
"The larger the sequence number (when compared as signed 32-bit integers)
the more recent the LSA." InitialSequenceNumber is 0x80000001, described in
that section as "-N + 1" where N = 2**31 — the *smallest* value, not a large
one. Decode it unsigned and a freshly originated LSA compares as newer than
MaxSequenceNumber (0x7fffffff), inverting §13.1's whole ordering.

**The RFC 1071 checksum field must sit at an even offset.** §2's zero pad for
an odd-length buffer is notional; it exists only while summing. *Appending* a
checksum to odd-length data moves the field to an odd offset, the last data
octet pairs with the checksum's high byte instead of with the pad, and
verification fails on intact data. OSPF is unaffected — Appendix A.3.1 fixes
the field at offset 12 — but the suite asserts both directions rather than
leave a caller to discover it.

## Errors

Returned, never thrown. Every decoder returns `[:ok ...]` or
`[:error <keyword>]`, and **those keywords are contract**:

`:ospf/packet-too-short`, `:ospf/unknown-packet-type`,
`:ospf/unsupported-version`, `:ospf/length-mismatch`,
`:ospf/checksum-mismatch`, `:ospf/hello-too-short`,
`:ospf/neighbor-list-misaligned`, `:ospf/dd-too-short`,
`:ospf/lsr-misaligned`, `:ospf/lsu-too-short`, `:ospf/lsu-trailing-bytes`,
`:ospf/lsa-header-too-short`, `:ospf/lsa-length-too-short`,
`:ospf/lsa-length-exceeds-packet`.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

The ClojureScript run is not a formality. `ospf.bytes` exists precisely
because JavaScript's bitwise operators coerce through ToInt32 where the JVM's
are 64-bit: `(bit-shift-left 0xC0 24)` — needed for any Router ID from
128.0.0.0 up — yields a *negative* Int32 under ClojureScript and the correct
value on the JVM. A codec that only round-trips on `kbb -M:test` has
proven itself on the platform least likely to expose that class of bug.

### What is RFC-cited and what is constructed

**The RFC 1071 §3 worked numerical example is asserted directly.** For the
bytes `00 01 f2 03 f4 f5 f6 f7`, the RFC's own table computes the
one's-complement sum as `ddf2`, and the test asserts exactly that value from
both implementations. (The RFC's table stops at the sum and does not also
print the final complement, so the checksum *field* value `0x220d` is derived
in the test, and is marked as derived rather than quoted.)

Every field layout, bit position, and constant in `src/` is cited to a
section or appendix number next to the code that uses it, mostly by quoting
the RFC's own ASCII diagram or prose into the namespace docstring:
Appendix A.3.1–A.3.6 and A.4.1 for the layouts, §13.1 for the recency rule,
Appendix B for MaxAge (1 hour) and MaxAgeDiff (15 minutes), §12.1.6 and
Appendix B for InitialSequenceNumber / MaxSequenceNumber.

**The framing test vectors are constructed, and are marked as such in the
test file.** RFC 2328 specifies its packets with diagrams and prose; unlike
the Modbus specification's §6, it contains no worked full-packet byte dumps
to lift. Constructed vectors are built against the cited diagrams and carry
the comment `;; constructed, not a published spec vector`. None of them is
presented as canonical.

## What this is not

**Not a router, and not a routing daemon.** This is a codec: bytes in, data
out, data in, bytes out. It has no IO, no sockets, no threads, and reads no
clock. Specifically absent:

- **No neighbor state machine.** Down / Init / 2-Way / ExStart / Exchange /
  Loading / Full, the DD master-slave poll-response exchange, adjacency
  formation, retransmission timers — none of it. This library will encode you
  a DD packet with the MS bit set; it has no opinion about whether you are
  the master.
- **No SPF computation.** No Dijkstra, no shortest-path tree, no routing
  table build (RFC 2328 §16).
- **No link-state database.** No LSA storage, no flooding, no aging, no
  origination, no MaxAge flush. `ospf.lsa/compare-instances` answers §13.1's
  question about two LSA headers you already hold; it does not hold them.
- **No DR/BDR election**, no interface state machine, no areas, no virtual
  links.

### Scoped out, deliberately

**The Fletcher LS checksum is not implemented.** The LSA header's
`:ls-checksum` (Appendix A.4.1) is "the Fletcher checksum of the complete
contents of the LSA, including the LSA header but excluding the LS age
field" — a *different algorithm* from the RFC 1071 checksum used for the
packet header, and one RFC 2328 §12.1.7 does not itself specify, deferring
instead to "Annex B of [Ref6]" (the ISO 8473 connectionless-datagram
standard). It is carried through here as an opaque 16-bit value: preserved
exactly across encode/decode, compared as an unsigned integer by §13.1's
recency rule (which is all that rule asks of it), and **never computed or
verified**. Note that §12.1.7 says plainly "calculation of the checksum is
not optional" — a full OSPF implementation must have it; this codec does
not, and says so here rather than shipping an approximation. A half-implemented Fletcher checksum that looks load-bearing and
silently never rejects a corrupt LSA is worse than no checksum at all, so it
is absent rather than approximated. The RFC 1071 checksum, which *is*
implemented, gets two independent implementations cross-checked against each
other and against the RFC's own worked example.

**Per-type LSA bodies are opaque.** `ospf.lsu` decodes the LSA *header* of
every LSA in an update exactly, then hands the remaining bytes back as
`:body` without interpreting them. Router-LSA, network-LSA, the two
summary-LSA flavors and AS-external-LSA (Appendix A.4.2–A.4.5) each have
their own body layout, and none is parsed here. What *is* exact is the
framing: the LSA header's own `:length` field ("the length in bytes of the
LSA. This includes the 20 byte LSA header") is used to walk to the next LSA,
so a caller that understands a given LS type can slice its body back out, and
a caller that does not can still traverse the whole list. Bodies whose
`:length` is under 20, or over what the packet actually holds, are rejected
by name.

**No authentication.** AuType 1 (simple password) and AuType 2
(cryptographic/MD5, Appendix D) are not implemented. The 64-bit
Authentication field is carried through as opaque bytes. Note that the
checksum is validated on decode regardless of AuType, even though RFC 2328
permits some authentication types to omit it — a codec with no
authentication implementation has no basis to selectively skip the one
integrity check it does have.

**OSPFv2 only.** OSPFv3 (RFC 5340) has a different header and different LSA
types; a Version # other than 2 is rejected as
`[:error :ospf/unsupported-version]` rather than parsed optimistically.
