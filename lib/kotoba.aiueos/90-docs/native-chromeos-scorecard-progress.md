# ChromeOS scorecard native probe

JUN-409 moves the 65-row comparison ledger away from the historical
`scripts/chromeos-scorecard.cljk` KBB/Node checker. The current Kotoba source
is `os/aiueos/kotoba/aiueos/chromeos_scorecard.kotoba`. A signed native Amu
Mac compiler builds it, and a signed native Kotoba packager emits the test
Mach-O. The host Python script stages immutable inputs, checks source/image
identities and runs the result; scorecard semantics execute in Kotoba.

The reader takes the exact `chromeos-scorecard-v1.edn` bytes through an FS2
file capability. It skips comments and collapses EDN whitespace outside
quoted strings before the bounded native document reader parses the map.
No hosted EDN reader, JVM, NBB, Node, Graal, C compiler or Linux guest runs
in this probe. All file reads use a private FD3 root containing the scorecard
and a copy of the qualification receipt tree.

Run the probe with the pinned Amu Mac images and a **new** output directory
under `github/workspaces`:

```sh
python3 os/aiueos/scripts/probe-chromeos-scorecard-native.py \
  --compiler "$AMU_MAC_COMPILER" \
  --compiler-sha256 012bfb77a364b3b68cb5e2c406ae49535784fa2b851dfdbbe1bd10efffcb950a \
  --packager "$AMU_MAC_PACKAGER" \
  --packager-sha256 2ee308409db572c08733a4b0a28fc1908c8b15c44b045cf78e671ff798439ad0 \
  --output "$NEW_WORKSPACE_OUTPUT"
```

The current Mac images are local diagnostic artifacts from the Amu
selfhost chain tracked in [Amu #1588](https://github.com/kotoba-lang/amu/pull/1588).
The output receipt `native-scorecard-core.json` binds their digests, the
Kotoba source, the scorecard and the compiled native executable. It records
whether the source and scorecard bytes match the named Git commit.

The native probe checks the fixed reference schema, 55 required rows,
required weight 100, zero-weight optional rows, unique IDs, known categories
and levels, owner confirmation, valid status/progress, receipt presence, and
the receipt's 40-hex commit and nonempty green verdict map. A passing
`:release` or `:user` row must cite the fixed v1 signed-release receipt; that
receipt must have 64-hex signature and artifact digest fields plus the three
named green verdicts. The probe reads the referenced JSON and binary signature
as FS2 bytes and computes their SHA-256 in Kotoba; both must match the receipt
fields. This uses the pure SHA-256 source copied from Amu
`seed/03-source-sha256.kotoba` at commit `392118c8` (source SHA-256
`40be511b6879d1c4c6a4b443b796ec1ef5cbe561d5c69c6ae52b8e62a96393d1`).
Known empty, `abc`, and multiblock vectors run in the native executable.
The native verifier then checks RSA-2048 exponent 65537 and the complete
PKCS#1 v1.5 SHA-256 encoding against the JSON bytes. It adapts the bounded
calculation in `os/aiueos/kotoba/rsa2048.kotoba` to the Mac native vector ABI.
The embedded modulus matches the checked-in qualification public key; no
private key is read by this verifier. This is the v1 **qualification** key,
not a production release key. The native probe also hashes the saved primary
serial log for every referenced passing VM receipt and the secondary log where
the receipt declares one. The `settings` secondary is
`kernel-serial.log.boot1`; the install-refusal receipt uses
`boot4-serial.log` and `install-serial.log`. The exact I3 receipt uses
`scale-run-serial.log` and `scanout-two-run-serial.log`; both digests are
mandatory. Missing or modified logs fail the
ledger admission. This verifies the declared log bytes, not the truth of every
feature claim or screenshot digest in a receipt.
The earlier source-bound probe printed the then-recorded score of 48 and
category weights, passes and gaps. The current canonical EDN declares 42
passing rows of weight 71. The runner first verifies that the native checker
refuses this current input, then constructs a diagnostic 53-point subset by
demoting exactly the ten newly passing rows whose receipts still lack
native-checkable logs. The checker admits that subset. All twenty-two negative
controls run from the admitted subset (twenty-one alter input files; one uses
a different public modulus), so each refusal demonstrates a working check
rather than repeating the canonical input's baseline refusal. They cover
malformed schema, missing or red
receipts, missing signed-release reference, malformed digest fields, missing
named verdicts, one-byte artifact changes, a modified signature with an
updated matching digest, a different public modulus, and missing or changed
primary and secondary serial logs. Each must return a nonzero native result;
expected output is checked exactly.

This is a **core schema and qualification-release signature probe**. Other
receipt marker text and non-serial artifact digests are not yet checked against
the underlying log/image, and the production release signature is not qualified.
Receipt commit age and relevant-source freshness remain unqualified. The
recorded VM ledger does not qualify physical hardware or a release. The
runner and receipt name keep `EVIDENCE_PENDING` until those
gates pass. The legacy checker stays historical and must not be used for
current native qualification.

## Current ledger admission after rebasing on main (2026-10-26)

The scorecard branch incorporated main at `90cda6e6142589239a5da43867333f60fea4a343`.
The signed Mac native probe compiled and ran the same Kotoba checker against
the current canonical EDN (SHA-256
`a1bd8a8dece8ed705e652a776890742ea4de696bd3930fbf05eb7db08004462b`).
It refused the positive case with `AIUEOS_SCORE -1`. This is a failure of
current evidence admission, not a 71-point native verdict.

Thirteen rows changed from `:unachieved` to `:pass` since the 48-point
ledger. Twelve cite receipts without a `:serial-sha256` field: A2, A5,
C9, F2, G1, G3, G5, H1, H2, H3, I3 and I6. A4 instead lacked the
signed-release receipt reference required for its `:release` level. A2's
serial log is checked in, so this branch adds its observed digest to that
receipt; A4 now cites the existing signed-release receipt. With only these
two new rows left at `:pass` in a scratch copy of the current card, the
native executable accepts 51 points (the previous 48 plus A2's 2 and A4's
1). A one-byte A2 serial-log change and removal of A4's signed-release
reference each make that same native executable refuse with `AIUEOS_SCORE -1`.
The canonical 71-point card still refuses admission. The initial isolated
runs are in the private scratch directory
`github/workspaces/codex/aiueos-scorecard-rebased-probe-20261026`. The
repaired full probe passed its 51-point diagnostic input, canonical refusal,
seventeen input mutations and a wrong-key refusal with the pinned
signed Mac native compiler and packager. Its report is
`github/workspaces/codex/aiueos-scorecard-probe-subset-v2-20261026/native-scorecard-core.json`.
All of these runs are diagnostics, not a release receipt.

The next native slice binds both I3 logs to exact SHA-256 fields and admits
their names only for that exact receipt path. The signed native probe accepts
53 points in its temporary input (the earlier 51 plus I3's 2), refuses the
canonical 71-point input, and rejects missing or one-byte-modified versions
of each I3 log. Its 22 negative controls all start from the admitted input;
see `github/workspaces/codex/aiueos-scorecard-i3-probe-20261026/native-scorecard-core.json`.
I3's receipt still describes two separate runs and a 32x32 second resource,
not an extended desktop or physical monitor. Native digest admission does not
settle whether the recorded behavior satisfies the row's user expectation.

The remaining ten newly passing receipt directories have no serial log in the repository. A
read-only scan of the current local workspaces found no copies under those
receipt-specific names. The next work is to recover or rerun the actual
evidence and bind it to the current source, then extend the native verifier
only for evidence formats that can be independently checked. The declared
71 points remain separate from native qualification and release acceptance.

## Historical 48-point ledger audit before the main rebase (2026-10-26)

A read-only host diagnostic inspected that earlier ledger's 31 receipt
references (14 distinct files). The 17 checked digest fields for adjacent
serial logs, WAV files, the qualification signature, and the signed JSON
receipt matched their files. The qualification release signature also passed
the existing host verifier with the checked-in qualification public key.
These observations are independent of the native scorecard probe and do not
make the release-production signing key or release gate qualified.

Six VM receipts name feature commits which are known locally but are not
ancestors of this branch's source commit: `ui`, `audio`, `backup`, `layout`,
`notify`, and `passkey`. Twenty-one `:pass` rows, weighing 33 of the ledger's
48 recorded points, reference at least one of them. Later squash merges may
contain those changes, so ancestry failure alone is not a failed feature.
The files changed by each original feature commit have since changed again;
the old receipts do not prove the present source at this branch's commit.
Rerun the affected gates against the selected release source before promoting
their points from recorded VM evidence to current-release evidence.

The six receipts' screenshot maps contain 117 distinct PPM names and no
conflicting hashes. A read-only check found all 117 files in local diagnostic
output `github/workspaces/claude/aiueos-gate/out31` and matched every declared
SHA-256. The image bytes are outside this repository and are not a durable
release evidence bundle. This check establishes local artifact integrity for
that output only; it does not establish source freshness, hardware behavior,
or native evidence admission. The diagnostic summary is kept under
`github/workspaces/codex/aiueos-scorecard-evidence-audit-20261026`.
