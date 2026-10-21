# Tooling source consolidation

LSP data, host-injected JSON-RPC framing, EDN linting and Kotoba static analysis
are tooling layers of the existing foundational stdlib. Keeping each definition
in a separate repository adds internal Git edges without an independent release
or execution boundary. Their source and tests now live in four packages:

| Canonical ID | Exact old aliases | Retained entry namespaces |
|---|---|---|
| `kotoba.lsp` | `kotoba-lang/lsp`, `io.github.kotoba-lang/lsp`, `kotoba.lang.lsp` | `kotoba.lsp`, `kotoba.lang.lsp` |
| `kotoba.lsp.rpc` | `kotoba-lang/lsp-rpc`, `io.github.kotoba-lang/lsp-rpc`, `kotoba.lang.lsp-rpc` | `kotoba.lsp-rpc`, `kotoba.lang.lsp-rpc` |
| `kotoba.lint` | `kotoba-lang/lint`, `io.github.kotoba-lang/lint`, `kotoba.lang.lint` | `kotoba.lint`, `kotoba.lang.lint` |
| `kotoba.lint.kotoba` | `kotoba-lang/lint-kotoba`, `io.github.kotoba-lang/lint-kotoba`, `kotoba.lang.lint-kotoba` | `kotoba.lint-kotoba`, `kotoba.lang.lint-kotoba` |

All per-definition namespaces remain available from these source roots. Dotted
package IDs select source; Lisp namespace spelling and function/value binding
identity retain their meanings. Runtime dependencies use declared sibling
packages. Existing standalone host test/lint alias values are retained.

## Provenance and compatibility

The 43 repositories were reviewed at immutable defaults, including every local
and remote branch/tag, worktree and stash. All reviewed refs are default
ancestors. The only untracked file is existing Finder metadata, retained in
place with a private byte-identical backup. It is not published here.

31 licensed origins are imported byte-for-byte, except changes explicitly bound
in each package's `local-changes.json`: bundled dependency declarations, one
inherited empty final line in LICENSE files, and the RPC repairs below.
Original bytes remain in full Git bundles with all 320 reviewed refs.

Twelve split LSP repositories contain no LICENSE. They are **not** labeled as
licensed source imports and no grant is inferred for them. Their implementation
forms were compared against the pinned Apache-2.0 `kotoba-lang/lsp` owner.
Active compatibility modules are derived from that owner's definitions and
docstrings, exposing private helpers in the existing split namespaces where
needed. Explicit dependency bindings retain shared value vars rather than
copying their current values. `lib/kotoba.lsp/derivations.json` records input
source/license hashes, output hashes and the separately reviewed compatibility
commit/hash. Both JVM and portable suites compare actual definition forms
(modulo docstrings, public spelling and lexical anonymous-function bindings).

The dated [recovery receipt](../maintenance/tooling-consolidation/2026-10-22/receipt.json)
keeps all 43 histories, including the compatibility-only predecessors. The
recovery checker can restore without GitHub and verify each original source
hash, default tree and preserved ref. Source provenance and historical recovery
remain separate records.

## RPC correctness

Regression tests reproduced a failure when JSON-RPC messages contained Japanese,
emoji or combining characters: `Content-Length` counted UTF-8 bytes while
`unframe` sliced UTF-16 characters. Concatenated frames also consumed bytes from
the following message. Both retained and assembled APIs now use the same byte
framing implementation, preserve subsequent messages, wait for incomplete
bodies and reject unsafe lengths or a UTF-8 character split by the declared
length. The input remains decoded string chunks supplied by the host; callers
own incremental transport decoding. Exception responses use `ex-message` on
both hosts. No socket, transport or service permission is added.

## Verification and retirement

```sh
node scripts/check-libraries.mjs
node scripts/test-library-provenance.mjs
node scripts/check-tooling-consolidation.mjs /absolute/github/workspaces/tooling-restore
node scripts/test-tooling-consolidation.mjs /absolute/github/workspaces/tooling-negative
node scripts/test-libraries.mjs
node scripts/test-library-jvm.mjs
bin/kotoba library import kotoba.lsp kotoba.lsp.rpc kotoba.lint kotoba.lint.kotoba --json
bin/kotoba run test/fixtures/library-import/tooling.cljk --runtime sci \
  --library kotoba.lsp --library kotoba.lsp.rpc --library kotoba.lint \
  --library kotoba.lint.kotoba --json
```

The public CLI fixture requires all 48 namespaces and reports source origins for
93 public vars. The CLI integration suite repeats it with every declared alias
family. SCI uses the existing JVM launcher plus the explicit local Node script
host; this is not native compiler, browser or signed-release qualification.
Previously disabled Actions remain disabled. Archive requires merged main,
import/CLI and test readback, plus immediate repository/ref/local-state checks.
Old URLs remain available for historical pins; no repositories are deleted in
this tooling batch. The original 239 dependency-pin holds, Amu and the other
execution foundations remain unchanged. Organization-wide review remains open.

All 43 repositories were archived and read back after source main
`1e06d72682b979fa7fc75d717b88a1b5d20e4f7e` passed portable 530 tests / 15,254
assertions, JVM 75 tests / 1,470 assertions, and public import/CLI 11 tests /
951 assertions. Each archive retained the original repository ID, default,
branches, tags and source bytes. The receipt keeps the full before/after
metadata. Existing local checkouts, branches, stashes and WIP remain in place.
