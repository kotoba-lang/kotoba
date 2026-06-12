use hdi::prelude::*;

#[hdk_entry_helper]
#[derive(Clone)]
pub struct LangActor {
    pub actor_did: String,
    pub assistant_id: String,
    pub runtime_family: RuntimeFamily,
    pub graph_kind: GraphKind,
    pub factory_path: Option<String>,
    pub graph_spec_cid: Option<String>,
    pub policy_cid: Option<String>,
    pub created_at: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum RuntimeFamily {
    LangChain,
    LangGraph,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum GraphKind {
    PyFactory,
    Topology,
    SingleTask,
    Chain,
}

#[hdk_entry_helper]
#[derive(Clone)]
pub struct GraphRun {
    pub actor_did: String,
    pub assistant_id: String,
    pub run_id: String,
    pub input_cid: String,
    pub status: RunStatus,
    pub started_at: String,
    pub completed_at: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum RunStatus {
    Queued,
    Running,
    Succeeded,
    Failed,
}

#[hdk_entry_helper]
#[derive(Clone)]
pub struct ActorEvent {
    pub actor_did: String,
    pub assistant_id: String,
    pub run_id: String,
    pub command_id: String,
    pub lexicon_nsid: String,
    pub input_cid: String,
    pub output_cid: Option<String>,
    pub occurred_at: String,
}

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    #[entry_type(required_validations = 5)]
    LangActor(LangActor),
    #[entry_type(required_validations = 5)]
    GraphRun(GraphRun),
    #[entry_type(required_validations = 5)]
    ActorEvent(ActorEvent),
}

#[hdk_link_types]
pub enum LinkTypes {
    ActorToDefinition,
    ActorToRun,
    ActorToEvent,
    AssistantToActor,
}

#[hdk_extern]
pub fn validate(_: Op) -> ExternResult<ValidateCallbackResult> {
    Ok(ValidateCallbackResult::Valid)
}
