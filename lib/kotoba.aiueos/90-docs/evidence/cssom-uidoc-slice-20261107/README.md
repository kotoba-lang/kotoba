# CSSOM UI-document front end: a compact UI document in a region becomes the style slice's input (JUN-856 / ADR-0287)

Date: 2026-11-07. Branch `claude/jun-856-ui-document`, from main `48540338e` (after #1279). Source, an independent host reference, a QEMU profile and a gate.
Nothing is wired into `browser.surface`, nothing runs in a CPL3 domain, nothing was merged or deployed.
Tags: **[M]** measured (a command ran, output in `measurements.json`), **[R]** read from source.

## What the slice is

ADR-0287 fixes the interface: UI document and events in, draw list out, through shared regions. The style, layout and draw slices existed; their input was the
"style wire stream" (rules then elements, `style_k_cases.py` `encode`) that gates loaded byte by byte. `src/cssom/uidoc_k.kotoba` (`cssom.uidoc-k`, `ud-run`,
`ud-word`) is the front end that turns a UI document in a region into that stream, so the chain **document -> style -> layout -> draw list** runs on the
documents of the dapp windows. Style, layout and draw are unchanged.

## The encoding (a PROPOSAL, not an accepted layout; ADR-0287 still lists the region layouts open)

The document sits in the two free pages 13 and 14 of the owned window (53248..61439, 8192 bytes), the pages the draw list reuses afterwards, as a stand-in for the
read-only UI-document region of ADR-0287. The output is the wire stream at 0..16383. Little endian.

| offset | content |
|---|---|
| 0 | magic `UID1` |
| 4, 6, 8, 10 | u16 S sheet bytes, N strings (<= 255), G string-table bytes, T tree bytes; `12 + S + G + T` must equal the document length (<= 8192) |
| 12 | sheet: the wire rule records (`R origin selector-length selector declaration-count declaration*`) without the terminator; selector_k validates them |
| 12+S | string table: N entries, u8 length (1..255) and bytes; 1-based index; tags, ids and class lists are entries, a repeated string is stored once |
| 12+S+G | tree ops: `0x00` close; `0x80\|f` open (f: 1 has id, 2 has class list) with u8 tag, u8 id if f&1, u8 class if f&2; `0x40` u16 len a text node placeholder |

A text placeholder emits nothing (the style slice has no text) and is counted (`ud-word` 2, 3: nodes and bytes); the length is the UTF-8 length of the stripped text.
The tree is one balanced element tree, text only inside it. Statuses (negative): -30 header (window, length, magic, section sum, N > 255), -31 string table not exactly
G bytes of non-empty entries, -32 unknown op or operands past the tree, -33 string index 0 or past N, -34 the stream would pass 16384 bytes, -35 unbalanced tree or text
outside an element. The first fault in tree order wins; inside an open op truncation (-32) is checked before the indices (-33). Not carried: the `style` attribute,
any attribute but `id` and `class`, text content, `hidden` (the host encoder emits the opened window), entities, comments. **No dapp window has a `style` attribute [M]**
(the encoder reads the 18 windows of `index.html`; the attribute set seen is aria-*, class, data-*, href, id, type, name, value, role and a few input attributes), so the
style attribute is out of this slice, not approximated: the cascade does not model inline style (cascade_k header), and lowering it to a generated rule would change specificity.

Honest size note [M]: the sheet is carried verbatim and the string table repeats the names, so a small document is not smaller than its wire stream (tokei 1,639 bytes
against 1,612); a large one is (torihiki 2,678 against 3,215). Where it wins is a shared string: a 255-byte class used by 79 elements costs 3 bytes per use
(`uidoc-wire-16384-bytes`: 679-byte document, 16,384-byte stream). It is a defined region boundary and a place for text placeholders, not a compression scheme.

## Documents and sheet

The 18 dapp windows (murakumo ... torihiki) are read as data from the checked-in `resources/aiueos/session/index.html` (the generated page; `ui.document` of the dapp
records) by `uidoc_k_cases.py` (element, id, class, text lengths; 13 to 105 elements, depth <= 11). Their sheet is **not** the page's stylesheet: the page uses `var()`, shorthands, flex and grid,
which the style/layout slices refuse or do not model, and a sheet may name at most 16 properties. `dapp_sheet()` keeps the real selectors of the window frame
(`.app-window`, `-head`, `-body`, `.window-close`, `.dds-ext-card`, `.session-out`, `.app-return`, `.app-empty-state`) with their resolved values (spacing N x 4 px, colours from
`:root`) and `* {display:block}`. Left out for the 16-property limit or because they are not block flow: `margin-bottom` of the window, the close button's `width`, `min-height` (written as
`height`), flex of the head, `border-radius`, shadow, fonts. So this shows that the chain runs on the dapp documents; it is **not** a claim that the native render equals the page.

## Gate [M]

`lib/kotoba.cssom/scripts/check-uidoc-k-native-macos.py` (native macOS Amu `e13a2054...` / `amu-full-root` `88623412...`, QEMU TCG, profile `uidoc`, observer
`os/aiueos/scripts/check-native-uidoc-qemu.py`, entry `os/aiueos/native/uidoc-entry.kotoba`), receipt `measurements.json`, status `PASS_NATIVE_CSSOM_UIDOC_K`.

* 202 cases (`scripts/uidoc_k_cases.py`): the tokei window with a hand-derived box table and draw list (21 ops, px written out from the CSS rules and CSS 2.1 block flow; the
  reference reproduces it before the kernel is looked at, and the kernel box table and list equal it), the 18 dapp windows (13 to 105 elements; all run the whole chain, layout
  and draw status 0, 10 to 28 ops each), the component trees of `ui_components_test.kotoba` with block sheets, hand cases (ids, class lists, string reuse, text placeholders, depth 32/33,
  128/129 elements, 255 strings, a 255-byte string, document 8192/8193 bytes, stream 16,384/16,385/over-long bytes, an empty tree, a malformed sheet and two roots passed through), 29 front-end
  refusals with hand-written statuses (-30 x7, -31 x4, -32 x6, -33 x5, -34 x2, -35 x5) and 40 seeded random documents with text placeholders. 173 documents expand; 884 draw ops; every role seen.
* Per case the kernel runs the expanded stream (path A) and the canonical wire stream (path B, the existing input of the draw gate) through the same style/layout/draw code. The observer checks
  from the host: the front-end status against `ref_expand`; the text counts; the stream byte for byte against the reference and the canonical stream; A equals B in every field (layout status,
  element count, box table, draw status, every op: 173 of 173); the draw list against the draw reference on the kernel's own box table. Layout refusals that pass through unchanged (depth 33 -11,
  129 elements -3, malformed sheet and two roots -1) are the style slice's, equal on both paths.
* Negative controls: 20 one-line mutants of `uidoc_k.kotoba`, each rebuilt into a kernel and run; all seen. 18 end `FAIL_NATIVE_UIDOC_K_QEMU` (1 to 196 cases differ). **Two are seen only because the
  guest stops** (the over-long-stream cases write past the window or accept a stream the window cannot hold; no receipt, killed after 480 s): the gate counts that as seen, but it is a weaker
  signal than a differing case. Mutants that cannot change a status (an element-size miscount, a limit one byte high in the open op, which the close checks catch anyway) were tried and dropped as equivalent.
* The reference is Python, not a native Amu program. `kernel-load-u32-4k` and the other region forms are refused by `x86_64-aiueos-user-v1` (E2101), as for the other slices.

## Size [M]

* kernel-v1 text of `uidoc_k` alone: 19,297 bytes (79 code lines, 244 bytes per line). Layout + draw closure in one object 226,563; with `uidoc_k` 243,088.
* Whole kernel-v3 image, `uidoc` profile: **3,007,744** text bytes against 2,974,208 for the `draw` profile built in the same run: **+33,536** (module plus the entry's glue: two PATH dumps, the
  stream dump, the document loader), 64 modules. Estimated margin under the compiler cap 3,080,192 (not changed): **82,848**. It fits; the `draw` image alone left 116,384. The `desktop` profile does not link cssom, so the
  figure for the shipping desktop was not measured here.

## Found on the way

* **Page CSS and its own variables disagree (read, not tested in a browser).** `index.html` defines `--hig-hairline` as a colour (`var(--color-neutral-solid-gray-300)`) but writes `border: var(--hig-hairline,1px) solid ...`
  in `.app-window`, `.app-window-head`, `.window-close`, `.session-out` and others (`:root` at line 2665; rules from 2693). A colour where a width is expected makes that declaration invalid at computed-value time, so
  those borders probably do not draw in a browser. The subset sheet uses 1 px. Reported, not changed: the page is a generated artifact (`scripts/session-page.py`).
* The sheet limit of 16 distinct properties is the first thing the real window frame hits (18 would be needed).
* `index.html` windows carry `hidden`; the host encoder drops it. A first parse of the page by regex stopped at the first `</section>` and undercounted torihiki (85 instead of 105 elements: it has nested sections).

## Out of scope

Text and images (placeholders only), the `style` attribute, other attributes, events, the real region mapping and a CPL3 domain (JUN-919), the compositor's own op encoding, `browser.surface`, flex/grid in the chain
(`flow_k` is block flow only; `flex_k`/`grid_k` are not wired into `fk-run`), UA stylesheet and `hidden`, the page's real stylesheet.

## Re-run

`python3 -I lib/kotoba.cssom/scripts/check-uidoc-k-native-macos.py --amu ... --amu-full-root ... --amu-source ... --owner-repo-root /Users/junkawasaki/github/kotoba-lang --qemu ... --qemu-sha256 ... --firmware ... --firmware-sha256 ... --output NEW`
(about 25 minutes with mutants; `--reuse-baseline DIR`, `--reuse-draw DIR`, `--skip-mutants`). Profile alone: `build-native-desktop-macos.py --profile uidoc` (about one minute). Run on the tree merged with main `48540338e`.
