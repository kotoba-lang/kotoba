# ADR-0134: Gate N2 — the persistent TCP byte stream is a runtime profile beside the diagnostics profile

## Status

Proposed (2026-09-04), on branch `n2-design-only`. Lives in this repository's
numbered ADR series at `90-docs/adr/`, beside 0131–0133. This is a design and
host-side integration scaffold. It
does not modify `native/rtl8125.kotoba`, does not build an artifact, does not
run QEMU, and does not touch the PXE server. Companion artifacts on the same
branch: `os/aiueos/scripts/k16-n2-import-integration-sketch.patch` (import
integration sketch) and `test/aiueos/tcp_stream_integration_test.cljk` (host
reassembly-parity test, green on this branch: 8 tests / 163 assertions).

## Context

ADR-2609031030 leaves Gate N2 (persistent TCP byte stream) red. The proof path
in `native/rtl8125.kotoba` is `tcp-ack-reset-and-receipt`: it completes the
three-way handshake, then sends RST and a UDP receipt. It is a diagnostic, not
a production path, and must not be renamed into one. The historical C path's
512-byte-chunk + 25 ms spacing workaround is explicitly not the target, and the
historical 2783-byte TLS response crossed a single RX buffer — which is exactly
why one descriptor cannot carry N2.

What the tree has measured so far:

* DMA window is **4 pages, 16384 bytes** at `dma-base`. Current layout:
  TX ring at `+0`, RX ring at `+4096`, TX frame at `+8192`, RX frame at
  `+12288`. Exactly **one TX descriptor and one RX descriptor**, 32-byte
  descriptor stride (matches `kernel/rtl8125.h`: both structs are 32 bytes,
  packed, 16-aligned; RX command is the u32 at descriptor offset 28, which is
  what `wait-rx-command` reads).
* Per-descriptor RX capacity is **2048 bytes**: `dma/rx-command 2048` and the
  RX max-size MMIO store of 2048. Frames are bounded 58..2048 bytes by the
  classifiers.
* The RX wait idiom is bounded windows: 250000-iteration polls, 4 windows,
  explicit timeout `21` — the change that made the 43-stop debuggable, kept as
  the profile's only waiting primitive.
* Gate N1 tranche one landed IPv4 checksum admission (`ipv4-checksum-valid`,
  source status literal `93`, wire rendering `NIC_5D`). The parent ADR's status
  map reserves rendered `93`/`96` for the two checksum gates. **The source
  integer and the rendered hex pair diverge and the tree currently mixes the
  two namespaces** — see §6, which names the namespace this ADR proposes in and
  records the reconciliation as an implementation-tranche obligation.
* `k16-kotoba-native-closure-v1.edn` lists `:https` as required and names
  `kotoba-lang/org-ietf-tcp` as a reuse candidate (`:available
  :kotoba-state-machine-cores`, `:missing :bare-metal-segment-engine`).
* `org-ietf-tcp` at commit `d8c15e23b6c169a4ed044cd7764923ecbb789be4` carries
  safe, typed, parity-tested decision cores. The two N2 needs first are
  `tcp.seq-core` (wrap arithmetic, `acceptable?`, `segment-end` with SYN/FIN
  +1) and `tcp.reassemble-core` (`duplicate?`, `trim-skip`,
  `trimmed-away?`, `overlaps?`, `prefix-len`, `held-order-key`,
  `contiguous?`, `queue-full?`). Both compile for native targets: neither
  holds an i64 shift. `tcp.state-core` is **wasm32-only** (amu#611 refuses a
  module holding both a shift and a `:bool` parameter; state_core has both),
  which constrains what the first native tranche can import.
* Constraints that bound every new object: kernel compiles with
  `--fuel 1048576`; every object stays under the 32768-byte kernel-object
  limit (the ecdsa-p256-sign story in the ssh-v1 contract); the kotoba subset
  rejects mixed-type equality, so predicates return integer 1/0 (the N1
  commit's subset-language note).

## Decision

A **runtime profile** — a second, separate TCP path in the sealed Kotoba
closure — living in a new module `native/tcp-stream.kotoba`, leaving
`native/rtl8125.kotoba` byte-identical. It owns sequence/ack tracking, a
multi-descriptor RX ring, reassembly, partial send/receive, FIN/RST, timeouts,
and bounded retransmission, importing the org-ietf-tcp decision cores for every
arithmetic decision those cores already own.

### 1. Runtime profile state machine, bounded by construction

One connection, one fixed 4-tuple (10.77.0.10:49155 ↔ 10.77.0.1:8443, the
measured peer). No listen queue, no TCB table, no allocation after boot:

* The **TCB is a fixed set of i64 scalars**: state, snd-una, snd-nxt, snd-wnd,
  rcv-nxt, rcv-wnd, iss, irs, mss, held-queue bytes, retransmit counters and
  tick stamps. Bounded memory by construction.
* State integers reuse `tcp.state-core`'s code **values** (st-listen 1,
  st-syn-sent 2, st-syn-received 3, st-established 4, st-fin-wait-1 5,
  st-fin-wait-2 6, st-close-wait 7, st-last-ack 9, st-time-wait 10), restated
  in `tcp-stream.kotoba` with the org-ietf-tcp state parity suite as oracle.
  Restating is the documented compromise: `tcp.state-core` cannot be imported
  into a native tranche until amu#611 lifts the shift+bool refusal. When it
  does, the require replaces the restatement — a one-line change, and the
  parity discipline stays.
* The path is the Murakumo client: **LISTEN** (gate entered, TCB installed) →
  **SYN_SENT** (SYN on the wire) → **ESTABLISHED** (SYN-ACK admitted, ACK
  sent) → close paths: active FIN (FIN-WAIT-1 → FIN-WAIT-2 → TIME-WAIT →
  CLOSED) and peer close (CLOSE-WAIT → LAST-ACK → CLOSED). SYN-RECEIVED stays
  in the code table for parity but is not occupied — the profile performs no
  passive open.
* **Every state has a bounded residence.** SYN and data retransmission use the
  retransmission bound of §4. TIME-WAIT is a bounded 2-MSL-equivalent window
  in the kernel's existing bounded-wait idiom, not an unbounded hold. There is
  no state from which the profile can wait forever.

### 2. Multi-descriptor RX ring inside the existing 4-page DMA window

The 16384-byte window is **re-laid out, not enlarged** — no new DMA map, no
allocator pages, the ring start register stays at a page-aligned address:

| offset | size | contents |
|---|---|---|
| +0 | 1024 | TX ring: 2 descriptors × 32 B (64 B used) |
| +1024 | 1024 | RX ring: 4 descriptors × 32 B (128 B used) |
| +2048 | 2048 | reserved |
| +4096 | 2048 | TX buffer A |
| +6144 | 2048 | TX buffer B |
| +8192 | 2048 | RX buffer A |
| +10240 | 2048 | RX buffer B |
| +12288 | 2048 | RX buffer C |
| +14336 | 2048 | RX buffer D |

Sizing arithmetic, all measured:

* Per-descriptor RX buffer stays **2048 bytes** (unchanged `dma/rx-command`
  capacity and RX max MMIO). Four descriptors give an **8192-byte hold
  capacity** — 2.9× the historical 2783-byte TLS response, so a record that
  crosses one buffer spans at most 2 descriptors with the other 2 free for
  reordering depth.
* RX descriptor count 4 and reassembly `max-bytes` 8192 are **the same
  number**: the held-queue bound equals what can physically arrive, so the
  reassembler's refusal boundary is never the DMA ring's failure mode in
  disguise.
* Two TX descriptors carry two in-flight segments (§4), enough to keep a
  partial-send stream moving while one descriptor completes.
* Descriptor stride 32 B and the command/extension/address field offsets are
  already the hardware layout the single-descriptor code and
  `kernel/rtl8125.h` agree on; growing the ring is stride repetition.
* The one flag this change needs that `capability-dma-map` does not yet
  express is the **ring-end (wrap) marker on the last descriptor**. Preferred
  resolution: add it to `capability-dma-map` (decision-free mechanism, same
  release-fence/rx-command style) rather than OR-ing a bare literal in the
  kernel module. Recorded as an implementation-tranche item with its
  C-reference provenance to be cited when taken.
* RX ownership per descriptor is the existing OWN-bit discipline
  (`wait-rx-command`'s bit-31 poll, `rx-rearm`'s address + fenced command
  rewrite), applied per descriptor instead of once.

### 3. Reassembly imports org-ietf-tcp decision cores

The native kernel profile links a **closed module graph** — that is exactly
how `capability.link.frame`, `capability.dma.map`, `capability.mmio.map` and
`capability.net.transport` are consumed today (`:require` + `--source-path`).
The "one entry, no calls" rule applies to sealed single objects, not to this
profile. So:

* `build-kotoba-native-kernel.sh` gains a fifth `--source-path` pointing at an
  org-ietf-tcp checkout pinned at `d8c15e23b6c169a4ed044cd7764923ecbb789be4`
  (same commit the `:test` alias already pins — one authority, no second
  number). Sketch: `os/aiueos/scripts/k16-n2-import-integration-sketch.patch`.
* `native/tcp-stream.kotoba` gains
  `(tcp.seq-core :as seq-core)` and `(tcp.reassemble-core :as reassemble)`
  requires. `tcp.state-core` is deliberately **not** required (amu#611).
* Division of labor: the object owns **staging** (copying a descriptor's bytes
  into a DMA buffer page, holding the 4-entry held table, delivery copies);
  `reassemble-core` owns every **range decision**: in-window admission via
  `seq-core/acceptable?`, duplicate/trim/overlap/prefix decisions,
  `held-order-key` ordering by forward distance from rcv-nxt, `contiguous?`
  delivery, and `queue-full?` — whose bound is charged **on what stays held**,
  not on arrivals (the exact bug the core's header documents and its parity
  test pins).
* Held-table capacity is 4 entries and 8192 bytes (§2); reassembly loops over
  at most 4 held entries, so fuel consumption is bounded and small against
  the 1048576 budget.
* Receive flow control: rcv-wnd is advertised as **free staging bytes**
  (8192 − held). A full held queue advertises a 0 window instead of dropping
  data. `queue-full?` then fires only on a peer that violates the advertised
  window, and its refusal is whole-segment (a trimmed fragment can never be
  completed).

### 4. TX with partial send, FIN/RST, bounded retransmit

* **Partial send**: a write is bounded per turn by `send-core`'s
  `send-bytes`/`room`/`effective-mss` arithmetic: at most one MSS per segment,
  at most `min(cwnd-room, rwnd-room)` bytes in flight, and the two TX
  descriptors cap concurrent segments at 2. A write returns the count actually
  queued; the remainder stays in the bounded 2-buffer TX staging and the
  stream's snd-nxt advances only with what went on the wire. First tranche
  fixes peer-MSS at 1460 (1500 minus 40; the link's frames are bounded ≤2048)
  and does not parse SYN options — importing `options-core`/
  `options_wire_core` belongs to the tranche that parses SYN options.
* **Retransmission queue**: one entry per unretired segment (seq, len,
  syn?, fin?, first-sent tick, sent tick, transmissions), bounded at 4
  entries — 2 in flight + 2 staged, sized to the TX ring. Retirement is
  `retransmit-core/retired?` (cumulative ACK must cover the entry's **last**
  byte, SYN/FIN each +1 via `seq-core/segment-end`). Re-fire is `due?`; the
  tick source is the kernel's existing bounded-iteration idiom (the
  250000/8000000-iteration windows become the RTO's unit — the profile does
  not invent a wall clock).
* **Bound**: `give-up?` with limit 5 (`retransmit-core`'s documented common
  default, passed in as policy, not hidden). Give-up → send RST once →
  CLOSED → stream status 100. No segment is retried forever.
* **FIN/RST**: FIN occupies one sequence number (`segment-end` syn?/fin?
  discipline — the off-by-one the core documents). Peer RST is admitted only
  in-window (`seq-core/acceptable?`); an in-window RST closes immediately:
  staging, held queue, and retransmit queue drop, CLOSED, status 100. RST is
  sent exactly once per close event (give-up, or a segment for the 4-tuple
  arriving while CLOSED — RFC 9293). A clean close runs the FIN hand paths of
  §1 and finishes with FIN, so the peer observably distinguishes graceful from
  abortive close at the wire level.

### 5. The diagnostics profile is untouched

`native/rtl8125.kotoba` is byte-identical to its N1 state. Untouched and still
the boot-time physical gate: `probe-tcp-after-arp`, `receive-tcp-syn-ack`,
`tcp-syn-ack-header-status`, `tcp-ack-reset-and-receipt`, the UDP diagnostic
receipt (`send-native-nic-diagnostic`, `10.77.0.1:7777`), the screen base
`0x60` encoding, the bounded windows, and every existing status literal. The
runtime profile lives in `native/tcp-stream.kotoba` with its own ring code
written against the same capability objects; the small duplication of ring
mechanics is accepted and named — the alternative (widening rtl8125's
`:export` list) is the implementation tranche's choice, recorded as open with
this tradeoff. The two profiles share nothing but the capability objects and
the status namespace rules of §6. A build receipt after N2 must still show the
diagnostics path compiling unchanged, and the N1 physical wire sequence must
still reproduce from an N2-era artifact.

### 6. Wire status codes — what becomes observable when

Namespace, named explicitly because the tree mixes two: provider statuses are
**source integers**, rendered as two hex digits in the UDP diagnostic receipt
(`AIUEOS_NATIVE_NIC_XX`) and added to screen base `0x60` — source 68 renders
`NIC_44`, which is how the physical run's sequence was produced. The parent
ADR's map (40/43/44/45, 90-series, reserved 93/96) is written in **rendered**
values; N1 tranche one took **source** integer 93 for IPv4 checksum (renders
`NIC_5D`). These two series overlap and disagree; reconciling them (renumber
N1's literal to 147, or accept `NIC_5D` and re-map the contract) is an
obligation of the first implementation tranche, recorded here rather than
silently resolved.

**Proposal — stream states take source integers 97..100**, unclaimed anywhere
in the source tree and unclaimed in the contract:

| source | wire | screen | state | what becomes observable |
|---|---|---|---|---|
| 97 | `NIC_61` | `STATUS F7` | LISTEN / stream gate entered | TCB installed for the fixed 4-tuple; retransmission bound armed; nothing on the TCP wire yet |
| 98 | `NIC_62` | `STATUS F8` | SYN_SENT | SYN on the wire (initial or retransmitted); the SYN retransmit window running |
| 99 | `NIC_63` | `STATUS F9` | ESTABLISHED | handshake completed by ACK; from here every reassembly delivery, every held-queue transition, every partial-send segment size (≤ MSS) is wire-observable; receive window advertisement is live |
| 100 | `NIC_64` | `STATUS FA` | CLOSED | stream ended; **the closing segment is on the wire** — FIN for graceful close, RST for peer-RST or retransmission give-up — so the independent receiver distinguishes the three without asking the kernel |

Failure observability rides the existing series rather than new numbers in
the contested 90-range: reassembly refusal (`queue-full?`) is observable as a
**delivery stall inside 99** — the held-queue is full against the advertised
window, delivery progress stops, and the diagnostic frame repeats `NIC_63`
each stall; retransmission give-up and peer-RST surface as **100 with their
closing-segment type on the wire**; ordinary timeouts keep the existing `21`/
`30`-series. A dedicated queue-full code is deliberately **not** taken here:
the rendered-9x neighborhood is partly reserved for TCP checksum admission and
partly claimed by N1; if a dedicated code is wanted, the implementation
tranche takes the next unclaimed pair and appends it to this table.

### 7. Gate conditions

N2 does not go green until the kernel, on the K16, **reconstructs multiple
records/segments without loss** over the persistent stream: an in-order and
an out-of-order arrival both delivered contiguously, the stream still open
afterwards (no RST), with the `97 → 98 → 99` sequence on the wire/screen and a
graceful FIN at close. Host-side preconditions, all runnable without hardware:

1. `test/aiueos/tcp_stream_integration_test.cljk` — the reassembly cores, at
   the pinned commit, hold the three properties this ADR names, on the same
   fixtures the org-ietf-tcp parity suite uses (green on this branch).
2. The import integration compiles: the sketch's `--source-path` set
   compiles `native/kernel.kotoba` for `x86_64-aiueos-kernel-v1` with the new
   requires, still fuel-1048576, every object ≤ 32768 bytes, imports 0,
   foreign 0, byte-identical rebuild.
3. QEMU bounded smoke (no device) unchanged-green.

Then the physical gate of §6.

## What is NOT done

* **No kernel source changed.** `native/rtl8125.kotoba` is untouched; the
  import-integration diff is a sketch, not an applied change.
* **No artifact, no QEMU, no PXE.** The build script is not modified; the
  sketch is.
* **`tcp.state-core` is not imported.** amu#611 refuses it for native
  targets; the state integers are restated under parity discipline until the
  compiler lifts the refusal.
* **No SYN options parsing, no SACK, no congestion control.** First tranche is
  fixed-peer-MSS, no SACK, IW-shaped conservatism via `send-core`'s room
  arithmetic only; `options_core`, `sack_core`, `congestion_core`,
  `pacing_core`, `pmtu_core` are later tranches with their own parity evidence.
* **The status-namespace reconciliation is open.** Source-integer 93 vs
  rendered `NIC_93` (§6) must be settled by the implementation tranche before
  any new code in the 90 range is written.
* **Nothing here says Gate N2 is green.** It says what green will be measured
  against.
