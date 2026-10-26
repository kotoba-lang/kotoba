# ADR-0272 — Sound output and a volume key

Date: 2026-10-24

## Status

Accepted. Adds the `guest-browser-audio` gate; no new floor. Row I4 ("Audio output": play a sound, change the volume; the sound plays at the set
level) of the ChromeOS-grade scorecard.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-audio` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_AUDIO_OK`: the backup gate is green on the same serial (so is the whole chain before it); the guest played a tone
burst at volume 100, took the volume-down key twice (100 -> 75 -> 50) and played it again, the device accepting every buffer; AND the host,
measuring the WAV file QEMU's sound card wrote, finds two bursts of about 0.4 s at 440 Hz, the first near full scale and the second at 0.45..0.55 of
the first's RMS. The measurement is the host's, not the guest's word.

## Decision

- `pci.c` gets a polled virtio-sound driver (device 0x1059): control queue 0 (set-params, prepare, start, stop, release) and tx queue 2, 16-entry
  rings of its own (the shared virtq structs hold four), 44100 Hz stereo S16, three-descriptor tx chains of 3072 data bytes, up to four in flight.
  It is compiled only into the guest-browser build (`AIUEOS_AUDIO`); other builds carry stubs.
- The stage (`main.c`, size build only) makes the tone from a 64-step sine table, scales it by a volume held in C (evdev 114 volume-down: -25,
  115 volume-up: +25) and plays two bursts of 0.1 s silence, 0.4 s tone, 0.1 s silence.
- The smoke harness attaches `-audiodev wav,...,path=$out/audio.wav -device virtio-sound-pci` when `AIUEOS_TEST_AUDIO=1`; the runner hands the file
  to the classifier, which parses the RIFF, windows it at 20 ms, finds the bursts and measures RMS, duration and the frequency between the first and
  last rising zero crossing.

## Not

The volume is a software gain in the stage, with no mixer, no on-screen indicator, no mute and no device choice; one output stream; no input
(microphone); no decoding of any audio format (E6, playback, is not here); a VM's sound card writing a file, not a speaker.
