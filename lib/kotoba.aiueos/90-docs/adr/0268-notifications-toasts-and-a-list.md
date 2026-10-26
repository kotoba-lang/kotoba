# ADR-0268 — Notifications: toasts and a list

Date: 2026-10-24

## Status

Accepted. Adds the `guest-browser-notify` gate; no new floor. Row C7 ("Notifications": it appears, can be dismissed, and is
listed) of the ChromeOS-grade scorecard.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-notify` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_NOTIFY_OK`: the layout gate (and so the clock and editing gates) is green on the same serial and all
15 `AIUEOS_GUEST_BROWSER_NOTIFY` lines equal the frame model's: the baseline, two raised notifications shown as toasts, F8 removing
the newest toast, F7 opening a list that still holds both, F7 closing it, F8 removing the other, F7 listing both again.

## Decision

- Surface words 1971..2002 hold four notification entries of eight words: a state (0 empty, 1 shown, 2 dismissed and kept in the list)
  and up to seven code points of text. Word 2003 is the list panel (0 closed, 1 open). An app raises a notification by writing an entry;
  the stage plays two apps (`Backup`, `Update`).
- `browser-frame2.kotoba` draws, above the windows and below the pointer: the shown entries as 208 x 26 toasts down the right edge, or,
  with the list open, a white panel with one row per entry (a `*` marks one still shown).
- `browser-ime.kotoba`: F8 dismisses the newest entry still shown, F7 opens and closes the list. Both are keyboard-only (I8), neither
  is text.

## Not

A real app-to-shell call (the stage writes the words); a pointer dismiss; a timeout; more than four entries or seven characters; a
sound; per-app grouping; clearing the list.
