# Native standard library compatibility (JUN-203)

The sixteen retained source repositories were reviewed at immutable branch
tips. All sixteen can retire after merged-main verification. The final text
WIP inputs and parents are retained separately from their corrected outputs;
JUN-232's explicit-fn change is ported onto the qualified I/O implementation.
Text's three profile sources have checked outputs at `hermes/profiles/` and
a corresponding source-home registry migration. No host profile is materialized,
no cron is started, and execution infrastructure stays separate.

The accepted [native API contract](ADR-261021-native-library-compat.kotoba)
records the host/native distinctions. Existing host names and exact import
aliases remain. Native canonical facades forward to the qualified implementations.

| Package | Qualified native reading |
| --- | --- |
| I/O | Complete memory-buffer/cursor family, bytes at public boundaries, updated writer returned explicitly |
| JSON | Encode/pretty/decode, explicit decode results, NDJSON record framing |
| EDN | Bounded native document reading/writing with explicit typed-error results |
| Process | Pure argv/allowlist/output/time validation; no OS process execution |
| Async | Bounded channels and structured scopes; native `channel-take`, host `take` |
| Text | starts-with/includes, Unicode whitespace predicate, ASCII-only folding; existing bounded kernels retained |

Native EDN has a narrower admitted syntax than the host reader. Language-owned
document-parser traps, including duplicate map keys, remain VM refusals rather
than typed results. Host EDN later lexer/parser fixes are kept byte-for-byte
inside its reading. Native process counts UTF-8 bytes; the compatibility host
reading retains its existing argument-counting behavior. These are explicit
boundaries, not universal host/native parity claims.

Branch adaptation fixes current schema references, unsupported protocol macros,
reserved names and unhandled error exports. Regression testing also found JSON
accepting invalid trailing commas, non-string object keys and raw control
characters; host and native readings now refuse them consistently.

`scripts/test-native-libraries.sh` builds both real source closures using the
three-generation self-built compiler from `native-toolchain.env`. It links and
executes them, checks every byte value, JSON/EDN refusals, state transitions,
Unicode behavior, invalid channel/scope refusals and fuel exhaustion. Source
digests are read back after execution. CI blocks hosted language executables
for this job and preserves its logs. This qualifies the declared fixture/API
subset; it does not migrate the public launcher to the selfhost compiler.

The async JVM/KIR/JavaScript/Wasm oracle now runs in the current launcher graph;
the obsolete isolated historical compiler project is removed. Portable suites
and public `bin/kotoba --runtime sci` checks exercise the host APIs separately.

`branch-reviews.json` binds retained original branch snapshots and adapted
outputs separately. `local-changes.json` records every changed imported file
and new native facade. `check-libraries.mjs` rejects source drift and undeclared
additions. Git history and immutable consumers remain supported after archive.

`worktree-reviews.json` binds both original text WIP files, parent bytes and
patches to the adapted host formatter and boundary regressions. The prototype's
`long(scaled + 0.5)` changes values just below a half and large integral values;
host `Math/pow` and `Math/round` remain the oracle. Absolute value uses the local
sign predicate, and fractional padding accepts a string. Native floating-format
support is outside the declared bounded native text API.

The Hermes branch's surviving files already match the imported default, with
its obsolete Python predecessors absent. `profile-homes.json` binds complete
source/destination inventories for all three preserved profile trees. Their
legacy configs are retained as inactive input; maintained configs use the
currently configured Hermes OpenRouter rail, with native inference providers
and fallbacks removed. Non-routing values are preserved. The root agent
registry changes only their source/home repository; identities, schedules,
permissions and profile bodies remain unchanged.
