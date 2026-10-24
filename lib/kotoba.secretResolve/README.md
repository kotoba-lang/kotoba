# secret-resolve

A small `.cljc`/nbb library: resolve a credential field via
**env → 1Password → macOS Keychain**, in that order, using the exact
`{:order [...] :env ... :1password ... :keychain ...}` spec shape already
established by this workspace's `manifest/repos.edn` `:b2 :credentials`.

Design is authoritative in
**`90-docs/adr/2607161000-kotoba-lang-secret-resolve-shared-lib.md`**
(superproject `com-junkawasaki/root`).

## Why this exists

Before this library, the exact same ~30 lines of env/1Password/Keychain
resolution logic were hand-copied into at least three places:
`scripts/b2-creds.cljs` and two files in `kotoba-lang/com-backblaze-secure`.
Two of those copies also independently hand-rolled the same subprocess
safety fixes (or missed them): calling
`security find-generic-password -s <service> -g` prints the item's
password in cleartext as part of its human-readable attribute dump, and
Node's `child_process.execFileSync` inherits a child's stderr straight to
the *caller's* stderr unless `:stdio` is explicitly overridden — so without
that override, a plaintext secret leaks onto whatever is watching the
calling process (this is exactly how a B2 application key leaked into a
chat transcript in the session that created this library — see
ADR-2607152322). A stale `op` CLI session also hangs indefinitely on
`op read` rather than failing fast. This library fixes both once, in one
place, instead of leaving every consumer to rediscover them.

## API

```clojure
(require '[secret-resolve.core :as sr])

(sr/resolve1 {:order [:env :1password :keychain]
              :env "B2_KEY_ID"
              :1password "op://gftdcojp/com-junkawasaki.b2_annex/keyID"
              :keychain {:service "b2:gftdcojp-m365-annex" :field :account}})
;=> "004d9f6c0ba12580000000009" (or nil if nothing resolved)

(sr/resolve-map! {:key-id  {:order [:env :1password :keychain]
                             :env "B2_KEY_ID"
                             :1password "op://.../keyID"
                             :keychain {:service "b2:gftdcojp-m365-annex" :field :account}}
                   :app-key {:order [:env :1password :keychain]
                             :env "B2_APP_KEY"
                             :1password "op://.../applicationKey"
                             :keychain {:service "b2:gftdcojp-m365-annex"}}})
;=> {:key-id "..." :app-key "..."}
;   throws ex-info naming the field + source order if any field can't
;   be resolved from anything it was told to check.
```

### Keychain `ref` shapes

- `{:service "svc"}` — plain `security find-generic-password -s svc -w`
  (single-field item).
- `{:service "svc" :account "explicit-account"}` — `-a explicit-account -w`
  (separate-item-per-field layout, account name known up front).
- `{:service "svc" :field :account}` — `-g`, parsed for just the `acct`
  attribute (the "combined" single-item layout: account = one field,
  password = the other). Never returns or logs the rest of the `-g` dump,
  which contains the item's password in cleartext.

## Layers

- `secret-resolve.resolver` (`.cljc`, pure, no I/O) — the ordered-fallback
  walk. Portable; unit-tested on the JVM (`kbb -M:test`) against fake
  sources with no subprocess calls at all.
- `secret-resolve.exec` (`.cljs`, Node-only) — the safe `execFileSync`
  wrapper (explicit `:stdio`, default timeout, `maxBuffer`).
- `secret-resolve.sources` (`.cljs`, Node-only) — concrete env/`op`/
  `security` source functions built on `secret-resolve.exec`.
- `secret-resolve.core` (`.cljs`) — thin convenience wiring the above two
  together as the default source map.

## Use from nbb

Add this repo's `src` to your `--classpath` alongside your own:

```bash
kbb --backend sci --classpath "src:../secret-resolve/src" your_script.cljs
```

(`../secret-resolve` assumes a sibling checkout under the same org, e.g.
both under `orgs/kotoba-lang/`; adjust the path otherwise.)

## Test

```bash
kbb -M:test   # resolver.cljc pure-logic tests (portable, no subprocess calls)
```

## Known limitations

- `secret-resolve.exec/sh` is synchronous (`execFileSync`) — a caller that
  wraps a slow subprocess blocks its own process until it returns or times
  out. This is a deliberate simplicity trade-off (matches this workspace's
  existing `scripts/nbb_compat.cljs` convention); an async variant is out
  of scope unless a real consumer needs one.
- The 1Password source never triggers an interactive re-auth — it treats a
  stale session as "unavailable" (5s timeout, falls through to the next
  source) rather than prompting. Sign in with `op signin` yourself before
  relying on `:1password` resolving.
