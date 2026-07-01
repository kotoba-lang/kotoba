# Rust Crate Migration

The `kotoba` repository is now a CLJC-first host repository with a legacy Rust
compatibility workspace. The target architecture is Kotoba/CLJC as the source
of truth for language, database, package, git/rad, deploy, and protocol
semantics.

Rust may remain only as:

- compatibility CLI/server host
- native execution backend
- generated adapter from a Kotoba/CLJC contract
- legacy implementation during migration

## Initial Classification

| area | current examples | target |
|---|---|---|
| language/profile/package | `kotoba-lang`, `kotoba-clj`, `kotoba-edn` | move authority to `kotoba-lang/kotoba-lang` and CLJC libraries |
| Datomic/db/query | `kotoba-datomic`, `kotoba-query`, `kotoba-graph`, server XRPC | CLJC Datomic/Transit contracts; Rust host is compatibility |
| CLI | `kotoba-cli` | Kotoba-native CLI surface; Rust CLI remains temporary host |
| git/rad/deploy | `kotoba-git`, `kotoba-rad`, `kotoba-lattice` | CLJC contracts first, generated/native adapters second |
| crypto/storage/network | `kotoba-crypto`, `kotoba-store`, `kotoba-net`, `kotoba-ipfs` | native backend adapters behind CLJC protocols |
| runtime/wasm | `kotoba-runtime`, `kotoba-rt`, `kotoba-wasm`, `kotoba-guest` | host execution backend; semantics in Kotoba/CLJC |

## CI Status

Default pull-request CI now gates the CLJ launcher and Python SDK surfaces. Rust
workspace checks moved to the `Rust legacy compatibility` workflow, which runs
manually and weekly. This keeps Rust visible while making CLJC/EDN the default
release path.

## Rule For New Work

New protocol or language behavior must land first in a Kotoba/CLJC contract or
specification. Rust code can implement, host, or test that contract, but should
not become the only definition of the behavior.

## Next Steps

1. Add crate-level `host`, `compat`, `backend`, `legacy`, or `migration-target`
   labels.
2. Move Datomic/Transit wire semantics to CLJC repos before expanding endpoints.
3. Move CLI command schemas to data so Rust, JS, and Kotoba-native hosts share
   one command contract.
4. Keep native crypto/storage/network implementations, but bind them through
   explicit CLJC protocols.
