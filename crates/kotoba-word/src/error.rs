use thiserror::Error;

#[derive(Debug, Error)]
pub enum WordError {
    #[error("invalid nsid `{0}` (expected dotted reverse-domain segments, e.g. com.etzhayyim.apps.kotoba.word.echo)")]
    InvalidNsid(String),

    #[error("nsid `{nsid}` is outside root namespace `{root}`")]
    OutsideRoot { nsid: String, root: String },

    #[error("word `{0}` already registered")]
    Duplicate(String),

    #[error("word `{0}` not found")]
    NotFound(String),

    #[error("invalid capability string `{0}` (expected proc:<bin> | net:<host> | fs:ro:<path> | fs:rw:<path>)")]
    InvalidCap(String),

    #[error("word `{nsid}` requests capability `{cap}` not granted by root")]
    CapExceedsGrant { nsid: String, cap: String },

    #[error("capability `{0}` denied for this invocation")]
    CapDenied(String),

    #[error("input failed schema/type validation: {0}")]
    InvalidInput(String),

    #[error("word input schema must be a JSON object at top level (got `{0}`) — required for MCP tool projection")]
    NonObjectInput(String),

    #[error("output failed serialization: {0}")]
    InvalidOutput(String),

    #[error("executor failed: {0}")]
    Executor(String),
}
