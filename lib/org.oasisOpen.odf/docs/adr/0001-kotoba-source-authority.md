# ADR 0001: Kotoba is the ODF production source authority

- Status: Accepted
- Date: 2026-07-21

## Context

The former CLJC parser accepted an open-ended sequence of byte maps, converted
bytes through host functions, and extracted XML with regular expressions. That
surface had no typed resource bound and could not run as sovereign Kotoba.

## Decision

`src/odf.kotoba` is the sole production source. Archive expansion and strict
UTF-8 decoding belong to an explicit capability/provider boundary. The pure
module accepts decoded `mimetype`, decoded `content.xml`, and an admitted entry
count. It exposes document kind, a bounded paragraph count, indexed paragraph
text as `[:option :string]`, and a typed summary document.

The sealed XML profile limits source strings to 64 KiB, nodes to 2,048, depth
to 32, attributes per node to 32, and path segments to 32. It does not use an
ambient DOM or external entity resolution. Invalid XML, invalid indexes, and
over-limit inputs fail closed.

CI runs reference KIR, restricted JavaScript, instantiated typed WebAssembly,
and the existing real Pandoc ODT fixture. It also rejects production `.clj`,
`.cljc`, and `.cljs` sources.

## Consequences

- Paragraphs remain fully observable through count plus indexed access.
- Package I/O and decoding authority are explicit rather than hidden in pure
  language code.
- JVM use is limited to compiler and qualification tooling.
