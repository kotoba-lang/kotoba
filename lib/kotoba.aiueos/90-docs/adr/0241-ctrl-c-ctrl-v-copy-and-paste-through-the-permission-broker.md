# ADR-0241 — Ctrl+C / Ctrl+V copy and paste through the permission broker

Date: 2026-09-26

## Status

Accepted. Closes the `:clipboard` floor of the ADR-0226 ladder, extending
ADR-0240 (selection) and ADR-0096 (the guest permission broker).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-clipboard`
(tablet profile, after the selection) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_CLIPBOARD_OK`: the host sent Shift down,
Left down / up three times, Shift up, Ctrl down, C down / up, Ctrl up,
Backspace down / up, Ctrl down, V down / up three times, Ctrl up; C handed
each key, as code * 4 + value, to Kotoba `kotoba_aiueos_browser_key`, asked
Kotoba `kotoba_aiueos_broker_admit` for each request it answered, and handed
the completion only when the broker admitted; all twenty-two
`AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME` lines were printed, and
`AIUEOS_GUEST_BROWSER_CLIPBOARD_OK events=22 requests=4 admitted=3 refused=1 copied=3 pasted=3,3 clip=3 body=51 focus=4 chain=9098b95f sel-chain=356612c5 ops=169 text-px=1080 hash=76577905`.
Every frame's key, answer, broker verdict, completion answer, body length,
selection, clipboard length, op count, #111111 census and #b5cdf1 census is
checked against `os/aiueos/scripts/browser-frame-model.cljk`'s clipboard
frames and the broker's expected verdicts.

Not, and stated here rather than at the end:

- **Text only** (`:text-only-clipboard`). The clipboard is up to 64 code
  points (a body's size); no other format.
- **Only Ctrl+C and Ctrl+V** (`:no-other-ctrl-shortcuts`). With Ctrl held
  every other key does nothing -- Ctrl+A select-all (browser.input) and Ctrl+X
  are not taken, and Shift+arrows with Ctrl held select nothing.
- **Nothing while composing** (`:no-clipboard-in-a-composition`). While
  romaji, a preedit or a conversion is pending, C and V ask for nothing.
- **The stage sets the grant** (`:grant-set-by-the-stage`). broker-admit is
  the same object and ABI as ADR-0096 (`[op granted-op]`); the granted op is
  the stage's -- clipboard for events 1..19, file-picker only (the
  `(1, 2) -> 0` vector) from event 20. No grant store, no user prompt, no
  per-origin grant.
- **The clipboard is the kernel's** (`:no-host-clipboard`). It is a 260-byte
  buffer in KERNEL.ELF; nothing crosses to the QEMU host's clipboard.

## Context

Text could be selected and deleted (ADR-0240) but not moved.
browser.desktop-backend lists `:clipboard/read` and `:clipboard/write` among
its privileged capabilities: `request` produces a host effect only after a
broker decision of `:allow`, and a deny is fail-closed with no effect.
browser.compat's navigator.clipboard readText / writeText are those two
capabilities. ADR-0096 put the broker's decision in a Kotoba object,
broker-admit, but nothing on the kernel desktop asked it.

## Decision

**Who decides what a key asks for: browser-key.** Ctrl (evdev 29 or 97) is
held in surface word 2038 from its press to its release, as Shift is in 2035.
With Ctrl held, a C (46) press over a selection of the focused body, nothing
composed, answers 512 -- a `:clipboard/write` request -- and a V (47) press,
nothing composed, answers 513 -- `:clipboard/read`. Neither changes the
surface. Every other press with Ctrl held changes nothing.

**Who decides whether the clipboard may be touched: broker-admit.** C calls
`kotoba_aiueos_broker_admit(1, granted-op)` for each 512 / 513. On 1 it hands
browser-key the completion; on 0 it hands nothing, so a refused request copies
and pastes nothing -- desktop-backend `request`'s fail-closed deny.

**The completion: the same object, value 3.** A key's value is 0, 1 or 2 from
the device (the keyboard ring passes only these), so value 3 is free: the
completion is the requesting key's code * 4 + 3, with the clipboard -- 260
bytes, word 0 its length L (0..64), words 1..L its code points -- in the place
of the dictionary (five parameters is the native ceiling). A write completion
copies the selection's code points into it (the selection's text, as
browser.text-edit keeps it) and answers k; a read completion is
browser.text-edit `insert-text` of its text: the selection goes and the text
is appended at the caret, the end of the body, whole or not at all (-5), and
answers L. An empty clipboard pastes nothing and keeps the selection. -7
refuses a completion whose clipboard is null, not 260 bytes, or whose length
is past 64. The surface keeps no clipboard state: word 2038 is the only word
taken, and 2039 is the surface's last unassigned word.

**What C does: mechanism.** The new stage after the selection reads the
keyboard ring, hands keys and completions to the object, asks the broker,
presents each frame and counts two colours. C never reads or writes a code
point of the clipboard or the body.

## Verification

Measured 2026-09-26, QEMU tcg + OVMF, tablet profile, `AIUEOS_QEMU_QUIET=600`
(host load ~76). The first boot of these sources reached the stage:

```
AIUEOS_GUEST_BROWSER_CLIPBOARD_GO events=22
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=1 key=169 answer=0 broker=none done=99 body=48 sel=0 clip=0 ops=168 text-px=1058 hash=6ca5ee4a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=2 key=421 answer=0 broker=none done=99 body=48 sel=1 clip=0 ops=167 text-px=1042 hash=a42dfe1a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=3 key=420 answer=0 broker=none done=99 body=48 sel=1 clip=0 ops=167 text-px=1042 hash=a42dfe1a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=4 key=421 answer=0 broker=none done=99 body=48 sel=2 clip=0 ops=168 text-px=1042 hash=a42dfe1a sel-px=106 sel-hash=e0f5b50f
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=5 key=420 answer=0 broker=none done=99 body=48 sel=2 clip=0 ops=168 text-px=1042 hash=a42dfe1a sel-px=106 sel-hash=e0f5b50f
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=6 key=421 answer=0 broker=none done=99 body=48 sel=3 clip=0 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=7 key=420 answer=0 broker=none done=99 body=48 sel=3 clip=0 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=8 key=168 answer=0 broker=none done=99 body=48 sel=3 clip=0 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=9 key=117 answer=0 broker=none done=99 body=48 sel=3 clip=0 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=10 key=185 answer=512 broker=admit done=3 body=48 sel=3 clip=3 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=11 key=184 answer=0 broker=none done=99 body=48 sel=3 clip=3 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=12 key=116 answer=0 broker=none done=99 body=48 sel=3 clip=3 ops=169 text-px=1042 hash=a42dfe1a sel-px=218 sel-hash=c1aab2b2
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=13 key=57 answer=0 broker=none done=99 body=45 sel=0 clip=3 ops=166 text-px=1020 hash=3f2fb2c5 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=14 key=56 answer=0 broker=none done=99 body=45 sel=0 clip=3 ops=166 text-px=1020 hash=3f2fb2c5 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=15 key=117 answer=0 broker=none done=99 body=45 sel=0 clip=3 ops=166 text-px=1020 hash=3f2fb2c5 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=16 key=189 answer=513 broker=admit done=3 body=48 sel=0 clip=3 ops=168 text-px=1058 hash=6ca5ee4a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=17 key=188 answer=0 broker=none done=99 body=48 sel=0 clip=3 ops=168 text-px=1058 hash=6ca5ee4a sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=18 key=189 answer=513 broker=admit done=3 body=51 sel=0 clip=3 ops=169 text-px=1080 hash=76577905 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=19 key=188 answer=0 broker=none done=99 body=51 sel=0 clip=3 ops=169 text-px=1080 hash=76577905 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=20 key=189 answer=513 broker=refuse done=99 body=51 sel=0 clip=3 ops=169 text-px=1080 hash=76577905 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=21 key=188 answer=0 broker=none done=99 body=51 sel=0 clip=3 ops=169 text-px=1080 hash=76577905 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=22 key=116 answer=0 broker=none done=99 body=51 sel=0 clip=3 ops=169 text-px=1080 hash=76577905 sel-px=0 sel-hash=811c9dc5
AIUEOS_GUEST_BROWSER_CLIPBOARD_OK events=22 requests=4 admitted=3 refused=1 copied=3 pasted=3,3 clip=3 body=51 focus=4 chain=9098b95f sel-chain=356612c5 ops=169 text-px=1080 hash=76577905
```

- The same boot: the eighteen other guest-browser classifiers exit 0 on its
  serial (frame .. selection); flow-parity answers exit 3
  `:no-hosted-answer`, as without its hosted answer file.
- The display: the screendumps after frames 1..21 and after the OK line hold
  1058, 1042 x 11, 1020 x 3, 1058 x 2, 1080 x 5 #111111 pixels and
  0 x 3, 106 x 2, 218 x 7, 0 x 10 #b5cdf1 pixels -- the memory census, frame by
  frame -- and 6 colours, 7 while something is selected
  (docs/assets/guest-browser-clipboard.png: frame 18, "19" pasted twice).
- Default profile (no tablet), same sources, `guest-browser-text` exit 0:
  `AIUEOS_GUEST_BROWSER_FRAME_OK ops=5`,
  `AIUEOS_GUEST_BROWSER_TEXT_OK ops=58 text-px=1079 hash=89910f34`,
  `AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=158 text-px=3593 hash=a19f95a8`
  -- unchanged -- and no CLIPBOARD line.
- QEMU red: the same sources linked with origin/main's browser-ime.o
  (`AIUEOS_KOTOBA_BROWSER_IME_OBJECT`, its digest swapped in for that run
  only): C and V were typed as romaji, nothing was asked --
  `AIUEOS_GUEST_BROWSER_CLIPBOARD leftover=census-miss off=13 chain=7137f641 sel-chain=c20c1401 requests=0 admitted=0 clip=0 ctrl=0`,
  classifier `:census-miss`, gate exit 1.
- Contracts in the KIR oracle: browser-ime-v2 120 vectors, 379 steps, 344
  memory assertions, 0 traps -- 26 new, printed by
  `os/aiueos/scripts/browser-clipboard-oracle.cljk` from browser.desktop-backend
  `request` (whether a completion follows) and browser.text-edit
  (`insert-text`, the selection's text) (`--check`: COMPARED 26). The runner
  (`verify-admissions.cljk`) places a 260-byte clipboard after the dictionary
  and takes six-element completion steps.
- Broken four times, each red on the vector that names it: the 64 bound as 65
  (`:a-paste-past-64-is-refused-whole`, 2 for -5); one code point fewer copied
  (`:ctrl-c-admitted-copies-the-selection`, 1 for 2); the composing check
  dropped (`:ctrl-c-while-composing-asks-nothing`, 512 for 0); the length
  bound as 65 (`:a-completion-with-a-length-past-64-is-refused`, -5 for -7).
- Fuel: browser-key traps at 694 and passes at 748 (the 64-code-point
  paste into a 63-code-point body with one selected), under the kotoba-native
  tier 16,384. No kotoba-native row and no amu pin change.
- Provenance: browser-ime.o (sha256 71076aa8...) compiled by amu main
  4977f767, twice, to the same bytes; its receipts are that compile's.
  `sync-kernel-object-digests --check`: scanned=111 stale=0.
- Classifier tests: 21 tests, 295 assertions, 0 failures.

## Consequences

- Text can be moved between places in the focused body, and the broker's
  decision is on the path of every clipboard access the desktop makes.
- Surface word 2039 is the only unassigned word left.
