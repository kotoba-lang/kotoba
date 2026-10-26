# ADR: where code lives — kotoba lib or an Itonami dapp

Status: accepted (owner decision, 2026-10-26)

## Decision

- **Pure functions and components go to `kotoba-lang/kotoba` `lib/`**, under a dotted ID (`kotoba.<name>`, or the publisher's reverse domain for an external specification). A library has no account, no deployment and no operator of its own.
- **Anything that needs account-level or operator-level elements when it is actually used is an Itonami dapp**, in the GitHub organization `cloud-itonami` as `app-itonami-<name>`. A dapp is not only a browser app: native programs, containers, services, Workers, CLI/agent runtimes, data feeds and catalogs are dapps too.
- **Products such as kagi and kotobase are dapps; their building blocks are libraries.** The part that is a pure function or a reusable component is bundled in `lib/`; the deployable whole is the dapp.
- `kotoba-lang` keeps the language, compiler and runtime infrastructure and the core products that carry maintainer profiles (amu, aiueos, kotoba, kotoba-lang, kami-engine, murakumo, torihiki, wasm-webcomponent, ...). Private repositories are never put into the public monorepo.

## Application on 2026-10-25/26

- About 1,000 repositories were bundled into `lib/` (or `kami-engine` `packages/` for the kami family) and archived; the old repositories keep their history.
- About 60 repositories moved to `cloud-itonami` as `app-itonami-*` (apps, services, the data feeds and catalogs, the `actor-*` packages, kagi).
- Not yet applied: splitting the building blocks out of kagi and kotobase into `lib/`.

## Consequences

- A repository that moved keeps its git URL working through GitHub's redirect; its GitHub Pages URL changes.
- West entries and consumers that pin a moved or archived repository by git coordinate are rewritten to the `kotoba` monorepo coordinate (`:deps/root lib/<id>`) one repository at a time.
