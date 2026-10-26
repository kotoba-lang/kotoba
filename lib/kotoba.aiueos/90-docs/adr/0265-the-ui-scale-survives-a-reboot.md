# ADR-0265 — The UI scale survives a reboot

Date: 2026-10-24

## Status

Accepted. Extends the `guest-browser-settings` gate (ADR-0260); no new floor. Row C8 ("Settings") of the ChromeOS-grade
scorecard stays `:partial`: contrast and scale are kept now, there is still no settings window and no network setting.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-settings` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_SETTINGS_OK`: the first boot (no record) takes six keys -- F10, then Ctrl+= -- and writes
the record twice with readback (contrast, then contrast + 125 %); the second boot of the SAME volume reads
`valid=1 contrast=1 scale=125`, applies both before its first frame and is sent only Alt, writes nothing, and both boots'
final frames equal the frame model's 125 % high-contrast frame (`244cc84c`, 77 ops, 1757 ink pixels).

## Decision

- The settings record (sector 1034, `AIUESET1`, version 1) keeps its 20-byte layout: the word that was reserved (always 0)
  now carries the scale in percent. 0 in an older record reads as 100; any value other than 0, 100, 125 or 150 makes the
  record invalid ("no settings"). The checksum covers it as before.
- `aiueos_settings_read(&contrast, &scale)` and `aiueos_settings_write(contrast, scale)` (write requires readback of both).
- The settings stage applies a stored scale before the first frame (`aiueos_desktop_set_scale`, the logical viewport, a
  refit key to Kotoba as the scale stage does), and writes whenever contrast or scale differs from what the volume holds.
  It expects 2 keys when a record was found and 6 when not (the host's phase 1 sends the extra four).

## Still open

A settings window (the choices are keys), a network setting, applying the record at boot rather than at the settings stage,
a reset, and device-level receipts for this row beyond the QEMU VM.
