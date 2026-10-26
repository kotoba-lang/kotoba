# ADR-0074 — A decision this repository can write and cannot link

Date: 2026-08-22

## Status

**Superseded in part by ADR-0076 on 2026-08-22, the same day.** The measurement
below stands and is worth keeping; the conclusion it reached — that the client
could not be built — does not, because the boundary it measured was moved.
kotoba-native#57 was reviewed and landed as `a60da444`, `amu` was advanced by
the one line that pins it, and the DHCPv4 client was built and gated. Row 1 of
ADR-0041 is closed for the bare-metal profile.

What this ADR still says correctly: the export symbol of a kernel object is not
chosen by its source, an unlisted entry compiled green while exporting
`kotoba_aiueos_probe` at the revision this repository pinned, and two written
decisions had already been stranded by that rule without anything recording it.
The last of those, `tcp-seq-acceptable.kotoba`, is **still** unlisted.

Accepted as a measurement.

What is executable: the existing UEFI suite with a NIC attached, measured green
on this host today — including the three network markers ADR-0020, ADR-0021 and
ADR-0022 earned. What is not executable, and could not be made executable from
inside this repository at the revision it pins: **any new kernel admission
object**, DHCP or otherwise. The export symbol a linked Kotoba object carries
comes from a closed allow-list in `kotoba-lang/kotoba-native`, and at the
compiler revision this repository pins, a source whose entry is not on that
list compiles **green** while exporting `kotoba_aiueos_probe` — the symbol
`kernel-probe.o` already exports and every link already contains.

Nothing about UDP, DHCP or address configuration is claimed. No OFFER was
admitted, no malformed option was refused, and no lease was configured.

## Context

ADR-0041 orders five gaps between the bare-metal profile and the cloud. Step 1
is address configuration, and its ledger column read `**nothing**`. Closing it
means a DHCPv4 client — DISCOVER, OFFER, REQUEST, ACK — over UDP/IPv4 broadcast
on the virtio-net path ADR-0020 built. UDP does not exist here either: this
repository has ICMP (ADR-0021) and one TCP connection (ADR-0022) and no third
transport.

By ADR-0015 the split is not negotiable. C owns the bounded DMA and hands the
bytes over; **every judgement about those bytes is a compiler-emitted Kotoba
object**. For DHCP that rule bites harder than it did for ICMP or TCP, because
a DHCP reply's most dangerous field is not a checksum but the **options
block**: attacker-controlled, variable-length, self-describing, and terminated
by a byte inside itself. A walk that trusts a length byte reads past the end of
the frame. That walk *is* the decision, so it cannot be moved into C to get
around a packaging problem.

## What was measured

Toolchain, 2026-08-22: zig 0.15.2, `qemu-system-x86_64` 10.0.3, OVMF
`/opt/homebrew/share/qemu/edk2-x86_64-code.fd`, `amu` at `8ff1030` — the
revision `scripts/reproduce-kotoba-kernel-object.sh` pins — which resolves
`kotoba-native` `15b4a0e2` through its `deps.edn`.

### 1. The platform is green here, including the network

```
$ AIUEOS_TEST_NET=1 AIUEOS_QEMU_ATTEMPTS=1 ./os/aiueos/scripts/smoke-qemu-uefi.sh
AIUEOS_UEFI_SMOKE_OK
```

69 `AIUEOS_*` lines on the serial log, among them:

```
AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured synthetic-smoke
AIUEOS_VIRTIO_NET_OK modern-pci rx/tx arp-reply kotoba-admitted
AIUEOS_IPV4_OK icmp-echo-reply kotoba-admitted
AIUEOS_TCP_OK handshake echo close kotoba-admitted
```

**This does not reproduce ADR-0019 item 3**, which records that on QEMU 10.0.3
the shared UEFI suite fails at `AIUEOS_VIRTIO_INPUT_FAIL queue-or-envelope`.
This host runs QEMU 10.0.3 and virtio-input passed. ADR-0019 is not corrected
here — a green run on one host does not retract a failure someone else measured
— but the next agent should re-measure rather than assume that gate is red, and
these runs are the reason to.

Three runs today, on the same tree: **two green, one hung.** The hang stopped
after `AIUEOS_APIC_TIMER_OK` with `AIUEOS_QEMU_ATTEMPTS=1` at a one-minute load
average of 419, which is exactly the flake the script's own retry policy exists
for (kotoba-lang/aiueos#108) and exactly the point in the boot its comment
names. Disabling the retry to get a cleaner measurement is what produced the
false one; the run quoted above is with the gate's own default of three
attempts. Reported because a suite that needs a retry to be green on a loaded
host is a property of the evidence, not a detail of how it was collected.

### 2. The export symbol is not chosen by the source

Two sources, compiled with `bin/amu compile --target x86_64-aiueos-kernel-v1`,
differing by **one identifier** and by nothing else — same arity, same body,
same `(defn main [] 0)`:

| entry name in the source | symbol the object exports |
|---|---|
| `aiueos-net-arp-reply-valid` (listed) | `kotoba_aiueos_net_arp_reply_valid` |
| `aiueos-dhcp-reply-valid` (unlisted) | `kotoba_aiueos_probe` |

Both compiles returned `{:ok true, …}`. Arity, body, `main` and the use of a
kernel intrinsic were all held constant, so the difference is the identifier —
and `package-kernel-object` says why. **It is membership in a list.**

The count corroborates it: the fixed compiler reports `:admitted-entry-count 56`
in its refusal (amu#626), which is exactly the number of entries at the pinned
revision.

### 3. Where the list is, and that it now has a documented door

`kernel-object-entries` in `kotoba-lang/kotoba-native`, a map from Kotoba entry
symbol to `{:arity n :symbol "kotoba_aiueos_…"}`. `package-kernel-object` takes
the first key of that map present in the artifact's exports; a miss falls back
to the program entry with `{:arity 0 :symbol "kotoba_aiueos_probe"}`.

- `kotoba-native` `15b4a0e2`, which `amu` `8ff1030` pins: **56 entries**, none
  naming DHCP or UDP.
- `kotoba-native` `origin/main` `95fd4b1`: **60**, none naming DHCP or UDP.

**ADR-0054's open question has been answered upstream since it was written.**
That ADR filed [amu#626](https://github.com/kotoba-lang/amu/issues/626) because
the naming rule was not derivable from the sources that depend on it. The issue
is closed. Its resolution:

- `kotoba-native` `dc1d2a9` — **an unlisted `aiueos-*` export now throws**
  instead of becoming the probe: *"Kotoba kernel object declares an aiueos
  export with no admitted symbol"*, with the unlisted entry named in `ex-data`.
  The rule was undiscoverable **because** the miss was silent.
- `kotoba-native` `1d51768` — entries whose aiueos contract carries a
  `:native {:export "…"}` block are **transcribed rather than chosen**. That is
  the documented door: declare the symbol in `os/aiueos/contracts/<name>-v1.edn`
  and the entry follows.
- `amu` `6bd93b7` — pins both and asserts the symbols.

**This repository pins none of it.** `amu` `8ff1030` is **250 commits behind**
`amu`'s tip `6889fa7`, and `git merge-base --is-ancestor 6bd93b7 8ff1030` is
false — the pin does not contain the fix. So the failure mode ADR-0054
discovered here is fixed upstream and still live here: measured above, the miss
is silent at the revision this repository actually builds with.

### 4. The silent miss is worse than a missing symbol

`kernel-probe.o` exports `kotoba_aiueos_probe`, and `build-uefi.sh` links it
into every kernel. An unlisted object exports **the same symbol**. So the
compiler's fallback does not merely fail to give a new object a name — it gives
it a name that is already taken, in an object that is always present.

`verify-kotoba-kernel-object.py` is what caught it, at link time:

```
error: invalid Kotoba kernel object: requires exactly one kotoba_aiueos_dhcp_reply_valid symbol
```

and the same bytes pass when asked for `kotoba_aiueos_probe`. That verifier is
the only thing between a silent compiler miss and a kernel with two objects
claiming one symbol.

### 5. This has already stopped work here twice, and only once was it named

- `kotoba/murakumo-join-plan.kotoba` — ADR-0019 names it: *"Exporting it as a
  kernel object would need an entry in `kotoba-lang/kotoba-native`'s
  `kernel-object-entries` allow-list — a reviewed ABI change in a third repo.
  Not taken."*
- `kotoba/tcp-seq-acceptable.kotoba` — RFC 9293 §3.10.7.4 segment acceptance,
  arity 4, parity-tested through the KIR interpreter against
  `kotoba-lang/org-ietf-tcp`. It has **no `.o`**, `build-uefi.sh` does not link
  it, and `aiueos-tcp-seq-acceptable` is on neither list. Nothing in this
  repository said so until now. It is part of step 3 of ADR-0041's ledger,
  written and unreachable.

DHCP would have been the third.

## Decision

**Do not build the DHCPv4 client at this revision. State the ABI ask instead,
in a form somebody can act on without inventing anything, and file it.**

Filed as
[kotoba-native#57](https://github.com/kotoba-lang/kotoba-native/issues/57),
carrying the table below, the measurement, and the one question worth asking
before the objects exist rather than after. Two entries, and the semantics each
carries:

| entry | arity | symbol | what it decides |
|---|---|---|---|
| `aiueos-dhcp-reply-valid` | 5 | `kotoba_aiueos_dhcp_reply_valid` | `(frame length xid mac expected-type)` → `0` to admit, or a distinct non-zero code naming the clause that refused: BOOTREPLY with `htype`/`hlen` for Ethernet; the transaction id this boot chose; the hardware address in `chaddr` (not the Ethernet destination — a client with no address yet is answered by broadcast); the magic cookie `0x63825363`; an options walk that never reads at or past `length`; the expected message type (OFFER, then ACK); a server identifier; an offered address and mask that are internally consistent; a lease in a sane range |
| `aiueos-dhcp-option-u32` | 3 | `kotoba_aiueos_dhcp_option_u32` | `(frame length code)` → the four-byte value of the first well-formed occurrence of that option, re-walking under the same bound rather than trusting that the admission already walked it |

A reason code rather than a boolean, because the three refusals a gate has to
tell apart — a foreign transaction id, the wrong message type, and an option
length running past the end of the frame — are three clauses of one decision,
and the object is the only place that knows which one fired. Deriving that in C
would make C decide.

**What was rejected, and why:**

- **Write the options walk in C and keep a boolean in Kotoba.** The walk is the
  decision. This is the failure ADR-0015 exists to prevent.
- **Reuse an allow-listed symbol.** Every entry on the list names a different
  decision and most are already linked, so it would either collide or be a lie
  in the symbol table. Usually both.
- **Override `kotoba-native` locally to produce the bytes, then commit the
  `.o`.** It would produce an artifact no pinned revision reproduces — the
  thing `reproduce-kotoba-kernel-object.sh` exists to detect, and whose own
  comments record that it already fails on one artifact (`user-smoke.elf`,
  *"NOT REPRODUCIBLE at the pinned revision, and the only one left that is
  not"*).
- **Land the `.kotoba` source unlinked, as `tcp-seq-acceptable.kotoba` was.**
  Rejected on the evidence of item 5: an unlinked source with nothing saying it
  is unlinked is how this repository lost track of the last one. It could not
  even be exercised off-target — `kotoba.kir` traps `kernel-load-u8-4k` with
  `:kernel-memory-unavailable` *by design*, because there is no frame contents
  it could honestly invent — so it would be a parser no test and no boot could
  run.
- **Write `os/aiueos/contracts/dhcp-*-v1.edn` to open the `1d51768` door now.**
  Deferred, not refused. That door is not reachable from a compiler that does
  not contain the commit that opened it; and of the eleven contracts in that
  directory with a `:native` block, nine carry `:vectors` that
  `os/aiueos/scripts/aiueos/verify_*.clj` executes through `kir/execute` —
  which, for the reason above, these two objects cannot have. A contract whose
  vectors nobody can run is the shape ADR-0050 already named here. It is the
  right first step **after** the pin advances.
- **Ship a QEMU gate for a client that does not exist.** A gate that cannot go
  green is not a gate (ADR-0063).

## Executable evidence

```
$ AIUEOS_TEST_NET=1 AIUEOS_QEMU_ATTEMPTS=1 ./os/aiueos/scripts/smoke-qemu-uefi.sh
AIUEOS_UEFI_SMOKE_OK

$ bin/amu compile listed-name.kotoba   --target x86_64-aiueos-kernel-v1 --output listed-name.o
{:ok true, :target :x86_64-aiueos-kernel-v1, …}
$ bin/amu compile unlisted-name.kotoba --target x86_64-aiueos-kernel-v1 --output unlisted-name.o
{:ok true, :target :x86_64-aiueos-kernel-v1, …}

$ python3 os/aiueos/scripts/verify-kotoba-kernel-object.py listed-name.o "" kotoba_aiueos_net_arp_reply_valid
AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export=kotoba_aiueos_net_arp_reply_valid imports=0 relocations=1

$ python3 os/aiueos/scripts/verify-kotoba-kernel-object.py unlisted-name.o "" kotoba_aiueos_dhcp_reply_valid
error: invalid Kotoba kernel object: requires exactly one kotoba_aiueos_dhcp_reply_valid symbol

$ python3 os/aiueos/scripts/verify-kotoba-kernel-object.py unlisted-name.o "" kotoba_aiueos_probe
AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export=kotoba_aiueos_probe imports=0 relocations=1

$ python3 os/aiueos/scripts/verify-kotoba-kernel-object.py os/aiueos/kotoba/kernel-probe.o "" kotoba_aiueos_probe
AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export=kotoba_aiueos_probe imports=0 relocations=1
```

The last two lines are the same symbol from two different objects, one of which
is linked into every kernel this repository builds.

## Both directions

The refusal is caused by the identifier and by nothing else, and it is shown
both ways on bytes that differ by one line of source:

- **Green on the listed name.** `listed-name.kotoba` verifies as
  `export=kotoba_aiueos_net_arp_reply_valid`.
- **Red on the unlisted name.** `unlisted-name.kotoba` is refused when asked for
  `kotoba_aiueos_dhcp_reply_valid`, and **passes** when asked for
  `kotoba_aiueos_probe` — which is how the emitted object is known to be a
  probe rather than a broken admission. The thing that was changed and the
  thing that was reported are the same thing: the export symbol.

What was **not** demonstrated in both directions, and is not claimed, is any
DHCP behaviour. There is no client to break.

## Consequences

- **Row 1 of ADR-0041 is updated in place** to name what it needs and what
  stands in front of it. It is not closed and no part of it is claimed.
- **`tcp-seq-acceptable.kotoba` is now on the record as unreachable.** Anyone
  reading ADR-0041's row 3 as "TCP continues here" should read that file's
  linkage status first.
- **The pin is the work, not the protocol.** The cheapest next step is not
  DHCP: it is advancing `amu` from `8ff1030` toward a revision carrying
  `6bd93b7`, at which point an unlisted export **fails loudly** instead of
  becoming the probe, and a contract can declare its own symbol. That advance
  is a real piece of work — `reproduce-kotoba-kernel-object.sh` pins
  `8ff1030` precisely because it is *"the revision the check was actually run
  against"*, and re-running it across 250 commits of compiler will move bytes.
- **Steps 2–5 of ADR-0041's ledger are untouched.** A DNS stub resolver, a
  usable TCP stream, TLS 1.3 with chain validation, and an HTTP/1.1 client
  remain unwritten for the bare-metal profile. Each lands the same way DHCP
  would have — a decision object plus a C mechanism — so each meets this
  boundary first. A resolver's answer parse and a TLS record layer are the same
  class of attacker-controlled, self-describing, variable-length parse as
  DHCP's options field, which is to say the same class of allow-list entry.
- **A node still cannot reach `murakumo.cloud` from bare metal**, and its
  addresses are still SLIRP's `10.0.2.15` and `10.0.2.2`, compiled into
  `kernel/pci.c`.

## Remaining boundary

- ~~**Nothing here was fixed.**~~ **Closed by ADR-0076.** The entries were
  reviewed and landed, and the smaller pin advance was taken after the full one
  was measured and rejected. What ADR-0054 said — *"Filing is not fixing"* —
  held for four hours.
- ~~**UDP remains unwritten**~~ — written in ADR-0076, and deliberately only as
  much of it as DHCP needs: no socket, no port table, no demultiplexer.
- **The two entries were reviewed and accepted**, reason code and all, and are
  now precedent. The question was worth asking before the objects existed; that
  it was answered quickly does not make asking it wrong.
- **Frame-parsing admissions have no off-target oracle at all.** `net-arp-`,
  `ipv4-icmp-` and `tcp-segment-valid` have no contract in
  `os/aiueos/contracts/` and no verifier in `os/aiueos/scripts/aiueos/`; the
  only place any of them has ever run is a booted kernel. That is a pre-existing
  gap this ADR did not create and did not close, and it is why "write the object
  and test it later" was not available.
