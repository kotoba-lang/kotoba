# Native CLI migration

Tracking: [AWAI-24](https://linear.app/kotobalabs/issue/AWAI-24),
[AWAI-43](https://linear.app/kotobalabs/issue/AWAI-43),
[AWAI-48](https://linear.app/kotobalabs/issue/AWAI-48) and
[JUN-290](https://linear.app/kotobalabs/issue/JUN-290).

## Current CI boundary

CI uses Amu selfhost and canonical Kotoba on native Linux kernels. Immutable
Amu/contract revisions and source/image digests are recorded in
`scripts/native-ci-inputs.json`. Amu's adopted frontend, checker, project
loader and backend compile the actual multi-module CLI fixture. No host
namespace rewriting or second semantic compiler is involved.

The ARM job rebuilds the loaderless compiler, checks its combined closure and
executes `test/kotoba/native_cli_request.kotoba`. The fixture reads the opaque
contract bytes itself and checks all12 commands, every flag/alias, defaults,
repeated options, integer bounds and named refusals. A changed runtime enum
and a denied capability set are negative controls. The x86 job rebuilds three
complete compiler generations and executes the sealed Amu/Kotoba controller,
including its complete24 result/fuel corpus, refusals and child cleanup.

Python stages immutable bytes, hashes files and observes processes. Native
Kotoba owns the request assertions and controller verdict. No C compiler or
loader, JVM, Node, NBB, KBB or hosted fallback participates. The required `CI`
context retains its name and requires both native jobs. Branch protection and
production routes are not modified by this source change.

## Retired checks

The former `clj-launcher` job and C-loader-based `native-selfhost` scripts are
removed. Their complete bytes and hashes are in
`docs/retired/native-ci-20261024/manifest.json`; these text archives are not
executable. The retired launcher lint/JavaScript/library/Q9/runtime-value,
SDK packaging and package-admission checks are no longer CI coverage. Their
source fixtures remain available for native porting. Documentation Pages
deployment is a separate workflow.

## Public command execution remains open

An isolated native execution slice now validates `check --kind cli-contract`
and `check --kind lock` inside the Kotoba guest. The contract check covers the
exact twelve command IDs, command and option uniqueness, option types and flag
shapes. The lock check reads an explicitly named file through Amu's bounded
FS2 provider, validates the module-lock schema and source CID pins, and
returns the canonical lock CID to the internal caller. The native fixture checks
the frozen two-module CID. Invalid pins and missing or extra lock paths
are refused; the fixture also denies the FS grant and filesystem scope.
Mutated version/command-set inputs are refused, and unimplemented verbs return
`:cli/native-execution-unavailable`. The source is
`src/kotoba/cli_exec.kotoba`; the native ARM fixture executes it through the
Amu selfhost compiler. These are internal check modes. The lock mode does not
yet read and verify its whole source closure or expose the computed CID on the
public CLI. The public launcher, other `check` modes, and the remaining command
execution paths are still open.

`src/kotoba/cli.kotoba` produces validated requests. Parsing a command does
not execute it, approve a provider operation, admit a package or qualify a
target. The public `bin/kotoba` still has legacy dispatch and must not be used
for this migration's execution proofs. The native implementation must finish
all12 command/provider paths, whole-closure CID/lock caller integration and general FS
fault/cleanup checks before public CLI parity can be claimed. Existing Web,
Wasm, signature and package contracts remain acceptance criteria.

The native request fixture currently exercises every command name and option,
but has no product execution receipt for any command. The completion ledger is:

| Command | Native execution acceptance still required |
| --- | --- |
| `id` | Create or inspect a principal with the declared identity and approval boundary. |
| `run` | Compile and execute the selected Kotoba entry with admitted inputs and capabilities. |
| `compile` | Produce and verify the requested Web or Wasm artifact. |
| `check` | Validate source, package, lock and CLI contract inputs with named refusals. |
| `graph` | Execute connect, query, transact, pull and status against an admitted graph. |
| `git` | Execute init, status, commit and sync against a selected repository. |
| `rad` | Execute new, build, test and export against a selected project. |
| `build` | Build a locked project and verify its target artifact. |
| `test` | Execute admitted project tests and report their verdict. |
| `deploy` | Execute plan, apply, status and rollback with explicit target authority. |
| `library` | Resolve, inspect and publish pinned library definitions. |
| `hinshitsu` | Execute evidence, gate, coverage and visual checks. |

Each row needs positive execution, refusal, resource and cleanup evidence on
the exact Amu/Kotoba source revision before public launcher replacement.

The Amu/Kotoba controller's two roles remain build infrastructure. A passing
controller gate is distinct from complete product command execution and from
a production route cutover. See `AGENTS.md` for uncovered checks and limits.
