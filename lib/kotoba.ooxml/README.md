# kotoba-lang/ooxml

EDN-first OOXML/Open Packaging Conventions substrate.

This library models package entries, relationships, content types, and package
kind detection as plain Clojure data. ZIP read/write is intentionally left to
host adapters.

## Coverage matrix

`ooxml` is the shared OPC (Open Packaging Conventions) substrate underneath
`drawingml`/`presentationml`/`slides` — it doesn't parse any part-level XML
(slide/shape/chart content) itself. Its scope is the package envelope: entries,
relationships, content types, and package-kind detection.

| Primitive | Status | Notes |
|---|---|---|
| Package-kind detection (pptx/docx/xlsx/opc) | ✅ | path-prefix heuristic (`ppt/`, `xl/`, `word/`) |
| `[Content_Types].xml` write (Default + Override) | ✅ | write-only; each consumer reads its own copy back directly (e.g. `presentationml.parse`'s own regexes) rather than through this repo |
| `.rels` relationship write, including `TargetMode` | ✅ | `relationship`/`relationship-xml` have carried an optional `target-mode` from the start; the 2026-07 internal-hyperlink fix (distinguishing an external URL from a same-deck slide-jump link) lives in `presentationml.parse`'s own relationship *reader*, not here |
| Idempotent content-type/relationship "ensure" (patch path) | ✅ | `ensure-content-type-extension`/`ensure-root-relationship`, used by `slides`' source-aware `update` path so a patched package still declares any new part types/relationships it needs |
| Well-known Office part detection (slide/sheet/document) | ✅ | `office-part?`/`office-parts`, regex-based, numeric-aware sort (`part-sort-key`: `slide2` before `slide10`) |
| EDN structural validators (`valid-package?`, `valid-relationship?`, `valid-content-type?`) | ✅ | shape-level validation only (right keys, right types) — not OOXML schema validation |
| Relationship/content-types XML *parsing* (read) | ❌ out of scope here | this repo only ever emits these XML strings; reading them back into EDN is each consumer's own concern (see `presentationml`'s coverage matrix for the `.rels` reader, including its `TargetMode` capture) |

## Test

```bash
kbb -M:test
```
