# ADR-0237 — Alt+Tab focuses and raises the next window

Date: 2026-09-25

## Status

Accepted. Closes the `:focus-cycle` floor of the ADR-0226 ladder, extending
ADR-0223 (frame / pointer input), ADR-0225 (the keyboard through the Kotoba
IME), ADR-0233 (launcher and close) and ADR-0236 (the pointer).

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-focus-cycle`
(tablet profile, after the pointer) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_FOCUS_CYCLE_OK`: the host pressed launcher
button 2 at (150, 14) and released (window 2 opened on top, stack 1 3 2), then
sent Alt down, Tab down / up three times, Alt up and a lone Tab down / up;
for each key C handed code * 4 + value to Kotoba
`kotoba_aiueos_browser_key`; the three Tab presses under Alt answered
256 + the bottom window's id and C handed each id to Kotoba
`kotoba_aiueos_browser_reduce` as a `:window/focus` (kind 5); all twelve
`AIUEOS_GUEST_BROWSER_FOCUS_FRAME` lines were printed, and
`AIUEOS_GUEST_BROWSER_FOCUS_OK events=12 answers=200103020000 wm=3 stack=132 focus=2 bodies=unchanged chain=2254db31 ops=129 text-px=1082 hash=e90ed2bc`.
Every frame's answer, focus, op count and #111111 census (count and FNV-1a)
is checked against `os/aiueos/scripts/browser-frame-model.cljk` and
browser-reduce-v1's `:the-kernel-focus-cycle`; the bodies (surface words
160..415) hash the same after the twelve keys as before them, and Alt, the
romaji and the preedit are empty at the end.

Not, and stated here rather than at the end:

- **The shortcut and its rule are the kernel's**
  (`:kernel-focus-cycle-shortcut`). browser.input maps no key to a
  `:window/focus` -- the hosted desktop has the host's window manager -- so
  there is no oracle for "Alt+Tab" or for "the next window". What the
  shortcut *does* is browser.surface's `focus-window`, and that half is
  checked against browser.surface itself.
- **Left Alt only** (`:left-alt-only`). evdev 56. Right Alt (100) is not the
  modifier; Shift+Alt+Tab does not go backwards.
- **No switcher** (`:no-switcher-overlay`). Each Tab press under Alt focuses
  and raises at once; there is no overlay listing the windows, and releasing
  Alt commits nothing.

## Context

The desktop took a pointer (ADR-0223) and a keyboard through the IME
(ADR-0225), and focus moved only by a press on a window: keyboard-only use
could not change the focused window. The floor asks for a window-manager
shortcut, Alt+Tab (evdev 56 + 15), that focuses and raises the next window in
stack order as a `:window/focus` through browser-reduce, with the key not
reaching the body.

## Decision

**Who decides that Alt+Tab is the window manager's: browser-key.** It is the
kernel's key entry, the place that already decides what every key means (a
letter, Space, the Hankaku/Zenkaku toggle, Backspace). A key is an input
event and its mapping to an action is browser.input's role; browser-key holds
that role for the keyboard. C decides nothing: it reads the ring and forwards
answers.

**Where Alt's state lives: surface word 431.** browser-reduce's 128-byte
state (words 0..31) is full since ADR-0233; the IME's words 432..479 are all
named. frame2's header claimed 416..431 as scratch, but its code uses
416..430 -- 431 was never read or written by any object or by C (grepped:
`sput s 431`, `surface[431]`). It is now browser-key's: 1 while Alt is held,
anything else not held. frame2's header says 416..430.

**What Alt+Tab answers.** Alt's press sets word 431, its release clears it, a
repeat changes nothing; all three answer 0. A Tab press while word 431 is 1
answers 256 + word 5, the id at the bottom of the stack, and changes nothing
else -- no body, no composition, no IME word. 256 cannot be a commit count
(a body holds 64 code points). A Tab without Alt, a Tab release or repeat,
and every other key under Alt go where they went before (the IME ignores Tab;
a letter under Alt composes as without it).

**Why the bottom window.** The stack is bottom first and a raise moves a
window to the top. Raising the bottom window rotates the stack by one, so n
presses visit every window once and come back to the order they started
from. "The window under the top" would only ever swap the top two.

**What the focus does: browser-reduce kind 5.** `:window/focus` of the id in
`a`: focus it and raise it -- the same raise a press does -- and answer the
id. The capture (words 25..30) and the app register (31) are untouched,
because browser.surface `focus-window` does not touch browser.input's state.
An id not in the stack changes nothing and answers 0, focus-window's own
no-op. C calls it with the id browser-key answered, whenever the answer is
above 256.

**Releases.** Every key stage before this read presses only
(`aiueos_keyboard_next_press`). Alt is held from its press to its release, so
the keyboard ring now also hands every key event as code * 4 + value
(`aiueos_keyboard_next_key`, pci.c), the form browser-key has taken since
ADR-0235. The earlier stages are unchanged: they still read presses only.

**The stage.** After the pointer: C hashes the bodies, drains both devices,
prints `FOCUS_GO events=12`, and for each event reduces (tablet) or keys
(keyboard), forwards a window-manager answer to browser-reduce, lays out,
presents, takes the census and folds it into a chain.

## Verification

Measured 2026-09-25, QEMU tcg + OVMF, first run of the tablet profile:

```
AIUEOS_GUEST_BROWSER_FOCUS_GO events=12
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=1 src=1 key=0 key-answer=0 answer=2 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=2 src=4 key=0 key-answer=0 answer=0 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=3 src=0 key=225 key-answer=0 answer=0 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=4 src=0 key=61 key-answer=257 answer=1 focus=1 stack=321 ops=129 text-px=2290 hash=47120e77
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=5 src=0 key=60 key-answer=0 answer=0 focus=1 stack=321 ops=129 text-px=2290 hash=47120e77
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=6 src=0 key=61 key-answer=259 answer=3 focus=3 stack=213 ops=129 text-px=946 hash=c461a68f
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=7 src=0 key=60 key-answer=0 answer=0 focus=3 stack=213 ops=129 text-px=946 hash=c461a68f
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=8 src=0 key=61 key-answer=258 answer=2 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=9 src=0 key=60 key-answer=0 answer=0 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=10 src=0 key=224 key-answer=0 answer=0 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=11 src=0 key=61 key-answer=0 answer=0 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=12 src=0 key=60 key-answer=0 answer=0 focus=2 stack=132 ops=129 text-px=1082 hash=e90ed2bc
AIUEOS_GUEST_BROWSER_FOCUS_OK events=12 answers=200103020000 wm=3 stack=132 focus=2 bodies=unchanged chain=2254db31 ops=129 text-px=1082 hash=e90ed2bc
```

- The same boot: the fourteen other guest-browser classifiers (frame, input,
  text, text-raised, type, preedit, ime-toggle, drag, resize, event-loop,
  caret, launch, dictionary, cursor) exit 0 on its serial; flow-parity
  answers exit 3 `:no-hosted-answer` there as it does without its hosted
  answer file, and the serial carries `AIUEOS_GUEST_BROWSER_FLOW_OK`.
- The display: the screendumps after frames 1..11 and after the OK line hold
  1082, 1082, 1082, 2290, 2290, 946, 946, 1082, 1082, 1082, 1082 and 1082
  #111111 pixels, equal to the memory census frame by frame.
- Default profile (no tablet), same image, `guest-browser-text` exit 0:
  `AIUEOS_GUEST_BROWSER_FRAME_OK ops=5`,
  `AIUEOS_GUEST_BROWSER_TEXT_OK ops=58 text-px=1079 hash=89910f34`,
  `AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=158 text-px=3593 hash=a19f95a8`
  -- unchanged -- and no FOCUS line.
- Contracts in the KIR oracle: browser-reduce-v1 90 vectors, 0 traps, 79
  memory assertions -- 13 new, printed by browser-reduce-oracle.cljk from
  browser.surface (`--check`: COMPARED 79, no DIFFERS); browser-ime-v2 71
  vectors, 232 steps, 0 traps, 216 memory assertions -- 16 new, the rule
  above written apart from the object by a generator that seeds from the
  contract's own `:ka-enter-commits-ka` surface.
- Broken four times, each red on the vector that names it: browser-reduce
  focusing without the raise (`:a-focus-action-raises-the-bottom-of-two`,
  memory mismatch); an unknown id answering the focus instead of 0
  (`:a-focus-action-of-an-unknown-id-changes-nothing`, 2 for 0); browser-key
  answering the focused window instead of the bottom
  (`:alt-tab-answers-256-plus-the-bottom-window`, 258 for 257); Alt's release
  not letting go (`:alt-release-lets-go`, word 431 1 for 0).
- QEMU red: the same image with C dropping browser-key's focus answer instead
  of handing it to browser-reduce --
  `AIUEOS_GUEST_BROWSER_FOCUS leftover=census-miss off=5 wm=3 bodies=unchanged chain=1e19707d focus=2 alt=0`,
  classifier `:census-miss`, gate exit 1.
- The model, with the new stage, reproduces every pinned scene and the
  pointer stage's five frames (chain f4bb42d8) before its new answers are
  used.
- Fuel: browser-key traps at 600 and passes at 640 on
  `:space-without-a-reading-commits-kana`, as before (tier 16,384);
  browser-reduce traps at 64 and passes at 128, under the default 1,024. No
  kotoba-native row and no amu pin change.
- Provenance: browser-reduce.o (sha256 e4497775...) and browser-ime.o
  (2eedb1f3...) compiled by amu main 0a6de52b, twice, to the same bytes;
  their `.o.provenance.edn` / `.o.publication.edn` receipts are that
  compile's; browser-frame2.o's bytes are unchanged (header comment only).
  `sync-kernel-object-digests --check`: scanned=105 stale=0.
- Classifier tests: 18 tests, 253 assertions, 0 failures.

## Consequences

- The keyboard now has a path to the window manager that the page never
  sees; the next shortcut (Shift+Alt+Tab, a close key) is another answer
  above 256 or another reduce kind, not a C table.
- Word 431 is taken; the surface has no unnamed word left below the op area.
