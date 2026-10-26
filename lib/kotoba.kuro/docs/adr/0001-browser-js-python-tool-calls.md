# Browser JavaScript and Python tool calls

Date: 2026-10-03. Status: implemented locally; production admission is separate.

## Decision

Extend kuro's browser backing with an explicit function-tool interface, rather
than pretending a browser Worker can spawn shell processes. The names are `js`
and `python`; the wire envelope is the usual function call with `id`,
`function.name`, and JSON `function.arguments`. The host returns JSON result,
explicit exported files, and a fixed `:kuro/*` terminal receipt. `toToolMessage`
returns a matching `role: "tool"` message for the agent's next turn.

Use QuickJS 0.32.0 compiled to Wasm for JavaScript and Pyodide 314.0.7 for
Python. Host scheduling, argument admission, file snapshots, and result
delivery are browser glue. Session/receipt and filesystem integration stay
in `kuro.host.tool-browser` `.cljk`, consuming the existing pure models.
The compiler, Kotoba component ABI, and stream-browser provider are unchanged.

Each invocation owns a fresh Worker, interpreter, and ephemeral filesystem.
The main thread terminates the Worker on completion, failure, cancellation,
or deadline. This is a real kill, including during synchronous guest loops,
and does not depend on the Worker processing a cancel message. It does not
change stream-browser's separately documented no-op stdin/kill behavior.

Arguments are JSON data: code, inputs, UTF-8 files, and exportFiles. Paths are
relative to a per-call workspace; absolute paths and traversal are refused.
`kuro.fs` snapshots are read through its existing get-block port; exports
are written through its put-block port. Publication remains explicit.
Callers serialize store updates or perform their own concurrent merge. Failed
tool execution imports no files; partial FS import denials remain visible.

## Enforced controls

- Unknown tools, malformed input, invalid paths, excessive input, and missing
  grants are refused before constructing a Worker.
- `tool/js` or `tool/python` admits the selected runtime. Snapshot input needs
  `fs/read`; exporting files needs `fs/write`. These gates control transfer,
  not mutation of the guest's private scratch filesystem.
- Python additionally requires `tool/python-js-bridge`. This is a separate,
  explicit admission of Python's ambient browser authority.
- A positive finite main-thread wall deadline covers bootstrap and execution.
  AbortSignal cancels the call. Both terminate the Worker.
- UTF-8 stdout, stderr, JSON result, and file exports share an output-byte
  budget. Oversize outputs fail with exit 125 and `:kuro/truncated? true`.
- QuickJS has an engine heap and stack limit. No DOM, fetch, Node APIs,
  module loader, or host network bridge is injected into the JS context.
  Internal Promise jobs are drained; unresolved external async results fail.
- Receipt exits: 0 success, 1 runtime/serialization failure, 124 deadline,
  125 output limit, 126 admission failure, 130 cancellation.

## Remaining boundaries

Pyodide is not an untrusted tenant sandbox. Python can import `js` and reach
Worker/browser APIs, including network and same-origin storage. A Worker is
not an origin boundary. The receipt says `pyodide-worker-js-bridge`, not
capability-confined Python. Run Python on a dedicated origin without secrets
and admit only trusted code under this profile. Suppressing `import js` or
removing builtins is not a replacement for an isolation mechanism. Arbitrary
untrusted Python needs an independently enforced origin/network/storage
boundary or a Python/WASI interpreter without an ambient JS bridge.

There is no hard Python heap limit, instruction fuel, interactive stdin,
PTY, shell, npm/pip installation, automatic package retrieval, binary-file
transfer, persistent interpreter state, or production multi-tenant approval
in this change. `maxMemoryBytes` limits QuickJS only. Python includes its
standard library; additional wheels need a separately admitted local asset
and package-loader design. QuickJS async code uses an async function
expression; script-level `await` is not enabled.

## Verification

`npm run test:browser-tools` builds self-hosted assets and drives real
Chromium. It checks both runtimes, Unicode stdout/stderr and files, JSON
results, script failures, JS Promise results, state freshness, denials before
Worker creation, path traversal, JS/Python infinite-loop termination,
cancellation, output limits, recovery, and matching tool response IDs.
No CDN or external request is allowed in this test.

`npm run test:tool-adapter` checks the `.cljk` adapter's session-derived
grant, fixed receipt shape, arbitrary JSON/file keys, `kuro.fs` round-trip,
and refusal before runtime invocation when the FS grant is missing.
Existing `test:host` and `test:parity` remain regression gates. The new
browser-tools CI job uses the checked-in npm lockfile and real Chromium.
