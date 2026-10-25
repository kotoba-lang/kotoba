# ADR-260728: W6 cloudflare pure-request oracle — stream validate/redact/path

Status: accepted first cutover slice of `cloudflare-pure-request-v1`

## Decision

Port the pure string core of `cloudflare.stream` to `kotoba/stream_core.kotoba`:

| function | notes |
|---|---|
| `api-base` | Cloudflare REST v4 base URL |
| `redact-key` | first 4 chars + length (unicode ellipsis) |
| `validate-flags` | bit mask for validate-output problem keywords |
| `destination-url` | youtube/twitch rtmp(s) tables; `""` ≡ nil |
| `inputs-path` / `live-input-path` / `outputs-path` | pure path construction |

### Not ported

- Full request map builders (`create-live-*-request` body maps)
- `parse-live-input` / map reduce
- `*!` HTTP over `client/rest!`

## Evidence

- `test/cloudflare/stream_kotoba_parity_test.cljk`
- Equality against `cloudflare.stream` offline unit corpus

## Related

- `lang/w6-cloudflare-path-inventory.edn` first-cutover-slice
- murakumo form-A pure-planner oracle pattern
