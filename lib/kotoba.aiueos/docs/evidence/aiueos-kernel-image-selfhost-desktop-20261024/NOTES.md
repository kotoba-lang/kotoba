# selfhost kernel object: GOP desktop input response + screenshots (JUN-31, 2026-10-24)

Same tree as `aiueos-kernel-image-selfhost-20261024/`, guest-browser profile
(`AIUEOS_GUEST_BROWSER=1`, real virtio-keyboard + virtio-tablet via QMP
injector, `synthetic=0`). Object: selfhost-built `kernel-probe-abi.o`
(`0e04108e…`, 841 B, `kotoba_aiueos_probe`) — the same object the previous
tick linked into KERNEL.ELF.

## Measured (this run)

* **Image**: `build-uefi.sh` (guest-input profile) → `KERNEL.ELF`
  sha256 `74b3e4e18b533a596dc11a8127194c1bb8f4546009756b16b3531ebbf499f6d4`
  (823,944 B). Containment byte-proven: the object's 74-byte `.text` is at
  file offset **325888**, identical except the link-time relocation
  `lea r9,[rip+0x75741]` (previous synthetic-profile build: offset 324461).
* **Desktop input response (this image, first time)**: serial log shows
  `AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0`,
  `AIUEOS_GUEST_BROWSER_INPUT_OK kind=pointer-down px=60 py=50 hit=1`,
  then every stage answered: `TYPE_OK presses=19 committed=5`,
  `PREEDIT_OK`, `IME_TOGGLE_OK presses=7`, `DICT_OK keys=16 committed=23665,20767`,
  `DRAG_OK answers=111100`, `RESIZE_OK clamp=120x80`, `LOOP_OK frames=9`,
  `CARET_OK caret=418,214`, `LAUNCH_OK windows=2`, `CURSOR_OK at=1000,600`,
  `FOCUS_OK stack=132`, `SCROLL_OK`, `SELECTION_OK max-sel=2`,
  `CLIPBOARD_OK copied=3 pasted=3 refused=1`, `DAMAGE_OK`, `UIUX_OK`.
* **Screenshots** (QMP `screendump`, 1280x800): `screens/guest-browser-typed.ppm`
  `61150847…`, `screens/guest-browser-preedit-committed.ppm` `dc45d0e6…`,
  `screens/guest-browser-drag.ppm` `ffd59811…`, `screens/guest-browser-selection.ppm`
  `b15e8709…`. 116 screenshots were captured in total (all input stages); these
  4 are the committed representatives.
* The run was cut by this tick's 240 s wall (`GUEST-NO-EXIT after 242s`) during
  the KEYS/MAX stage — before `FLOW_OK` and before the process phase.

## Stall attribution (the previous tick's open question, answered)

* **Control boot, committed `os/aiueos/kotoba/kernel-probe.o` (default, sha-pinned
  `3f7409bf…`), synthetic-input profile**: reproduces the SAME stall —
  `HOST-FLAKE-SIGNATURE … last serial line:
  AIUEOS_KOTOBA_ELF_PROCESS_OK source=catalog apps=2 et-exec segments=rx,rw
  result=42 domains=4,5` after 124 s. **The stall is not attributable to the
  selfhost object or the object route** — the committed object stalls the same
  way in the same profile. (Retry attempt 2 was still running when this tick's
  budget ended; its outcome is unmeasured.)
* Guest-input-profile control (committed object): full desktop input response
  too (`…_MAX_CTL_OK` reached), also cut at 242 s by the same wall. Its QMP
  screenshots were **deleted before archiving** (an errant `rm -f build/aiueos/*.ppm`
  in this tick); the serial + verdict survive in the run log and the
  screenshots are regenerable — not claimed here.

## Boundary (say this, do not round it up)

* `kernel/*.c` is still compiled by zig cc; the C-free claim covers the
  compiler lineage and the kotoba object route only.
* `FLOW_OK` / `guest-browser-flow.ppm` for this image and a boot that passes the
  process phase (`AIUEOS_KOTOBA_ELF_PROCESS_OK` and beyond) are **not** captured
  this tick — the 240 s run wall ended both guest-profile runs mid-input-flow,
  and the synthetic-profile runs stop at the process-phase signature.
