# Mithril restricted secret adapter

The `@kotoba-lang/kagitaba/secret-item` JavaScript export is a bounded, versioned
adapter for API credentials. It does not persist, encrypt or synchronize values.
Its JSON wire shape is separate from the existing EDN item model; it does not claim
to implement the full 1Password model or 1PUX import in JavaScript.

Encrypt the entire object, including its title and environment-variable name.
Only opaque random identifiers belong in the server index. Unknown keys, malformed
identifiers, empty values and oversized fields fail without echoing input.

The EDN field model now classifies unknown/future field types as restricted.
`sensitive-fields` derives sensitivity from the type instead of trusting an
imported boolean. Import remains loss-preserving; this change tightens protection,
not category admission. Run `npm run test:sdk` and the item-model tests before use.
