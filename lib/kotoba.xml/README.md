# kotoba-lang/xml

Dependency-free Hiccup to XML emitter and parser.

Two emitters, deliberately separate:

- `xml.core/xml` — indented output, for documents whose element content is
  other elements (OOXML, the case this library was written for).
- `xml.core/compact` — **no inserted whitespace**, for wire protocols where
  element content is a *value*. `xml` would emit `[:clTRID "ABC-1"]` as
  `<clTRID>\n  ABC-1\n</clTRID>`, whose text content is `"\n  ABC-1\n"` —
  harmless in a document, a defect in EPP where that value is compared.

Compatibility namespace:

- `kotoba.xml`

Verify:

```sh
kbb -M:test
```
