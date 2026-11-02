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

## Conservative sparse damage candidate

The next candidate uses a576-bit 64×64-cell mask in effects16312..16383,
after the cursor save-under16000..16311. Effects83/85 hold enable/columns;
no cache, cursor, audio or blur range overlaps. Larger displays, full
invalidation and pathological blur chains retain dense fallback. Tile rows
stop at cell boundaries, skip clean cells and coalesce only marked runs.

Only identical-position-in-list opaque paint is considered: kind1 constant
rectangles, kind7 rounded rectangles with a conservative12px inner inset,
and kind6 vertical gradients when y is unchanged or both endpoints match.
Other changes mark both complete boxes. Code review caught the initial
incorrect assumption that kind6 was constant; that v2 artifact was never
deployed, and v3 contains the explicit gradient restriction.

The first sparse build exceeded the unchanged RXcap by5937 bytes. Existing
public SC KAT constants are now packed in u64 words, and two existing HID
descriptor vectors in u32 words. Native21-module component execution matches
the same369 SC bytes/1216 selector bytes/38 bounds, plus139 HID bytes/160
selector bytes/4 bounds. The original literal digests remain in fixtures.
No test, feature, ABI or memory allowance was removed or expanded.

The exact44-module v3 reproduces ELF/EFI, passes USB/NVMe12 and PXE hub
keyboard/mouse smoke, and passes24 USB drags with28 full-reference pixel
comparisons. The observer now compares each held-button drag frame, so an
alternating six-step round trip cannot hide a transient rendering error.
Normal one/four-window QEMU scene medians are343/391ms, raster227/302ms,
copy86/46ms. Actual core pixel stores per sample fall from505197 (span) to
243053/136557. Timing is diagnostic: the observer changed and other gate VMs
also ran. It is not a controlled physical speed or ChromeOS comparison.

The separate physical profile-v5 baseline boot is observed from one-shot PXE
transfer, fresh signed ping, USB0504 resume15 and Goal aba cold readback.
At800×600, six four-window focus switches have median scene544.50ms,
raster94.89ms and GOP copy443.75ms; reduced effects517.98/76.00/436.55ms.
These are PIT-calibrated TSC CPU phases for app/focus switching, not drag or
input-to-panel latency. They show why removing GOP reads needs physical
verification. Sparse-candidate deployment and human drag acceptance are
separate remaining gates.

## Physical scene comparison, drag acceptance pending

The exact sparse-v3 PXE/netlog image626e4ee1…5de2f9 is now running on the
6600H (source0fc8842e3, kernel10225112…4f200d). TFTP completion and one-shot
consumption, a fresh signed ping, USB0504 result15 and visible Goal aba cold
restore are observed. No OS image was installed into NVMe; PXE fallback and
Mac SSH bridge remain. The same four-window focus-switch sequence (six per
mode) changes normal scene median544.50→205.03ms, GOP copy443.75→99.47ms,
raster94.89→99.21ms. Reduced mode scene517.98→183.44ms, copy436.55→98.66ms,
raster76.00→78.67ms. This establishes less CPU time for this physical scene
sequence, particularly GOP transfer, with no raster-speed claim. It is not
a drag or panel-latency measurement. No ChromeOS same-hardware timing exists.

The separate existing12-scenario pointer/compositor gate also passes on the
exact candidate, including dock icons, overlap drag, viewport clipping and
modal pointer movement without granting approval. The owner has been asked
once to judge actual Trackpad drag and residual Window/Dock flicker. No
acceptance answer has arrived yet, and JUN-502 remains open.
