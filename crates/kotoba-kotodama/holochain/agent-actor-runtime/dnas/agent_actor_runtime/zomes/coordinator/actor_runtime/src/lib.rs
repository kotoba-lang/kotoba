use actor_runtime_integrity::{
    ActorEvent, EntryTypes, GraphKind, GraphRun, LangActor, LinkTypes, RunStatus, RuntimeFamily,
};
use hdk::prelude::*;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct RegisterLangActorInput {
    pub actor_did: String,
    pub assistant_id: String,
    pub runtime_family: RuntimeFamily,
    pub graph_kind: GraphKind,
    pub factory_path: Option<String>,
    pub graph_spec_cid: Option<String>,
    pub policy_cid: Option<String>,
    pub created_at: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct StartGraphRunInput {
    pub actor_did: String,
    pub assistant_id: String,
    pub run_id: String,
    pub input_cid: String,
    pub started_at: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CommitActorEventInput {
    pub actor_did: String,
    pub assistant_id: String,
    pub run_id: String,
    pub command_id: String,
    pub lexicon_nsid: String,
    pub input_cid: String,
    pub output_cid: Option<String>,
    pub occurred_at: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ActorHeadInput {
    pub actor_did: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AgentActorDescriptor {
    pub agent_pub_key: AgentPubKey,
    pub actor_did: String,
    pub assistant_id: String,
    pub runtime_family: RuntimeFamily,
    pub graph_kind: GraphKind,
    pub entry_hash: EntryHash,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ActorEventReceipt {
    pub action_hash: ActionHash,
    pub entry_hash: EntryHash,
    pub actor_did: String,
    pub assistant_id: String,
    pub run_id: String,
    pub command_id: String,
}

#[hdk_extern]
pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
    Ok(InitCallbackResult::Pass)
}

#[hdk_extern]
pub fn register_langgraph_actor(input: RegisterLangActorInput) -> ExternResult<AgentActorDescriptor> {
    register_lang_actor(RegisterLangActorInput {
        runtime_family: RuntimeFamily::LangGraph,
        ..input
    })
}

#[hdk_extern]
pub fn register_langchain_actor(input: RegisterLangActorInput) -> ExternResult<AgentActorDescriptor> {
    register_lang_actor(RegisterLangActorInput {
        runtime_family: RuntimeFamily::LangChain,
        ..input
    })
}

#[hdk_extern]
pub fn register_lang_actor(input: RegisterLangActorInput) -> ExternResult<AgentActorDescriptor> {
    let actor = LangActor {
        actor_did: input.actor_did.clone(),
        assistant_id: input.assistant_id.clone(),
        runtime_family: input.runtime_family,
        graph_kind: input.graph_kind,
        factory_path: input.factory_path,
        graph_spec_cid: input.graph_spec_cid,
        policy_cid: input.policy_cid,
        created_at: input.created_at,
    };
    let action_hash = create_entry(&EntryTypes::LangActor(actor.clone()))?;
    let entry_hash = hash_entry(&EntryTypes::LangActor(actor.clone()))?;

    let actor_base = actor_path_hash(&actor.actor_did)?;
    create_link(
        actor_base,
        entry_hash.clone(),
        LinkTypes::ActorToDefinition,
        LinkTag::new(actor.assistant_id.clone()),
    )?;

    let assistant_base = assistant_path_hash(&actor.assistant_id)?;
    create_link(
        assistant_base,
        entry_hash.clone(),
        LinkTypes::AssistantToActor,
        LinkTag::new(actor.actor_did.clone()),
    )?;

    let agent_pub_key = agent_info()?.agent_initial_pubkey;
    debug!("registered Lang actor {:?} at {:?}", action_hash, entry_hash);
    Ok(AgentActorDescriptor {
        agent_pub_key,
        actor_did: actor.actor_did,
        assistant_id: actor.assistant_id,
        runtime_family: actor.runtime_family,
        graph_kind: actor.graph_kind,
        entry_hash,
    })
}

#[hdk_extern]
pub fn start_graph_run(input: StartGraphRunInput) -> ExternResult<ActionHash> {
    let run = GraphRun {
        actor_did: input.actor_did.clone(),
        assistant_id: input.assistant_id,
        run_id: input.run_id.clone(),
        input_cid: input.input_cid,
        status: RunStatus::Running,
        started_at: input.started_at,
        completed_at: None,
    };
    let action_hash = create_entry(&EntryTypes::GraphRun(run.clone()))?;
    let entry_hash = hash_entry(&EntryTypes::GraphRun(run))?;
    let actor_base = actor_path_hash(&input.actor_did)?;
    create_link(
        actor_base,
        entry_hash,
        LinkTypes::ActorToRun,
        LinkTag::new(input.run_id),
    )?;
    Ok(action_hash)
}

#[hdk_extern]
pub fn commit_actor_event(input: CommitActorEventInput) -> ExternResult<ActorEventReceipt> {
    let event = ActorEvent {
        actor_did: input.actor_did.clone(),
        assistant_id: input.assistant_id.clone(),
        run_id: input.run_id.clone(),
        command_id: input.command_id.clone(),
        lexicon_nsid: input.lexicon_nsid,
        input_cid: input.input_cid,
        output_cid: input.output_cid,
        occurred_at: input.occurred_at,
    };
    let action_hash = create_entry(&EntryTypes::ActorEvent(event.clone()))?;
    let entry_hash = hash_entry(&EntryTypes::ActorEvent(event.clone()))?;
    let actor_base = actor_path_hash(&event.actor_did)?;
    create_link(
        actor_base,
        entry_hash.clone(),
        LinkTypes::ActorToEvent,
        LinkTag::new(event.command_id.clone()),
    )?;
    Ok(ActorEventReceipt {
        action_hash,
        entry_hash,
        actor_did: event.actor_did,
        assistant_id: event.assistant_id,
        run_id: event.run_id,
        command_id: event.command_id,
    })
}

#[hdk_extern]
pub fn latest_actor_head(input: ActorHeadInput) -> ExternResult<Option<ActorEvent>> {
    let actor_base = actor_path_hash(&input.actor_did)?;
    let mut links = get_links(
        LinkQuery::try_new(actor_base, LinkTypes::ActorToEvent)?,
        GetStrategy::default(),
    )?;
    links.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));
    let Some(link) = links.last() else {
        return Ok(None);
    };
    let Some(entry_hash) = link.target.clone().into_entry_hash() else {
        return Ok(None);
    };
    let Some(record) = get(entry_hash, GetOptions::default())? else {
        return Ok(None);
    };
    record
        .entry()
        .to_app_option::<ActorEvent>()
        .map_err(|e| wasm_error!(e))
}

#[hdk_extern]
pub fn list_actor_events(input: ActorHeadInput) -> ExternResult<Vec<ActorEvent>> {
    let actor_base = actor_path_hash(&input.actor_did)?;
    let mut links = get_links(
        LinkQuery::try_new(actor_base, LinkTypes::ActorToEvent)?,
        GetStrategy::default(),
    )?;
    links.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));

    let mut events = Vec::new();
    for link in links {
        let Some(entry_hash) = link.target.into_entry_hash() else {
            continue;
        };
        if let Some(record) = get(entry_hash, GetOptions::default())? {
            if let Some(event) = record
                .entry()
                .to_app_option::<ActorEvent>()
                .map_err(|e| wasm_error!(e))?
            {
                events.push(event);
            }
        }
    }
    Ok(events)
}

fn actor_path_hash(actor_did: &str) -> ExternResult<EntryHash> {
    anchor_hash(format!("actor.{}", path_segment(actor_did)))
}

fn assistant_path_hash(assistant_id: &str) -> ExternResult<EntryHash> {
    anchor_hash(format!("assistant.{}", path_segment(assistant_id)))
}

fn anchor_hash(value: String) -> ExternResult<EntryHash> {
    let bytes = SerializedBytes::from(UnsafeBytes::from(value.into_bytes()));
    let entry = Entry::app(bytes).map_err(|e| wasm_error!(e.to_string()))?;
    hash_entry(entry)
}

fn path_segment(value: &str) -> String {
    value
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.' {
                c
            } else {
                '_'
            }
        })
        .collect()
}
