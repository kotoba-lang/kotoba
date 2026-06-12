//! kotoba-word — agent-callable "words" with a root registry.
//!
//! A **word** is the minimal callable unit: `NSID + typed input/output schema
//! + executor + capability requirements`. A **root** is where words are
//! planted: registry + runtime + capability boundary + projections.
//!
//! SSOT model (S2', see docs/ADR-kotoba-word.md): the *authoring* source of
//! truth is a typed Rust closure (`Fn(I, Ctx) -> O` where `I: JsonSchema +
//! DeserializeOwned`, `O: JsonSchema + Serialize`). Schemas are extracted
//! mechanically from the type signature via schemars. The *interchange*
//! source of truth is the extracted [`manifest::Manifest`] (lockfile-style:
//! commit it, CI-diff it). Local apps and web services are wrapped by
//! closures that reach them through capability-gated [`Ctx::exec`] /
//! [`Ctx::http_get`]; untrusted third-party words run as `kotoba-udf` WASM
//! components on kotoba-runtime (feature `wasm-udf`).
//!
//! Projections (generated, never hand-written):
//! - MCP: [`projection::mcp`] — `tools/list` + `tools/call` JSON-RPC
//! - ATProto Lexicon: [`projection::lexicon`] — one lexicon doc per word

pub mod cap;
pub mod ctx;
pub mod error;
pub mod examples;
pub mod manifest;
pub mod projection;
pub mod root;
pub mod word;

pub use cap::Cap;
pub use ctx::{Ctx, ExecOutput};
pub use error::WordError;
pub use manifest::{Manifest, ManifestDiff, WordManifest};
pub use root::Root;
pub use word::{ExecutorKind, Word, WordMode};
