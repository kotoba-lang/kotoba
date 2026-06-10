//! Word — the minimal callable unit.
//!
//! Authoring SSOT is the typed closure: `I` and `O` carry serde + schemars
//! derives, so the JSON Schemas are extracted from the type signature and the
//! word body is the only thing a human writes. Every executor kind (process,
//! http, wasm) is still defined *through* a typed signature — the executor is
//! distribution metadata, not a second definition language.

use std::future::Future;
use std::sync::Arc;

use futures::future::BoxFuture;
use schemars::JsonSchema;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::cap::Cap;
use crate::ctx::Ctx;
use crate::error::WordError;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum WordMode {
    /// Read-only — projects to a lexicon `query` when its params allow it.
    Query,
    /// Side-effecting — always projects to a lexicon `procedure`.
    Procedure,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ExecutorKind {
    Closure,
    Process,
    Http,
    Wasm,
}

/// Distribution metadata for the manifest. A closure can't cross a process
/// boundary, so its ref is `inline`; wasm words carry a content address and
/// are the only kind that travels whole.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutorMeta {
    pub kind: ExecutorKind,
    #[serde(rename = "ref")]
    pub reference: String,
}

type Runner =
    Arc<dyn Fn(Value, Ctx) -> BoxFuture<'static, Result<Value, WordError>> + Send + Sync>;

#[derive(Clone)]
pub struct Word {
    pub nsid: String,
    pub description: String,
    pub mode: WordMode,
    pub caps: Vec<Cap>,
    pub input_schema: Value,
    pub output_schema: Value,
    pub executor: ExecutorMeta,
    runner: Runner,
}

impl std::fmt::Debug for Word {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Word")
            .field("nsid", &self.nsid)
            .field("mode", &self.mode)
            .field("caps", &self.caps)
            .field("executor", &self.executor)
            .finish_non_exhaustive()
    }
}

pub(crate) fn schema_of<T: JsonSchema>() -> Value {
    let schema = schemars::SchemaGenerator::default().into_root_schema_for::<T>();
    serde_json::to_value(&schema).unwrap_or(Value::Null)
}

/// NSID: ≥3 dotted segments, each `[a-zA-Z][a-zA-Z0-9-]*` (final segment may
/// be camelCase per atproto convention).
pub fn validate_nsid(nsid: &str) -> Result<(), WordError> {
    let segs: Vec<&str> = nsid.split('.').collect();
    if segs.len() < 3 {
        return Err(WordError::InvalidNsid(nsid.to_string()));
    }
    for seg in &segs {
        let mut chars = seg.chars();
        let ok_head = chars.next().is_some_and(|c| c.is_ascii_alphabetic());
        let ok_tail = chars.all(|c| c.is_ascii_alphanumeric() || c == '-');
        if !ok_head || !ok_tail {
            return Err(WordError::InvalidNsid(nsid.to_string()));
        }
    }
    Ok(())
}

impl Word {
    /// Define a word from a typed closure — the authoring SSOT.
    ///
    /// The compile-time bound `I: JsonSchema` *is* the expressiveness lint:
    /// types that can't lower to JSON Schema don't implement it.
    pub fn closure<I, O, F, Fut>(
        nsid: &str,
        description: &str,
        mode: WordMode,
        caps: Vec<Cap>,
        f: F,
    ) -> Result<Word, WordError>
    where
        I: DeserializeOwned + JsonSchema + Send + 'static,
        O: Serialize + JsonSchema + Send + 'static,
        F: Fn(I, Ctx) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = Result<O, WordError>> + Send + 'static,
    {
        let f = Arc::new(f);
        let runner: Runner = Arc::new(move |input: Value, ctx: Ctx| {
            let f = f.clone();
            Box::pin(async move {
                let typed: I = serde_json::from_value(input)
                    .map_err(|e| WordError::InvalidInput(e.to_string()))?;
                let out = f(typed, ctx).await?;
                serde_json::to_value(out).map_err(|e| WordError::InvalidOutput(e.to_string()))
            })
        });
        Self::build::<I, O>(
            nsid,
            description,
            mode,
            caps,
            ExecutorMeta {
                kind: ExecutorKind::Closure,
                reference: "inline".to_string(),
            },
            runner,
        )
    }

    /// Define a word that runs a `kotoba-udf` WASM component on kotoba-runtime.
    ///
    /// Convention: input is one CBOR row (the JSON input encoded as CBOR), the
    /// component's `eval` returns one CBOR row decoded back as the typed output.
    /// This is the only executor kind whose body can travel between roots —
    /// its ref is the blake3 content address of the component bytes.
    #[cfg(feature = "wasm-udf")]
    pub fn wasm_udf<I, O>(
        nsid: &str,
        description: &str,
        mode: WordMode,
        caps: Vec<Cap>,
        wasm_bytes: Vec<u8>,
    ) -> Result<Word, WordError>
    where
        I: DeserializeOwned + Serialize + JsonSchema + Send + 'static,
        O: DeserializeOwned + Serialize + JsonSchema + Send + 'static,
    {
        use std::sync::OnceLock;
        static UDF: OnceLock<kotoba_runtime::UdfExecutor> = OnceLock::new();

        let program_cid = format!("blake3:{}", blake3::hash(&wasm_bytes).to_hex());
        let bytes = Arc::new(wasm_bytes);
        let cid_for_runner = program_cid.clone();

        let runner: Runner = Arc::new(move |input: Value, _ctx: Ctx| {
            let bytes = bytes.clone();
            let cid = cid_for_runner.clone();
            Box::pin(async move {
                // validate against the typed signature before crossing into wasm
                let typed: I = serde_json::from_value(input)
                    .map_err(|e| WordError::InvalidInput(e.to_string()))?;
                let json = serde_json::to_value(&typed)
                    .map_err(|e| WordError::InvalidInput(e.to_string()))?;
                let mut row = Vec::new();
                ciborium::into_writer(&json, &mut row)
                    .map_err(|e| WordError::Executor(format!("cbor encode: {e}")))?;

                let out_rows = tokio::task::spawn_blocking(move || {
                    let exec = UDF.get_or_init(|| {
                        kotoba_runtime::UdfExecutor::new().expect("init wasm udf engine")
                    });
                    exec.eval(&cid, &bytes, vec![row])
                })
                .await
                .map_err(|e| WordError::Executor(format!("join: {e}")))?
                .map_err(|e| WordError::Executor(format!("udf eval: {e}")))?;

                let first = out_rows
                    .into_iter()
                    .next()
                    .ok_or_else(|| WordError::Executor("udf returned no rows".into()))?;
                let json: Value = ciborium::from_reader(first.as_slice())
                    .map_err(|e| WordError::Executor(format!("cbor decode: {e}")))?;
                let out: O = serde_json::from_value(json)
                    .map_err(|e| WordError::InvalidOutput(e.to_string()))?;
                serde_json::to_value(out).map_err(|e| WordError::InvalidOutput(e.to_string()))
            })
        });

        Self::build::<I, O>(
            nsid,
            description,
            mode,
            caps,
            ExecutorMeta {
                kind: ExecutorKind::Wasm,
                reference: program_cid,
            },
            runner,
        )
    }

    fn build<I: JsonSchema, O: JsonSchema>(
        nsid: &str,
        description: &str,
        mode: WordMode,
        caps: Vec<Cap>,
        executor: ExecutorMeta,
        runner: Runner,
    ) -> Result<Word, WordError> {
        validate_nsid(nsid)?;
        let input_schema = schema_of::<I>();
        let output_schema = schema_of::<O>();
        let top = input_schema
            .get("type")
            .and_then(|t| t.as_str())
            .unwrap_or("unknown");
        if top != "object" {
            return Err(WordError::NonObjectInput(top.to_string()));
        }
        Ok(Word {
            nsid: nsid.to_string(),
            description: description.to_string(),
            mode,
            caps,
            input_schema,
            output_schema,
            executor,
            runner,
        })
    }

    /// Override the executor metadata recorded in the manifest (e.g. a closure
    /// that wraps `git` can declare itself `process / git` for provenance).
    pub fn with_executor_meta(mut self, kind: ExecutorKind, reference: impl Into<String>) -> Word {
        self.executor = ExecutorMeta {
            kind,
            reference: reference.into(),
        };
        self
    }

    pub async fn invoke(&self, input: Value, ctx: Ctx) -> Result<Value, WordError> {
        (self.runner)(input, ctx).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize, Serialize, JsonSchema)]
    struct AddIn {
        a: f64,
        b: f64,
    }
    #[derive(Deserialize, Serialize, JsonSchema)]
    struct AddOut {
        sum: f64,
    }

    fn add_word() -> Word {
        Word::closure(
            "com.example.word.math.add",
            "add two numbers",
            WordMode::Query,
            vec![],
            |i: AddIn, _ctx| async move { Ok(AddOut { sum: i.a + i.b }) },
        )
        .unwrap()
    }

    #[tokio::test]
    async fn closure_word_invokes_typed() {
        let w = add_word();
        let out = w
            .invoke(serde_json::json!({"a": 2.0, "b": 40.0}), Ctx::default())
            .await
            .unwrap();
        assert_eq!(out, serde_json::json!({"sum": 42.0}));
    }

    #[tokio::test]
    async fn closure_word_rejects_bad_input() {
        let w = add_word();
        let err = w
            .invoke(serde_json::json!({"a": "two"}), Ctx::default())
            .await
            .unwrap_err();
        assert!(matches!(err, WordError::InvalidInput(_)));
    }

    #[test]
    fn schema_extracted_from_signature() {
        let w = add_word();
        assert_eq!(w.input_schema["type"], "object");
        assert_eq!(w.input_schema["properties"]["a"]["type"], "number");
        assert_eq!(w.output_schema["properties"]["sum"]["type"], "number");
    }

    #[test]
    fn non_object_input_rejected() {
        let r = Word::closure(
            "com.example.word.bad.scalar",
            "scalar input is not MCP-projectable",
            WordMode::Query,
            vec![],
            |i: String, _ctx| async move { Ok(i) },
        );
        assert!(matches!(r, Err(WordError::NonObjectInput(_))));
    }

    #[test]
    fn nsid_validation() {
        assert!(validate_nsid("com.example.word.fooBar").is_ok());
        assert!(validate_nsid("two.segments").is_err());
        assert!(validate_nsid("com.exa mple.word").is_err());
        assert!(validate_nsid("com.example.9word").is_err());
    }
}
