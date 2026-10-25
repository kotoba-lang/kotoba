# kotoba-lang/org-fixtrading-fix

**FIX (Financial Information eXchange) tag=value/SOH wire codec — the classic
FIX.4.2/FIX.4.4/FIX.5.0 session encoding — in portable `.cljc`, with no
dependencies.**

## What this is not

- Not an order-routing engine, a matching engine, or anything that decides
  what to do with a message once it's decoded.
- Not a session state machine: no sequence-number tracking, no resend logic,
  no Logon handshake, no reconnect. It encodes/decodes one message at a
  time; a caller owns the session.
- Not a socket. No IO, no threads, nothing that opens a connection.
- Not a full FIX data dictionary. The field/message tables in
  `fix.dictionary` cover exactly the tags this library's test suite
  exercises (see below) — enough to prove the dictionary is a swappable
  parameter, not enough to validate arbitrary messages against the full FIX
  standard.
- Not FIXML, FAST, or SBE — the other three wire encodings FIX also
  standardizes. This is tag=value only.
- Not a validator of required-vs-optional fields per message type. This
  codec checks framing (header order, BodyLength, CheckSum, trailer
  presence) and repeating-group structure; it does not check that, say, a
  NewOrderSingle actually contains OrderQty.

## Surface

```clojure
(require '[fix.message :as message] '[fix.dictionary :as dict] '[fix.bytes :as b])

(def enc
  (message/encode dict/fix42
    {:begin-string "FIX.4.2"
     :msg-type "D" ; NewOrderSingle
     :body [[49 "BUYSIDE"] [56 "SELLSIDE"] [34 "2"] [52 "20260830-12:00:00"]
            [11 "CLORD001"] [21 "1"] [55 "IBM"] [54 "1"]
            [60 "20260830-12:00:00"] [40 "2"] [38 "100"] [44 "50.25"] [59 "0"]
            {:group 78 :entries [[[79 "ACCT1"] [80 "60"]]
                                  [[79 "ACCT2"] [80 "40"]]]}]}))
;; (:bytes enc) is a vector of ints 0..255 — the actual wire bytes,
;; including the computed BodyLength(9) and CheckSum(10)

(message/decode dict/fix42 (:bytes enc))
;; => [:ok {:begin-string "FIX.4.2" :msg-type "D" :body-length 165
;;          :check-sum "239" :body [... [{:group 78 :entries [...]}]]}]

(b/bytes->str (:bytes enc)) ; human-readable form, SOH shows as \x01
```

| namespace | |
|---|---|
| `fix.bytes` | byte<->string primitives (the Latin-1 byte mapping, `char-code` — see "The trap" below), SOH-delimited field splitter/parser |
| `fix.checksum` | BodyLength and CheckSum — the two arithmetic fields |
| `fix.codec` | the tag=value/SOH wire codec: header, trailer, framing. No dictionary. |
| `fix.groups` | repeating-group structuring/flattening, dictionary-driven |
| `fix.message` | `fix.codec` + `fix.groups` composed, parameterized on a `fix.dictionary` |
| `fix.dictionary` | `fix42`/`fix44`/`fix50` — field/message/group tables as **data** |

Bytes are `Sequential` collections of ints in 0..255, in and out — same
convention as `org-modbus`.

## Three details that are usually got wrong

**BodyLength(9) counts from MsgType(35) through the trailing SOH before
CheckSum(10) — not the whole message, and not excluding that trailing SOH.**
Get either boundary wrong and the frame you built still looks fine on its
own; only the *next* message on the wire desyncs, because a receiver reads
exactly `BodyLength` bytes past the `9=NNN` field to find `10=`.

**CheckSum(10) is the sum of every byte from BeginString's `8` through that
same trailing SOH, mod 256, rendered as *exactly three* ASCII digits,
zero-padded.** `"62"` is not the same field value as `"062"` even though
they're numerically equal — a receiver comparing strings correctly rejects
the unpadded form, and this library's decoder does too
(`checksum-must-be-exactly-three-digits` in the test suite).

**Every repeating-group entry must begin with the group's first defined
member tag, even when that field would otherwise be optional** — that's the
only thing that lets a decoder tell where one entry ends and the next
begins without an explicit per-entry length. Skip enforcing it and an
optional field simply missing from entry 1 gets silently misattributed as
belonging to entry 2. `fix.groups` enforces it and returns
`:fix/group-missing-delimiter` rather than accepting the ambiguity.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule:
`:fix/malformed-field` (no `=`, or a non-numeric tag), `:fix/invalid-header-order`
(BeginString/BodyLength/MsgType aren't the first three fields in that order),
`:fix/missing-trailer` (last field isn't CheckSum, or fewer than 4 fields
total), `:fix/body-length-mismatch`, `:fix/checksum-mismatch`,
`:fix/group-count-mismatch` (a NoXXX field's declared count doesn't match
how many entries are actually present), `:fix/group-missing-delimiter`
(described above). **Those keywords are contract.**

## Repeating groups: how they're modeled

A group in the logical (pre-encode / post-decode) body is
`{:group tag :entries [[[t v] [t v] ...] [[t v] ...] ...]}` — the NoXXX
count is *computed* from `(count entries)` on encode, never asked for, so it
can't disagree with what actually got written. Decoding restructures the
flat wire fields back into that same shape using the dictionary's `:groups`
table (`{count-tag {:member-tags [first-tag & rest]}}`).

This only handles one level of nesting — no group inside another group's
entries. Every message this library covers only nests one level deep;
extending `fix.groups` to recurse is straightforward but not done.

The one repeating group implemented and tested is **NoAllocs(78)** on
FIX.4.2's NewOrderSingle — `AllocAccount(79)`/`AllocShares(80)` per entry,
delimiter `79`. Declared only on `fix42` in `fix.dictionary`, not copied
onto `fix44`/`fix50`, because this library has verified that shape against
FIX.4.2's message definition and not against the later versions (see that
dictionary's docstring).

## The swappable dictionary

`fix.codec` and `fix.groups` take no version-specific knowledge at all —
`fix.codec` doesn't know what any tag means, and `fix.groups` only consults
whatever `:groups` table it's handed. `fix.message/encode` and
`fix.message/decode` take a `fix.dictionary` value (`fix42`/`fix44`/`fix50`,
or a caller's own) as an explicit first argument. The one place this
actually matters in the tables shipped here: `fix50`'s `:begin-string` is
`"FIXT.1.1"`, not `"FIX.5.0"` — FIX.5.0 split its session layer out into the
FIXT.1.1 transport protocol, and BeginString on the wire reflects that. A
codec that hardcoded `"FIX.5.0"` would build a wire-invalid FIX.5.0 message.

## Relationship to `kotoba-lang/kotoba-iso20022`

Both are financial-messaging codecs, but for different eras and different
networks. FIX is the **trading-venue-facing** protocol — order entry,
execution reporting, market data, session management between a buy-side/
sell-side pair or a venue — invented in 1992 and still tag=value/SOH at the
wire level for the classic session (newer FIX transports like FIXP/Simple
Binary Encoding exist but aren't this library's scope). ISO 20022 is the
**bank-to-bank settlement/payment** message family SWIFT itself migrated
to via CBPR+, XML-based, and is what `kotoba-iso20022` implements for the
kawase-yui on/off-ramp ingress boundary. They don't overlap in scope: a
trade executed over FIX might, downstream, settle via an ISO 20022
credit-transfer message, but this library doesn't encode that relationship
— it only speaks FIX.

## Relationship to `com-fixprotocol` / `com-fix-fast-protocol`

Both of those are ~190-line CRUD REST facades (`entity-specs`/`routes`/
`POST /v1/...`) with zero byte operations — an audit found they do not
implement FIX at all, despite the name. This library is the real thing:
byte-level SOH framing, BodyLength/CheckSum arithmetic, repeating groups.
Read the two facades only to see what not to produce.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both run the same 19 deftests / 436 assertions in `test/fix/core_test.cljk`.

**Test vectors are constructed, not published spec vectors** — FIX.5.0 SP2
Volume 1 documents the BodyLength/CheckSum *algorithm* precisely (confirmed
against b2bits FIXOpaedia and OnixS's FIX Dictionary for tag-level detail),
but the official spec text doesn't publish a worked full-message byte
example with BodyLength/CheckSum filled in. So the two full-message test
vectors (a Logon and a NewOrderSingle-with-NoAllocs-group) were built here,
and their BodyLength/CheckSum were computed **independently in Python**
(`sum(bytes) % 256`, three-digit zero-padded — literally the algorithm this
library implements, written a second time in a different language, not
copied from this library's own output) before being hardcoded into the
test file. See the comment above `logon-wire` in `core_test.cljc` for the
exact Python one-liner.

Every individual field tag used (49 SenderCompID, 56 TargetCompID, 78
NoAllocs/79 AllocAccount/80 AllocShares on NewOrderSingle, 150 ExecType, 39
OrdStatus, 371 RefTagID/372 RefMsgType/373 SessionRejectReason on Reject,
etc.) was checked against the FIX.4.2/4.4 field dictionaries (b2bits
FIXOpaedia, OnixS FIX Dictionary) rather than recalled from memory.

**Discrimination was verified by breaking the implementation, not just the
test fixtures.** `fix.checksum/checksum`'s `mod 256` was changed to
`mod 255` (the classic modulus off-by-one) and the JVM suite re-run:
`logon-vector`, `new-order-single-vector-with-group`, and
`checksum-known-values` failed immediately (they check the recomputed
checksum against the independently-computed `"062"`/`"239"` values, which a
broken modulus can no longer reproduce), while `round-trip-encode-decode-known-messages`
errored, and — instructively — the group and session-message round-trip
tests that only check `encode(x)` against `decode` of its own output kept
passing, because encode and decode shared the same broken arithmetic and
stayed self-consistent with each other. That's the concrete argument for
why this suite pins expected values computed independently rather than
relying on round-trip alone. The change was then reverted and both JVM and
ClojureScript suites re-run clean (0 failures, 436 assertions each).

## The trap this library's own primitives are built to avoid

`fix.bytes/char-code` exists because `(int (nth s i))` on a JVM string gives
you a codepoint, and the equivalent-looking ClojureScript expression does
not — the same idiom org-modbus's README documents as having silently
turned nine ASCII digit bytes into nine zero bytes under ClojureScript
(`(map int "123456789")`) while passing clean on the JVM, on the same day it
also broke a WebSocket handshake digest and made two different passwords
hash identically elsewhere in this workspace. A FIX CheckSum computed over
an all-zero body would still print as a plausible three-digit number; only
running the ClojureScript suite (not just the JVM one) would ever reveal it
was wrong. `char-code`/`byte->char` in `fix.bytes` use `.charCodeAt`/
`String.fromCharCode` under ClojureScript specifically to not be that idiom,
and `test/fix/core_test.cljk`'s `bytes-round-trip-all-256-values` test
exercises every byte value 0..255 on both runtimes to prove it.
