# ADR 0146: secret host transports (fn-fetch + keychain single-get)

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0145 landed `provider.secret` (id 21) with pure name policy and
`map-fetch` / `env-fetch`. W6 kbb gap Next still listed:

1. ops CLI cutover from ambient getenv  
2. optional kagi one-shot getter as `:fetch`

Hosts need production transport shapes that never dump env or keychain.

## Decision

| transport | injects as | host-required config |
|---|---|---|
| `secret-transport/fn-fetch` | `:fetch` | `(fn [name] string-or-nil)` (+ optional allowed set) |
| `secret-transport/keychain-fetch` | `:fetch` | `{name {:service s :account a}}` (JVM) |

### Non-goals / fail-closed rules

- **No keychain dump** — no `dump-keychain`, no list-all, no `-g` attribute
  dump (password can leak on stderr).
- **No ambient env scan** — still only exact names from host maps.
- **kagi not a provider dep** — hosts wrap kagi `get-secret` with `fn-fetch`.
- `:cljs` keychain remains an explicit gap.

### kagi wiring (host)

```clojure
(secret/create-providers
  {:allowed-names #{"murakumo-token"}
   :fetch (secret-transport/fn-fetch
           (fn [n]
             (when-let [ref (get {"murakumo-token" "keychain://murakumo/token"} n)]
               (kagi.secret-store/get-secret store ref {}))))})
```

## Consequences

- Ops CLIs can inject env-fetch, keychain-fetch, or kagi via fn-fetch under
  the same allowlist contract.
- secret-custody status advances to **host-transports-landed**; consumer
  cutover evidence still required to close the gap.

## Related

- ADR 0145 secret-custody contract first slice
- ADR 0144 process/scoped-fs OS transports (same inject, no ambient)
- `lang/w6-kbb-ability-gap.edn` `:secret-custody`
