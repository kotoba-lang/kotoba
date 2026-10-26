# Native Itonami desktop: passwordless QMP debug readback

On 2026-10-26, the macOS host ran the local-draft AIUEOS image under
QEMU TCG with `-display none`, `-nic none`, and a local Unix QMP socket.
No VNC login or manual guest action was used.

The independent cold-process gate reported
`PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE`: commit generation 1, restore,
uncommitted power loss, commit generation 2, and seven corrupt/missing-media
refusals. See [native-draft-restart.json](native-draft-restart.json).

The live QMP observer read the same kernel's desktop context and framebuffer.
Its expected goal, focus, draft availability, and generation all matched;
see [qmp-pass.json](qmp-pass.json). A deliberately wrong expected focus
returned exit 1 and a `FAIL` receipt with expected 1 and actual 2;
see [qmp-negative-control.json](qmp-negative-control.json). The framebuffer
captured in the workspace showed the Itonami card with `Goal local:`.

A second attachment to the still-running :5902 VM sent `2` through QMP and
passed all four state assertions with no VNC login or manual key press.
Its [live receipt](qmp-live-20261026.json) records `focus=2`, `keys=3`,
`framesStarted=frames=4`, `draftEnabled=1`, `generation=0`, and exact goal
`Goal local:\n`. The [captured image](qmp-live-20261026.png) shows the
Itonami card and blank local goal editor. The shell sandbox needed permission
to connect to the local QMP socket; no guest authentication was involved.

The kernel SHA-256 in all receipts is
`38872271cda98dfdd5482ef06451f99b3dd9ac15e1bb5fd9b9aec8a8af993801`.
This proves the local diagnostic desktop path, not a registered Itonami dapp,
full agent loop, physical hardware, or Linux-free build producer.

The [QMP stdio gate](qmp-stdio-gate.json) reran the same 11 guest cases with
the headless controller using private pipes instead of a Unix listener. It
returned `PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE` in the default local sandbox,
without a VNC login, password entry, manual key press, or socket-bind approval.
The receipt pins the updated observer source and the same kernel, EFI, media,
and firmware digests.

The [one-shot stdio observer](qmp-stdio-once-pass.json) launched a new VM in
the default local sandbox with `-display none`, `-nic none`, no VNC endpoint,
and no QMP listener. It used an output-owned mode 0600 draft fixture inside
a mode 0700 directory, sent `2`, `a`, `b`, and returned `PASS` in 5.1 seconds.
The guest reported `Goal local:\nab`, focus 2, three keys, four completed
frames, draft enabled, generation 0, and restore/commit codes 0.
The [guest screenshot](qmp-stdio-once-pass.png)
shows the actual Itonami card and `ab`. The receipt pins observer source SHA-256
`878bb584f2e079c95d10f147160b2245e34a97c9fcd41e295659432ca5d23fb2`,
kernel SHA-256, boot-media SHA-256, and screenshot SHA-256.

The [wrong-focus control](qmp-stdio-once-fail.json) sent `2` but expected
focus 1. It exited 1 with `FAIL`, actual focus 2, and a captured framebuffer.
The [missing-disk control](qmp-stdio-once-no-disk.json) expected restore code
0 but observed `-22` and exited 1. `draftEnabled=1` alone is the opt-in
profile switch, not proof of an attached medium.
Sending F5 without `--allow-draft-write` exited 2 before starting QEMU or
creating an output directory. This one-shot route is for diagnostic UI work;
the independent cold-restart gate above remains the persistence proof.

The short `--build-dir` route then resolved media, EFI, kernel, QEMU and OVMF
from one native build and the local QEMU installation. Its
[receipt](qmp-build-dir-pass.json) pins observer SHA-256
`1f8580d8c8b04dc897dae53d98e3f77e8e6b77548341b1f89ff3f0bf2d02319e`
and reports PASS: key `2` opened Itonami, `a` and `b` produced exact
`Goal local:\nab`, focus 2 and four completed frames. The
[guest screenshot](qmp-build-dir-pass.png) independently shows that text.
QMP used private stdio, with no VNC, network or human authentication.
