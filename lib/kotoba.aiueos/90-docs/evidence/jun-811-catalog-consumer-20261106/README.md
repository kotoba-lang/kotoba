# JUN-811 / JUN-812: can the desktop list the apps of an admitted AIUECAT1 catalog? (read-only budget check, 2026-11-06)

Result: **no, not in the current surface layout, and no kernel code was changed.** The task said to stop and report the limit if the
draw-op budget or the surface words do not allow the consumer. This file is that report. Everything below was read from source on
main `d3b50df04` (kotoba#1269) and computed by hand; **nothing was built or run for it** (no QEMU, no compiler). The two measured
numbers it starts from (253 and 254 ops, 259 capacity) are ADR-0285 Amendment 4's, taken from the pinned launcher-pages gate.

## Sources read

- `os/aiueos/aiueos/browser_frame2.kotoba`: surface layout (header, lines 55-125), `put-op` (capacity 259), `put-glyph` fold,
  `place`, `lay`, `cp-at`, `chrome-button`, `page-buttons`, `page-arrows`, `launcher`, the register check (-9).
- `os/aiueos/aiueos/session/app_catalog.kotoba` (generated): `app-count` is the constant 18.
- `os/aiueos/native/desktop.kotoba`: every `app-catalog/` use (titles, bodies, `app-count` at the launch and page sites).
- `os/aiueos/native/update.kotoba` and ADR-0286 Amendment 5: the admission leaves flags only; no entry is stored anywhere.
- ADR-0285 (decisions 1-9, Amendments 1-4), ADR-0283.

## 1. Surface words: none are free

The surface is 8192 bytes (words 0..2047) and fully allocated: 0..31 state, 32..159 titles, 160..415 bodies, 416..430 frame2
scratch, 431 Alt, 432..479 the input method, 480..2033 draw ops (259 x 6), 2034..2047 flags/scroll/pointer.
Words 25..29 (the last unused ones) were taken by ADR-0285 for `slot-app` and the launcher page; word 30 by the dapps profile.
The only reclaimable space is **the op list itself**: capacity 259, peak 254 (ADR-0285 Amendment 4) = **5 ops = 30 words**.

## 2. What an installed-apps table needs

Per entry: the verified title is 31 ASCII bytes + NUL = 32 bytes = **8 words** (4 bytes per word); the dock id (19..82) fits in the
otherwise-zero last byte, so it costs no word. Plus one word for the count and the "more than N" flag.

| N entries | words | ops reclaimed (ceil(words/6)) | op capacity left | headroom over the 254 peak |
|---|---|---|---|---|
| 1 | 9 | 2 | 257 | 3 |
| 2 | 17 | 3 | 256 | 2 |
| 3 | 25 | 5 | 254 | 0 |
| 4 | 33 | 6 | 253 | below the existing peak |

So the table is limited to **N = 3 entries with zero headroom**, before any drawing is added. (A table kept outside the surface needs
a second region in `chrome-button`, which already has the maximum 5 arguments, or a separate drawer; ADR-0285 Amendment 1 measured a
dedicated drawer at 6.1 KiB of kernel text, which the 2.5 MiB cap now affords, but it does not change the op budget below.)

## 3. Draw ops: a page of installed apps overflows the list

A launcher button is 1 op (`glass-fill`, kind 4) plus its label. `place` draws every code point including U+0020, the pairs fold
(kind 3), and the label stops at the right limit `x + 90` (glyphs of 8 px from `x + 6`, so **10 glyphs**). A label costs
ceil(glyphs/2) ops, at most **5**.

| page | label ops | + 8 fills | total |
|---|---|---|---|
| page 0 (Murakumo .. Saifu) | 4+4+5+3+4+3+3+3 = 29 | 8 | 37 |
| page 1 (Bunsho .. "Itonami Ap") | 3+5+3+3+3+5+3+5 = 30 | 8 | 38 |
| worst possible, all titles of 9+ glyphs | 8 x 5 = 40 | 8 | 48 |

ADR-0285 Amendment 4's 253 (page 0, four windows) and 254 (maximum, page 1) imply the rest of the frame is **216 ops** (254 - 38,
including the two arrow buttons). A page that holds eight installed apps with 9+ glyph titles is therefore **216 + 48 = 264 ops,
5 over the 259 capacity**: `put-op` drops the excess, sets word 427, and the frame returns -5. Page 2 of an 18-app list plus catalog
entries (Updates, Torihiki and six installed) is the first such page. Titles are only constrained to 1..31 printable ASCII bytes by
admission, so 9+ glyph titles are legal.

Clipping installed labels to 8 glyphs would give 216 + 8 x 5 = 256, which fits 259, but it leaves 3 ops, and combined with section 2
(N = 2 already costs 3 ops of capacity) it leaves **0**. 6 glyphs gives 248. Either is a display truncation of a verified title that
nobody has decided on.

## 4. What ADR-0285's paging implies

- Paging is by `perPage` (at most 8) over `app-count`; every extra entry only adds pages, so pages beyond page 1 hold installed
  apps and each can be a full 8-button page. The measured headroom (5 ops) was for built-in titles, not for arbitrary ones.
- `app-count` is a compiled constant (18) read at 10+ sites in frame2 and desktop; a consumer makes it a runtime value (18 + N).
- `launcher` refuses a frame whose register word 31 is `>= pow2(app-count, 1)` (reason -9). With `app-count` at 64 or more `pow2`
  reaches 2^64; if the kernel's i64 multiply wraps (not checked here) the check is always true and every frame is refused. Decision 7
  of ADR-0285 ("word 31 stays launcher present when not 0") would need the check changed first.
- Window ids stay slot ids 1..4 (decision 1), so launching installed app 19+ reuses the slot rules: it needs a body (apps 5..18 share a
  catalog line; an installed app has none) and a title copy from the table into a slot title.

## 5. What would make it fit (decisions for the owner, not taken here)

1. Shrink the op list on purpose and clip installed labels: N = 2, label limit 8 glyphs, 0 ops of headroom. Possible, but every
   later launcher or window feature then has no room, and the gate would have to pin 256.
2. Free surface words elsewhere: the input method's 32 preedit words (446..477) are the only block of that size, and are in use.
3. Keep the table and the label drawing outside the surface: a second region reaching `chrome-button` (needs a call-site and
   signature redesign, since 5 arguments is the limit) and a label clip, still within 259.
4. Page the *draw*, not just the list: draw only the installed labels of the visible page from a smaller per-page op allowance.

Recommended: 3 with a clip of 8 glyphs; it is the only variant whose cost is paid in kernel text (which has 574,752 B of margin),
not in op budget.

## Not verified

No build, no QEMU run, no ops counted in a running kernel: sections 2-3 are arithmetic over source. In particular the 216-op rest of
the frame is derived from the ADR's two measured numbers (254 peak on the page-1 layout), not measured, and the i64-wrap claim in
section 4 is unchecked against the compiler. A mutant or measured run would be the first step of option 1 or 3.

## Doc/code mismatches found

- ADR-0285 decision 4 gives `perPage = clamp((vw - 62) / 102, 1, 8)`; the code (`page-size`) uses the Amendment 1 formula
  (`vw - 6 - 56 - 112` at 640 and up). Amendment 1 already says it replaces decision 4; the decision text was not edited.
- ADR-0285 "Not decided here" still says a signed catalog (option B) is separate; ADR-0286 Amendment 5 now defines it, and
  `update.kotoba` admits it, but nothing consumes it (as Amendment 5 itself says).
