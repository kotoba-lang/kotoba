# authenticator-clj

An [Authy](https://authy.com/)-like command-line **TOTP/HOTP one-time-password
manager**, written in **ClojureScript** (runs on Node.js) with a **Datomic-API
account vault**.

```
$ authenticator-clj add "otpauth://totp/GitHub:octocat?secret=JBSWY3DPEHPK3PXP"
Added GitHub (octocat).
  684 243     27s    GitHub (octocat)

$ authenticator-clj code
  4121 6694   18s    ACME (alice@acme.com)
  684 243     18s    GitHub (octocat)
```

## Design

| Concern | Choice | Why |
|---|---|---|
| Language / host | **ClojureScript → Node.js** (shadow-cljs `:node-script`) | the requested cljs CLI |
| Datastore | **Datomic-API EAV store** ([`langchain.db`](../langchain)) | pure-`.cljc`, dependency-free, Datomic-shaped (`transact!`/`q`/`pull`); accounts are entities, lookups are Datalog |
| OTP core | RFC 4226 (HOTP) + RFC 6238 (TOTP), SHA1/256/512, 6/8 digits | `auth.otp`, verified against the RFC test vectors |
| HMAC | Node `crypto` (cljs) / `javax.crypto` (JVM) via reader conditionals | only host-specific code; one `hmac-bytes` fn |
| Persistence | EDN vault at `~/.authenticator-clj/vault.edn`, mode `0600` | the connection state is plain data, so it round-trips through `pr-str` |
| Schema dialect | Datomic installation tx-data, converted by `langchain.db/schema-from-tx-data` | one dialect across the workspace's datom corpora, stated once rather than once per host |

> **Why the vault is a snapshot and not a journal.** The decision ledgers in
> [`authentication`](https://github.com/kotoba-lang/authentication) and
> [`authorization`](https://github.com/kotoba-lang/authorization) persist through
> [`journal`](https://github.com/kotoba-lang/journal), an append-only history
> replayed on open. That is the right shape for an audit trail and the wrong one
> here: an append-only file keeps every value it was ever given, so `remove`
> would retract a secret from the index while leaving it on disk forever. A
> vault's delete has to actually erase, so this one rewrites the whole state.

> **Why "Datomic" is `langchain.db` here.** This workspace's `*-clj` projects
> share a pure-`.cljc`, zero-dependency, **Datomic-API-compatible** EAV/Datalog
> engine (`langchain.db`: `create-conn`, `transact!`, `q`, `pull`, `entity`,
> `as-of`). It gives us the Datomic programming model on a ClojureScript host —
> where real Datomic (JVM-only) cannot run — and the same `langchain.db/api` map
> lets a real Datomic Local / DataScript connection be swapped in unchanged.

Every namespace is `.cljc`, so the identical logic is unit-tested on the JVM
test-runner and shipped as a ClojureScript Node binary. The HMAC primitive is
proven host-identical (Node and JVM emit the same codes for the same secret).

### Namespaces

```
auth.base32  RFC 4648 Base32 decode/encode (pure)
auth.otp     HOTP/TOTP; HMAC is the only host seam
auth.uri     otpauth:// Key-URI parse / build (pure)
auth.db      account vault over langchain.db (Datomic-API): schema, put!/remove!/search/all
auth.vault   EDN persistence (host file IO), 0600
auth.clock   the single wall-clock seam
auth.cli     command dispatch + rendering
auth.core    entry points (cljs main / JVM -main)
```

## Build & run (ClojureScript / Node)

```bash
npm install                       # optional: pulls the shadow-cljs npm wrapper
kbb -M:dev:cljs -m shadow.cljs.devtools.cli release cli   # → target/authenticator.js
node target/authenticator.js help
# or, after `npm link`:  authenticator-clj help
```

## Commands

```
authenticator-clj [code] [query]   Show current codes (all, or matching query)
authenticator-clj list             List stored accounts (no codes)
authenticator-clj add <otpauth://…>                       Add by Key-URI (scanned QR)
authenticator-clj add --name N --secret BASE32 [--issuer I] [--type totp|hotp]
                      [--algorithm sha1|sha256|sha512] [--digits 6|8] [--period 30]
authenticator-clj remove <query>   Remove the single matching account
authenticator-clj export [query]   Print accounts as otpauth:// URIs
authenticator-clj import <file>    Add every otpauth:// URI in a file
authenticator-clj help
```

`code` with no query is the default (the Authy "home screen"): it prints every
account's current code with a countdown; HOTP accounts advance and persist their
counter when shown.

Vault location override: `AUTHENTICATOR_HOME=/path/to/vault.edn`.

## Test (JVM)

```bash
kbb -M:dev:test
```

Covers the RFC 4226 HOTP vectors, the RFC 6238 TOTP vectors (SHA1/256/512),
Base32 round-trips, `otpauth://` parse/build, and the Datalog vault
(upsert-on-identity, search, counter bump, EDN persistence round-trip).

## Security notes

- The vault is written `0600`; secrets are stored as cleartext EDN (the model
  used by `pass`-style tools: rely on filesystem permissions + an encrypted
  home). An encrypted-vault codec (master password → PBKDF2 → AES-GCM) is the
  intended next layer — `auth.vault/read-state` / `write-state!` are the seam.
- Test fixtures use the **public** RFC test secret `GEZDG…` — not a real account.
