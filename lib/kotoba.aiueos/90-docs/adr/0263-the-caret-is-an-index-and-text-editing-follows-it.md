# ADR-0263 — The caret is an index, and text editing follows it

Date: 2026-10-23

## Status

Accepted. Adds the `guest-browser-text-edit` gate; no new floor. Row D6 ("Text editing") of the ChromeOS-grade
scorecard has its procedure -- caret, selection, delete, word movement, line start/end, undo -- run end to end in the
reference VM.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-text-edit` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_TEXT_EDIT_OK`: the keyboard-only gate is green on the same serial, the seventy-two
`AIUEOS_GUEST_BROWSER_EDIT` lines equal the frame model's (the model has its own statement of the editing rules and
draws the frame: ops, ink census), and the text and caret at the steps that name a rule are what the rule says.

Not, and stated here rather than at the end: a caret placed by the pointer, Up and Down, a composition at the caret in
the middle of the text (the first letter of a Japanese composition puts the caret at the end), more than one undo
step, redo, and a text longer than the body's 64 code points. Direct typing is English mode; Space and Enter now
insert a space and a line break there.

## Decision

Until now the caret was always at the end of the body and a selection was the last k code points. Both were true of
every state the object could reach, which made Left, Home, Ctrl+Left and undo impossible. The editing state is now:

- word 2004: window id * 128 + caret + 1 (0, or another window's, means the end);
- word 2005: the selection's anchor + 1 (0 none) -- with the caret it bounds the selection, either way round;
- word 2036 (the window it belongs to) and 2037 (its length) as before, so ADR-0240's readers are unchanged;
- word 2006: the undo record -- the window, a kind (text was inserted / text was deleted), an index, a length and
  where the caret goes; the deleted text (up to 32 code points) waits in the preedit buffer, which composing would
  overwrite, so composing forgets the record.

`browser-ime.kotoba` inserts, deletes and pastes at the caret (the body shifts), keeps the caret as a position,
and takes Left / Right (collapsing a selection to its near edge), Home / End (the caret's line, lines being separated
by 10), Delete, Ctrl+Left / Right (the start of the word at or before the caret / the end of the next word), the
same with Shift (extend), and Ctrl+Z (undo the last edit of the window once: a run of typed code points is one step).
`browser-frame2.kotoba` draws the highlight over the span [lo, hi) and the caret where the layout reached its index
(`cap`, in `place-body`, and at a line break in `pack`); at the end it draws it where it always did. With the caret at
the end and the selection ending there every earlier frame is bit for bit what it was: all the earlier gates (caret,
selection, clipboard, type, preedit) are green on the same boot.

## Measured

Seventy-two keys on the clean session's empty window: "ab cd" typed; Home, Right Right; Ctrl+Right (caret 5),
Ctrl+Left (3); Left; x typed at the caret ("abx cd") and Ctrl+Z (back to "ab cd", caret 2); Shift+Right twice
(selection 2,4), Backspace ("abd") and Ctrl+Z ("ab cd", caret 4); Delete ("ab c"); Enter and e ("ab c" / "e", caret 6);
Left Left (the caret on the line break), End (4), Home (0), End (4), Right (5), End (6); Shift+Home (selection 5,6)
and Left (collapsed, 5). Every line equals the model's.

## Still open

The pointer's caret and selection, Up and Down, a composition at the caret, a stack of undo steps and redo, and the
pixels.
