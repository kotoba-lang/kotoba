//! Social Capital ledger — re-exported from `kotoba-kqe` (the engine home).
//!
//! The implementation moved to [`kotoba_kqe::social`] (ADR-2606082100) so the
//! incremental MaterializedView reducer (`SocialCapitalView`) and the
//! `SocialCapitalLedger` share a single decay primitive. The
//! `kotoba_server::social::*` path is preserved for callers.
//!
//! See `docs/SOCIAL-CAPITAL-LEDGER.md` + `docs/MISHMAR-OBSERVATION.md`.

pub use kotoba_kqe::social::*;
