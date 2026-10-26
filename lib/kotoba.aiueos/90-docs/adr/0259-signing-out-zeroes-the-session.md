# ADR-0259 — Signing out zeroes the session

Date: 2026-10-23

## Status

Accepted. Adds the `guest-browser-sign-out` gate (sixteen events after the lock's thirty); no new floor. Row B3
("Sign out") of the ChromeOS-grade scorecard has its procedure run end to end in the reference VM.

**Green only when** `guest-browser-sign-out` prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_SIGN_OUT_OK`: the
screen-lock gate is green on the same serial, `AIUEOS_GUEST_BROWSER_MAX n=91..106` and
`AIUEOS_GUEST_BROWSER_LOCK n=91..106` equal the frame model's, the session has data before the sign-out (the kernel
reads non-zero body words at n=90..92) and none after (`AIUEOS_GUEST_BROWSER_SIGNOUT`: body, scroll, saved maximize
rects and the minimized register all 0 from n=93, one window, focused).

Not, and stated here rather than at the end: a wipe of everything a user could have left (the clipboard held by the
broker, a persisted file, the input method's dictionary cache) -- only the desktop session's words are zeroed and read
back from the surface, not from the RAM behind it; the same test PIN signs in again; the account is not switched.

## Decision

`browser-ime.kotoba` `sign-out-now`, on Ctrl+Alt+Q: every window body (words 160..415), the scroll offsets
(2040..2043), the saved maximize rects (2010..2025), the double-press bookkeeping, the selection and the minimized
register are zeroed; the stack becomes one window 1 at the default rect (80, 80, 520, 360) holding the focus, with
the capture dropped; and the screen locks (ADR-0258). The apps' titles are the apps', not the session's, and stay.
The PIN signs in to that clean session.

## Measured

Events 91..106: Ctrl, Alt, Q down and up (the lock screen at once: 30 ops), the PIN 4 2 4 2 and Enter (dots 1..4),
then the clean desktop: windows 1, focus 1, 72 ops, 582 text pixels -- the title of one empty window -- against 187 ops
and 1080 pixels of the three-window session before.

## Still open

Clearing what lives outside the desktop words, switching accounts, a real credential (ADR-0258), and the pixels.
