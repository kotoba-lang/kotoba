# Unified Amu user ELF to AIUEOS guest, unattended (2026-10-26)

The [Mac native build receipt](build.json) used one F1=F2 Amu compiler
(signed SHA-256
`e4c2e427b7c37651e313d5980fe449d1a577dae044182e8b45abf29d659122fd`)
that had generated both the user-v2 ELF and its AIUP v2 slot. It rebuilt
the 31-module kernel and dual EFI with that slot. The kernel and EFI were
byte-identical to the previous separately generated candidate: SHA-256
`b62438f3604438a9bf2e97851fbaf131f28f7a1f42b7aac44fe19e3a164cea6f`
and `7682a44f81d7b96238ae3ef6f8bb0fd63de7d3ed4693cdbb7feea3805a28edd4`.

The [four-boot QMP receipt](qmp.json) entered `native chain` and `hello`
through the guest Itonami desktop. The compiled ELF returned `12` and `5`
at CPL3. Empty Enter left the request page unchanged at CPL0. A one-byte
change in the EFI user slot left both user pages unchanged at CPL0. The
[guest screenshot](native-chain.png) shows the typed Goal. QMP used private
standard I/O; there was no NIC, VNC listener, password or human key press.

Repeat the guest check with the matching Mac build directory:

```sh
python3 os/aiueos/scripts/debug-native-user-v2-unattended.py "$BUILD" \
  --goal 'native chain'
```

This is an integrated native build and VM diagnostic. It does not qualify
signed general admission, fresh per-operation approval, real model/tool
turns, durable recovery, release or physical hardware.
