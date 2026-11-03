# Native application sender — JUN-757

`kekkai.application-send-region` composes the canonical frame codec, managed
Noise session and pending-request owner. It uses the explicit kernel-v5
`kernel-application-transmit-pool` root, exactly 1MiB. The existing receive
8MiB root, 1MiB message limit, 2048-part receive bound, 128 assemblies,
4MiB buffered limit and 256 pending requests remain unchanged. The sender
chooses 700-byte payload chunks, so an exact 1MiB request has 1498 parts.

This is a data-path component. Producing ciphertext does not grant socket,
service, endpoint, port, direction or operation consent. The installed Mac
backend, complete application controller, physical peer and production
lifecycle remain separate requirements.

## Ownership

One trusted host owns one zero-initialized 24576-byte sender region, the
dedicated transmit root, the actual 262144-byte session/pending/IO regions
and all their consumers. It serializes calls and consumption in the same
critical section with interrupts disabled. The kernel getter enforces
kernel privilege and IF off. The regions must be physically disjoint;
the API checks complete supplied allocations, pins their addresses and
never reconstructs a region from a saved scalar address. Never import or
clone sender/pending/session state. A second sender for the global TX root
is invalid even when its metadata allocation is disjoint. This trusted-host
invariant is not isolation from a malicious privileged host.

The four existing scheduler domains are not expanded. The diagnostic host
reserves scratch pages 4–9 exclusively for sender metadata, apart from
receipt page 0, completed-copy page 2 and NIC pages 10–13. It explicitly
zeros those six pages before initialize; the loader's scratch sentinel is
not an initialized owner. Production integration must independently reserve
an exclusive region and prove coexistence with the complete desktop, rather
than assume that this fixture's scratch placement is available there.

`initialize` succeeds only for an owner whose magic is zero and an actual
pending/session pair before established phase. `stop` wipes the sender and
TX root and permits a later initialization. A host must not zero a live
owner to bypass its lifetime. An active/building owner requires explicit
cancel or terminal handling before stop.

## Commands and results

Both exports accept eight arguments:
`(sender senderBytes session sessionBytes pending pendingBytes io ioBytes)`.
The IO layout retains frame input at 4096 and output at 73728. Command
data are output capacity `u32@4` (0..65538), trusted epoch milliseconds
`u64@8` (0..2^53-1), request length `u32@16`, egress outcome `u32@20`,
and operation `u32@24`. They are data, never consent or an approval token.

| Operation | Meaning and return |
| --- | --- |
| 1 acquire | Idle only. Reserve TX before writing, erase all 1MiB and emit the actual pending-issued 64-byte ID. Returns 64/-1. |
| 2 ID-copy | Building only; emit the same ID if still current in the actual pending owner. Returns 64/-1. |
| 3 begin | Validate the immutable full request in TX and reserve pending context before any encryption. Returns positive handle/-1. Invalid schema can be repaired while building. A consumed prepared ID is refused. |
| 4 next-packet | Produce one encrypted outer frame or recopy an eligible held frame without consuming another nonce. Returns wire length/-1. Output capacity is checked before encryption. |
| 5 report | Cached frame only. Egress 0: definitely not emitted, retain identical wire (return 0). Egress 1: definitely queued, advance (return 1, or 0 on final terminal). Egress 2: unknown, terminal and return 0; no automatic retry. |
| 6 cancel | Building: egress 0 discards unissued data. Active/cached: egress 0 cancels pending and erases remaining data; egress 2 terminates unknown and retains pending. Egress 1 is invalid. Returns 0/-1. |
| 7 event-copy | Terminal only. Copy a 256-byte data observation, return 256/-1. No raw addresses are exposed. |
| 8 release-event | Terminal only. Clear metadata for the next acquire; retain any outstanding pending context. Returns 1/-1. |
| 9 stop | Idle/terminal only. Erase sender and TX, preserving session and unrelated pending requests. Returns 1/-2 busy/-1 refusal. |

After successful acquire the caller may write TX. It must not alter TX after
begin succeeds, nor retain an unowned writable alias across release. The
caller hands over the IO plaintext prefix for `next-packet`; the sender
clears the prefix it used, restores input length, and leaves output tails
unchanged. Private record/JSON/codec/binding/ID scratch is erased after each
processed operation. Only pending ciphertext is held while cached. Every
terminal outcome erases all TX and held ciphertext.

Shape/header/clock/invalid-command refusals preserve regions. Processed
operations synchronize actual pending/session time and can reap expired or
revoked state even if the requested transition refuses. A fresh operation
after a UI/consent/scheduler yield must revalidate the current context before
any actual egress or effect. Never infer permission from a copied event.

## Backpressure and uncertainty

Phases are idle 0, building 1, active 2, cached wire 3 and terminal 4.
Terminal outcomes are all-queued 1, cancelled 2, unknown 3, channel-changed 4,
replay-window-lost 5, request-gone 6 and counter-exhausting 7. All-queued
means only observed local queue admission, never remote execution success.

The actual session exposes `next-send-counter`; it polls live roster/key/
clock state before returning data. For cached counter `c` and actual next
counter `N`, recopy requires `0 < N-c <= 2048`. Control traffic may interleave
but a frame beyond this replay-window guarantee is retired, not silently
re-encrypted or retried. The sender reserves the final counter boundary for
session replacement instead of creating a cache whose next poll would expire
the entire channel. Rekey advice remains a separate lifecycle obligation.

Unknown/window/counter outcomes retain pending for reconciliation. The
sender never issues the same operation again automatically. A late valid
response can still correlate; its input lifetime remains the authenticated
response controller's responsibility. An external cancel, completed response
or deadline removes the live request and produces request-gone, without
claiming which of those occurred. Actual binding includes the final Noise
hash, so same-peer/key/epoch/time reconnection is a different channel.

The 256-byte terminal event contains KSE1/version, outcome/request length/
part count/queued count, handle, last observed time, queued payload/wire byte
counts, original 96-byte channel binding and 64-byte request ID. Remaining
bytes are zero. Channel changes do not turn historical local queue data into
current authority.

## Qualification boundary

The accompanying native diagnostic uses public keys and synthetic trusted
time, actual signed-roster admission, actual Noise handshakes and isolated
QEMU NICs. Python stages public vectors and observes independently decrypted
bytes; it provides no product backend, policy evaluator, state injection or
consent. GDB writes only observation acknowledgements. Evidence records
failed prototypes separately from successful full runs. Production keys,
fresh entropy/clock, durable floors, hostile CPL3 execution, installed apps,
physical networking, native SSH and L1/distributed-OS release gates stay open.
