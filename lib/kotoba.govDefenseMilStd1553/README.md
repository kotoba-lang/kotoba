# kotoba-lang/gov-defense-mil-std-1553

**A codec for MIL-STD-1553B — the 20-bit word (Command, Data, Status),
mode codes, and the BC-to-RT / RT-to-BC / RT-to-RT / mode-command
message-transfer formats — in portable `.cljc`, published as a US
Department of Defense standard.**

## What this is not

This is a *codec and a pure message-structure validator*: it packs and
unpacks 1553 words and checks whether a sequence of words forms a valid
instance of one of the standard's message-transfer formats. It is
**not** a bus controller, not an RT simulator, not a line
driver/transceiver, has **no IO, no threads, no timing** (the real
1553B response-time and inter-message-gap requirements are physical
properties this pure codec does not enforce), and makes **no
airworthiness, flight-worthiness, or certification claim of any kind**.
MIL-STD-1553B is used in flight-critical and mission-critical military
avionics; this library is for reasoning about word bit patterns and
message structure in a test bench or simulator, not a validated
component of a weapons or aircraft data bus.

## Provenance — read this before trusting a number here

**This implementation has not read the paid SAE/DoD MIL-STD-1553B text
itself.** That said, per this task's own brief, MIL-STD-1553B is **the
most openly documented of the three standards this library's siblings
(`com-aviation-ia-arinc-429`, `com-aviation-ia-arinc-664`) implement** —
the field layout, odd-parity rule, Command/Status/Data word structure,
and standard Status Word bit assignments are consistently and widely
repeated across public unclassified sources: Wikipedia's own MIL-STD-1553
article, DDC (Data Device Corporation)/aerospace bus-analyser vendor
application notes, and numerous unclassified DoD/NASA training
materials. Confidence, worst to best:

1. **`mil1553.mode`'s reserved code entries** (9-15, 22-31) — marked
   `:unknown`/`:reserved` because this implementation does not have a
   confidently-sourced meaning for them, not because they are
   guaranteed unused in real systems. `mil1553.message/mode-command`
   fails closed (`:mil1553/mode-code-data-word-unknown`) on these rather
   than guessing whether they carry a data word.
2. **`mil1553.word`'s Sync field numeric values** (`sync-command-status`
   = `2r110`, `sync-data` = `2r001`) — a software abstraction, not a
   physical fact. On the real bus, Sync is a Manchester bi-phase
   encoding VIOLATION (3 bit-times of contiguous high or low), which has
   no natural NRZ bit-pattern equivalent; the specific 3-bit numbers
   here exist purely so the field has a fixed slot in a packed integer.
3. **`mil1553.mode`'s enumerated codes 0-8 and 16-21** — reasonably
   confident, consistently named across sources, but still not a
   standard citation.
4. **The Command/Data/Status word field layouts** (`mil1553.command`,
   `mil1553.status`), the odd-parity rule, and the 00000-means-32 word
   count convention (`mil1553.word`, `mil1553.command`) — the most
   confidently sourced claims in this library, per the task brief's own
   assessment that 1553B is more openly documented than the ARINC
   standards.

Every concrete worked value in the test suite that is not an
**exhaustive sweep** is commented `;; constructed, not a published spec
vector`.

## Surface

```clojure
(require '[mil1553.word :as w] '[mil1553.command :as cmd]
         '[mil1553.status :as st] '[mil1553.mode :as mode]
         '[mil1553.message :as msg])

(cmd/pack {:rt-address 12 :tr :receive :subaddress-mode 5 :word-count-or-mode 4})
;=> [:ok 24740]

(w/pack w/sync-command-status 24740)   ;=> [:ok 835912]
(w/unpack 835912)                      ;=> [:ok {:sync 6 :payload 24740}]
(cmd/unpack 24740)
;=> [:ok {:rt-address 12 :tr :receive :subaddress-mode 5
;         :mode-command? false :word-count-or-mode 4}]

(mode/lookup 8)     ;=> [:ok {:name "Reset Remote Terminal" :data-word :none}]

(msg/bc-to-rt {:rt-address 12 :subaddress 5 :data-words [10 20 30 40]})
;=> [:ok {:command-word {:rt-address 12 :tr :receive :subaddress-mode 5
;                        :mode-command? false :word-count-or-mode 4}
;         :data-words [10 20 30 40]}]
```

| namespace | |
|---|---|
| `mil1553.word` | the 20-bit Sync+payload+Parity frame, common to all three word types |
| `mil1553.command` | Command Word: RT Address, T/R, Subaddress/Mode, Word Count/Mode Code (with the 00000-means-32 remapping) |
| `mil1553.status` | Status Word: RT Address, ME, Instrumentation, SR, BCR, Busy, Subsystem Flag, DBCA, Terminal Flag |
| `mil1553.data` | Data Word — raw 16-bit pass-through, symmetric with Command/Status for uniform handling |
| `mil1553.mode` | the 5-bit Mode Code table + which mode codes carry an accompanying data word |
| `mil1553.message` | the message-transfer formats: BC-to-RT, RT-to-BC, RT-to-RT, Mode Commands with/without data |

## Two details this library got right the second time, not the first

**Odd parity covers 17 bits (payload + parity), not 16.** This
library's own test suite caught its own first bug here: an internal
`popcount` helper was written fixed at 16 iterations (correct for
counting the 16 payload bits `pack` needs), then reused unchanged for
`parity-ok?`'s 17-bit check (payload + parity together) — silently
dropping bit 16, the payload's own most-significant bit, from every
parity verification. The bug was invisible for any payload whose top
bit happened to be 0, and wrong for every payload whose top bit was 1
(exactly the words this library's own exhaustive sweep, not a hand-picked
example, happened to include). `popcount` now takes an explicit `width`
argument (16 in `pack`, 17 in `parity-ok?`) instead of a number baked
into the loop — see the function's own docstring for the full account.
**This was a real bug caught by the JVM test run itself, on the first
attempt to run this library's own test suite** — a concrete instance of
why this task's instruction to actually run the tests, not just write
them, matters.

**A Command Word's Word Count field pattern 00000 means 32, never
zero.** A 1553 message can never request zero data words, so the
all-zero 5-bit pattern is reused for the one count (32) that would not
otherwise fit. `mil1553.command/pack`/`unpack` do this remapping for
every caller; the test suite explicitly checks that the raw wire bits
for a count of 32 are literally `00000`, and that reading those bits
back naively (as if 0 meant 0) is wrong.

**A second real bug, also caught by this library's own test suite,
was in `mil1553.message`, not `mil1553.word`**: several builder
functions destructured a 2-tuple (`[status value]`) out of calls whose
error case is actually a 3-tuple (`[:error reason-keyword data]`),
silently truncating the diagnostic `data` — `mode-command`'s specific
"which mode code" value disappeared from its own error. Fixed by
checking `(first result)` before destructuring rather than assuming a
fixed arity.

## Errors

`[:error keyword data]`, never thrown: `:mil1553/sync-out-of-range`,
`:mil1553/payload-out-of-range`, `:mil1553/parity-mismatch`,
`:mil1553/rt-address-out-of-range`, `:mil1553/bad-tr-bit`,
`:mil1553/subaddress-out-of-range`, `:mil1553/word-count-out-of-range`,
`:mil1553/mode-code-out-of-range`,
`:mil1553/mode-code-data-word-unknown`,
`:mil1553/mode-code-requires-data-word`,
`:mil1553/mode-code-forbids-data-word`,
`:mil1553/data-word-count-out-of-range`,
`:mil1553/data-word-count-mismatch`,
`:mil1553/status-rt-address-mismatch`,
`:mil1553/data-words-present-after-message-error`. The test suite
asserts the specific keyword (and, where relevant, the actual offending
value), never just "some error came back".

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

24 tests, 86,355 assertions, on both runtimes. Exhaustive sweeps: all 32
RT addresses x all 32 Subaddress/Mode values x both T/R values for
Command Words; all 32 RT addresses x all 256 Status Word flag
combinations; the full 0..65535 Data Word space; every Word Count 1..32
(including the 00000-means-32 case); every Mode Code 0..31; and the full
20-bit word round-tripped over both Sync tags and representative
payloads (including payloads with the top bit set — the exact case that
exposed this library's own popcount bug).

## Not here

**A bus controller or RT simulator.** `mil1553.message` builds and
validates the STRUCTURE of a message transfer; it does not drive a real
exchange, enforce response-time windows, or retry.

**RT-to-RT/mode-command T/R-bit derivation.** `mil1553.message`
requires the caller to supply `:tr` explicitly for mode commands rather
than guessing it from the mode code — see `mil1553.mode`'s docstring for
why this library does not have confident-enough sourcing to automate
that.

**Vendor-specific mode code 9-15/22-31 semantics.** Real systems use
some of these; this library does not claim to know which.

## Naming

`gov-defense-mil-std-1553` follows this workspace's origin-domain naming
convention for a US Department of Defense standard (`gov-` for a
government-agency origin, per the sibling `com-aviation-ia-arinc-*`
libraries' SAE ITC/AEEC naming). `manifest/origin-domains.edn` in the
parent workspace does not currently record an origin for this repo; this
name was chosen rather than looked up, and should follow that file if it
is later updated with an authoritative origin.
