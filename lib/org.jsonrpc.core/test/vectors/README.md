# Vendored JSON-RPC 2.0 vectors

Copied from the JSON-RPC 2.0 specification
<https://www.jsonrpc.org/specification> for offline fixture tests.

CI does not fetch jsonrpc.org. The executable cases live in
`test/fixtures.kotoba`. This file is the human-readable source list.

Copyright (C) 2007-2010 by the JSON-RPC Working Group. The specification
permits copies that implement or explain the protocol when this notice is
kept.

## Requests

Positional parameters:

```json
{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}
{"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}
```

Named parameters:

```json
{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}
{"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 4}
```

Notifications (no `id`):

```json
{"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}
{"jsonrpc": "2.0", "method": "foobar"}
```

String id and omitted params:

```json
{"jsonrpc": "2.0", "method": "foobar", "id": "1"}
{"jsonrpc": "2.0", "method": "get_data", "id": "9"}
```

## Errors

```json
{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
```

Invalid JSON (parse error) and invalid request object:

```text
{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz}
{"jsonrpc": "2.0", "method": 1, "params": "bar"}
[]
[1]
```

## Batch

Empty batch is an invalid request (single object, not an array).
A notification-only batch encodes to the empty string (nothing on the wire).
Notifications are omitted from a mixed response array.
