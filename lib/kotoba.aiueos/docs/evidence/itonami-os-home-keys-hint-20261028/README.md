# Itonami home: a keys hint line (2026-10-28)

The Itonami home gains one read-only line, `Keys: 1-4 apps, F9 fold, Esc close`,
so the shell's keyboard controls can be found without reading source. Each
named control exists and is exercised by the QEMU gates: digits open apps
(`sendkey 2` opens Itonami), F9 rolls the focused window up (consent gate
`collapse-key`), Esc closes the focused card (desktop gate
`keyboard-closes-focused-card`).

Evidence: `native-consent-qemu.json` (QEMU TCG, Apple Silicon, `--profile
consent`, signed kernel-v3 compiler 4350f3ba): event `pointer-allow` records
`keysHintInk`; the gate asserts the band carries ink and the band below stays
blank. `home-after-allow.png` is the frame. Desktop GPT+ISO, local-draft (12
events) and idle (4 events) also pass.

Limits: synthetic input; static text, not generated from the key table, so it
must be edited with it. Source change and built candidate with QEMU results;
not deployed.
