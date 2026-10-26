# ADR-0264 — The launcher row shows the clock

Date: 2026-10-23

## Status

Accepted. Adds the `guest-browser-clock` gate; no new floor. Row C9 ("Status area: network, power, clock") of the
ChromeOS-grade scorecard gains its first third in the QEMU-level evidence and stays `:partial`: the clock is a real
status, the power and network states are not yet.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-clock` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_CLOCK_OK`: the text-edit gate is green on the same serial, the machine's clock reads
back as it was set (`CLOCK_RTC set=12:34 read=12:34`), both `AIUEOS_GUEST_BROWSER_CLOCK` frames equal the frame model's, and
the clock frame is the other frame plus the five glyphs of HH:MM.

Not, and stated here rather than at the end: a power state (AC / battery) -- the kernel's ACPI code reads the MADT and
a few security tables, not the DSDT or a battery device, and a VM has no battery; a network state -- the desktop stages run
before the network comes up, so only whether an adapter exists could be said, not whether the machine is online; a clock
that follows the minute (C reports the time when a frame is drawn; the production loop does not yet call the reader each
minute); time zones.

## Decision

C owns the fact, Kotoba the drawing, as for the pointer and the button state.

- `kernel/main.c`: `rtc_minute_of_day` reads the CMOS real-time clock (registers 0x02 and 0x04 through ports 0x70 / 0x71,
  BCD or binary and 12 or 24 hour as register B says, waiting out an update in progress) and the stage reports the minute of
  the day + 1 in surface word 1968 (0 = nothing reported, nothing drawn). The stage first sets the clock to 12:34 -- the test
  hook that makes the frame knowable -- and reads it back, which also proves the write and read paths agree.
- `browser-frame2.kotoba`: `clock` draws HH:MM in the ink from (vw - 48, 6), at the right end of the launcher row, after the
  buttons. The op capacity is 248 (words 1968..2003 are free; 1968 is this status word).
- The frame model states the same glyphs independently.

## Measured

The launcher-row frame without a status word: 77 ops. With the clock at 12:34 (status word 755): 82 ops, 755 ink pixels
(668 before) -- five glyphs and their pixels, equal to the model's.

## Still open

The power source and battery (a DSDT / battery device read), the network state (the stage order, or a status read after the
network is up), refreshing the clock each minute in the desktop loop, and the pixels.
