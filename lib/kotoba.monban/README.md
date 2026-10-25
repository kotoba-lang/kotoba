# monban (門番)

**Deciding whether a call may ring — before the callee's phone wakes.**

Runs on the callee's home node. The ladder (`monban.policy/decide`):

| caller | verdict |
|---|---|
| on a subscribed blocklist | `:reject` |
| contact / vouched by a contact / introduced by a contact | `:ring` |
| member of a trusted community, within its quota | `:ring` |
| unknown, paid a proof-of-work stamp or put credit at stake | `:screen` |
| unknown, paid nothing | `:voicemail` (or `:reject`) |

Every admitting rung is rate-limited per caller (token bucket).

- `monban.stamp` — SHA-256 proof-of-work bound to one call attempt.
- `monban.postage` — refundable stake on `moyai-ledger` credit
  (non-monetary, non-transferable, decaying): released if welcome or on
  expiry, burned if the callee reports the call.
- Blocklists and reports are signed statements; the callee chooses whose to
  believe. There is no global reputation.

```sh
npm test
```
