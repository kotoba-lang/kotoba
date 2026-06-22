use thiserror::Error;

/// Errors raised by the lattice control-plane core.
#[derive(Debug, Error)]
pub enum LatticeError {
    #[error("EDN parse error: {0}")]
    Edn(String),

    #[error("manifest schema error: {0}")]
    Schema(String),

    #[error("CBOR encode error: {0}")]
    CborEncode(String),

    #[error("CBOR decode error: {0}")]
    CborDecode(String),

    #[error("unknown component language: {0}")]
    UnknownLang(String),
}
