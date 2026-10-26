# capability-data-json

Atomic authority package for `data/json`.

- provider status: **reference-implemented**
- semantic definition CID: `bafyreia2fucycy5w6nmxp3j473pz5vzamg2yisjiog6jw7bzoeqzqcprfq`
- artifact: `artifacts/provider.core.wasm`
- JVM reference: `kotoba.capability.data.json.provider`
- host ABI (module `kotoba`):
  - `json_encode` `(i32 i32 i32 i32) → i32`
  - `json_extract_field` `(i32 i32 i32 i32 i32 i32) → i32`

`json_encode` consumes flat `key\tvalue` / LF pairs → JSON object of strings.
`json_extract_field` does a bounded `"field":"value"` scan (not a full parser).

Definition CID is unchanged. `:signature :reference-unsigned` is reference
packaging.

```sh
kbb -M:test
```
