# ADR-0273 — Suspend to idle and resume

Date: 2026-10-24

## Status

Accepted. Adds the `guest-browser-suspend` gate; no new floor. Row I1 ("Suspend and resume": close the lid, open it; the session resumes in
under 3 s with state intact) of the ChromeOS-grade scorecard, for suspend-to-idle.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-suspend` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_SUSPEND_OK`: the audio gate (and the whole chain before it) is green on the same serial; the kernel prints
`SUSPEND_GO`, `SUSPEND_ENTER screen=black` and `SUSPEND_RESUME ... frame-intact=1 state-intact=1` with equal frame hashes and equal
fingerprints of the 2048 surface words before and after; AND the host's own evidence holds: its screendump while asleep is all black, its
screendumps of the awake desktop before and after are byte-identical (equal SHA-256), and the time from the wake key to the guest's RESUME line is
under 3 s.

## Decision

- The "lid" is the sleep key (evdev 142) and the "open" is the wake key (143): QEMU has no lid switch. The stage (`main.c`, size build only):
  draws the desktop and fingerprints the surface, waits for the sleep key, blanks the screen with one black rect over the whole surface and idles
  in `sti; hlt; cli` taking no input but the wake key, then redraws the desktop from the same surface and fingerprints it again.
- The resumed frame is held until the host has taken its screendump (the host sends F1); the persistent desktop that follows would otherwise draw
  its own frame over it (found when the first run's "after" screendump showed that desktop).
- The host (`smoke-qemu-uefi.sh`) takes the three screendumps by QMP and times the wake; the runner hashes them and tests the sleeping one for
  black, and hands the result to the classifier. The receipt keeps the hashes and the timing, not the 3 MB dumps.

## Not

Not ACPI S3: the RAM stays powered and no device is powered down, so nothing is saved and restored across a loss of power; the lid is a key;
the resume time includes the harness's own latency (51 ms measured); the state that survives is the desktop's surface and the machine's, with no
application restart.
