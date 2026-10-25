# ADR 0001: Kotoba is the EPUB production source authority

- Status: Accepted
- Date: 2026-07-21

## Context

The former CLJC parser accepted an open-ended byte-entry sequence and used
regular expressions for container, OPF, spine, and XHTML parsing. Archive I/O,
decoding, path resolution, and pure document semantics were not separated by a
typed capability boundary.

## Decision

`src/epub.kotoba` is the sole production source. An explicit provider owns
archive expansion, strict UTF-8 decoding, and bounded relative archive-path
resolution. Pure Kotoba exposes the package path, title, manifest count/id/href,
spine count/idref, and chapter text. Count plus indexed option-string access
preserves manifest and spine order without admitting unbounded host sequences.

The sealed XML profile limits source strings to 64 KiB, nodes to 2,048, depth
to 32, attributes per node to 32, and path segments to 32. Only the fixed
XHTML5 `<!DOCTYPE html>` declaration is admitted; PUBLIC/SYSTEM identifiers,
internal subsets, alternate roots, and duplicate declarations are rejected.

CI runs reference KIR, restricted JavaScript, instantiated typed WebAssembly,
hostile-doctype rejection, and the real Pandoc EPUB fixture. Production `.clj`,
`.cljc`, and `.cljs` sources fail CI.

## Consequences

- EPUB package semantics are observable through a bounded typed ABI.
- Archive and path authority are explicit provider responsibilities.
- JVM use is limited to compiler and qualification tooling.
