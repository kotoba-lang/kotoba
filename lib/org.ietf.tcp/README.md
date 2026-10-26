# org-ietf-tcp

**RFC 9293 TCP — sequence arithmetic and the connection state machine, in
portable `.cljc`.**

No sockets, no buffers, no clock. `step` takes a connection and one event and
returns the next connection plus the segments to send; the caller passes
`:now-ms`, which is what makes TIME-WAIT testable without waiting out 2×MSL.

```clojure
(require '[tcp.state :as tcp])

(def c  (tcp/connection {:iss 1000}))
(def r1 (tcp/step c {:kind :connect}))              ; => :send [SYN]
(def r2 (tcp/step (:tcp/connection r1)
                  {:kind :segment
                   :segment {:tcp/seq 5000 :tcp/ack 1001 :tcp/flags #{:syn :ack}}
                   :now-ms 0}))
(tcp/established? (:tcp/connection r2))              ; => true
```

## Sequence arithmetic is its own namespace for a reason

Sequence numbers are 32 bits and **wrap**. `<` on the raw integers is not the
comparison TCP means: after a wrap, a small number can be newer than a large
one. A stack that compares raw integers works perfectly for the first four
gigabytes of a connection and then starts discarding valid segments.

`tcp.seq` implements RFC 9293 §3.4's modular comparison, and two numbers exactly
2^31 apart are reported as **unordered** rather than given an invented answer
(`ordered?` exists so a caller that must not act on an undefined ordering can
ask).

## What the state machine refuses

- **A RST outside the receive window** is dropped, not obeyed. Obeying it is how
  a blind off-path attacker kills connections.
- **A RST in SYN-SENT** is believed only when it acknowledges our SYN.
- **An unacceptable segment is answered with an ACK**, not with silence — the
  peer has to learn our window.
- **Data against a zero window** is never acceptable. That is one of the four
  cases in §3.10.7.4's table and the one hand-written stacks let through.
- **A RST to a closed connection is not answered.** Answering a RST with a RST
  is how two closed peers loop forever.

## Simultaneous open is in the table

Two peers can SYN each other at once, and SYN-SENT receiving a bare SYN goes to
SYN-RECEIVED. It is rare, it is exactly the arm that gets dropped when the table
is written from the common path, and it has a test whose name says so.

## What this is not

**Not a transmission stack.** No retransmission timers, no congestion control,
no Nagle, no window scaling, no options, no reassembly of out-of-order data.
Those are separable, and they are named here as absent rather than half-built.

`kotoba-lang/aiueos` carries a one-connection TCP *probe* whose own README says
"this is a probe, not a stack". This namespace is the connection half of what
would replace it; the transmission half is still unwritten.

## Retransmission

`tcp.rto` is RFC 6298's estimator and `tcp.retransmit` is the queue it drives.

RTO covers the round trip **and its variance** — an estimator tracking only the
mean retransmits on jitter, and every early retransmission is a segment the
receiver already has plus a congestion signal the sender invented. RTTVAR is
updated from the **old** SRTT, because updating SRTT first collapses the
deviation term exactly when a jump makes the headroom necessary.

**Karn's algorithm is enforced, not weighted.** An ACK for a retransmitted
segment is ambiguous — it may acknowledge the original or the copy — so the
sample is refused and reported as refused (`:karn`), which is not the same as no
measurement having been taken. The flag lives on the queue entry, so one
retransmitted segment and one clean segment in flight together still yield the
one sample that is entitled to be measured.

`due` returns only the **oldest** expired entry. Flushing the queue on one timer
turns a single loss into a burst the network already asked the sender not to
send.

## Congestion control

`tcp.congestion` is RFC 5681: slow start, congestion avoidance, fast retransmit
and fast recovery.

The window is a **guess about a path nobody can see**. A sender cannot observe
the bottleneck; it observes that segments arrived and that some did not, and
5681 turns those two observations into a number.

- **Three duplicate ACKs is a heuristic, not a proof.** A duplicate means the
  receiver got something out of order, which happens on loss *and* on
  reordering. Three is where 5681 bets that loss is likelier — a path that
  reorders heavily will make this sender halve for no reason. Said here so a
  reader does not assume the number was derived.
- **A timeout is harsher than duplicates because the evidence is.** Duplicates
  mean the receiver is still hearing something; a timeout means it is not. So a
  timeout drops cwnd to one segment while fast recovery only halves it.
- **Fast recovery inflates, and the inflation must be undone.** Leaving it
  deflates cwnd back to ssthresh — a sender that forgets keeps a window it never
  earned. That has its own test.
- The initial window follows 5681 (`min(4·MSS, max(2·MSS, 4380))`), not RFC
  6928's 10·MSS. The larger burst is available as `initial-window-10` because
  how much an unmeasured path can absorb belongs to whoever deploys this.

`may-send` knows only what the **network** will take. The receiver's advertised
window is the other limit and stays with the caller.

## Reassembly

`tcp.reassemble` holds in-window segments that arrived out of order and hands up
the prefix that has become contiguous. A receiver that discards everything after
a gap turns one lost segment into a whole window of retransmissions — and the
congestion controller reads those as a much worse path than the one it is on.

**Overlap has a policy and the policy is first-data-wins.** Segments can overlap
and the overlapping bytes can *disagree*. Two receivers resolving that
differently see two different streams from the same packets, which is the whole
family of overlap-based IDS evasions. This keeps the bytes it already has and
trims the arrival down to what is genuinely new; taking the newer bytes would
let anyone able to inject a later packet rewrite what the peer already sent.

**The queue is bounded and overrun is refused whole.** An unbounded out-of-order
queue is a memory-exhaustion primitive. The bound is charged against what stays
*held* — in-order data is delivered and never occupies the queue — and a
segment that would exceed it is refused entirely, because a trimmed fragment can
never be completed.

`gaps` reports the holes as `[start end)` pairs — what a SACK option would say
if this stack had one.

## Window scaling and timestamps

`tcp.options` is RFC 7323. The header's window field is 16 bits, so without
scaling a receiver cannot advertise more than 65535 bytes — which makes
`tcp.congestion` an exercise on any path with a large bandwidth-delay product,
because cwnd can grow all it likes and the advertised window is the binding
limit.

- **Both sides must offer it or neither uses it.** There is no partial adoption:
  a scaled window read as unscaled is 2^N too small and the other way round is
  2^N too large.
- **A SYN's window is never scaled.** The option agreeing the scale travels in
  that very segment. `apply-scale` takes `syn?` and refuses rather than trusting
  the caller to remember — this is the classic bug in the option.
- **The two shifts are not interchangeable.** We shift our own advertisements by
  what we offered and read theirs by what they offered. Swapping them only shows
  on asymmetric shifts, which is why it survives casual testing.
- **`advertise` returns nil for a window it cannot express** rather than
  truncating, because truncating advertises a smaller window and stalls
  throughput with no error anywhere.

Timestamps buy two things. **PAWS** rejects old duplicates that the sequence
space could have wrapped past, comparing modularly because the timestamp clock
wraps too. And **the echo lifts Karn's restriction**: `tcp.rto` refuses samples
from retransmitted segments because the ACK is ambiguous about which copy it
acknowledges, and the echo is not ambiguous. `rtt-sample` is a named function so
that lifting is deliberate rather than a caller forgetting a flag.

Only an in-sequence segment updates the recorded timestamp — recording from a
reordered arrival lets an old segment raise the bar against the ones behind it.

## Selective acknowledgement

`tcp.sack` is RFC 2018. Without it a sender that loses one segment out of a
window knows only that the cumulative ACK stopped moving — it cannot tell one
loss from ten, so it resends from the hole onward and the receiver discards most
of what arrives. Data the network carried twice, on a path the sender has just
decided is congested.

**SACK is advisory, and that is the whole subtlety.** §8 permits a receiver to
renege: to report a range and later discard it. So `apply-blocks` *marks* queue
entries and does not remove them — only the cumulative ACK retires anything,
because only the cumulative ACK is a promise. A sender that frees SACKed data
and then meets a reneging receiver has lost bytes it can never resend, and the
connection stalls with nothing reporting why.

**The option is small and how small depends on what else is on.** Four blocks
fit in 40 bytes of option space; with timestamps also present, three. A stack
that always emits four overruns the option space on every timestamped
connection, so `max-blocks` takes the answer as an argument rather than assuming.

**Order is not arbitrary.** §4 wants the block covering the most recently
received segment first, with the previous report repeated behind it — so a lost
ACK does not cost the sender its picture, and truncation drops the oldest
information rather than the newest.

`pipe` is RFC 6675's estimate of what is really still in the network. Counting
SACKed data as in flight under-sends for the rest of the recovery.

## Nagle and the delayed ACK

`tcp.pacing` has both, in one namespace, because their interaction is the reason
either is interesting.

Each alone is reasonable. Nagle stops a sender turning one keystroke into one
41-byte packet. The delayed ACK stops a receiver spending a packet on every
acknowledgement.

**Together they deadlock.** A sender writes data ending in a partial segment;
Nagle holds it because earlier data is unacknowledged. The receiver has that
earlier data and is waiting — for a second full segment that will never come,
because the sender is holding it. Nothing is lost, nothing errors, and the
transfer stalls for the receiver's whole delay on every request that ends in a
partial segment.

`deadlock?` and `stall-ms` name that state so it can be asserted against rather
than discovered in a latency graph. **This namespace will not resolve it by
quietly disabling one side** — which one to disable belongs to the application
(a request/response protocol wants Nagle off; a bulk transfer does not), and a
library choosing silently is how a setting becomes impossible to find later.

Two details loss recovery depends on:

- **An out-of-order segment is acknowledged immediately.** Those duplicate ACKs
  are what `tcp.congestion`'s fast retransmit counts; delaying them delays the
  third duplicate, and so the retransmission, by the whole timer — on exactly
  the path that has just lost a segment. A test drives three of them into the
  controller to show the retransmit fires now rather than a timer later.
- **The delay timer runs from the first unacknowledged segment**, not the most
  recent. Restarting it on each arrival lets a steady trickle of small segments
  defer the ACK indefinitely.

## Path MTU discovery

`tcp.pmtu` is RFC 8899 (PLPMTUD), not RFC 1191.

The classic method sends large packets with don't-fragment set and waits for a
router to reply with ICMP naming a smaller size. **Firewalls filter ICMP.** When
they do, the oversized packets are dropped and nothing comes back — a PMTU black
hole. The connection completes its handshake perfectly, because SYNs are small,
and hangs the moment it sends a full-sized segment. "Connects fine, stalls on the
first real transfer" is that failure, and it is invisible to every check that
only asks whether the connection came up.

So the search is driven by the transport: probe upward, and an **acknowledged
probe is the confirmation**. A filtered network is no longer silent; it simply
fails to confirm, which is a signal.

ICMP is still used, as a hint that narrows the search, never as an authority:

- A message that does not quote a packet we sent is refused. Without that check,
  anyone able to send an ICMP packet can shrink this connection to the floor and
  leave it there.
- A claim below `min-mtu` is **refused, not clamped** — a path that cannot carry
  1200 bytes is not one this transport can use, and clamping hides that behind
  tiny segments.
- A claim at or below a size a probe already carried is refused. A changed path
  and a forgery are indistinguishable from here, so the evidence this connection
  gathered itself wins, and the black-hole detector catches a genuinely changed
  path using timeouts rather than anyone's assertion.

**Repeated timeouts at a size that used to work fall back to base.** That turns
a hung connection into a slow one, and a slow connection is one somebody can
debug. It is the failure the ICMP method cannot see at all.

Losing a probe is **not** a congestion signal: probes are deliberately oversized
and their loss says something about size, not about queueing.

## The scheduler

`tcp.send` composes the rest into the question a sender actually has: is there
something to put on the wire now, and what.

**The binding limit is reported on every decision.** Three things cap how much
may go — the congestion window (what the *network* will take), the receiver's
advertised window (what the *peer* will take) and the path MTU (what one packet
may be) — and which one was smallest is the diagnostic. "This connection is
slow" is unanswerable without it; `why-slow` turns a decision into `:the-network`
or `:the-peer` or `:held-for-coalescing`, which is the difference between
looking at the network and looking at the application on the other end.

**Flight size is un-SACKed bytes, not queue bytes.** SACKed data has left the
network — the receiver said so — and counting it as in flight holds the sender
back for the rest of the recovery by exactly the amount the receiver already
has. This is a throughput bug no single-namespace test can catch, because
`tcp.sack` and `tcp.congestion` are each individually correct; it exists only in
the composition, which is why this namespace has tests of its own.

Precedence: a timed-out segment outranks everything, including a collapsed
congestion window (RFC 5681 permits one loss-recovery segment). Then, in
recovery, the SACK-named holes go before anything new (RFC 6675). Then new data,
subject to Nagle.

## What this is not

A socket. Nothing here reads from a send buffer, writes to a wire, or holds a
timer — every namespace decides, and the mechanism is the caller's. That
boundary is deliberate: this has to run where there is no socket API at all.

## Status

169 tests / 386 assertions across ten namespaces. Shown to discriminate at every layer: replacing the
modular comparison with a raw `<` fails 8; removing the simultaneous-open arm
fails 2; dropping Karn's refusal and flushing the queue on one timer fails 5;
forgetting to deflate on leaving fast recovery and making a timeout as gentle as
a fast retransmit fails 5; taking the newer bytes on overlap plus unbounding
the out-of-order queue fails 8; scaling the SYN, swapping the two shifts and
comparing timestamps raw fails 5; treating a SACK as a promise plus always
emitting four blocks fails 10; delaying the out-of-order ACK plus restarting
the delay timer on each arrival fails 5; believing unvalidated ICMP,
clamping a below-floor claim and removing the black-hole fallback fails 5; and
counting SACKed data as in flight plus sending new data before the holes fails 3.
