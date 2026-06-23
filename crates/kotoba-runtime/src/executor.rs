use anyhow::Result;
use tracing::instrument;
use wasmtime::component::Func;

use crate::error::RuntimeError;
use crate::host::{HostState, InferenceFn, KotobaEngine, PendingQuad, WitQuad};
use crate::program::ProgramStore;

/// InvokeContext is CBOR-decoded from the Invoke ChainEntry input field.
#[derive(Debug, serde::Deserialize, serde::Serialize)]
pub struct InvokeContext {
    /// Named graph CID this invocation operates on
    pub graph: String,
    /// Session CID (for stateful invocations; None for UDF-style)
    pub session_cid: Option<String>,
    /// CBOR-encoded arguments
    pub args_cbor: Vec<u8>,
}

/// InvokeResult is written back as the Result ChainEntry output field.
#[derive(Debug, serde::Deserialize, serde::Serialize)]
pub struct InvokeResult {
    pub output_cbor: Vec<u8>,
    pub gas_used: u64,
    /// Datom projection writes to apply after successful execution
    pub assert_quads: Vec<SerializedQuad>,
    pub retract_quads: Vec<SerializedQuad>,
    /// kse.publish calls made by the guest — caller routes to KSE LiveBus
    pub pending_publishes: Vec<(String, Vec<u8>)>,
    /// chain.append-infer calls made by the guest — caller appends to SourceChain
    pub pending_chain_entries: Vec<(String, String, String)>,
    /// llm.load-lora calls made by the guest — (base_model_cid, lora_cid) pairs
    pub pending_lora_loads: Vec<(String, String)>,
}

#[derive(Debug, serde::Deserialize, serde::Serialize)]
pub struct SerializedQuad {
    pub graph: String,
    pub subject: String,
    pub predicate: String,
    pub object_cbor: Vec<u8>,
}

impl From<PendingQuad> for SerializedQuad {
    fn from(q: PendingQuad) -> Self {
        Self {
            graph: q.graph,
            subject: q.subject,
            predicate: q.predicate,
            object_cbor: q.object_cbor,
        }
    }
}

/// Executor: takes an Invoke ChainEntry and runs the WASM component.
///
/// Execution model (Kotoba Superstep):
///   1. Decode InvokeContext from Invoke.input (CBOR)
///   2. Load / compile program_cid → Component (via ProgramStore)
///   3. Create `Store<HostState>` + bind all KOTOBA WIT host interfaces
///   4. Instantiate Component → call guest export `run(ctx_cbor)`
///   5. Collect pending_asserts + pending_retracts from HostState
///   6. Return InvokeResult (caller appends to SourceChain + applies to Arrangement)
pub struct WasmExecutor {
    engine: KotobaEngine,
    programs: ProgramStore,
    gas_limit: u64,
    inference_engine: Option<InferenceFn>,
}

impl WasmExecutor {
    pub fn new(gas_limit: u64) -> Result<Self> {
        anyhow::ensure!(
            gas_limit > 0,
            "gas_limit must be > 0 (gas-less execution is prohibited)"
        );
        let engine = KotobaEngine::new()?;
        let programs = ProgramStore::new(engine.clone());
        Ok(Self {
            engine,
            programs,
            gas_limit,
            inference_engine: None,
        })
    }

    /// Construct a `WasmExecutor` with a pre-loaded local inference engine.
    ///
    /// The engine is forwarded into every `HostState` created at execute time,
    /// making `llm.infer` calls in guest WASM functional without a remote bridge.
    pub fn with_inference(gas_limit: u64, engine: InferenceFn) -> Result<Self> {
        let mut s = Self::new(gas_limit)?;
        s.inference_engine = Some(engine);
        Ok(s)
    }

    #[instrument(
        skip(self, agent_did, wasm_bytes, ctx_cbor, quad_snapshot, head_commits),
        fields(program_cid)
    )]
    /// Invoke the `run` export (kotoba-node world): `run(ctx-cbor) -> result`.
    pub fn execute(
        &self,
        program_cid: &str,
        wasm_bytes: &[u8],
        agent_did: &str,
        ctx_cbor: Vec<u8>,
        quad_snapshot: Vec<WitQuad>,
        head_commits: std::collections::HashMap<String, String>,
    ) -> Result<InvokeResult, RuntimeError> {
        use wasmtime::component::Val;
        let args = vec![Val::List(ctx_cbor.iter().map(|b| Val::U8(*b)).collect())];
        self.invoke(program_cid, wasm_bytes, agent_did, "run", args, quad_snapshot, head_commits)
    }

    /// HTTP trigger (M11): `on-http(req-cbor) -> result` — same ABI as `run`.
    pub fn execute_on_http(
        &self,
        program_cid: &str,
        wasm_bytes: &[u8],
        agent_did: &str,
        req_cbor: Vec<u8>,
        quad_snapshot: Vec<WitQuad>,
        head_commits: std::collections::HashMap<String, String>,
    ) -> Result<InvokeResult, RuntimeError> {
        use wasmtime::component::Val;
        let args = vec![Val::List(req_cbor.iter().map(|b| Val::U8(*b)).collect())];
        self.invoke(program_cid, wasm_bytes, agent_did, "on-http", args, quad_snapshot, head_commits)
    }

    /// Cron trigger (M11): `on-tick(epoch-ms: u64) -> result`.
    pub fn execute_on_tick(
        &self,
        program_cid: &str,
        wasm_bytes: &[u8],
        agent_did: &str,
        epoch_ms: u64,
        quad_snapshot: Vec<WitQuad>,
        head_commits: std::collections::HashMap<String, String>,
    ) -> Result<InvokeResult, RuntimeError> {
        use wasmtime::component::Val;
        let args = vec![Val::U64(epoch_ms)];
        self.invoke(program_cid, wasm_bytes, agent_did, "on-tick", args, quad_snapshot, head_commits)
    }

    /// KSE-topic trigger (M11): `on-kse(topic: string, payload: list<u8>) -> result`.
    #[allow(clippy::too_many_arguments)]
    pub fn execute_on_kse(
        &self,
        program_cid: &str,
        wasm_bytes: &[u8],
        agent_did: &str,
        topic: String,
        payload: Vec<u8>,
        quad_snapshot: Vec<WitQuad>,
        head_commits: std::collections::HashMap<String, String>,
    ) -> Result<InvokeResult, RuntimeError> {
        use wasmtime::component::Val;
        let args = vec![
            Val::String(topic),
            Val::List(payload.iter().map(|b| Val::U8(*b)).collect()),
        ];
        self.invoke(program_cid, wasm_bytes, agent_did, "on-kse", args, quad_snapshot, head_commits)
    }

    /// Invoke a named component export via dynamic `Val` dispatch, applying the
    /// shared host setup (HostState, gas, snapshot, head commits) and parsing a
    /// `result<list<u8>, string>` return. The trigger-specific methods above are
    /// thin wrappers that build the right export name + args.
    #[allow(clippy::too_many_arguments)]
    pub fn invoke(
        &self,
        program_cid: &str,
        wasm_bytes: &[u8],
        agent_did: &str,
        export_name: &str,
        args: Vec<wasmtime::component::Val>,
        quad_snapshot: Vec<WitQuad>,
        head_commits: std::collections::HashMap<String, String>,
    ) -> Result<InvokeResult, RuntimeError> {
        let component = self
            .programs
            .get_or_compile(program_cid, wasm_bytes)
            .map_err(RuntimeError::CompileFailed)?;

        let state = match &self.inference_engine {
            Some(e) => HostState::with_inference_and_snapshot(
                agent_did,
                self.gas_limit,
                e.clone(),
                quad_snapshot,
            )
            .with_head_commits(head_commits),
            None => HostState::new(agent_did, self.gas_limit)
                .with_snapshot(quad_snapshot)
                .with_head_commits(head_commits),
        };
        let mut store = self.engine.new_store(state);

        let mut linker = self.engine.new_linker();
        linker
            .bind_kotoba_interfaces()
            .map_err(RuntimeError::HostCall)?;

        let instance = linker
            .0
            .instantiate(&mut store, &component)
            .map_err(RuntimeError::InstantiateFailed)?;

        // Locate the requested export (run / on-http / on-tick / on-kse, …)
        let func: Func = instance
            .get_func(&mut store, export_name)
            .ok_or_else(|| RuntimeError::GuestError(format!("missing `{export_name}` export")))?;

        // Call via dynamic Val dispatch (avoids wit-bindgen dependency at call site)
        use wasmtime::component::Val;
        let mut results = vec![Val::Bool(false)];

        func.call(&mut store, &args, &mut results)
            .map_err(|e| RuntimeError::Trap(e.to_string()))?;

        // Parse result<list<u8>, string> from Val
        let output_cbor = match &results[0] {
            Val::Result(Ok(Some(inner))) => match inner.as_ref() {
                Val::List(bytes) => bytes
                    .iter()
                    .filter_map(|v| if let Val::U8(b) = v { Some(*b) } else { None })
                    .collect::<Vec<u8>>(),
                _ => return Err(RuntimeError::GuestError("unexpected output type".into())),
            },
            Val::Result(Err(Some(inner))) => {
                let msg = match inner.as_ref() {
                    Val::String(s) => s.to_string(),
                    _ => "unknown guest error".into(),
                };
                return Err(RuntimeError::GuestError(msg));
            }
            _ => return Err(RuntimeError::GuestError("unexpected result variant".into())),
        };

        let gas_used = self.gas_limit - store.data().gas_remaining;
        let assert_quads = store
            .data()
            .pending_asserts
            .iter()
            .cloned()
            .map(SerializedQuad::from)
            .collect();
        let retract_quads = store
            .data()
            .pending_retracts
            .iter()
            .cloned()
            .map(SerializedQuad::from)
            .collect();
        let pending_publishes = store.data().pending_publishes.clone();
        let pending_chain_entries = store.data().pending_chain_entries.clone();
        let pending_lora_loads = store.data().pending_lora_loads.clone();

        Ok(InvokeResult {
            output_cbor,
            gas_used,
            assert_quads,
            retract_quads,
            pending_publishes,
            pending_chain_entries,
            pending_lora_loads,
        })
    }
}
