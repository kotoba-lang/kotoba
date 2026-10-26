# ADR-0225 — The guest desktop takes typing: the hosted IME's rules as a kernel object

Date: 2026-09-24

## Status

Accepted, extending ADR-0223 (browser surface as the guest desktop) and
ADR-0224 (text).

**Typing is green only when**
`kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-type`
(`AIUEOS_GUEST_BROWSER=1`) prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_TYPE_OK`:
after ADR-0224's raised text frame, KERNEL.ELF serial has
`AIUEOS_GUEST_BROWSER_TYPE_OK presses=13 committed=5 ops=62 text-px=1052 hash=7caecfe8`.
The host types `n i h o n n g o Enter k a Space Enter` once on a real
virtio-keyboard; the focused window's body gains にほんご加, and the #111111
census equals a model of that frame.

Not executable, and stated here rather than at the end:

- **Not mozc, not a dictionary.** The dictionary is the hosted oracle's three
  readings (か 加可課, ひ 日火, あ 亜). Leftover `:three-reading-dictionary`.
- **The preedit is not drawn.** Composition lives in the IME words and is
  committed on Enter/Space; nothing shows it being typed. Leftover
  `:no-preedit-shown`.
- **No IME toggle key.** The kernel sets IME on; IME-off behaviour is in the
  object and its contract but no key reaches it.
- **Oracle quirks are kept**, not fixed: a lone `n` before a consonant does
  not become ん (`nihongo` commits にほngo; `nihonngo` commits にほんご).
- **Not P5.** QMP key events are a real virtio-keyboard used ring, not a
  laptop keyboard.

## Context

ADR-0224 drew titles and bodies but nothing could change them from a
keyboard. The keyboard driver stopped after its first event (ADR-0093).
`aiueos/compositor/ime.cljk` is the hosted IME -- romaji table, greedy
conversion, sokuon, a tiny dictionary, commit on Enter -- and ADR-0090's
`ime-romaji.kotoba` carries only `ka`.

## Decision

1. **`browser-ime.kotoba`** (`kotoba_aiueos_browser_key(surface, 8192, key-code, value)`)
   mirrors the oracle's `handle-key` branch by branch: letters into the
   romaji buffer and `convert-buf` (greedy 3/2/1-byte mora, sokuon), Backspace,
   Escape, Space (flush, convert or cycle, else commit), Enter (flush and
   commit), IME-off letters straight in, other keys ignored. Committed text
   goes onto the end of the focused window's body -- browser.input's
   `:text/input` target. Linux key codes are mapped in the object.
2. **The romaji table is generated** from the oracle's own `mora` by
   `os/aiueos/scripts/gen-ime-mora.cljk` (`--check`): 113 entries.
3. **State** lives in the frame2 surface, words 432..479. Laying it out found
   a real defect: frame2's scratch (400..415) overlapped window 4's body
   (352..415). Scratch moved to 416..431, ops to word 480 (cap 261);
   `fourth-window-body-reads-all-64` was red on the old layout and is green
   now.
4. **C is mechanism.** The keyboard ring is kept after its first key;
   `aiueos_keyboard_drain` discards what arrived before `TYPE_READY`,
   `aiueos_keyboard_next_press` returns each later press. The QMP injector
   stops its repeated keys at TYPE_READY and types the sequence once at
   TYPE_GO.
5. kotoba-native row `aiueos-browser-key` (arity 4), default fuel tier.

## Consequences

The desktop takes keyboard input end to end: virtio-keyboard → Kotoba IME →
the focused window's body → Kotoba layout → C blit → virtio-gpu scanout.
Leftovers: `:no-preedit-shown`, `:three-reading-dictionary`,
`:no-flow-layout`, `:no-pointer-capture`, browser component migration, P5.

![typed into the focused window](../../docs/assets/guest-browser-typed.png)

## Measurement

**2026-09-24, this Mac, QEMU tcg + OVMF.**

- KIR oracle `browser-ime-v1`: 27 vectors, 98 steps, 69 memory assertions.
  Every key-sequence vector's expected values are the oracle's `handle-key`
  output (committed / buffer / preedit / conversion), including two that end
  mid-composition. Seen red for the named vector: k not a sokuon letter →
  `doubled-k-is-sokuon`; lone n not doubled → `lone-n-flushes-to-n-kana`;
  commits into window 1 → `ka-enter-commits-ka`; candidates reordered →
  `second-space-cycles-candidates`. Fuel: traps at 128, passes at 256.
- `browser-frame2-v1` after the layout fix: 19 vectors, 7 memory assertions.
- `guest-browser-type` (first run): `AIUEOS_COMPOSITOR_GUEST_BROWSER_TYPE_OK`;
  serial `TYPE_READY`, `TYPE_GO keys=13`,
  `AIUEOS_GUEST_BROWSER_TYPE_OK presses=13 committed=5 ops=62 text-px=1052 hash=7caecfe8`;
  the screendump of the display counts the same 1,052 #111111 pixels.
