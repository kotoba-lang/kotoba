# ADR-0258 — The screen locks and a PIN unlocks it

Date: 2026-10-23

## Status

Accepted. Closes the `:screen-lock` floor (ladder: 33 floors, 31 gated). Row B2 ("Lock and unlock the
screen") of the ChromeOS-grade scorecard has its procedure run end to end in the reference VM.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-screen-lock`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_SCREEN_LOCK_OK`: the minimize gate is green on the same serial,
`AIUEOS_GUEST_BROWSER_MAX n=61..90` and `AIUEOS_GUEST_BROWSER_LOCK n=61..90` equal the frame model's, no
window is drawn while locked, a wrong PIN leaves it locked, the right one unlocks, and the session after it
has the windows, focus, stack and rect it had before the lock, and its op count less the 4 rects of the keyboard focus ring (the lock clears it).

Not, and stated here rather than at the end: a real credential. The unlock check is a four-digit PIN against
a SHA-256 baked into the image, and the image carries the TEST PIN's hash (the user's own application, test
value 4242); there is no first-run provisioning, no attempt limit, no lock on idle or lid, no passkey (B1), and
the gate reads the draw list, not the pixels.

## Decision

The decision is Kotoba's, the check is C's, because a hash comparison is mechanism and "locked" is policy.

- `browser-ime.kotoba`: Ctrl+Alt+L (evdev 38 with Ctrl and Alt held) sets surface word 2030, clears the
  pointer capture, the focus ring and the composition. While it is 1 the only keys taken are the PIN's:
  digits fill word 2031 (count in bits 0..2, the number above), Backspace takes one back, Enter with four digits
  answers `100000000 + number` (above every press answer, 65536 + 2048 x + y). Everything else -- shell actions,
  typing, the IME -- is swallowed. The verdict comes back as a key event of value 2 (code 1 accepted, 2 refused):
  accepted clears word 2030, refused sets word 2026 (a red bar) and empties the digits.
- `kernel/main.c` `aiueos_pin_ok`: SHA-256 of `aiueos-pin/dddd` with the already-linked Kotoba SHA-256 object,
  compared with the provisioned hash, then the verdict event; nothing else about the lock is C's.
- `browser-reduce.kotoba`: with word 2030 set (the whole surface), every event answers 0 and changes nothing.
- `browser-frame2.kotoba`: with word 2030 set the frame is a dark background (black in the high-contrast
  palette), ロック中 in white, four dots (digits typed white, the rest grey), the refusal bar, and the arrow
  (never the resize cursor); no window, launcher, dock or tray.

## Measured

Events 61..90: Ctrl, Alt, L down and up (locked: 30 ops, no window bar), a press at (456, 146) and a key (x)
change nothing, four digits and Enter (dots 1..4, then refused: 31 ops, the bar), four digits and Enter again
(unlocked: windows 3, focus 4, stack 314, the same as before the lock; 187 ops, the 191 of before less the 4 rects of the keyboard focus ring, which the lock clears).

## Still open

First-run provisioning of the PIN (A5), an attempt limit and back-off, locking on idle, a passkey unlock (B1),
and the pixels.
