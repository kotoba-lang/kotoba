# ADR-0269 — The settings window

Date: 2026-10-24

## Status

Accepted. Extends the `guest-browser-settings` gate (ADR-0260, ADR-0265). Row C8 ("Settings") of the ChromeOS-grade scorecard:
contrast, scale and the network setting change in a settings window, apply, and are kept across a reboot.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-settings` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_SETTINGS_OK`: the sign-out gate is green on the same serial; on the first boot (no record, a NIC
attached) window 2 opens from a press on launcher button 2, three pointer clicks on the lines of its body change the three settings
(contrast, scale, network), each change is written to the
volume with readback and the status area goes from ONLINE to OFFLINE; on the second boot of the same volume the stage reads
`valid=1 contrast=1 scale=125 net=1`, opens the window showing those values, writes nothing and draws the frame the model gives for
them; all 10 `AIUEOS_GUEST_BROWSER_SETTINGS` frames equal the frame model's.

## Decision

- Window 2 is the settings app: its title slot says `Settings` (also launcher button 2's label) and its body is rebuilt from the
  settings after every key: `Contrast: Normal|High`, `Scale: 100|125|150%`, `Network: On|Off`.
- F5 (evdev 63) flips the network setting, a flag the settings stage holds in C (1 = off; no surface word is free, and 2044 / 2045 are frame2's scratch). The shell treats the network as off: the status area (ADR-0266)
  says OFFLINE whatever the adapter reports.
- The settings record (sector 1034) carries it: the word that holds the scale also holds 256 when the network setting is off.
- The lines of the body are the controls: a press on the Contrast line flips the contrast, on the Scale line steps the scale 100 -> 125
  -> 150 -> 100, on the Network line flips the network setting (C hit-tests the window record's body rect and applies it; the settings
  are C's facts, as the pointer and the clock are). F10, Ctrl+= / Ctrl+- and F5 do the same from the keyboard.
- The stage opens the window by a press and release through the reducer at launcher button 2's centre -- the path a pointer press
  takes -- so the window is opened the way the launcher opens any app.

## Not

The network setting is a shell flag: it does not power down or reconfigure the adapter, and Wi-Fi is not here. The controls are
lines of text, not drawn buttons (no hover or pressed look). The record is applied at the settings stage, not at boot.
