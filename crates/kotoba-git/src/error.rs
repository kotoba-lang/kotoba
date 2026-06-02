//! Error type for kotoba-git.

#[derive(Debug, thiserror::Error)]
pub enum GitError {
    #[error("invalid git oid: {0}")]
    InvalidOid(String),
    #[error("unknown git object kind: {0}")]
    UnknownObjectKind(String),
    #[error("malformed git object header")]
    MalformedHeader,
    #[error("malformed git tree object")]
    MalformedTree,
    #[error("object size mismatch: header declared {declared}, body is {actual}")]
    SizeMismatch { declared: usize, actual: usize },
    #[error("wrong object kind: expected {expected}, got {actual}")]
    WrongKind {
        expected: &'static str,
        actual: &'static str,
    },
    #[error("object not found in datom projection: {0}")]
    ObjectNotFound(String),
    #[error("block missing from store for cid {0}")]
    BlockMissing(String),
    #[error("git oid {oid} does not match stored block (got {recomputed})")]
    OidMismatch { oid: String, recomputed: String },
    #[error("could not parse cid value from datom: {0}")]
    BadCid(String),
    #[error("datomic error: {0}")]
    Datomic(#[from] kotoba_datomic::DatomicError),
    #[error("block store error: {0}")]
    Store(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, GitError>;
