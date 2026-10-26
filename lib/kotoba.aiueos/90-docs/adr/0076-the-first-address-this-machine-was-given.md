# ADR-0076 — The first address this machine was given

Date: 2026-08-22

## Status

Accepted and executable. **Row 1 of ADR-0041's gap ledger is closed for the
bare-metal profile.** aiueos performs a real DHCPv4 exchange — DISCOVER, OFFER,
REQUEST, ACK — against QEMU's own DHCP server, and every judgement about the
replies is made by two compiler-emitted Kotoba objects.

Executable: the exchange, the lease it records, and a four-boot gate that shows
the admission refusing three separately broken replies with three distinct
reason codes and admitting an unmodified one.

**Not executable, and not claimed**: nothing consumes the lease. `kernel/pci.c`
still sends from the compiled-in `10.0.2.15`, which is the address the server
happens to hand out, so no behaviour changes when it is configured. Row 1 buys
a marker and a five-word record, not a reconfigured stack.

## Context

ADR-0074 stopped here without writing a line of it. The obstacle was not DHCP:
a new kernel admission object could not be exported at all, because the export
symbol comes from a closed `kernel-object-entries` allow-list in
`kotoba-lang/kotoba-native`, and at the revision this repository pins an
unlisted entry compiled **green** while exporting `kotoba_aiueos_probe` — the
symbol `kernel-probe.o` already exports and every link already contains.

That was filed as
[kotoba-native#57](https://github.com/kotoba-lang/kotoba-native/issues/57) and
is now landed. This ADR is the work ADR-0074 declined to guess at.

## Decision

### 1. Two entries, and a return convention that is new for this ABI

`kotoba-native` `a60da444` lists:

| entry | arity | symbol |
|---|---|---|
| `aiueos-dhcp-reply-valid` | 5 | `kotoba_aiueos_dhcp_reply_valid` |
| `aiueos-dhcp-option-u32` | 3 | `kotoba_aiueos_dhcp_option_u32` |

The admission returns a **reason code**, not a boolean: `0` admits, `1..12`
name the clause that refused, and non-zero is never a truthy success. Every
existing boolean entry is untouched; the convention is local to these two and
is spelled out at the entry, in the contracts, and in the C that calls it,
because `if (validate(...))` — the shape every neighbouring object invites —
admits exactly what this rejects.

It is a reason code because a DHCP client has to tell a foreign transaction id
from a wrong message type from an options length running past the end of the
frame. Those are three clauses of one decision. A boolean makes them the same
event, and the caller would have to re-derive the difference in C, which is the
thing ADR-0015 forbids. The codes ascend with how far into the frame the check
reaches, so a caller holding several candidates can name the one that got
furthest without deciding anything.

### 2. The options walk is the decision, and it is in Kotoba

Every field the ARP, ICMP and TCP admissions read sits at a constant offset. A
DHCP reply's payload ends in a chain of `(code, length, value)` records —
variable length, self-describing, terminated by a byte inside itself, written
entirely by whoever answered. The length byte says how far to jump, and a walk
that believes it reads past the end of the frame. That is the classic DHCP
client defect and the reason the parse cannot be C.

`aiueos-dhcp-opts-ok` and `aiueos-dhcp-find` prove, at every step, that a
record's header **and its whole value** lie strictly below a limit derived from
the IPv4 total length, which has already been proved to fit the received frame.
The whole field is proved to parse **before** any option is looked up, so a
field that does not parse is reported as exactly that rather than as whichever
option the walk failed to reach.

### 3. UDP appears, and this is not a UDP stack

There is no socket, no port table, no demultiplexer, and no receive path for
anything that is not this exchange: exactly the header construction and the one
checksum DHCP needs. The transmitted checksum is computed with the same
`ipv4-checksum` object ICMP and TCP already use; the received one is verified
inside the admission. Nothing here is reusable by a second protocol without
being written.

The received UDP checksum is accepted when the field is **zero**, because
RFC 768 makes it optional over IPv4 and zero means "not computed". That is
conformant and it is also a real hole — anything that can rewrite the payload
can zero that field — so it is stated in the object, in the contract, and here
rather than left to be discovered.

### 4. The lease is five words, and nothing reads it

`dhcp_address`, `dhcp_mask`, `dhcp_router`, `dhcp_server`,
`dhcp_lease_seconds`, plus accessors. There is one interface, one lease and no
renewal, so anything larger would be a shape invented ahead of its second
caller. **No general configuration subsystem was built.**

### 5. The smaller pin advance, and why

ADR-0074 said the pin advance was the work. It was, and the full one was
measured and **not taken**.

`amu` is advanced from `8ff1030` to `9cf3a0a`, which differs by **one line**:
its `kotoba-native` dependency moves from `15b4a0e2` to `a60da444`, and
`a60da444` is `15b4a0e2` plus the two entries and nothing else. Codegen is
untouched.

The full advance — `amu` tip, 250 commits ahead, pinning `kotoba-native` main,
121 commits ahead and moving 2,076 lines of `machine_ir.cljc` and 281 of
`x86_64.cljc` — was measured by compiling five checked-in objects there and
comparing bytes:

| object | at amu tip | at 9cf3a0a |
|---|---|---|
| `net-arp-reply-valid` | differs | — |
| `ipv4-checksum` | differs | — |
| `ipv4-icmp-reply-valid` | differs | **byte-identical** |
| `tcp-segment-valid` | differs | — |
| `sha256` | differs | — |

Taking it means regenerating every object in
`reproduce-kotoba-kernel-object.sh` and every pinned digest in
`build-uefi.sh`. That is a change to the shipped kernel, and it is not a side
effect of adding DHCP. It is named here rather than absorbed.

**The whole script was re-run at the new pin.** It compiles every checked-in
object one at a time and compares bytes, and it verified **37 objects
byte-for-byte with no mismatch**, the two DHCP objects among them:

```
$ ./os/aiueos/scripts/reproduce-kotoba-kernel-object.sh <amu@9cf3a0a>
AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export=kotoba_aiueos_dhcp_reply_valid imports=0 relocations=1
AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export=kotoba_aiueos_dhcp_option_u32 imports=0 relocations=1
user-smoke.elf … differ: char 97, line 1
```

It then stops where it stopped before this change, at `user-smoke.elf`, which
the script's own comment records as *"NOT REPRODUCIBLE at the pinned revision,
and the only one left that is not"*. **That failure is pre-existing and this
change neither caused nor fixed it** — the same file, the same way. The two
DHCP entries were placed before it deliberately, so a `set -e` exit there
cannot be mistaken for them not having been checked.

That is the measurement that makes the smaller advance real rather than
plausible: 37 objects that had to keep their bytes kept them.

⚠ **The first measurement of the table above was wrong and would have justified
the same conclusion for the wrong reason.** It compared against the shared west checkout
of `aiueos`, which is 134 commits behind `origin/main` and carries another
session's edits, so an object that reproduces perfectly reported `DIFFERS`. The
table above is against `origin/main` content.

### 6. The contracts declare the export

`os/aiueos/contracts/dhcp-reply-valid-v1.edn` and `dhcp-option-u32-v1.edn`
carry `:native {:target :export :imports}`, which is the door
`kotoba-native` `1d51768` opened: an entry transcribed from a declaration by
the repository that owns the decision, rather than invented by the one that
packages it. They also carry the reason-code table, the policy bounds, and —
explicitly — **why they have no `:vectors`**.

Every other contract in that directory carries vectors a verifier runs through
`kir/execute`. That interpreter refuses `kernel-load-u8-4k` with
`:kernel-memory-unavailable` **by design**, because there is no frame contents
it could honestly invent. A frame-parsing object therefore has no off-target
oracle at all, and writing vectors nobody can run is the shape ADR-0050 already
named here. The contracts say so and point at the gate instead.

This is a pre-existing gap, not one this ADR created: `net-arp-reply-valid`,
`ipv4-icmp-reply-valid` and `tcp-segment-valid` have no contract and no
verifier either, and the only place any of them has ever run is a booted kernel.

## Executable evidence

Toolchain: zig 0.15.2, `qemu-system-x86_64` 10.0.3, OVMF
`/opt/homebrew/share/qemu/edk2-x86_64-code.fd`, `amu` `9cf3a0a`,
`kotoba-native` `a60da444`.

```
$ AIUEOS_TEST_NET=1 ./os/aiueos/scripts/smoke-qemu-uefi.sh
AIUEOS_UEFI_SMOKE_OK
```

```
AIUEOS_VIRTIO_NET_OK modern-pci rx/tx arp-reply kotoba-admitted
AIUEOS_IPV4_OK icmp-echo-reply kotoba-admitted
AIUEOS_TCP_OK handshake echo close kotoba-admitted
AIUEOS_DHCP_OK offer-ack kotoba-admitted address=10.0.2.15 mask=255.255.255.0 router=10.0.2.2 server=10.0.2.2 lease=86400
```

`10.0.2.15`, `255.255.255.0`, `10.0.2.2` and 86,400 seconds are what QEMU's
built-in DHCP server hands out. Nothing in the guest simulates a server: the
guest broadcast a DISCOVER and something outside it answered, twice.

Four boots — one unmodified and three with the reply broken in one named way
each — with each case's own progress line on stderr and its verdict here:

```
$ ./os/aiueos/scripts/smoke-qemu-dhcp.sh
AIUEOS_DHCP_GATE_CASE_OK unmodified lease=86400s
AIUEOS_DHCP_GATE_CASE_OK transaction id refused=5 foreign-transaction-id
AIUEOS_DHCP_GATE_CASE_OK message type refused=9 message-type
AIUEOS_DHCP_GATE_CASE_OK option length past the end of the frame refused=8 options-overrun
AIUEOS_DHCP_SMOKE_OK admitted=1 refused=3 distinct-reasons=5,9,8
```

## Both directions

**The thing that was broken is the thing that was reported, three times.** Each
tamper mode breaks a received reply in exactly one way and the gate requires
the reason code that names that way — and rejects the other two, so a run that
went red for an unrelated reason fails the gate rather than passing it:

| broken | expected | marker |
|---|---|---|
| the transaction id becomes somebody else's | 5 | `AIUEOS_DHCP_FAIL no-admitted-offer reason=5 foreign-transaction-id` |
| the OFFER's message type becomes an ACK | 9 | `AIUEOS_DHCP_FAIL no-admitted-offer reason=9 message-type` |
| an option claims 255 bytes past the end | 8 | `AIUEOS_DHCP_FAIL no-admitted-offer reason=8 options-overrun` |

**The tampering recomputes the UDP checksum afterwards**, with the same helper
the transmit path uses. Without that, every tampered datagram would have been
refused at the checksum (reason 3) and all three runs would have been red for a
reason nobody chose — three green-looking demonstrations of nothing. That is
the specific trap ADR-2608136000 names, and it was avoided by construction
rather than noticed afterwards.

**Tamper mode 2 is guarded and reports when it could not fire.** It rewrites
the message-type option at the offset the server puts it, and only if it finds
code 53 with length 1 there. A layout change makes the tampering not apply,
the reply is admitted, and the gate fails on `AIUEOS_DHCP_OK` where it required
a refusal — rather than silently testing nothing.

**The gate hardcodes no passing status.** It reads the marker the kernel
printed, requires the full `AIUEOS_DHCP_OK` prefix including SLIRP's exact
address, mask, router and server, and requires the lease to be a number. A boot
that never reaches the DHCP stage prints no marker at all and is failed
explicitly, because absence is not refusal.

**Its first version reported the right answer as wrong.** `run_case` echoed a
progress header to stdout, which its caller captured as the marker, so the
unmodified boot — which had printed exactly the right address — was reported as
having printed a header. The header now goes to stderr. Worth recording because
the failure was in the instrument and it failed in the direction that *looks*
like diligence: a gate that goes red is not thereby measuring anything.

**The main net suite asserts the lease too.** `smoke-qemu-uefi.sh` requires
`AIUEOS_DHCP_OK` whenever a NIC is attached and the reply is not being
deliberately broken, so this cannot rot behind a gate nobody runs by habit.

## What is C and what is Kotoba

| | lines | code lines |
|---|---|---|
| `kotoba/dhcp-reply-valid.kotoba` | 247 | 111 |
| `kotoba/dhcp-option-u32.kotoba` | 85 | 37 |
| `kernel/pci.c` | 300 | 184 |
| — of which test-only tampering | 44 | 26 |
| `kernel/main.c` | 93 | 71 |

The C is: Ethernet/IPv4/UDP/BOOTP header construction, the transmitted
checksum's byte layout, ring posting and polling, five words of lease, and
formatting. **It decides nothing.** The two places it might look like it does,
and does not:

- **`yiaddr` is read in C** at a constant offset from an already-admitted
  frame. That is derivation, the same rule under which the peer's MAC is lifted
  out of an admitted ARP reply (ADR-0021). Where an *option* sits is not a
  constant offset, so finding one is the object's job.
- **C keeps the maximum reason code** across candidate frames. That chooses
  which refusal to print, not whether to admit: the gateway's ARP traffic lands
  on the same queue and refuses at clause 1, and without this it could be the
  last thing seen and hide a DHCP reply that failed deep.

`main.c` gains this kernel's first number printer. Every marker before DHCP is
a fixed string because everything they report is either true or false. A lease
is neither, and a marker saying an address was configured without saying which
one cannot be wrong.

## Consequences

- **ADR-0041 row 1 is closed for the bare-metal profile** and updated in place.
  Row 1's consumption, and rows 2–3 as probes, moved in ADR-0081. Rows 4–5 on
  this profile still have no guest HTTPS GET. A node still cannot complete
  `https://kotobase.net` as KERNEL.ELF.
- **ADR-0074's status is corrected in place.** Its measurement stands; its
  conclusion — that the client could not be built — does not, because the
  boundary it measured has since been moved.
- **ADR-0019 item 3 is corrected in place.** Its `AIUEOS_VIRTIO_INPUT_FAIL`
  record does not reproduce on this host at QEMU 10.0.3, across the five boots
  whose serial logs were kept. One host is all either measurement covers, so
  the honest statement is that the result is host-dependent — not that the
  original was wrong.
- **The reason-code convention is now precedent.** If it is the wrong one, the
  place to say so is kotoba-native#57, and the cost of reversing it is two
  entries and one C call site.
- **`tcp-seq-acceptable.kotoba` is deliberately still not listed.** Listing it
  falls out of the same mechanism — a contract plus an entry — but an export
  for an object no kernel links reserves ABI for work that has not been done,
  and wiring RFC 9293 §3.10.7.4 into `net_tcp_receive` is ADR-0041 row 3. The
  note ADR-0074 added stands.

## Remaining boundary

- **The lease is consumed on the DNS / cloud-TCP path (ADR-0081).**
  `aiueos_dhcp_address()` is the UDP/TCP source for those probes. ARP, ICMP and
  guestfwd-TCP still send from compiled-in `10.0.2.15` so the four-boot tamper
  gate remains a demonstration of the admission, not of routing.
- **No renewal, ever.** One exchange at boot, then nothing: no T1/T2 timers, no
  rebinding, no DECLINE if the address is already in use, no RELEASE at
  shutdown, no retransmission with backoff if a datagram is lost. A machine
  that stays up past its lease keeps using an address it no longer holds.
- **The transaction id is a compile-time constant.** A real client picks it
  randomly, and an attacker who can guess it can answer a DISCOVER it never
  saw. That the object checks it at all is what makes the constant a property
  of this probe rather than of the protocol — but it is a weakness, and the
  virtio-rng device this kernel already drives is where the fix comes from.
- **Proved under QEMU SLIRP only.** One server, one interface, no relay agent,
  no second offer to choose between, no physical NIC.
- **The DHCP fuel tier is a computed bound, not a measurement.** 65,536, at
  roughly 34x the worst walk the object can be asked to perform. Every tier
  below it in `kernel-object-entries` was measured by execution; this one was
  not, and the all-PAD options field the gate's third case produces is the only
  thing that has exercised its worst shape.
- **Frame-parsing admissions still have no off-target oracle.** Four of them
  now. `kir/execute` refuses kernel memory by design, so the only place any of
  them runs is a booted kernel — which means every one of them costs a QEMU
  boot to test and none can be unit-tested at all.
