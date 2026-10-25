# ADR 0018: Bounded XML element/path subset

Status: implemented in Kotoba Script; compiler qualification pending

Kotoba admits XML only as a pure, bounded value transformation. The profile
supports a strict XML declaration (with case-insensitive `UTF-8` encoding
spelling), comments, elements, quoted attributes,
self-closing elements, and whitespace between elements. It rejects DTDs,
entities, processing instructions, CDATA, mixed/text content, duplicate
attributes, mismatched closing tags, malformed UTF-16, and trailing content.

Limits are 65,536 UTF-8 input bytes, 2,048 elements, depth 32, 32 attributes
per element, ASCII XML names of at most 128 characters, and 32 exact path
segments. Paths contain no wildcard, descendant, predicate, namespace
resolution, or callback behavior.

`xml-path-count` returns the number of elements whose exact root-relative path
matches. `xml-path-attr` returns `[:option :string]` for one zero-based matching
element. A missing element or attribute is `none`; malformed input, invalid
paths, negative indices, and limit exhaustion trap. Neither operation performs
I/O, resolves external identifiers, decodes entities, or grants authority.

Qualification requires identical reference, restricted JavaScript, and typed
Wasm behavior, negative vectors for every rejected XML feature and limit, and
an actual bounded URDF consumer comparison.

Kotoba Script evidence is `kbb -M:test`: 39 tests and 133 assertions pass,
including URDF-shaped positive queries, typed absence, every structural limit,
and rejection of DTDs, entities, text, duplicate attributes, mismatched tags,
processing instructions, CDATA, and trailing content. This does not qualify the
language-wide feature until compiler and consumer evidence also passes.
