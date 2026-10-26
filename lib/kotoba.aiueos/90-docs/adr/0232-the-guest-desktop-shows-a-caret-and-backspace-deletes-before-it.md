# ADR-0232 — The guest desktop shows a caret, and Backspace deletes before it

Date: 2026-09-25

## Status

Accepted. Closes the `:caret` floor of the ADR-0226 ladder.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-caret`
(`AIUEOS_GUEST_BROWSER=1`, `AIUEOS_QEMU_TIMEOUT=720`) prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_CARET_OK`: after ADR-0231's event loop
(window 2 focused, に committed, nothing composed), the host sends `k` `a`
and three Backspaces, each after the previous frame line. Serial: five
`AIUEOS_GUEST_BROWSER_CARET_FRAME n=<1..5> ...` lines and
`AIUEOS_GUEST_BROWSER_CARET_OK keys=5 answers=00000 body=13 caret=412,208 chain=fba4ae02 ops=68 text-px=872 hash=5cacb661`.

Not: a caret anywhere but at the end of the text (`:caret-only-at-the-end`
-- nothing moves it yet; arrow keys, Home / End and a click are
browser.input `:text/edit` ops this kernel does not take), blinking
(`:no-caret-blink`), or a selection (`:no-selection`).

## Decision

1. **The caret is a layout decision, so it is in browser-frame2.** After
   the focused window's body and composition, the object emits one rect,
   1 x 16, #111111, where the next glyph would go. That is cssom.layout's
   `sel-ops` for a collapsed selection (`:w 1 :h font-size :color (:fg
   theme)`) with the caret at the end of the text, which is where
   browser.text-edit `insert-text` leaves it. It does not wrap by itself --
   at the right inset it stands in the inset -- and it is not drawn when its
   foot passes the bottom inset, like a glyph. Only the focused window has
   one. C does not draw it; C reads the last op only to print where it is.
2. **Backspace with nothing composed deletes, in browser-ime.** The key
   object takes a conversion, a romaji byte and a preedit code point first,
   as before. With none of them, Backspace now runs browser.text-edit
   `delete-backward` on the focused body with the caret at its end: the last
   code point goes, an empty body stays empty. Bodies hold code points, so
   there is no surrogate pair to keep whole. With the IME off, Backspace
   does the same (the hosted IME bypasses it to the page).
3. **Here the object leaves its IME oracle on purpose.** The hosted
   `aiueos.compositor.ime/handle-key` consumes a Backspace with nothing
   composed and does nothing. browser.input maps Backspace to `:text/edit
   :delete-backward`, and a key the IME has no use for belongs to the page.
   The six new browser-ime-v1 vectors therefore take text-edit, not the
   hosted IME, as their oracle; the contract header says so, and the
   classifier test has a line for the consumed Backspace (`body=14`), which
   is not green.
4. **Every earlier frame changed, and was re-pinned from the model.** A
   focused window is on every desktop frame since ADR-0224, so every
   `frame2` frame gained one op and 16 #111111 px. The model
   (`os/aiueos/scripts/browser-frame-model.cljk`) draws the caret by the
   rule above, written apart from the object, and gives the new answers:
   text 58 / 1100 / 4ab25516, text-raised 58 / 880 / ca6c2709, typed
   63 / 1068 / b741bf74, preedit 67 / 1146 / 04d93a5f and 65 / 1128 /
   e67d620b, ime-toggle 68 / 1205 / f516238a, drag 68 / 1947 / a2969186,
   resize 68 / 1947 / 4fa3baa2, loop chain 1341d966 ending 70 / 906 /
   61ad1f7f. The kernel's constants, the classifier's regexes, the tests
   and the README were moved to them; the QEMU run below measured every one.
   The browser-frame2-v1 success vectors were regenerated the same way: the
   generator first reproduced all thirteen old op lists from their seeds
   with the old model, then eleven changed by exactly the caret (the two
   bottom-cut vectors did not, as rule 1 says).
5. **The caret frames.** `k` (composition k, caret at 452,208), `a` (か,
   460,208), Backspace (preedit dropped; 444,208 -- the same frame as the
   loop's last), Backspace (に deleted; 428,208 -- the same frame as the
   loop's move), Backspace (。 deleted; 412,208). Ops 72 72 70 69 68, chain
   fba4ae02. Each frame must end with the caret op at the model's x and
   y 208, or the kernel counts it off.
6. **No new rows.** browser-frame2 and browser-key keep their arity; the
   contracts pass at fuel 16,384 (frame2, tier 262,144; traps at 12,288)
   and 192 (key, default tier; traps at 128). No kotoba-native row or amu
   pin changes.

## Measurement

**2026-09-25, this Mac, QEMU tcg + OVMF.**

- `guest-browser-caret` (first run): `AIUEOS_COMPOSITOR_GUEST_BROWSER_CARET_OK`,
  leftover `[:caret-only-at-the-end :no-caret-blink :no-selection]`. Every
  re-pinned line before it came out as the model said, in the same boot:
  `TEXT_OK ops=58 text-px=1100 hash=4ab25516`,
  `TEXT_RAISED_OK hit=1 ops=58 text-px=880 hash=ca6c2709`,
  `TYPE_OK ... ops=63 text-px=1068 hash=b741bf74`,
  `PREEDIT_OK shown-ops=67 shown-px=1146 shown-hash=04d93a5f committed=2 ops=65 text-px=1128 hash=e67d620b`,
  `IME_TOGGLE_OK ... ops=68 text-px=1205 hash=f516238a`,
  `DRAG_OK ... ops=68 text-px=1947 hash=a2969186`,
  `RESIZE_OK ... ops=68 text-px=1947 hash=4fa3baa2`,
  `LOOP_OK ... chain=1341d966 ops=70 text-px=906 hash=61ad1f7f idle-min=536`; then
  `CARET_FRAME` 1..5: 72 / 452,208 / 933 / 10db4b13, 72 / 460,208 / 957 /
  c5cd4582, 70 / 444,208 / 906 / 61ad1f7f, 69 / 428,208 / 880 / 56d3e215,
  68 / 412,208 / 872 / 5cacb661, and
  `AIUEOS_GUEST_BROWSER_CARET_OK keys=5 answers=00000 body=13 caret=412,208 chain=fba4ae02 ops=68 text-px=872 hash=5cacb661`.
- Display: `guest-browser-caret-1.ppm` .. `-4.ppm` and `guest-browser-caret.ppm`
  count 933, 957, 906, 880 and 872 #111111 px (6 colours each) -- the memory
  census, frame by frame. On the last, column x 412 is #111111 for y
  208..223 (16 of 16) and x 413 is not; on frame 2 the column is at 460.
  `guest-browser-text.ppm` 1100, `-ime-toggle.ppm` 1205, `-resize.ppm` 1947,
  `-loop.ppm` 906, as re-pinned.
- Seen red in QEMU: browser-ime compiled with the hosted IME's behaviour
  (Backspace with nothing composed consumed), linked by
  `AIUEOS_KOTOBA_BROWSER_IME_OBJECT` with its digest swapped in for that run
  only: frames 4 and 5 stayed at 444,208 / 906 / 61ad1f7f and
  `AIUEOS_GUEST_BROWSER_CARET leftover=census-miss off=2 frames=5 chain=dc982777 body=15 romaji=0 preedit=0`,
  classifier `:census-miss`, exit 1.
- Default profile (no tablet): `guest-browser-frame` green with
  `FRAME_OK ops=5` unchanged, `TEXT_OK ops=58 text-px=1100 hash=4ab25516`
  (the caret, as pinned), and no LOOP or CARET line.
- Contracts (verify-admissions, no JVM): browser-frame2-v1 30 vectors, 15
  memory assertions, reasons -8..-1; browser-ime-v1 40 vectors, 139 steps,
  112 memory assertions. Seen red, each on its named vector: caret before the
  composition -> `composition-ruled-after-the-focused-body`; caret wrapping
  at the inset -> `caret-stands-in-the-right-inset-without-wrapping`;
  IME-off Backspace ignored -> `ime-off-backspace-deletes-before-the-caret`;
  Backspace consumed -> `backspace-with-nothing-composed-deletes-before-the-caret`.
- Objects compiled with amu main f0a4316e: browser-frame2.o 1c732c25,
  browser-ime.o ab404180 (reproduce match=2), digests stale=0.
- Frame model: eight re-pinned scenes reproduced; classifier tests 13 / 180.
