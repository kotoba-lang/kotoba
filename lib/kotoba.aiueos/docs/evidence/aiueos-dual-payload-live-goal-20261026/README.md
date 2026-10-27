# Dual-payload Itonami Goal to CPL3, unattended (2026-10-26)

The Mac native [build receipt](build.json) binds 31 Kotoba modules, a
fixed-point Mac Amu compiler, the AIUF desktop font and an AIUP v2 user ELF
slot in one EFI. The EFI SHA-256 is
`7682a44f81d7b96238ae3ef6f8bb0fd63de7d3ed4693cdbb7feea3805a28edd4`.
The guest checks the slot header and fixed whole-ELF SHA-256 before copying
the compiled code into its CPL3 page. This kernel entry does not use the
earlier inline diagnostic program.

The [private-QMP receipt](qmp.json) is a fresh four-boot readback. The
[unattended debugger](../../../os/aiueos/scripts/debug-native-user-v2-unattended.py)
typed `debug run` and `hello` through Itonami. Their compiled user program
returned `9` and `5` at CPL3. Empty Enter kept the request page untouched
at CPL0. Changing one code byte in the EFI user slot kept both user pages
untouched at CPL0. The [guest screenshot](debug-run.png) shows the typed
Goal. The [one-command summary](debug-summary.json) records the output
paths. QEMU had no NIC, VNC listener or password; QMP used private standard
I/O, with no human key press.

Repeat from this checkout with the matching Mac native build directory:

```sh
python3 os/aiueos/scripts/debug-native-user-v2-unattended.py "$DUAL_BUILD" \
  --goal 'debug run'
```

The command validates build receipt hashes, uses the staged font and slot,
extracts the pinned ELF, and creates a new private observation directory.
It does not grant an app operation. Signed general admission, fresh
per-operation approval, real model/tool turns, durable recovery, release
and physical qualification remain open.
