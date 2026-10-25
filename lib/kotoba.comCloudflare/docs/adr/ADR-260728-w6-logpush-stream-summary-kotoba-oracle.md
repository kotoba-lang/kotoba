# ADR-260728: W6 cloudflare pure-request — logpush paths + live-input-summary

Status: accepted extension of `cloudflare-pure-request-v1`

## Decision

| artifact | notes |
|---|---|
| `kotoba/logpush_path_core.kotoba` | datasets/jobs/job REST path strings |
| `kotoba/stream_core.kotoba` | add `live-input-summary` (credential-free log line) |

HTTP create/delete and map parse of live inputs remain cljc/host.

## Evidence

- `test/cloudflare/logpush_path_kotoba_parity_test.cljk`
- `test/cloudflare/stream_summary_kotoba_parity_test.cljk`

## Related

- com-cloudflare#1 stream core
- com-cloudflare#2 analytics + workers paths
