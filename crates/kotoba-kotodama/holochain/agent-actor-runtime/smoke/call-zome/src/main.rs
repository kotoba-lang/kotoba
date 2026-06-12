use actor_runtime_integrity::{ActorEvent, GraphKind, RuntimeFamily};
use anyhow::{Context, Result};
use holo_hash::HasHash;
use holochain::sweettest::{SweetConductor, SweetDnaFile};
use holochain_types::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Serialize, Debug)]
struct RegisterLangActorInput {
    actor_did: String,
    assistant_id: String,
    runtime_family: RuntimeFamily,
    graph_kind: GraphKind,
    factory_path: Option<String>,
    graph_spec_cid: Option<String>,
    policy_cid: Option<String>,
    created_at: String,
}

#[derive(Serialize, Debug)]
struct StartGraphRunInput {
    actor_did: String,
    assistant_id: String,
    run_id: String,
    input_cid: String,
    started_at: String,
}

#[derive(Serialize, Debug)]
struct CommitActorEventInput {
    actor_did: String,
    assistant_id: String,
    run_id: String,
    command_id: String,
    lexicon_nsid: String,
    input_cid: String,
    output_cid: Option<String>,
    occurred_at: String,
}

#[derive(Serialize, Debug)]
struct ActorHeadInput {
    actor_did: String,
}

#[derive(Deserialize, Serialize, Debug)]
struct AgentActorDescriptor {
    agent_pub_key: AgentPubKey,
    actor_did: String,
    assistant_id: String,
    runtime_family: RuntimeFamily,
    graph_kind: GraphKind,
    entry_hash: EntryHash,
}

#[derive(Deserialize, Serialize, Debug)]
struct ActorEventReceipt {
    action_hash: ActionHash,
    entry_hash: EntryHash,
    actor_did: String,
    assistant_id: String,
    run_id: String,
    command_id: String,
}

#[derive(Serialize)]
struct SmokeProof {
    runtime: &'static str,
    call_zome: bool,
    conductor: &'static str,
    dna: &'static str,
    zome: &'static str,
    actor: AgentActorDescriptor,
    start_graph_run_action: ActionHash,
    event_receipt: ActorEventReceipt,
    latest_actor_head: Option<ActorEvent>,
    event_count: usize,
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<()> {
    let root = runtime_root();
    let wasm_dir = root.join("target/wasm32-unknown-unknown/release");
    let integrity_wasm = load_wasm(&wasm_dir.join("actor_runtime_integrity.wasm"))?;
    let coordinator_wasm = load_wasm(&wasm_dir.join("actor_runtime.wasm"))?;

    let integrity_hash = DnaWasmHashed::from_content(integrity_wasm.clone())
        .await
        .into_hash();
    let coordinator_hash = DnaWasmHashed::from_content(coordinator_wasm.clone())
        .await
        .into_hash();

    let integrity_zome = IntegrityZome::new(
        "actor_runtime_integrity".into(),
        IntegrityZomeDef::from_hash(integrity_hash),
    );
    let coordinator_zome = CoordinatorZome::new(
        "actor_runtime".into(),
        CoordinatorZomeDef::from_hash(coordinator_hash),
    );
    let (dna, _, _) = SweetDnaFile::unique_from_zomes(
        vec![integrity_zome],
        vec![coordinator_zome],
        vec![integrity_wasm, coordinator_wasm],
    )
    .await;

    let mut conductor = SweetConductor::from_standard_config().await;
    let app = conductor
        .setup_app("holochain-agent-runtime-call-zome-smoke", [&dna])
        .await
        .context("install and enable smoke app")?;
    let zome = app.cells()[0].zome("actor_runtime");

    let actor_did = "did:web:holochain-agent-runtime.etzhayyim.com".to_string();
    let assistant_id = "echo".to_string();
    let run_id = "call-zome-smoke-20260509".to_string();

    let actor: AgentActorDescriptor = conductor
        .call(
            &zome,
            "register_langgraph_actor",
            RegisterLangActorInput {
                actor_did: actor_did.clone(),
                assistant_id: assistant_id.clone(),
                runtime_family: RuntimeFamily::LangGraph,
                graph_kind: GraphKind::PyFactory,
                factory_path: Some("pykotodama.langgraph_graphs.echo:build_graph".to_string()),
                graph_spec_cid: None,
                policy_cid: Some("cid://policy/holochain-agent-runtime-smoke".to_string()),
                created_at: "2026-05-09T18:00:00+09:00".to_string(),
            },
        )
        .await;

    let start_graph_run_action: ActionHash = conductor
        .call(
            &zome,
            "start_graph_run",
            StartGraphRunInput {
                actor_did: actor_did.clone(),
                assistant_id: assistant_id.clone(),
                run_id: run_id.clone(),
                input_cid: "cid://input/holochain-langgraph-echo-smoke".to_string(),
                started_at: "2026-05-09T18:00:01+09:00".to_string(),
            },
        )
        .await;

    let event_receipt: ActorEventReceipt = conductor
        .call(
            &zome,
            "commit_actor_event",
            CommitActorEventInput {
                actor_did: actor_did.clone(),
                assistant_id: assistant_id.clone(),
                run_id: run_id.clone(),
                command_id: "cmd-call-zome-smoke-20260509".to_string(),
                lexicon_nsid: "com.etzhayyim.agentRuntime.graphRun.completed".to_string(),
                input_cid: "cid://input/holochain-langgraph-echo-smoke".to_string(),
                output_cid: Some("cid://output/holochain-langgraph-echo-smoke".to_string()),
                occurred_at: "2026-05-09T18:00:02+09:00".to_string(),
            },
        )
        .await;

    let latest_actor_head: Option<ActorEvent> = conductor
        .call(
            &zome,
            "latest_actor_head",
            ActorHeadInput {
                actor_did: actor_did.clone(),
            },
        )
        .await;
    let events: Vec<ActorEvent> = conductor
        .call(
            &zome,
            "list_actor_events",
            ActorHeadInput { actor_did },
        )
        .await;

    let proof = SmokeProof {
        runtime: "holochain-agent-actor-runtime",
        call_zome: true,
        conductor: "SweetConductor",
        dna: "agent_actor_runtime",
        zome: "actor_runtime",
        actor,
        start_graph_run_action,
        event_receipt,
        latest_actor_head,
        event_count: events.len(),
    };
    println!("{}", serde_json::to_string_pretty(&proof)?);
    Ok(())
}

fn runtime_root() -> PathBuf {
    std::env::var_os("HC_AGENT_RUNTIME_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

fn load_wasm(path: &Path) -> Result<DnaWasm> {
    let bytes = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    Ok(DnaWasm {
        code: bytes::Bytes::from(bytes),
    })
}
