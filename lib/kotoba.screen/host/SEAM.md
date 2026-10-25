# Host seam — the contract between the host and the screen guest

The guest (this library, compiled by amu) and the host (a desktop resident,
a browser, an OS process) meet at exactly two operations. The host owns the
authority; the guest owns the judgment. This file is the promise each side
makes, so neither has to guess.

## observe — `:screen/observe`, wire id 31

Host promise:

1. The request is the guest's small integer (which screen/window; 0 = the
   default surface). The host may refuse any request; a refusal is digest 0.
2. The answer carries a tree digest (i64, the host's own content hash) and
   the flattened rows: parallel sequences of ref-ids and role-codes,
   delivered as the legacy i64 pair chain (terminated by 0, walked with
   pair-first/pair-second).
3. digest 0 means "nothing readable" — no OCR text, or a refused capture.
   A digest of 0 is never a digest of real content.
4. ref-id 0 is NOT-FOUND and is never a real node. Real ref-ids start at 1.
5. role-code is a small integer from the host's role vocabulary in [1, 64].
   The guest's quota checks assume this bound; a host that hands an
   unbounded integer has handed the guest a value the guest will refuse.

Guest promise:

1. The guest never asks for raw pixels. The host digests; the guest
   compares digests. Screen bytes never cross the capability boundary.
2. The guest quotes the digest on every later operation. A stale digest is
   the host's currency check, not the guest's.

## act — `:screen/act`, wire id 32

Host promise:

1. Before EVERY effect, re-validate the expect digest the operation quotes.
   If the tree changed since the guest read it, refuse — that refusal is
   the currency check and it happens host-side, last.
2. The host enforces its own bounds (text length, ref existence, quota)
   regardless of what the guest checked. The guest's checks are shape;
   the host's are authority. Both run.
3. Every effect produces a receipt the host can audit. No receipt, no
   admission next time.

Guest promise:

1. The guest runs shape checks (screen.intent) BEFORE spending an act
   grant: ref-id >= 1, expect digest non-empty, text <= 4096 bytes.
   A guest that fails shape does not burn a capability, a quota tick,
   or an approval card.
2. The guest never synthesizes a digest it did not receive from observe.
3. The guest does not declare `:screen/act` unless it actually issues
   host act operations through its own code — the compiler refuses unused
   capability declarations, and that refusal is load-bearing.

## Why observe and act are separate capabilities

A guest that may SEE a screen has not thereby been allowed to press
anything on it. The split is the same one `:stream/accept` and
`:stream/send` make: hearing is not speaking. A read-only summarizer
(chronicle-style context feed) takes observe only. An operator with a
human approval card takes both, and the approval card gates the host's
act admission, not the guest's judgment.
