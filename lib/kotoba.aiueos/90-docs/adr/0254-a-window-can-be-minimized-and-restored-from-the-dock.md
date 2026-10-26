# ADR-0254 — A window can be minimized and restored from the dock

Date: 2026-10-23

## Status

Accepted. Closes the `:minimize` floor (ladder: 32 floors, 30 gated). Row C5 ("Minimize,
and a list of open windows") of the ChromeOS-grade scorecard (docs/chromeos-scorecard.md)
goes from `:none` to `:partial` in the QEMU-level progress; its score stays 0 until the row
passes on the real machine.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-minimize`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_MINIMIZE_OK`: the pressed-state gate is green on the same
serial, `AIUEOS_GUEST_BROWSER_MAX n=35..40` and `AIUEOS_GUEST_BROWSER_MIN n=35..40` equal the frame
model's, and, apart from the model, the minimized frame is smaller than the frame before it, the press
where the window was does not answer window 1, and the restored frame has the op count the frame before
the minimize had.

Not, and stated here rather than at the end: a list of open windows with their titles (the dock
is the only list, one icon per app), an animation, a keyboard minimize (Alt+- in the reference),
a minimized window in Alt+Tab, the control shown when it is the only visible window.

## Decision

Window state is Kotoba's. The minimized register is surface word 31 bits 4..7 (bit 3 + id for
window id 1..4); the app register keeps bits 0..3, so the 128-byte state needs no new word and
every reduce call, including the 128-byte one, sees it. `browser-reduce.kotoba`:

- `inside` answers 0 for a minimized window: a press goes through to the window under it, and
  the topmost-first hit, the resize handle and the pointer cursor never see it.
- a press on the minimize control -- 16 x 16 at (x + w - 64, y + 6), left of the maximize control,
  on a window at least 200 wide while two or more windows are visible -- raises the window, sets
  its bit and gives the focus to the topmost window that is not minimized; the answer is that window's id.
- a press on the dock icon of a minimized app (36 x 36 at (vw - 184) / 2 + 8 + 44 (k - 1), vh - 46)
  clears the bit and raises and focuses the window; the dock is above every window, so it wins.
  A launcher button of a minimized app does the same.
- a close that would leave no visible window is refused (-8, as the last window always was), and a
  close gives the focus to the topmost window that is not minimized.

`browser-frame2.kotoba` does not draw a minimized window, draws the control (a face and a bar 8 x 2 in
the icon colour, hot and pressed like its neighbours) and shortens the title clip by 20, and draws a bar
12 x 3 under the dock icon of a minimized app. `browser-ime.kotoba` makes Alt+Tab raise the bottom-most
window that is not minimized. The state size check in both objects now admits word 31 up to 255.

Earlier frames change only in the op count (each visible window at least 200 wide with a launcher
gains the control's two rects, +2 per window); the ink census (text pixels and hash) is unchanged because
the control is drawn in the icon colour, not the ink -- every earlier pin was re-derived from the frame model,
whose old and new output differ by exactly that.

## Measured

The kernel stage grew from 34 to 40 events: the press on the minimize control at (456, 146)
(window 1 leaves the list: 192 ops to 133, focus 4, the dock icon 1 carries its bar), a press at
(380, 142), where window 1 is (answers window 4, which is raised: stack 314 -- not window 1), and a press on
app 1's dock icon at (574, 772) (window 1 returns on top: 192 ops again, focus 1, stack 341); each followed
by the release.

## Still open

A window list with titles, an animation (the reference animates), keyboard minimize, Alt+Tab to a minimized
window, a dock icon for an app with no window, and the pixels (the gate reads the draw list).
