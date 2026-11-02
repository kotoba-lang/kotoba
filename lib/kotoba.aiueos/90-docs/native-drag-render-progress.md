# Native drag latency work (JUN-502, 2026-11-02)

The owner reports severe window-drag lag on the 6600H. Movement works; smooth
interaction is not accepted. PXE and the existing Mac SSH management bridge
remain available. HHKB physical testing remains paused.

The first checked unit adds numeric native renderer profiling. Effects words
88–127 hold raw TSC phase counters, last scene timings and frame counts, without
growing the 16 KiB grant. The component gate checks the adjacent motion-state
sentinel at word128. Signed debug command17 exposes only these numeric fields
and the calibrated cycles/ms value at tags c380–c397, followed by c011 with the
request counter. `aiueos-remote.py ... render-stats` refuses an incomplete reply.
This is an opt-in debug operation, not an OS-native SSH implementation.

The profiler separates scene generation, damage, composition and retained-op
cache copying; inside composition it separates tile raster from GOP transfer.
Raw cycles are not physical input-to-display latency. The clock is convertible
only when its guest PIT calibration is valid. Source and QEMU/physical evidence
must remain separate.

The initial profile build exceeded the fixed RX limit by 8609 bytes (E7104,
detail2105761). Nineteen existing public Bluetooth SC KAT literal tables were
packed into u32 constants with explicit bounds preserving their default zero.
No test was removed and no compiler/layout/memory allowance grew. All 369 public
bytes, all 1216 selector/padding bytes and 38 out-of-range results match the old
literal fixture in native QEMU execution. The old literal source digest is
recorded in the checked-in fixture data. The full profile has exactly44 modules;
the builder now checks44 instead of43, with its other receipt checks retained.

`check-native-drag-profile-qemu.py` executes24 actual USB-mouse drag samples:
one/four windows with normal/reduced effects, six drags per case. It checks
press/release, geometry, packet consumption, native phase/frame counters,
ordinary tiled composition and four pixel comparisons against the forced full
reference painter. Final v5 passes all24 and all four comparisons. The final
profile component gate also passes; the preceding v3 full product passes the
standard12 USB/NVMe checks. V5 adds per-tile timings and retains an exact-source
compile/reproduction plus its component/drag gates; those boundaries are not
collapsed into a single full-release claim.

Baseline QEMU viewport is1280×800, while the last physical screenshot was
800×600. Median guest scene times are approximately445ms (one window, normal),
443ms (one, reduced),841ms (four, normal),832ms (four, reduced). In the normal
one-window case, raster is268ms and transfer152ms; with four windows raster642ms
and transfer151ms. Composition accounts for almost all frame time. These are
diagnostic guest timings, not measured physical latency or a ChromeOS comparison.
The next changes target redundant raster work and per-pixel GOP transfer.

Documentation discrepancy: existing JUN-502 text described F10 as reduced
effects. The actual reducer uses scancode59/F1; scancode68/F10 opens the
device-key Forget request. The first observer passed six drags and its pixel
control, then stopped on that incorrect shortcut assumption. It was corrected
to F1; F10 was not sent to the physical6600H. Key assignments were not remapped.

Receipts: `docs/evidence/jun502-drag-profile-20261102/`. No profile candidate has
been deployed by this unit, and no improvement or physical smoothness is yet
claimed. The goal remains open until the remaining roadmap gates also pass.

## Page-span transfer candidate

The next candidate removes per-pixel GOP reads/page resolution/comparison. It
copies each completed tile in page-bounded spans, pairing aligned pixels into
u64 stores and retaining a u32 tail. Only completed final pixels reach GOP.
This writes every core tile pixel, including unchanged values; tileStores
continues to count actual pixel stores, so its volume increases. No intermediate
layer is exposed. No allocation or ABI expansion is used.

The exact44-module candidate passes USB/NVMe12, all24 drag samples/four pixel
controls, and all12 pointer/compositor scenarios including clipped edges,
window overlap, dock materials and modal pointer movement without approval.
The observer now also retains its owned VM handle if its constructor fails.

QEMU transfer medians change from152/151ms to141/147ms (one/four normal
windows), while total scene medians are439/869ms against445/841ms baseline.
These samples do not establish an overall drag-speed improvement; four-window
raster work remains dominant. The change avoids hardware framebuffer reads,
but its physical benefit and the effect of additional stores require direct
measurement. Physical smoothness is not accepted. Further raster/damage
reduction remains necessary if hardware measurements do not close the gap.
