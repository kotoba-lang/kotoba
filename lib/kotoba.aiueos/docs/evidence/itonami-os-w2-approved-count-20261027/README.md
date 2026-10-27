# Itonami OS W2 slice: the "Approved" count on the home is live (2026-10-27)

What changed: the Itonami home line "Approved: n" showed a fixed `0`. It now
shows the number of Allow decisions on the W1 consent surface this boot
(capped at 9 on screen). Word 2039 carries the consent flag in bit 0 and the
count in bits 1 and up; `desktop.kotoba` adds one on Allow and keeps it on Deny.

Evidence: `native-consent-qemu.json` (QEMU TCG, Apple Silicon host,
`--profile consent`, signed kernel-v3 compiler 4350f3ba). Event
`pointer-allow` records `approvedCount` 1 and the columns of the only changed
pixels in the Approved band (x 268..273 of the frame). `approved-0.png` is the
frame before the Allow click, `approved-1.png` the frame after.

Also passing with this change: desktop GPT and ISO (`--profile desktop`),
`--profile local-draft` (12 events) and `--profile idle` (4 events).

Limits: input is synthetic, so it proves no human consent; the count is
display state that grants nothing and is not persisted; DID and wallet lines
are still static (`none`); the count resets on boot. W2 stays open: the strip
is not yet in the launcher row and does not show DID/wallet state. This is a
source change and a built candidate with a QEMU result; it is not deployed.
