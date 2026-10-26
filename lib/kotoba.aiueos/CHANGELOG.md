# Changelog

All notable changes to **aiueos** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); this crate is pre-1.0 (Phase-0).

## [Unreleased]

### power: suspend to idle and resume (ADR-0273)
- The sleep key blanks the screen and idles the machine in HLT; the wake key redraws the desktop from the same surface. The host's screendumps
  (black while asleep, byte-identical awake before and after) and the measured resume time gate it as `guest-browser-suspend`.

### audio: a virtio-sound driver and a volume key (ADR-0272)
- A polled virtio-sound output driver (guest-browser build) plays a 440 Hz burst at a volume held in C; the volume-down key lowers it; QEMU's WAV
  output is measured on the host (two 440 Hz bursts, the second at half the level). `guest-browser-audio` gates it.

### storage: backup and restore of the user's records (ADR-0271)
- A four-sector door (1034..1037) and a stage that copies the settings and passkey records to backup sectors, wipes the originals, restores
  them and checks them byte for byte (SHA-256), the settings and the key's public point. `guest-browser-backup` gates it.

### desktop: a device-bound passkey opens the lock (ADR-0270)
- A P-256 device key (from the virtio-rng, kept with its public point in sector 1035) signs a fresh challenge on the lock screen and the
  signature is verified against the registered public point; F4 is this device's passkey (the session opens), F3 a passkey of another
  device (refused). `guest-browser-passkey` checks the ceremony and the ten frames against the frame model.

### desktop: the settings window (ADR-0269)
- Window 2 is the settings app (Contrast / Scale / Network), opened from launcher button 2 and rebuilt after every key; a press on its Contrast / Scale / Network lines changes that setting (F10, Ctrl+= and F5 still do); F5 flips the
  network setting (a flag the settings stage holds), which the status area follows (OFFLINE while it is off). The settings record keeps all three across a
  reboot. `guest-browser-settings` attaches a NIC and checks both boots' frames against the frame model.

### desktop: notifications, toasts and a list (ADR-0268)
- Surface words 1971..2003 carry four notification entries and a list flag; browser-frame2 draws toasts (or the list) above the windows;
  F8 dismisses the newest toast, F7 opens and closes the list, a dismissed notification stays listed. `guest-browser-notify` raises two,
  dismisses and lists them, every frame checked against the frame model.

### desktop: keyboard layouts US and JIS (ADR-0267)
- F9 flips surface word 1970 between US and JIS; with the input method off the digit row and punctuation keys type, Shift picks the
  second character of a key and makes letters upper case. `guest-browser-layout` types the same physical keys on both layouts and
  checks every frame against the frame model.

### desktop: the launcher row shows the network state (ADR-0266)
- Surface word 1969 carries OFFLINE / LINK / ONLINE from the boot's own virtio-net ARP and ICMP exchange (which runs before the
  desktop stages, contrary to ADR-0264); browser-frame2 draws it left of the clock. `guest-browser-clock` now attaches a SLIRP NIC
  and checks the third frame (ONLINE) against the frame model. Power is still not reported.

### desktop: the UI scale survives a reboot (ADR-0265)
- The settings record's reserved word now carries the scale (0 = 100); the settings stage applies a stored scale before its first
  frame and writes when contrast or scale changed. `guest-browser-settings` sends F10 and Ctrl+= on the first boot (six keys) and
  checks the second boot of the same volume draws the 125 % high-contrast frame from the record alone. Scorecard C8 stays partial
  (no settings window, no network setting).

### desktop: the launcher row shows the clock (ADR-0264)
- C reads the CMOS real-time clock and reports the minute of the day (surface word 1968); browser-frame2 draws HH:MM at the right end
  of the launcher row. `guest-browser-clock` gates it. The op capacity is 248 (words 1968..2003 free). Power and network states are not
  yet reported.

### desktop: the caret is an index and text editing follows it (ADR-0263)
- Insertion, Backspace, Delete and paste happen at the caret; Left / Right, Home / End, Ctrl+Left / Right (by word),
  Shift extending a selection between the anchor and the caret, and Ctrl+Z (undo the last edit) work; Space and Enter
  insert in English mode. `guest-browser-text-edit` gates it against a model of the rules written apart from the Kotoba.

### desktop: every shell control is reachable and activatable from the keyboard (ADR-0262)
- The focus ring (F6) now has eleven targets: launcher buttons, the focused window\'s close, maximize and minimize controls and
  the tray\'s buttons; Enter presses the one it is on through the same path as the pointer. `guest-browser-keyboard-only` gates it.

### desktop: a UI scale of 100/125/150 percent (ADR-0261)
- Ctrl+= and Ctrl+- choose the scale (Kotoba); C magnifies what it paints and sets the logical viewport; Kotoba fits the
  windows into it. `guest-browser-ui-scale` gates it with a model that paints the scale as the present does. The op
  capacity is 254 (words 2004..2009 are free; 2009 is the scale).

### desktop: the contrast choice survives a reboot (ADR-0260)
- A settings record (sector 1034 of the object-store volume, readback on write) holds the high-contrast choice;
  `guest-browser-settings` boots the same volume twice to prove it. The first persistent write the desktop makes.

### desktop: signing out zeroes the session (ADR-0259)
- Ctrl+Alt+Q zeroes the session words, leaves one fresh window 1 and locks; the PIN signs in to the clean session.
  `guest-browser-sign-out` gates it (16 more events) and reads the zeroed words back.

### desktop: the screen locks and a PIN unlocks it (ADR-0258)
- Ctrl+Alt+L locks: only the lock screen is drawn, pointer and keys are swallowed; a four-digit PIN (SHA-256 checked by C against
  the test PIN\'s hash) unlocks and the session is as it was. `guest-browser-screen-lock` gates it (30 more events).

### scorecard: the owner's VM is the reference; ten rows pass by receipt (17%)
- Reference = the owner's Mac VM (QEMU + UEFI), counted as :device-level evidence when a receipt is kept
  (`scripts/vm-receipt.cljk`, `os/aiueos/qualification/receipts/vm-20261023/`). C1 C2 C3 C4 D1 D2 D4 D7 G4 I5 are :pass;
  the checker refuses a :pass without a readable receipt with green verdicts. Expected behaviours not re-measured in a ChromeOS VM.

### desktop: the close control of the only visible window is disabled (ADR-0257)
- browser-frame2 draws it greyed and never hot; the refused press is measured. `guest-browser-minimize` is 26 events.

### desktop: Alt+- minimizes the focused window (ADR-0256)
- browser-ime answers the minimize control's press for Alt+- when the control exists; the same action path as the pointer.
  `guest-browser-minimize` grew to sixteen events.

### desktop: a tray of minimized windows (ADR-0255)
- While a window is minimized, a titled 120 x 24 button per minimized window sits bottom left;
  a press restores it (browser-reduce `tray-at`, browser-frame2 `tray`). `guest-browser-minimize`
  grew from six to ten events. Scorecard C5 stays partial: the list holds minimized windows only.

### desktop: minimize and restore from the dock (ADR-0254)
- A minimize control in the titlebar (left of maximize) marks the window in the minimized register
  (surface word 31 bits 4..7): it is neither drawn nor hit, the focus goes to the topmost visible window,
  and a press on its dock icon restores it raised and focused. Decided by Kotoba (browser-reduce,
  browser-frame2, browser-ime for Alt+Tab). `guest-browser-minimize` gates it on QEMU; ladder 32 floors,
  30 gated. Every earlier frame's op count grew by the control's two rects (ink census unchanged).

### JUN-34: a blank block volume formats itself at first boot (OCI needs no helper VM)
- The object-store probe rejected any second virtio-blk disk whose sector 0
  was not a valid AIUEFS1 superblock, so an OCI block volume -- which arrives
  zeroed -- stopped the boot at `AIUEOS_VIRTIO_BLK_FAIL capacity-or-read`
  (measured: `pci_result input-rng-base=010`, 2 runs). A disk whose sector 0
  is ALL ZERO is now recognized as blank and provisioned in place: the
  catalog is reconstructed byte for byte as `scripts/make-aiuefs-image.py`
  builds it and the carried `recovery/app-catalog.sig` must verify over those
  exact bytes, and the carried app signature must verify over the recovery
  ELF, before a single sector is written. Every sector is read back and
  compared; the superblock is written last, so a crash mid-format leaves a
  blank volume that the next boot formats again. The volume then rejoins the
  ordinary admission path, which re-verifies everything from disk. Measured
  on a zeroed 50 GiB disk (the OCI block volume minimum) in the OCI dual
  virtio-blk topology: `AIUEOS_OBJECT_STORE_FORMAT_OK blank-volume
  source=initramfs catalog=rsa2048 write-readback`, full desktop boot with
  sustained input (14 keys, ring n=31), 0 FAIL markers. A pre-populated
  AIUEFS1 volume boots exactly as before (98 markers, no format marker).
  Anything not all zero -- the GPT boot disk's protective MBR, a foreign
  filesystem -- is still simply not ours.

### JUN-34: the persistent desktop pumps the key ring; the ring counter counts once
- The desktop loop's keyboard section called `aiueos_keyboard_drain` every turn,
  and drain DISCARDS: every key that arrived between turns was thrown away
  (measured 2026-10-23: `AIUEOS_DESKTOP_KEY` 1, `AIUEOS_INPUT_RING` n=1, while
  the host virtio ring showed 103 used entries, all reposted). It now takes
  `aiueos_keyboard_take_key()` -- one non-blocking reap per turn as evdev
  code * 4 + value, the form Kotoba browser-key takes. No live ring (the
  synthetic smoke build) falls back to the boot probe's mailbox.
- The virtio-input boot probe no longer counts ring entries: it peeks
  (`kbd_seen` stays 0) and `kbd_recycle` reaps and counts what it saw, so the
  counter lives at the reap and only there -- the double count of ring slot 0
  is gone. Measured after: `AIUEOS_DESKTOP_KEY` 120 (press/release in ring
  order), `AIUEOS_INPUT_RING` n=180 = 60 injected batches of
  [press + release + SYN], each used entry counted exactly once.

### Guest browser desktop: a frame sends only the rectangle that changed (ADR-0242)
- browser-damage.kotoba (`kotoba_aiueos_browser_damage`) compares the list just
  painted with the previous one (kept in the caller's 8,192-byte shadow) and
  answers the bounding box of every op at a slot where the two differ; nothing
  when they are the same; the whole viewport after no list.
- framebuffer.c / pci.c send that rectangle with virtio-gpu
  TRANSFER_TO_HOST_2D / RESOURCE_FLUSH, or nothing; anything the object did not
  answer for sends the whole screen.
- Gate `guest-browser-damage` (tablet profile, 3300 s):
  `AIUEOS_GUEST_BROWSER_DAMAGE_OK events=5 partial=2 empty=3 bytes=1870144 whole-bytes=20480000 focus=1 chain=6653b143 ops=211 text-px=2330 hash=5581e21a`,
  and every damage screendump byte-identical to the whole-screen one after it.
  browser-damage-v1 24 vectors (browser-damage-oracle.cljk).

### Guest browser desktop: Ctrl+C / Ctrl+V through the permission broker (ADR-0241)
- browser-ime.kotoba holds Ctrl (evdev 29 / 97) in surface word 2038. With it
  held, C over a selection answers 512 (a `:clipboard/write` request) and V
  answers 513 (`:clipboard/read`); neither changes anything. The admitted
  request's completion is the same code with value 3 and the clipboard (260
  bytes: a length word, 64 code points) in place of the dictionary: a write
  copies the selection's text, a read is `insert-text` of the clipboard's text
  (whole or -5). -7 refuses a completion's clipboard. Every other Ctrl
  shortcut does nothing, and nothing is asked while something is composed.
- main.c's new stage after the selection: C asks `kotoba_aiueos_broker_admit`
  (ADR-0096) for each request with the stage's grant (clipboard, then
  file-picker only) and hands the completion only on admit.
- Gate `guest-browser-clipboard` (tablet profile, 3000 s):
  `AIUEOS_GUEST_BROWSER_CLIPBOARD_OK events=22 requests=4 admitted=3 refused=1 copied=3 pasted=3,3 clip=3 body=51 focus=4 chain=9098b95f sel-chain=356612c5 ops=210 text-px=1080 hash=76577905`.
  browser-ime-v2 120 vectors (26 new, from browser.desktop-backend `request`
  and browser.text-edit via browser-clipboard-oracle.cljk).

### Guest browser desktop: Shift+Left / Shift+Right select, Backspace deletes the selection (ADR-0240)
- browser-ime.kotoba holds Shift (evdev 42 / 54) in surface word 2035 and takes
  Shift+Left / Shift+Right as browser.text-edit `move-caret` with `:extend?` on
  the focused body: the selection is the last k code points (word 2036 the
  window id, 2037 k), clamped to the body. Backspace deletes a selection
  (`delete-backward`), and a letter replaces it (`insert-text`; with the IME on
  the composition starts over the emptied place). The arrows do nothing while
  something is composed; plain arrows are still not taken.
- browser-frame2.kotoba draws a #b5cdf1 rect (cssom sel-ops'
  rgba(70,130,220,0.4) over #ffffff) behind each selected glyph of the focused
  body and no caret while something is selected. The op capacity is 259
  (words 480..2033); 2034 is its scratch.
- main.c's new stage after the wheel: five notches (offset 100), Shift, Left,
  Left, Right, Left, Shift up, Backspace; each frame's #111111 and #b5cdf1
  census against browser-frame-model.cljk.
- Gate `guest-browser-selection` (tablet profile, 2700 s):
  `AIUEOS_GUEST_BROWSER_SELECTION_OK events=17 answers=44444000000000000 max-sel=2 body=48 focus=4 scroll=100 chain=2b46197d sel-chain=cb830579 ops=209 text-px=1058 hash=6ca5ee4a`.
  browser-ime-v2 94 vectors (23 new, from browser.text-edit via
  browser-selection-oracle.cljk), browser-frame2-v1 74 (11 new).

### Guest browser desktop: the wheel scrolls the window under the pointer (ADR-0238)
- browser-reduce.kotoba takes a wheel notch at the pointer as kind 6 (toward
  the end, +20 px) or 7 (toward the start, -20): the window under it --
  window-at, as a press hits -- scrolls, clamped at 0, with no focus, raise or
  capture change (browser.input `:pointer/wheel` -> browser.surface
  `scroll-window`); a miss answers 0. The offsets are surface words
  2040..2043 (window id 1..4), so reduce now also takes the whole 8192-byte
  surface (-10 on 128 bytes for a wheel; -11 a hit id outside 1..4; -12 past
  65535). With the surface, a close zeroes the closed window's offset.
- browser-frame2.kotoba draws each window's body, composition and caret the
  offset higher, laid out unscrolled, and cuts them at the top inset (y + 36)
  as at the bottom; -11 for an offset past 65535. The op capacity is 260
  (words 480..2039); 2044..2045 are its scratch.
- pci.c turns a REL_WHEEL batch (or a BTN_GEAR press) into tablet kind 6 / 7;
  main.c's new stage after Alt+Tab registers app 4 (the lines 1 .. 20) and
  takes seventeen events: offset 0 -> 120 -> 0.
- Gate `guest-browser-scroll` (tablet profile, 2400 s):
  `AIUEOS_GUEST_BROWSER_SCROLL_OK events=17 answers=40004444444444444 max=120 stack=1324 focus=4 scroll=0 chain=7421f3aa ops=205 text-px=994 hash=78270fda`.
  browser-reduce-v1 115 vectors (25 new), browser-frame2-v1 63 (13 new).
### sync-kernel-object-digests reads build-multiboot.sh too
- The re-attest above left two literals stale in `build-multiboot.sh`
  (`acpi-checksum-ok.o`, `acpi-table-valid.o`); `--check` read only
  `build-uefi.sh` and reported OK, and the Multiboot boot failed closed in CI.
  The gate now scans every script that pins a digest (111 slots in 2 scripts)
  and names the script on each STALE line; both literals are synced and
  `smoke-qemu-multiboot.sh` passes.

### Kernel objects re-attested with one amu
- `reproduce-kotoba-objects.cljk --attest` with amu `53799cb` compiled all 115
  committed Kotoba objects and rewrote the 68 whose bytes changed; 46 were
  recorded against an older amu and 1 (`install-intent-admit.o`) had no
  recorded compiler. A strict rerun matches 115/115.
- `provenance.edn` regenerated (`--emit-provenance`: 115 recorded, 0
  unrecorded); `sync-kernel-object-digests.cljk --write` rewrote 59 stale
  digest pins in `build-uefi.sh` (`--check` then exit 0).
- All 24 guest compositor gates pass on the rebuilt objects; the restricted
  K16 link is now `kotoba=92 foreign=0 unattested=0`.

### Guest browser desktop: Alt+Tab focuses and raises the next window (ADR-0237)
- browser-ime.kotoba holds Alt (evdev 56) in surface word 431 from its press to
  its release, and answers a Tab (15) press under it with 256 + the id of the
  window at the bottom of the stack, touching nothing else: the key does not
  reach the body or the composition. Word 431 is the one frame2's scratch
  range named but never used (416..430 now).
- browser-reduce.kotoba takes kind 5, `:window/focus` of the id in a --
  browser.surface focus-window: focus and raise as a press does, capture and
  app register untouched, an unknown id a no-op answering 0. C hands it the
  id browser-key answered, without looking at it.
- The keyboard ring hands releases too (`aiueos_keyboard_next_key`, code * 4 +
  value). A new stage after the pointer, `guest-browser-focus-cycle`: open
  window 2 from the launcher, Alt, Tab x3, Alt up, a lone Tab; stack 132 ->
  321 -> 213 -> 132, twelve frames, every census from browser-frame-model.cljk.
- Contracts: browser-reduce-v1 90 vectors (13 new, from browser.surface
  through browser-reduce-oracle.cljk), browser-ime-v2 71 vectors / 232 steps
  (16 new, the rule as ADR-0237 writes it). Fuel unchanged (key: trap 600 /
  pass 640; reduce: pass 128) -- no kotoba-native row or amu pin change.

### Guest browser desktop: the pointer is drawn (ADR-0236)
- browser-frame2.kotoba ends the draw list with the pointer when surface word
  2046 (x + 1; 0 = none) is set, 2047 its y: a 12-row arrow, #111111 outline
  and #ffffff fill, 21 rects, over everything, cut at the viewport. New
  refusal -10 (pointer outside the viewport). Words 2046 / 2047 are the two
  past the op area; nothing else used them.
- C writes the scaled tablet position into them in a new stage after the
  dictionary; `guest-browser-cursor` moves, presses on no window and
  releases, a frame after each, every census from browser-frame-model.cljk.
  Earlier frames are unchanged (word 2046 was 0 for all of them).
- Contract browser-frame2-v1: 50 vectors (7 new: the arrow over a window, cut
  at the right edge, at the bottom, at the last pixel; x at vw, y at vh,
  y = 2^32 - 1 refused), 31 memory assertions. Fuel: trap 20,480 / pass
  24,576 on the same worst vector as before, inside the 262,144 tier -- no
  kotoba-native row or amu pin change.

### Guest browser desktop: the IME converts through a Unihan dictionary (ADR-0235)
- `os/aiueos/scripts/gen-ime-dictionary.cljk` writes `os/aiueos/ime/aiueos-kanji.dic`
  (aiueos-dict/v1, 189,892 bytes) from Unicode 17.0.0 Unihan `kJapanese` for the
  font's 6,355 kanji: 3,871 readings, 23,679 pairs, Unicode License v3. The
  candidate order is a rule in the generator (Jouyou, Jinmeiyou, JIS level 1,
  level 2; then the reading's place in the kanji's list; then code point).
- browser-ime.kotoba takes `[surface surface-bytes dictionary dictionary-bytes key]`
  (key = code * 4 + value), binary-searches the whole preedit as the reading,
  keeps the record's offset at word 444 while converting, and puts the reading
  back from it on Escape / Backspace. New refusal -6 (header or record).
- The hosted oracle `aiueos.compositor.ime` reads the same file; か converts to
  下 first (the hosted ADR-0088 admission and tests say so).
- C carries `ime/aiueos-kanji.dic` from the initramfs to every key call. The type
  gate types `kuwawaru` for 加 (19 presses, same census); the new
  `guest-browser-dictionary` gate converts やま and しょう after the launcher.
- Contract browser-ime-v1 -> v2: 55 vectors / 205 steps / 162 memory assertions
  against the committed dictionary. kotoba-native fe3409bf: arity 5 and fuel tier
  16,384 (bisected trap 600 / pass 640).

### Guest browser desktop: window bodies laid out as cssom does (ADR-0234)
- browser-frame2's body follows browser.surface + cssom.layout: text 14 in from
  the body box (y + 28), lines w - 28 wide, a JS-whitespace run (U+3000, TAB
  and NBSP included) one space, a fitting body one line as collapsed, otherwise
  packed by words (no break inside a word, CJK included), each 10 a `<br>`.
  Glyphs past the bottom inset or the viewport are not drawn; nor is a caret
  past the viewport. The composition wraps at x + w - 14.
- `browser-flow-oracle.cljk` renders every desktop scene through the hosted
  engine and writes `contracts/browser-flow-parity-v1.edn` (68 window bodies);
  `browser-frame-model.cljk --parity` and the new gate compare against it glyph
  by glyph. The model gained `--scenes`, `--parity` and `--vectors`.
- Every text frame the desktop gates pin moved (op counts unchanged) and was
  re-pinned from the model; browser-frame2-v1 has 43 vectors (8 new).
- Gate `guest-browser-flow-parity` (default profile, no tablet).

### Guest browser desktop: a launcher opens a window, a close control closes it (ADR-0233)
- Word 31 of the surface is the app register (bit k-1 = app k, whose title and
  document are window slot k's). With it 0 nothing changes: every earlier
  frame and vector is as it was.
- browser-frame2, with a register: the launcher row (#edf0f5, 28 px) and a
  #e4e8ef button per registered app right after the background, and in each
  window at least 40 wide a 16 x 16 close control with U+00D7 after the title
  (which now clips 20 px earlier). New reason -9 (register past app 4).
- browser-reduce, with a register: a press on a close control is
  browser.surface close-window (the focus goes to the window now on top only
  if the closed one had it); a press on no window inside a launcher button is
  launch-app at open-window's default rect (80, 80, 520, 360). Both clear the
  capture. Named differences: one window per app, the last window stays (-8),
  a default rect past the viewport is refused (-9); -7 a register past app 4.
  browser-reduce-oracle.cljk writes the geometry apart from the object and
  applies browser.surface's own actions; 27 new vectors.
- Gate `guest-browser-launch` (840 s QEMU wall clock).

### Guest browser desktop: a caret, and Backspace deletes before it (ADR-0232)
- browser-frame2 ends the focused window with a 1 x 16 #111111 caret where the
  next glyph would go (cssom sel-ops' collapsed selection), after the body and
  composition; not drawn past the bottom inset.
- browser-key: Backspace with nothing composed (or with the IME off) deletes
  the focused body's last code point (browser.text-edit delete-backward). The
  hosted IME consumes that Backspace; this object does not, on purpose.
- Every frame2 frame gained the caret: the census constants of the text,
  raised, type, preedit, ime-toggle, drag, resize and loop gates were re-pinned
  from browser-frame-model, and the browser-frame2-v1 success vectors were
  regenerated from it. browser-ime-v1 gains six delete vectors.
- Gate `guest-browser-caret` (720 s QEMU wall clock).

### Guest browser desktop: one running loop drives the desktop (ADR-0231)
- After the resize, one loop polls the tablet and the keyboard, hands each
  event to browser-reduce or browser-key, and presents a frame after every
  one: nine interleaved events (k a Enter, a titlebar drag of window 2,
  n i Enter), each frame's census folded into a chain the frame model
  reproduces. No object changes.
- browser-frame-model pins the resize frame and lays out the nine loop frames.
- Gate `guest-browser-event-loop` (600 s QEMU wall clock).

### Guest browser desktop: the resize handle resizes the window (ADR-0230)
- browser-reduce captures a resize on a press in the 16 px resize handle
  (words 25..30: kind 2, id, press point, size at the press); pointer/move
  sets the size to the press size plus the travel, clamped at 120 x 80,
  keeping the origin. -4 now also refuses a resize of an absent window.
- browser-reduce-v1: 50 vectors (40 from the kotoba-lang/browser oracle).
  Gate `guest-browser-resize`.

### Guest browser desktop: a titlebar drag moves the window (ADR-0229)
- browser-reduce captures a drag on a titlebar press and moves the window to
  the pointer minus the press offset on each pointer/move (kind 3); pointer/up
  (kind 4) releases. Refusals -4 (bad capture) and -6 (origin below 0).
- browser-reduce-v1: 30 vectors, success vectors printed from
  kotoba-lang/browser by `os/aiueos/scripts/browser-reduce-oracle.cljk`.
- The virtio-tablet ring stays live after its first press
  (`aiueos_tablet_next`). Gate `guest-browser-drag`.

### Guest browser desktop: Hankaku/Zenkaku switches the IME (ADR-0228)
- browser-ime turns the IME off and on at evdev 41 and discards the
  composition when it switches (the hosted desktop's `set-ime`); off, letters
  go straight into the focused body as latin. Gate `guest-browser-ime-toggle`.
- browser-ime-v1: 7 toggle vectors generated from the oracle (34 vectors,
  124 steps, 94 memory assertions).

### Guest browser desktop shows the composition (ADR-0227)
- browser-frame2 draws the focused window's preedit and pending romaji,
  underlined, after its body; gone once committed. Gate
  `guest-browser-preedit`.
- `os/aiueos/scripts/browser-frame-model.cljk`: the independent model the
  desktop gates' known answers come from; it must reproduce the frames
  already pinned before its new answers are used.

### Guest browser desktop takes typing (ADR-0225)
- `os/aiueos/kotoba/browser-ime.kotoba` (`kotoba_aiueos_browser_key`): the
  hosted IME's `handle-key` as a kernel object -- romaji buffer, greedy mora
  conversion, sokuon, Space conversion over the oracle's three readings,
  Enter commit into the focused window's body. Romaji table generated from
  the oracle by `os/aiueos/scripts/gen-ime-mora.cljk` (`--check`).
- The keyboard ring is kept after its first key (`aiueos_keyboard_drain`,
  `aiueos_keyboard_next_press`); the QMP injector types once at TYPE_GO.
  Gate `guest-browser-type`; KIR-oracle contract `browser-ime-v1` (expected
  values from the oracle).
- Fixed: browser-frame2's scratch overlapped window 4's body; scratch moved to
  words 416..431, ops to 480 (cap 261).

### Guest browser desktop draws text (ADR-0224)
- `os/aiueos/fonts/aiueos-16.fnt`: GNU Unifont 17.0.05 `unifont_jp`, JIS X
  0208 + ASCII + U+3000 + U+FFFD (7,422 glyphs, 267,208 bytes), SIL OFL 1.1,
  built by `os/aiueos/scripts/make-font.cljk` (`--check` recompiles and
  compares). Carried as the fourth initramfs entry
  (`AIUEOS_INITRAMFS_OK newc entries=4`), copied to `.high_bss`.
- `os/aiueos/kotoba/browser-frame2.kotoba` (`kotoba_aiueos_browser_frame2`):
  rects and glyphs in one list, window by window in stack order; font
  admission, binary-searched lookup, U+FFFD fallback, 8/16 advance, title
  clip, body wrap at the right inset, bottom cut.
- C `aiueos_desktop_present_ops2` blits the list; gates `guest-browser-text`
  and `guest-browser-text-raised` compare the #111111 pixel census with a
  model of the frame. KIR-oracle contract `browser-frame2-v1`.

### Guest browser desktop: frame and pointer on KERNEL.ELF (ADR-0223)
- `os/aiueos/kotoba/browser-frame.kotoba` (`kotoba_aiueos_browser_frame`)
  turns the 128-byte surface state into kotoba-lang/browser's retained draw
  list -- workspace, then body + titlebar per window in `:surface/windows`
  order, browser.surface's colours, browser.input's 28 px titlebar.
- `os/aiueos/kotoba/browser-reduce.kotoba` (`kotoba_aiueos_browser_reduce`)
  applies one event as browser.input + browser.surface do: pointer/down hits
  the topmost window (inclusive), focuses and raises it; a key moves nothing.
- C presents the list in order (`aiueos_desktop_present_ops`, whole frame or
  nothing) and the virtio-input driver now tells a tablet from a keyboard and
  records a BTN_LEFT press. `AIUEOS_GUEST_BROWSER=1` adds a virtio-tablet and
  a QMP press. Gates `guest-browser-frame` / `guest-browser-input`; KIR-oracle
  contracts `browser-frame-v1` / `browser-reduce-v1`. Leftover
  `:no-text-raster`, `:no-pointer-capture`, `:no-text-edit`.

### Kotoba guests: thirteen kernel-adjacent namespaces (ADR-0202)
- `aiueos/topic.kotoba`, `aiueos/os_update.kotoba`,
  `aiueos/model_channel.kotoba`, `aiueos/runtime_update.kotoba`,
  `aiueos/device_auth.kotoba`, `aiueos/vm.kotoba`,
  `aiueos/hardware_qualification.kotoba`, `aiueos/pid1.kotoba` and
  `aiueos/bare_metal.kotoba`, `aiueos/virtio.kotoba` and
  `aiueos/image.kotoba`, `aiueos/compositor/ime.kotoba` and
  `aiueos/compositor/ime_key.kotoba` compile as pure Kotoba guests
  (`amu compile --target wasm32-browser`); the `.cljc` sources stay as
  parity oracles. The topic bus guest carries the whole public surface
  (publish / latest / take-sample / pending / topic-count / tick /
  advance); device-auth carries all sixteen proof refusal reasons in the
  oracle's order, as a linear scan of numbered checks.
- None of the thirteen declares or calls a capability: effect inference
  answers `:effects #{}` for a guest that only moves immutable documents
  (ADR-0202 records the rule — a pure guest is written with zero
  capability lines; a guest that touches the world declares exactly the
  capabilities it uses, through `perform`).
- Measured bounds stated in each header: `:container-items 32` (a 33rd
  queued sample traps `document-vector-too-large`, fail-closed),
  `max-parameters 5` (booleans as an i64 flags vector), no
  `document-is-null` lowering (absence is `document-count = 0`), no
  `rem`/`mod` lowering. Regexes over wire bytes and the publisher
  closures stay in the host.
- Reference: `docs/kotoba-guests.md`.

### Passkey-bound device addition (ADR-0113)
- The Kotoba Browser setup surface now starts and polls the one-time device
  authorization flow at the formal authority `auth.kotoba.cloud`, under the
  dedicated `/v1/aiueos/device/*` namespace. Passkey and phone scan share one
  ceremony; phone scan renders the public approval URL as a local QR.
- A separate poll secret remains only in helper memory. The browser cannot
  grant itself authority, and a successful authority result must match the
  exact flow, device DID, challenge, model, method, origin and RP ID before a
  local device-key possession proof can claim the node.
- The new adapter/state-machine files and QR runtime are content-addressed in
  the TCB inventory. Production deploy and a real human Passkey ceremony remain
  separate live evidence.

### nbb guest compositor gates (ADR-0100)
- Guest KERNEL.ELF serial gates run on nbb:
  `kbb --backend sci --classpath src scripts/compositor-guest.cljk <profile>`.
  Classifiers live in portable `aiueos.compositor.guest`. Hosted JVM
  `kbb -M:compositor wm` / `ime` stay red. JVM `kbb -M:compositor
  guest-*` is leftover `:jvm-gate-runner`. Serial lines unchanged.
  Leftover `:native-compositor-absent` (native component runtime, P5).
  **P5 UNVERIFIED**.

### Guest session restore (ADR-0098)
- KERNEL.ELF restores packed front window 2 when Kotoba
  `kotoba_aiueos_session_restore(2) == 2`, refuses packed 0 and packed 3,
  and `kotoba_aiueos_wm_hit` uses that front. Restore is Kotoba; C does
  not hardcode front. Gate host as of ADR-0100:
  `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-session`.
  Named red is hosted JVM `AIUEOS_COMPOSITOR_WM_OK` and restore that
  always returns 2 (`:always-front`). Default `gpu` / `guest-broker`
  boots stay green without requiring `GUEST_SESSION_OK`. Leftover
  `:native-compositor-absent` (native component runtime, P5).
  **P5 UNVERIFIED**.

### Guest permission broker (ADR-0096)
- KERNEL.ELF admits clipboard and refuses file-picker when Kotoba
  `kotoba_aiueos_broker_admit(1, 1) == 1` and
  `kotoba_aiueos_broker_admit(2, 1) == 0`. Admit is Kotoba; C copies
  the clipboard scratch only when admitted. Gate:
  `kbb -M:compositor guest-broker`. Named red is hosted JVM
  `AIUEOS_COMPOSITOR_WM_OK` and picker on a clipboard-only grant
  (`:always-grant`). Default `gpu` / `guest-scanout-two` boots stay
  green without requiring `GUEST_BROKER_OK`. Leftover
  `:native-compositor-absent` (native component runtime, P5).
  **P5 UNVERIFIED**.

### Guest scanout-two (ADR-0095)
- KERNEL.ELF `SET_SCANOUT` scanout 1 onto resource 2 when Kotoba
  `kotoba_aiueos_scanout_bind(2, enabled) == 2`. Bind count is Kotoba;
  C does not hardcode `2`. QEMU `virtio-vga` uses `max_outputs=2`.
  Gate: `kbb -M:compositor guest-scanout-two`. Named red is hosted
  JVM `AIUEOS_COMPOSITOR_WM_OK` and one scanout when Kotoba admits two
  (`:one-scanout`). QEMU 10.1 enables extra heads only after a UI
  frontend `ui_info`; the gate owns a unix session bus and `gdbus`
  `SetUIInfo` on Console_1. Default `gpu` / `guest-gpu-two` boots stay
  `-display none` and stay green without requiring
  `GUEST_SCANOUT_TWO_OK`. Leftover
  `:native-compositor-absent` (native component runtime, P5). **P5 UNVERIFIED**.

### Guest gpu-two (ADR-0094)
- KERNEL.ELF creates and flushes two virtio-gpu 2D resources when Kotoba
  `kotoba_aiueos_wm_hit(2, 2, 100, 80) == 2`. Count is Kotoba; C does not
  hardcode `2`. Gate: `kbb -M:compositor guest-gpu-two`. Named red is
  hosted JVM `AIUEOS_COMPOSITOR_WM_OK` and one resource when Kotoba admits
  two (`:one-resource`). Default `gpu` / `guest-input` / `guest-paint` boots
  stay green without requiring `GUEST_GPU_TWO_OK`. Leftover
  `:native-compositor-absent` (permission broker, native component runtime,
  one virtio-gpu scanout). **Measured 2026-08-24:**
  `guest-gpu-two` leftover `[]` with
  `AIUEOS_GUEST_GPU_TWO_OK resources=2 flush=2 kotoba-n=2`. **P5 UNVERIFIED**.

### Guest input (ADR-0093)
- KERNEL.ELF copies the desktop envelope from a virtio-keyboard
  used-ring event, not the `#ifdef AIUEOS_INPUT_SMOKE_SYNTHETIC` fill.
  Gate: `kbb -M:compositor guest-input`. Named red is hosted JVM
  `AIUEOS_COMPOSITOR_WM_OK` and C synthetic fill (`:synthetic-smoke`).
  Default `gpu` / `guest-ime` / `guest-wm` / `guest-paint` boots keep
  the synthetic ifdef so they stay green without this serial line.
  Injector is QMP `input-send-event`, not HMP `sendkey`. Leftover
  `:native-compositor-absent` (permission broker, native component
  runtime, one virtio-gpu resource). **Measured 2026-08-23:**
  `guest-input` leftover `[]` with
  `AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0`. **P5 UNVERIFIED**.

### Guest paint (ADR-0092)
- KERNEL.ELF paints both boot-desktop rects back-then-front from
  Kotoba `kotoba_aiueos_wm_hit` and samples the overlap pixel.
  Gate: `kbb -M:compositor guest-paint`. Named red is hosted JVM
  `AIUEOS_COMPOSITOR_WM_OK` and a key-order paint (window 1 on top at
  overlap). `guest-wm` / `guest-ime` / `gpu` stay green without this
  serial line. Leftover `:native-compositor-absent`. virtio-input still
  synthetic. **Measured 2026-08-23:** `guest-paint` leftover `[]` with
  `AIUEOS_GUEST_PAINT_OK boot-overlap=2 raised-overlap=1 key-order=0`.
  P5 UNVERIFIED.

### Guest WM (ADR-0091)
- KERNEL.ELF Kotoba `kotoba_aiueos_wm_hit` z-hits two overlapping boot
  rects. Gate: `kbb -M:compositor guest-wm`. Named red is hosted JVM
  `AIUEOS_COMPOSITOR_WM_OK`. Leftover after this slice was
  `:one-guest-scanout`. P5 UNVERIFIED.

### Guest IME (ADR-0090)
- KERNEL.ELF Kotoba `kotoba_aiueos_ime_commit(107, 97)` returns U+304B.
  Gate: `kbb -M:compositor guest-ime`. Named red is hosted JVM
  `AIUEOS_COMPOSITOR_IME_OK`. Latin echo is leftover `:latin-leak`.
  `ime` / `kanji` / `kami` / `gpu` stay green without this serial line.
  Leftover `:native-compositor-absent`. virtio-input still synthetic.
  **Measured 2026-08-23:** `guest-ime` leftover `[]` with
  `AIUEOS_GUEST_IME_OK committed=u+304b latin-leak=0`. P5 UNVERIFIED.

### Hosted kami.webgpu presenter (ADR-0089)
- `#kami-viewport` calls `kami.webgpu/init!` then `draw!`. Gate:
  `kbb -M:compositor kami`. Named red is `clear-only-desktop`
  (sky-only `beginRenderPass`). IR is `kami.webgpu.ir/render-ir` with
  ≥1 instance. `kanji` / `ime` stay green without a kami frame.
  Leftover `:native-compositor-absent` after ADR-0090. P5 UNVERIFIED.

### Hosted IME kanji (ADR-0088)
- Space converts `か` to first candidate `加`; Enter commits. Gate:
  `kbb -M:compositor kanji`. Named red is `kana-only-desktop`
  (Space commits kana). `kbb -M:compositor ime` stays kana-only.
  Leftover `:native-compositor-absent` after ADR-0090. Not mozc. Hosted
  IME stays. P5 UNVERIFIED.

### Bare-metal net (P2, green on QEMU UEFI)
- Guest TLS 1.3 (0x1301) + HTTPS GET of empty raw CID with SHA-256 admit
  (ADR-0082). Gate: `kbb -M:bare-metal cloud` EXIT=0 leftover `[]`.
  Hosted `cloud-live` does not count. CertificateVerify is ADR-0087
  (`kbb -M:bare-metal cert-verify`). Chain-to-anchor still leftover.
  **Measured 2026-08-23:** `cert-verify` EXIT=0 leftover `[]` with
  `AIUEOS_CERTVERIFY_PROBE result=ok scheme=ecdsa_secp256r1_sha256`, and
  `cloud` still EXIT=0 leftover `[]` on the same firmware (ADR-0087).

The Phase-0 substrate plus the runtime/robotics/agent work built on top of it.

### Capability OS core
- Component **manifests** as kotoba (EDN) with strict, fail-loud validation —
  unknown `:aiueos/*` keys, bad kind/trust, out-of-range limits, non-integer
  args, empty entry, and malformed topic maps are all hard errors.
- **Capability graph** + **policy reasoner**: imports must resolve (exporter /
  kernel primitive / grant), effect-vs-trust lockdown (`:ai-generated` denied
  network/secrets/persist), and the driver **DMA→IOMMU** rule.
- **Fail-loud policy files**: unknown `:aiueos/*` policy keys, an unknown trust in
  `:aiueos/forbid`, and non-map `grants`/`forbid` are hard errors (a typo can't
  silently drop a grant or a lockdown).
- **Broker**: verify → safe-check → compile/load → run, every decision audited.
- **Safe-kotoba subset** gate (no eval/require/slurp/reflection/dotted host
  classes) before compiling source.
- **Staged boot** (`aiueos up`, Stage 0–4): link → topological order → verify →
  launch; boot order derived from the capability graph.
- **Duplicate component id** and **device-binding exclusivity** (one driver per
  `bus:vendor:device`) are rejected.

### Runtime + robotics
- Broker-mediated **`aiueos:host` ABI**, capability-gated per call:
  `log` / `clock` / `random` / `publish` / `poll` / `take` / `count`.
- **Topic bus**: latest-value (`poll`) + per-topic **FIFO** queue (`take`) +
  publish `count`; the ROS-topic analogue.
- **Per-topic isolation**: `:aiueos/publishes` / `:aiueos/subscribes` confine a
  component to declared topic ids; a call to an undeclared topic traps.
- **Named topics linked to ids** via `:aiueos/topics {:name id}` — publishes/
  subscribes are derived from the `:topic/<name>` exports/imports.
- **Periodic control loop** (`aiueos up --rounds N`): one bus threaded across N
  rounds; `clock()` returns the monotonic cycle.
- Fuel + linear-memory limits enforced; runaways trap.
- **Per-cycle IO quota** (`:aiueos/quota`, ADR-0006): host-call / publish rate caps
  enforced in the host ABI — an over-budget call traps like an ungranted capability.
- **Cooperative scheduler** (`:aiueos/schedule`, ADR-0006): deterministic
  period-skipping (run every N cycles) + priority ordering *within* dependency
  depth, so an urgent node runs earlier without ever preceding its provider.

### Self-owned VMM ("hvt tender", ADR-0014 V0)
- **`aiueos.hvt`** — the monitor side of aiueos virtualization, complementing
  `aiueos.vm` (which *launches QEMU*) and `aiueos.vfio` (raw access to a device
  QEMU exposes). Creates a VM through Linux **KVM** (`/dev/kvm`), maps guest
  RAM, loads a guest image, runs the vcpu, and services its exits — the Solo5
  `hvt` shape ADR-2607022400 named and ADR-0011 Phase 1 deferred. Every syscall
  (`open`/`ioctl`/`mmap`) goes through `java.lang.foreign` (FFM), "clj on clj,"
  no new Rust/C (honors the 2026-07-10 owner rule without a waiver).
- **V0 boot spike, verified end-to-end on real KVM**: a minimal aarch64 guest
  writes `HI\n` byte-by-byte to an MMIO serial port (each `strb` traps out as
  `KVM_EXIT_MMIO`, reconstructed by the VMM) then writes a poweroff MMIO port
  for a controlled halt. `spike` returns an audit-shaped **run receipt**
  (`:serial "HI\n" :serial-ok? true :shutdown? true :steps 4 :halt
  :mmio-poweroff`). Exercised on Apple M4 → Lima vz nested-virt → aarch64
  Ubuntu `/dev/kvm`. Pure parts (ioctl-number encoding, kvm_run/…-region
  struct offsets, the aarch64 PC core-reg id, the fixed guest program) are
  unit-tested on any JVM host; the live KVM loop is gated by
  `scripts/hvt-smoke.cljk` (nbb) in a Linux/KVM VM (#110).
- Deferred to V1+ (#110): real PSCI SYSTEM_OFF clean shutdown (the bare
  MMU-off guest's `hvc` did not raise `KVM_EXIT_SYSTEM_EVENT`, so V0 halts via
  the MMIO poweroff port), direct-loading the ADR-0013 kernel image, a virtio
  device model reusing `aiueos.virtio`'s ported protocol logic, and an x86_64
  long-mode guest. macOS/HVF backend is V2 (behind the
  `com.apple.security.hypervisor` entitlement question).
- **V1 progress (2026-07-17), two hard findings** (ADR-0014 "V1 progress"):
  (1) the ADR-0013 kernel is **x86_64-only**, so direct-loading it under the
  tender needs an **x86_64 KVM host** — an aarch64 host (the dev machine) can
  only run aarch64 guests, so the kernel-boot gate waits on x86 hardware; the
  ELF-load logic itself is arch-independent and authorable now. (2) PSCI
  SYSTEM_OFF does **not** fire for a hand-written bare guest — reproduced via
  the new `guest-program-psci` diagnostic (serial → `hvc` → poweroff
  fall-through): the `hvc` blocks `KVM_RUN` in-kernel with neither a
  system-event nor the fall-through exit, so KVM injects an exception the
  vector-table-less guest spins on; forcing `KVM_ARM_VCPU_PSCI_0_2` regressed
  it further. A real PSCI shutdown needs a real-kernel guest (finding 1).
  Landed: `spike` parametrized over `{:program …}`, the PSCI diagnostic + tests
  (7 tests / 41 assertions), a `kbb -M:hvt psci` diagnostic entry
  (intentionally blocking — run under `timeout`), and `KVM_ARM_VCPU_INIT`
  return-code checking. Default poweroff path + smoke gate stay green.
- **V1 progress (2026-07-17), ELF64 direct-loader** (ADR-0014 "V1 progress"):
  the arch-independent half of kernel-direct-load, built and verified
  end-to-end. Pure `parse-elf64`/`rd-le`/`elf-load-range` (host-testable);
  `spike` generalized via `boot-plan` to accept `{:elf-bytes …}`, mapping guest
  RAM at the ELF's load base (the fixture links at `0x40000000` — an arbitrary
  non-zero GPA), copying PT_LOAD segments and setting PC = `e_entry`. Real
  fixture `resources/hvt/guest-aarch64.elf` (genuine `ld` output; reproducible
  byte-identical via `scripts/build-hvt-guest.cljk`, nbb, SHA-pinned). Verified
  on real KVM: `kbb -M:hvt elf …` boots it to `{:serial "HI\n" :shutdown?
  true}`. `scripts/hvt-smoke.cljk` now gates both the raw-word (V0) and ELF (V1)
  cases; `aiueos.hvt-test` is 11 tests / 57 assertions. The remaining
  kernel-boot gap is purely the x86_64 KVM host (Finding 1); the ELF-load
  mechanism is done.
- **V1 progress (2026-07-17), virtio-mmio device model** (ADR-0014 "virtio-mmio
  device model"): the tender now emulates a device the guest can probe, the
  first reuse of `aiueos.virtio`'s host-side logic. Adds **MMIO read
  emulation** (`set-mmio-data!` answers guest register reads before re-entering
  `KVM_RUN`) and a pure, host-tested **`virtio-console` device model**
  (`virtio-console-read`/`-write` over `aiueos.virtio/mmio-reg` + magic/version/
  status/feature constants) presenting device-id 3 with `VIRTIO_F_VERSION_1`.
  A real aarch64 driver guest (`guest-virtio-aarch64.S` → `.elf`, loaded by the
  V1 ELF loader) runs the full `ACKNOWLEDGE → DRIVER → feature-negotiate →
  FEATURES_OK → DRIVER_OK` transport handshake and emits `HI\n` only on total
  success. Verified on real KVM (21-step trace, `:virtio-status 15` = DRIVER_OK).
  `hvt-smoke.cljs` now gates raw + ELF + virtio; `aiueos.hvt-test` is 14 tests /
  75 assertions. The virtqueue data path (rings/descriptor DMA) is the next
  milestone; queue-config writes are already tracked in device state.
- **V1 progress (2026-07-17), virtqueue data path** (ADR-0014 "virtqueue data
  path"): the virtio-console device now moves **data**, not just handshake
  registers — a freestanding guest driver sets up a split virtqueue in guest RAM
  and transmits `HI\n` through the transmitq; the tender reads the avail ring +
  descriptor chain out of guest RAM and pulls the bytes into the receipt's
  `:console`. Adds guest-RAM access (`gram-rd`/`gram-set-le!`), pure split-queue
  servicing (`read-descriptor`/`walk-descriptor-chain`/`virtqueue-plan`,
  host-tested with synthetic RAM, reusing `aiueos.virtio/desc-flag`), per-queue
  config tracking + `queue-config`, and SP-register setup so guests can be
  written in freestanding C (`guest-virtqueue-aarch64.c`). Verified on real KVM
  (31-step trace, `:console "HI\n"` via the virtqueue + `:serial "HI\n"` guest
  confirmation, `:virtio-status 15`). `hvt-smoke.cljs` gates 4 cases (raw / ELF
  / transport / virtqueue); `aiueos.hvt-test` is 17 tests / 87 assertions. Both
  open V1 items (kernel direct-load, virtio device model) are now substantially
  delivered. Bug recorded: gcc `-O2` post-index `strb` MMIO stores fail
  `KVM_RUN` `ENOSYS` (no decodable syndrome) — write to a fixed register address.
- **V1 progress (2026-07-17), virtqueue receiveq** (ADR-0014 "virtqueue
  receiveq"): the virtio-console is now **bidirectional** — the device→guest
  mirror of transmit. On a receiveq notify (queue 0) the device *fills* the
  driver's device-**writable** buffers instead of reading them. Adds pure
  receive servicing (`walk-writable-chain`/`fill-targets`/`virtqueue-rx-plan`,
  host-tested incl. capacity truncation) + `process-virtqueue-rx!`, queue-index
  routing (queue 1 = tx into `:console`, queue 0 = rx delivering
  `virtio-console-rx-input`), and a real receive guest
  (`guest-virtqueue-rx-aarch64.c` → `.elf`) that posts a writable buffer, is
  filled by the tender, and echoes the received bytes to serial. Verified on
  real KVM (31-step trace, `:serial "HI\n"` from the device→guest path).
  `hvt-smoke.cljs` gates 5 cases; `aiueos.hvt-test` is 20 tests / 100 assertions.
  The virtio-console device model is complete in both directions.
- **V1 progress (2026-07-17), PSCI finding corrected + vcpu power-state control**
  (ADR-0014 "PSCI finding, corrected"): by reading the `hvc` return code in `x0`,
  established that this KVM environment answers **every** PSCI function id
  (`PSCI_VERSION`/`SYSTEM_OFF`/`SYSTEM_RESET`/`CPU_OFF`) with `NOT_SUPPORTED`
  (`0xFFFFFFFF`) and resumes — so no PSCI shutdown-exit exists here (correcting
  the earlier, wrong "guest spins in a zeroed vector table" explanation). The
  `KVM_ARM_VCPU_PSCI_0_2` feature bit doesn't help and leaves the boot vcpu
  `MP_STATE_STOPPED` (the earlier "regression"). Adds real vcpu power-state
  control (`KVM_GET_MP_STATE`/`KVM_SET_MP_STATE` + `mp-state` constants) and a
  `:psci-0-2?` diagnostic option (sets the feature + forces RUNNABLE). MMIO
  poweroff remains the halt mechanism. `aiueos.hvt-test` is 18 tests / 92
  assertions.

### Security / supply chain
- **Artifact integrity**: `:aiueos/wasm-sha256` is verified before run
  (tamper detection); `aiueos hash` computes it.
- **Manifest authenticity (ed25519 signatures, ADR-0003)**: `:aiueos/signature`
  over the identity↔artifact binding, verified against the policy
  `:aiueos/signers` registry. Valid → trust elevated to `:verified` + signer
  audited; forged/unregistered → denied. `:aiueos/require-signed` rejects unsigned
  components. `aiueos sign` produces signatures (`signing` feature, default-on).
- **Audit**: append-only EDN log records grant/deny/compile/run **and runtime
  traps (reject)**; queryable with `aiueos audit --event/--component/--edn`.

### Code as data (agent admission)
- **`Broker::admit` / `aiueos admit`** (ADR-0004): the front door for a component
  an AI agent emits at runtime. Trust is **floored to `:ai-generated`** before
  verification — agent code can never grant itself trust (a signature can still
  elevate it). Returns a structured verdict `{admitted, result, reason,
  reason-code}` so an agent loop branches on a stable `:reason-code`
  (`:denied` / `:unsafe` / `:run` / …) and iterates.

### Tooling / agent surface
- Machine-readable **`--edn`** on `verify`/`inspect`/`up`/`run`/`audit` (verdicts,
  denials, and structural errors all as EDN).
- **`inspect --dot`** — Graphviz of the component dependency graph (named topics
  render as the actual dataflow edges).
- **`up --dry-run`** — link → order → verify a whole system without launching
  anything (CI / pre-boot validation, no side effects).
- `aiueos hash`, helpful errors (e.g. `inspect`/`up` on a single manifest point at
  `verify`/`run`), robust CLI arg parsing.
- A runnable **authoring example** (`examples/authoring/`) kept verified by a test.

### Build / project
- Standalone build: `kotoba-edn` is a git dependency; the CLJ compiler
  (`kototama`) is an opt-in monorepo-only feature.
- **CI** (GitHub Actions): core + exec-only + rustfmt.
- **193 tests + 3 doctests** green across the core / exec-only / full configs.

[Unreleased]: https://github.com/kotoba-lang/aiueos/commits/main
