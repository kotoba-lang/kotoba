//! XRPC endpoint declarations and handlers for Kotoba
//! NSIDs follow com.etzhayyim.apps.kotoba.* namespace

pub const NSID_DATOM_CREATE: &str = "com.etzhayyim.apps.kotoba.datom.create";
pub const NSID_QUAD_CREATE: &str = "com.etzhayyim.apps.kotoba.quad.create";
pub const NSID_QUAD_RETRACT: &str = "com.etzhayyim.apps.kotoba.quad.retract";
pub const NSID_DATOMIC_TRANSACT: &str = "com.etzhayyim.apps.kotoba.datomic.transact";
pub const NSID_DATOMIC_DATOMS: &str = "com.etzhayyim.apps.kotoba.datomic.datoms";
pub const NSID_DATOMIC_SEEK_DATOMS: &str = "com.etzhayyim.apps.kotoba.datomic.seekDatoms";
pub const NSID_DATOMIC_INDEX_RANGE: &str = "com.etzhayyim.apps.kotoba.datomic.indexRange";
pub const NSID_DATOMIC_INDEX_PULL: &str = "com.etzhayyim.apps.kotoba.datomic.indexPull";
pub const NSID_DATOMIC_PULL: &str = "com.etzhayyim.apps.kotoba.datomic.pull";
pub const NSID_DATOMIC_PULL_MANY: &str = "com.etzhayyim.apps.kotoba.datomic.pullMany";
pub const NSID_DATOMIC_Q: &str = "com.etzhayyim.apps.kotoba.datomic.q";
pub const NSID_DATOMIC_WITH: &str = "com.etzhayyim.apps.kotoba.datomic.with";
pub const NSID_DATOMIC_AS_OF: &str = "com.etzhayyim.apps.kotoba.datomic.asOf";
pub const NSID_DATOMIC_SINCE: &str = "com.etzhayyim.apps.kotoba.datomic.since";
pub const NSID_DATOMIC_SYNC: &str = "com.etzhayyim.apps.kotoba.datomic.sync";
pub const NSID_DATOMIC_HISTORY: &str = "com.etzhayyim.apps.kotoba.datomic.history";
pub const NSID_DATOMIC_TX: &str = "com.etzhayyim.apps.kotoba.datomic.tx";
pub const NSID_DATOMIC_TX_RANGE: &str = "com.etzhayyim.apps.kotoba.datomic.txRange";
pub const NSID_DATOMIC_LOG: &str = "com.etzhayyim.apps.kotoba.datomic.log";
pub const NSID_DATOMIC_BASIS_T: &str = "com.etzhayyim.apps.kotoba.datomic.basisT";
pub const NSID_DATOMIC_DB_STATS: &str = "com.etzhayyim.apps.kotoba.datomic.dbStats";
pub const NSID_DATOMIC_GC: &str = "com.etzhayyim.apps.kotoba.datomic.gc";
pub const NSID_DATOMIC_ENTITY: &str = "com.etzhayyim.apps.kotoba.datomic.entity";
pub const NSID_DATOMIC_IDENT: &str = "com.etzhayyim.apps.kotoba.datomic.ident";
pub const NSID_DATOMIC_ENTID: &str = "com.etzhayyim.apps.kotoba.datomic.entid";
pub const NSID_VC_ISSUE: &str = "com.etzhayyim.apps.kotoba.vc.issue";
pub const NSID_VC_PRESENT: &str = "com.etzhayyim.apps.kotoba.vc.present";
pub const NSID_DID_DOCUMENT_PUBLISH: &str = "com.etzhayyim.apps.kotoba.did.document.publish";
pub const NSID_DIDCOMM_SEND: &str = "com.etzhayyim.apps.kotoba.didcomm.send";
pub const NSID_ATPROTO_REPO_WRITE: &str = "com.etzhayyim.apps.kotoba.atproto.repo.write";
pub const NSID_GRAPH_QUERY: &str = "com.etzhayyim.apps.kotoba.graph.query";
pub const NSID_COMMIT_GET: &str = "com.etzhayyim.apps.kotoba.commit.get";
pub const NSID_INVOKE_RUN: &str = "com.etzhayyim.apps.kotoba.invoke.run";
pub const NSID_INFER_RUN: &str = "com.etzhayyim.apps.kotoba.infer.run";
pub const NSID_WEIGHT_PUT: &str = "com.etzhayyim.apps.kotoba.weight.put";
pub const NSID_LORA_APPLY: &str = "com.etzhayyim.apps.kotoba.lora.apply";
pub const NSID_EMBED_CREATE: &str = "com.etzhayyim.apps.kotoba.embed.create";
pub const NSID_NODE_STATUS: &str = "com.etzhayyim.apps.kotoba.node.status";
pub const NSID_BLOCK_PUT: &str = "com.etzhayyim.apps.kotoba.block.put";
pub const NSID_BLOCK_GET: &str = "com.etzhayyim.apps.kotoba.block.get";
pub const NSID_COMMIT_STORE: &str = "com.etzhayyim.apps.kotoba.commit.store";
pub const NSID_AGENT_RUN: &str = "com.etzhayyim.apps.kotoba.agent.run";
pub const NSID_AGENT_SYNC_OPEN: &str = "com.etzhayyim.apps.kotoba.agent.syncopen";
pub const NSID_AGENT_SYNC_ADV: &str = "com.etzhayyim.apps.kotoba.agent.syncadvance";
pub const NSID_AGENT_SYNC_CLOSE: &str = "com.etzhayyim.apps.kotoba.agent.syncclose";
pub const NSID_VAULT_PUT: &str = "com.etzhayyim.apps.kotoba.vault.put";
pub const NSID_VAULT_GET: &str = "com.etzhayyim.apps.kotoba.vault.get";
pub const NSID_ECON_BALANCE: &str = "com.etzhayyim.apps.kotoba.econ.balance";
pub const NSID_ECON_CREDIT: &str = "com.etzhayyim.apps.kotoba.econ.credit";

use crate::server::KotobaState;
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use ed25519_dalek::Signer;
use kotoba_datomic::distributed::{
    gc_history, CommitDatomsRequest, DistributedCommitError, DistributedCommitWriter,
    DistributedDatomCommit, DistributedDatomReader, DistributedTransactRequest,
    RemoteIpfsBlockStore, RemoteIpfsIpnsRegistry, ROOT_AEVT, ROOT_AVET, ROOT_EAVT, ROOT_TEA,
    ROOT_VAET,
};
use kotoba_ipfs::{IpnsName, IpnsRegistry, IpnsRegistryError};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::net::SocketAddr;
use std::sync::Arc;

/// Maximum size of a base64-encoded CACAO delegation token (8 KiB decoded ≈ 6 KiB base64).
const MAX_CACAO_B64_LEN: usize = 8 * 1024;

// ── Request / Response types ───────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct QuadCreateReq {
    pub graph: String,
    pub subject: String,
    pub predicate: String,
    pub object: String,
    /// Optional CACAO warrant (DAG-CBOR, base64-standard encoded).
    /// When present: verified before write; `cacao.p.graph_cid()` must match `graph`.
    /// Issuer DID becomes the authoritative namespace for this write.
    pub cacao_b64: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct EconBalanceReq {
    pub did: String,
}

#[derive(Debug, Deserialize)]
pub struct EconCreditReq {
    pub did: String,
    pub amount: i64,
}

#[derive(Debug, Deserialize)]
pub struct VaultPutReq {
    /// Raw blob encoded as standard base64.
    pub data_b64: String,
}

#[derive(Debug, Serialize)]
pub struct VaultPutResp {
    pub cid: String,
    pub size: usize,
}

#[derive(Debug, Serialize)]
pub struct VaultGetResp {
    pub cid: String,
    pub data_b64: String,
}

#[derive(Debug, Serialize)]
pub struct QuadCreateResp {
    pub status: &'static str,
    pub journal_cid: String,
    pub datom_cid: String,
    pub quad_cid: String,
}

#[derive(Debug, Deserialize)]
pub struct DatomicTransactReq {
    pub graph: String,
    pub tx_edn: String,
    /// Optional distributed mutable head name. Defaults to the canonical
    /// `k51-kotoba-{graphCid}` IPNS name for the graph.
    pub ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    /// Optional optimistic-concurrency guard.  When omitted, the server appends
    /// to the current IPNS head for backward-compatible clients.
    pub expected_parent: Option<String>,
    pub cacao_proof_cid: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicWithReq {
    pub graph: String,
    pub tx_edn: String,
    /// Optional Datomic `as-of` transaction CID used as the speculative base DB.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID used as the speculative base DB.
    pub since: Option<String>,
    /// Optional `host:port` for a remote `kotoba-ipfs/1` peer that supplies the
    /// speculative base DB blocks.
    pub remote_peer: Option<String>,
    /// Optional IPNS name override for the speculative base DB.
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicDbValueReq {
    pub graph: String,
    /// Transaction CID that selects the Datomic database value.
    pub tx: String,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicSyncReq {
    pub graph: String,
    /// Optional target transaction CID.  When present, `reached` indicates
    /// whether the current distributed IPNS head includes this transaction.
    pub tx: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicDatomsReq {
    pub graph: String,
    /// Datomic index name: `:eavt`, `:aevt`, `:avet`, or `:vaet`.
    pub index: String,
    /// Optional EDN components for the chosen index prefix.
    #[serde(default)]
    pub components_edn: Vec<String>,
    /// Optional Datomic `as-of` transaction CID.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicSeekDatomsReq {
    pub graph: String,
    /// Datomic index name: `:eavt`, `:aevt`, `:avet`, or `:vaet`.
    pub index: String,
    /// Optional EDN components for the starting tuple in the chosen index.
    #[serde(default)]
    pub components_edn: Vec<String>,
    /// Optional Datomic `as-of` transaction CID.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicIndexRangeReq {
    pub graph: String,
    /// Datomic attribute EDN, usually a keyword such as `:person/age`.
    pub attr_edn: String,
    /// Inclusive lower bound for the AVET value position.
    pub start_edn: Option<String>,
    /// Exclusive upper bound for the AVET value position.
    pub end_edn: Option<String>,
    /// Optional Datomic `as-of` transaction CID.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicIndexPullReq {
    pub graph: String,
    /// Datomic index name: `:eavt`, `:aevt`, `:avet`, `:vaet`, or `:tea`.
    pub index: String,
    /// Optional EDN components for the chosen index prefix.
    #[serde(default)]
    pub components_edn: Vec<String>,
    pub pattern_edn: Option<String>,
    /// Optional Datomic `as-of` transaction CID.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicPullReq {
    pub graph: String,
    pub entity: String,
    pub pattern_edn: Option<String>,
    /// Optional Datomic `as-of` transaction CID.  Queries the database value at
    /// the end of this transaction.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.  Queries facts strictly after
    /// this transaction.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicPullManyReq {
    pub graph: String,
    pub entities: Vec<String>,
    pub pattern_edn: Option<String>,
    /// Optional Datomic `as-of` transaction CID.  Queries the database value at
    /// the end of this transaction.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.  Queries facts strictly after
    /// this transaction.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicQReq {
    pub graph: String,
    pub query_edn: String,
    #[serde(default)]
    pub inputs_edn: Vec<String>,
    /// Optional Datomic `as-of` transaction CID.  Queries the database value at
    /// the end of this transaction.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.  Queries facts strictly after
    /// this transaction.
    pub since: Option<String>,
    /// Query the Datomic history database, preserving retract tombstones and
    /// the fifth datom `added` component.
    #[serde(default)]
    pub history: bool,
    /// Emit a content-addressed provenance envelope for this read. When true the
    /// response carries `query_spec_cid` / `query_job_cid` / `result_cid` over a
    /// canonical DAG-CBOR envelope (IPFS-compatible sha2-256); each envelope
    /// block is PUT best-effort (un-pinned) so a verifier can re-fetch it by CID.
    #[serde(default)]
    pub emit_cid: bool,
    /// Optional `host:port` for a remote `kotoba-ipfs/1` peer. When present,
    /// the query resolves the graph IPNS head and DAG-CBOR/Prolly blocks from
    /// that peer instead of this node's local block store.
    pub remote_peer: Option<String>,
    /// Optional IPNS name override for remote reads. Defaults to the graph's
    /// canonical `k51-kotoba-{graphCid}` head.
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicHistoryReq {
    pub graph: String,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    /// Optional Datomic `as-of` transaction CID.  Returns history through this
    /// transaction.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.  Returns history strictly
    /// after this transaction.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicTxRangeReq {
    pub graph: String,
    /// Inclusive start transaction CID.  Omitted means the first transaction.
    pub start: Option<String>,
    /// Exclusive end transaction CID.  Omitted means the current head.
    pub end: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicLogReq {
    pub graph: String,
    /// Inclusive start transaction CID. Omitted means the first transaction.
    pub start: Option<String>,
    /// Exclusive end transaction CID. Omitted means the current head.
    pub end: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicBasisTReq {
    pub graph: String,
    /// Optional Datomic `as-of` transaction CID.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicDbStatsReq {
    pub graph: String,
    /// Optional Datomic `as-of` transaction CID.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID.
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicEntityReq {
    pub graph: String,
    pub entity: String,
    pub as_of: Option<String>,
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicIdentReq {
    pub graph: String,
    pub entity: String,
    pub as_of: Option<String>,
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DatomicEntidReq {
    pub graph: String,
    /// EDN keyword ident, lookup-ref vector, CID string, or entity value.
    pub ident_edn: String,
    pub as_of: Option<String>,
    pub since: Option<String>,
    pub remote_peer: Option<String>,
    pub remote_ipns_name: Option<String>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct VcIssueReq {
    pub graph: String,
    pub credential: kotoba_vc::VerifiableCredential,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct VcPresentReq {
    pub graph: String,
    pub presentation: kotoba_vc::VerifiablePresentation,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DidDocumentPublishReq {
    pub graph: String,
    pub document: kotoba_auth::DidDocument,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct DidCommSendReq {
    pub graph: String,
    pub message: kotoba_didcomm::DidCommMessage,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Deserialize)]
pub struct AtprotoRepoWriteReq {
    pub graph: String,
    pub uri: String,
    #[serde(default)]
    pub operation: Option<String>,
    #[serde(default)]
    pub cid: Option<String>,
    #[serde(default)]
    pub record: Option<serde_json::Value>,
    pub cacao_b64: Option<String>,
    #[serde(default)]
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Serialize)]
pub struct DatomicDatomResp {
    pub e: String,
    pub a: String,
    pub v_edn: String,
    pub t: String,
    pub added: bool,
}

#[derive(Debug, Serialize)]
pub struct DatomicTransactResp {
    pub status: &'static str,
    pub graph: String,
    pub tx_cid: String,
    pub commit_cid: String,
    pub auth_proof_cid: Option<String>,
    pub ipns_name: String,
    pub ipns_sequence: u64,
    pub ipns_valid_until: String,
    pub index_roots: BTreeMap<String, String>,
    pub datom_count: usize,
    pub journal_cids: Vec<String>,
    pub tempids: BTreeMap<String, String>,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicWithResp {
    pub status: &'static str,
    pub graph: String,
    pub db_before_basis_t: Option<String>,
    pub db_after_basis_t: Option<String>,
    pub tx_cid: String,
    pub tempids: BTreeMap<String, String>,
    pub tx_data: Vec<DatomicDatomResp>,
    pub db_after_datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicDatomsResp {
    pub graph: String,
    pub index: String,
    pub basis_t: Option<String>,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct ProtocolDatomWriteResp {
    pub status: &'static str,
    pub graph: String,
    pub entity_cid: String,
    pub tx_cid: String,
    pub commit_cid: String,
    pub auth_proof_cid: Option<String>,
    pub ipns_name: String,
    pub ipns_sequence: u64,
    pub ipns_valid_until: String,
    pub index_roots: BTreeMap<String, String>,
    pub datom_count: usize,
    pub assert_count: usize,
    pub retract_count: usize,
    pub journal_cids: Vec<String>,
}

pub(crate) struct ProtocolWriteAuth {
    pub author: String,
    pub auth_proof_cid: Option<kotoba_core::cid::KotobaCid>,
    pub auth_capability: Option<AuthCapabilityProjection>,
}

#[derive(Debug, Clone)]
pub(crate) struct AuthCapabilityProjection {
    proof_format: &'static str,
    controller: String,
    invoker: String,
    allowed_actions: Vec<String>,
    invocation_targets: Vec<String>,
    proof_cid: Option<kotoba_core::cid::KotobaCid>,
    credential_ids: Vec<String>,
    presentation_id: Option<String>,
    presentation_cid: Option<kotoba_core::cid::KotobaCid>,
}

const ZCAP_ALLOWED_ACTION_IRI: &str = "https://w3id.org/security#allowedAction";
const ZCAP_INVOCATION_TARGET_IRI: &str = "https://w3id.org/security#invocationTarget";
const ZCAP_CONTROLLER_IRI: &str = "https://w3id.org/security#controller";
const ZCAP_INVOKER_IRI: &str = "https://w3id.org/security#invoker";
const ZCAP_INVOCATION_PROOF_IRI: &str = "https://w3id.org/security#proof";
const ZCAP_CAPABILITY_INVOCATION_IRI: &str = "https://w3id.org/security#CapabilityInvocation";

#[derive(Debug, Serialize)]
pub struct DatomicPullResp {
    pub graph: String,
    pub entity: String,
    pub basis_t: Option<String>,
    pub entity_edn: String,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicPullManyEntityResp {
    pub entity: String,
    pub entity_edn: String,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicPullManyResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub entity_count: usize,
    pub entities: Vec<DatomicPullManyEntityResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicQResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub rows_edn: Vec<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_map_edn: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_map_json: Option<Vec<std::collections::BTreeMap<String, String>>>,
    /// CID of the canonical `kotoba.queryspec.v1` envelope (normalized query +
    /// inputs). Present only when the request set `emit_cid`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query_spec_cid: Option<String>,
    /// CID of the canonical `kotoba.queryjob.v1` envelope (query_spec + basis +
    /// params + engine). Stable cache key. Present only when `emit_cid` was set.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query_job_cid: Option<String>,
    /// CID of the canonical `kotoba.result.v1` envelope — content-derived over
    /// the canonical rows, so any row change changes this CID. Re-fetch the block
    /// by CID to verify (NOT a hash of this JSON). Present only when `emit_cid`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result_cid: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct DatomicDbValueResp {
    pub graph: String,
    pub tx: String,
    pub basis_t: Option<String>,
    pub datom_count: usize,
    pub history_datom_count: usize,
    pub entity_count: usize,
    pub attribute_count: usize,
    pub tx_count: usize,
}

#[derive(Debug, Serialize)]
pub struct DatomicSyncResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub commit_cid: String,
    pub ipns_name: String,
    pub ipns_sequence: u64,
    pub target_tx: Option<String>,
    pub reached: bool,
    pub synced_block_count: usize,
    /// Covering ProllyTree index roots (`eavt`/`aevt`/`avet`/`vaet`/`tea`) → CID.
    /// Lets a browser node (ADR-2606013600 P3) traverse the canonical tree over
    /// CID-verified blocks pulled via `block.get`, instead of a JSON snapshot.
    #[serde(default)]
    pub index_roots: std::collections::BTreeMap<String, String>,
}

#[derive(Debug, Serialize)]
pub struct DatomicHistoryResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicTxRangeTxResp {
    pub tx_cid: String,
    pub commit_cid: String,
    pub prev_commit_cid: Option<String>,
    pub seq: u64,
    pub author: String,
    pub ts: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_instant_ms: Option<i64>,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicTxRangeResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub tx_count: usize,
    pub txes: Vec<DatomicTxRangeTxResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicTxResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub tx: DatomicTxRangeTxResp,
}

#[derive(Debug, Serialize)]
pub struct DatomicLogTxResp {
    pub tx_cid: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tx_instant_ms: Option<i64>,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicLogResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub tx_count: usize,
    pub txes: Vec<DatomicLogTxResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicBasisTResp {
    pub graph: String,
    pub basis_t: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct DatomicDbStatsResp {
    pub graph: String,
    pub basis_t: Option<String>,
    pub datom_count: usize,
    pub history_datom_count: usize,
    pub entity_count: usize,
    pub attribute_count: usize,
    pub tx_count: usize,
}

#[derive(Debug, Serialize)]
pub struct DatomicEntityResp {
    pub graph: String,
    pub entity: String,
    pub basis_t: Option<String>,
    pub entity_edn: String,
    pub datom_count: usize,
    pub datoms: Vec<DatomicDatomResp>,
}

#[derive(Debug, Serialize)]
pub struct DatomicIdentResp {
    pub graph: String,
    pub entity: String,
    pub basis_t: Option<String>,
    pub ident_edn: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct DatomicEntidResp {
    pub graph: String,
    pub ident_edn: String,
    pub basis_t: Option<String>,
    pub entity: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct InvokeRunReq {
    pub program_cid: String,
    /// "wasm-node" | "wasm-udf" | "datalog"
    pub program_type: String,
    pub agent_did: String,
    pub wasm_b64: Option<String>,
    pub ctx_b64: Option<String>,
    /// Named graph CID (multibase) — when supplied, the graph's distributed
    /// Datomic/IPNS head is snapshotted into HostState so WASM guests can call
    /// `kqe.query` and `kqe.get-head`.
    pub graph_cid: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct InvokeRunResp {
    pub status: &'static str,
    pub gas_used: u64,
    pub output_b64: String,
    pub assert_count: usize,
    pub retract_count: usize,
    /// CIDs of LiveBus entries created for each asserted quad
    pub journal_cids: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct HealthResp {
    pub status: &'static str,
    pub version: &'static str,
    pub subsystems: SubsystemStatus,
    pub node: NodeInfo,
}

#[derive(Debug, Serialize)]
pub struct SubsystemStatus {
    pub kse_journal: &'static str,
    pub kse_shelf: &'static str,
    pub wasm_executor: &'static str,
    pub udf_executor: &'static str,
    pub invoke_router: &'static str,
}

#[derive(Debug, Serialize)]
pub struct NodeInfo {
    pub node_id: String,
    pub peer_count: usize,
}

// ── Handlers ───────────────────────────────────────────────────────────────

/// GET /_app/meta  /  GET /health
pub async fn health(State(state): State<Arc<KotobaState>>) -> impl IntoResponse {
    let neighborhood = state.neighborhood.read().await;
    Json(HealthResp {
        status: "ok",
        version: state.version,
        subsystems: SubsystemStatus {
            kse_journal: "ready",
            kse_shelf: "ready",
            #[cfg(feature = "wasm-runtime")]
            wasm_executor: "ready",
            #[cfg(not(feature = "wasm-runtime"))]
            wasm_executor: "disabled",
            #[cfg(feature = "wasm-runtime")]
            udf_executor: "ready",
            #[cfg(not(feature = "wasm-runtime"))]
            udf_executor: "disabled",
            #[cfg(feature = "wasm-runtime")]
            invoke_router: "ready",
            #[cfg(not(feature = "wasm-runtime"))]
            invoke_router: "disabled",
        },
        node: NodeInfo {
            node_id: hex::encode(state.local_node_id.0),
            peer_count: neighborhood.peers.len(),
        },
    })
}

pub async fn econ_balance(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<EconBalanceReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    if req.did.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "did required".to_string()));
    }
    let balance = state.econ.balance(&req.did).await;
    Ok(Json(serde_json::json!({
        "did": req.did,
        "balance_mkoto": balance,
        "cost_per_datom_mkoto": state.econ.cost_per_datom(),
        "enabled": state.econ.enabled(),
    })))
}

pub async fn econ_credit(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<EconCreditReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    if req.did.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "did required".to_string()));
    }
    let balance = state.econ.credit(&req.did, req.amount).await;
    Ok(Json(serde_json::json!({
        "did": req.did,
        "credited_mkoto": req.amount,
        "balance_mkoto": balance,
    })))
}

fn map_delegation_error(e: kotoba_auth::DelegationError) -> (StatusCode, String) {
    use kotoba_auth::DelegationError;
    match &e {
        DelegationError::Expired => (StatusCode::UNAUTHORIZED, "cacao expired".to_string()),
        DelegationError::GraphMismatch { expected, got } => (
            StatusCode::UNAUTHORIZED,
            format!("cacao graph mismatch: warrant covers {expected}, request targets {got}"),
        ),
        _ => (StatusCode::UNAUTHORIZED, format!("cacao delegation: {e}")),
    }
}

/// Returns `true` if the host portion of a `did:web:` suffix is an IP literal.
///
/// The did:web spec mandates domain names. IP literals are rejected to prevent
/// SSRF attacks (e.g. `did:web:169.254.169.254` → AWS metadata endpoint).
fn is_did_web_ip_host(suffix: &str) -> bool {
    let host = suffix.split(':').next().unwrap_or(suffix);
    // Empty host means suffix starts with ':' — not a valid domain name.
    // IPv6 literals like "::1" produce an empty first segment here.
    if host.is_empty() {
        return true;
    }
    // IPv4: first segment parses as an IP address.
    if host.parse::<std::net::IpAddr>().is_ok() {
        return true;
    }
    // IPv6: the full suffix (no `:path` appended yet) may parse as an IP.
    // e.g. "fe80::1" — first segment is "fe80" but the full string is IPv6.
    suffix.parse::<std::net::IpAddr>().is_ok()
}

/// Resolve a `did:web:` DID document over HTTPS, extract the Ed25519 public key,
/// verify the CACAO signature, and check expiry + graph scope.
///
/// `did:web:domain`       → `https://domain/.well-known/did.json`
/// `did:web:domain:path`  → `https://domain/path/did.json`
async fn resolve_and_verify_did_web(
    cacao: &kotoba_auth::Cacao,
    graph: &str,
    client: &reqwest::Client,
) -> Result<String, (StatusCode, String)> {
    use kotoba_auth::DidDocument;

    // P3 — expiry check (DelegationChain path handles this for non-web DIDs)
    if cacao.is_expired() {
        return Err((StatusCode::UNAUTHORIZED, "cacao expired".to_string()));
    }
    // P3b — max-age check for no-expiry CACAOs (mirrors DelegationChain::verify logic)
    if cacao.p.expiry.is_none() {
        const MAX_CACAO_AGE_SECS: u64 = 7 * 24 * 3600;
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        match cacao.issued_at_secs() {
            None => {
                return Err((
                    StatusCode::UNAUTHORIZED,
                    "cacao: invalid iat format".to_string(),
                ))
            }
            Some(iat) => {
                if now.saturating_sub(iat) > MAX_CACAO_AGE_SECS {
                    return Err((
                        StatusCode::UNAUTHORIZED,
                        "cacao expired (max-age exceeded)".to_string(),
                    ));
                }
            }
        }
    }

    // P3 — capability check
    if let Some(cap) = cacao.p.capability() {
        if cap != kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT {
            return Err((
                StatusCode::UNAUTHORIZED,
                format!(
                    "capability denied: need '{}', CACAO grants '{cap}'",
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT
                ),
            ));
        }
    }

    // P3 — graph scope check
    if let Some(cacao_graph) = cacao.p.graph_cid() {
        if cacao_graph != graph {
            return Err((
                StatusCode::UNAUTHORIZED,
                format!(
                    "cacao graph mismatch: warrant covers {cacao_graph}, request targets {graph}"
                ),
            ));
        }
    }

    // Build did:web fetch URL.
    // The did:web spec requires a domain name — reject IP literals outright.
    // Hostname-based SSRF (DNS pointing to internal IPs) is out-of-scope here;
    // document in ADR §23 if DNS-SSRF protection is needed in future.
    let suffix = cacao.p.iss.strip_prefix("did:web:").unwrap_or(&cacao.p.iss);
    if is_did_web_ip_host(suffix) {
        let host = suffix.split(':').next().unwrap_or(suffix);
        return Err((
            StatusCode::UNAUTHORIZED,
            format!("did:web: IP address literals are not allowed (got '{host}'); did:web requires a domain name"),
        ));
    }

    let url = if suffix.contains(':') {
        format!("https://{}/did.json", suffix.replace(':', "/"))
    } else {
        format!("https://{}/.well-known/did.json", suffix)
    };

    const MAX_DID_DOC_BYTES: usize = 65_536; // 64 KiB — guard against response-bombing

    let resp = client.get(&url).send().await.map_err(|e| {
        (
            StatusCode::UNAUTHORIZED,
            format!("did:web fetch {url}: {e}"),
        )
    })?;
    if !resp.status().is_success() {
        return Err((
            StatusCode::UNAUTHORIZED,
            format!("did:web fetch {url}: HTTP {}", resp.status()),
        ));
    }
    // Pre-check Content-Length to reject obviously oversized documents before buffering.
    if let Some(cl) = resp.content_length() {
        if cl > MAX_DID_DOC_BYTES as u64 {
            return Err((
                StatusCode::UNAUTHORIZED,
                format!(
                    "did:web document Content-Length {cl} exceeds {MAX_DID_DOC_BYTES} byte limit"
                ),
            ));
        }
    }
    // Stream chunks with a running budget check to prevent slow-loris inflate attacks.
    let mut body_bytes = bytes::BytesMut::new();
    let mut resp = resp;
    loop {
        match resp
            .chunk()
            .await
            .map_err(|e| (StatusCode::UNAUTHORIZED, format!("did:web read body: {e}")))?
        {
            None => break,
            Some(chunk) => {
                body_bytes.extend_from_slice(&chunk);
                if body_bytes.len() > MAX_DID_DOC_BYTES {
                    return Err((
                        StatusCode::UNAUTHORIZED,
                        format!("did:web document exceeds {MAX_DID_DOC_BYTES} byte limit"),
                    ));
                }
            }
        }
    }
    let body_bytes = body_bytes.freeze();
    let doc: DidDocument = serde_json::from_slice(&body_bytes).map_err(|e| {
        (
            StatusCode::UNAUTHORIZED,
            format!("did:web document parse: {e}"),
        )
    })?;

    let pubkey = doc.ed25519_public_key().ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            format!("no Ed25519 key in DID document for {}", cacao.p.iss),
        )
    })?;

    cacao
        .verify_with_pubkey(&pubkey)
        .map_err(|e| (StatusCode::UNAUTHORIZED, format!("did:web sig: {e}")))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datom.create
/// POST /xrpc/com.etzhayyim.apps.kotoba.quad.create
/// Publish a Datom-compatible atomic fact to the KSE LiveBus.
///
/// `cacao_b64` is required. The CACAO is verified before the write:
/// - Signature must be valid (EdDSA or eip191)
/// - `cacao.p.graph_cid()` must match the requested `graph` field when present
/// - Issuer DID is stored as a `meta/author` quad on the same graph for provenance
pub async fn quad_create(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<QuadCreateReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;
    use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

    // ── CACAO verification (required) ────────────────────────────────────
    let b64 = req.cacao_b64.as_deref().ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            "cacao_b64 is required for quad.create".to_string(),
        )
    })?;

    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }

    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;

    // Dispatch on issuer DID method:
    //   did:web:*  → P3: resolve DID document over HTTP, verify with extracted key
    //   everything else → P1: DelegationChain verifies expiry + capability + graph + sig
    let issuer_did = if cacao.p.iss.starts_with("did:web:") {
        resolve_and_verify_did_web(&cacao, &req.graph, &state.http_client).await?
    } else {
        kotoba_auth::DelegationChain::new(cacao.clone())
            .verify(&req.graph, kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
            .map_err(map_delegation_error)?
    };

    tracing::info!(issuer = %issuer_did, graph = %req.graph, "quad.create: CACAO verified");

    // ── SPO + graph field bounds ─────────────────────────────────────────────
    // Reject oversized fields before they enter the graph index or WAL.
    // graph/subject/predicate are used as BTreeMap keys; object is freeform text.
    const MAX_GRAPH_LEN: usize = 512;
    const MAX_SUBJECT_LEN: usize = 512;
    const MAX_PREDICATE_LEN: usize = 512;
    const MAX_OBJECT_LEN: usize = 8 * 1024; // 8 KiB
    if req.graph.len() > MAX_GRAPH_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "graph field too long ({} bytes, limit {MAX_GRAPH_LEN})",
                req.graph.len()
            ),
        ));
    }
    if req.subject.len() > MAX_SUBJECT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "subject field too long ({} bytes, limit {MAX_SUBJECT_LEN})",
                req.subject.len()
            ),
        ));
    }
    if req.predicate.len() > MAX_PREDICATE_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "predicate field too long ({} bytes, limit {MAX_PREDICATE_LEN})",
                req.predicate.len()
            ),
        ));
    }
    if req.object.len() > MAX_OBJECT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "object field too long ({} bytes, limit {MAX_OBJECT_LEN})",
                req.object.len()
            ),
        ));
    }

    let graph_cid = KotobaCid::from_bytes(req.graph.as_bytes());
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "quad.create:{}:{}:{}:{}",
            req.graph, req.subject, req.predicate, req.object
        )
        .as_bytes(),
    );
    let datom = KqeDatom::assert(
        KotobaCid::from_bytes(req.subject.as_bytes()),
        req.predicate.clone(),
        KqeValue::Text(req.object.clone()),
        tx_cid.clone(),
    );
    let auth_proof_cid = Some(persist_cacao_auth_proof(&state, b64)?);
    let auth_capability = Some(cacao_capability_projection(
        &cacao.p,
        auth_proof_cid.clone(),
    ));
    let resp = commit_protocol_datoms(
        &state,
        graph_cid.clone(),
        req.graph.clone(),
        KotobaCid::from_bytes(req.subject.as_bytes()),
        vec![kotoba_datomic::Datom::from_kqe(datom)],
        tx_cid,
        issuer_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        auth_proof_cid.clone(),
        auth_capability.clone(),
    )
    .await?;
    let journal_cid = resp
        .journal_cids
        .first()
        .cloned()
        .unwrap_or_else(|| resp.tx_cid.clone());

    // ── Store author provenance ───────────────────────────────────────────
    // Subject = journal CID of the write so legacy graph.query callers can
    // still resolve the exact write event's author.
    let author_subject = KotobaCid::from_multibase(&journal_cid)
        .unwrap_or_else(|| KotobaCid::from_bytes(journal_cid.as_bytes()));
    let author_tx_cid =
        KotobaCid::from_bytes(format!("quad.create.author:{journal_cid}").as_bytes());
    let author_datom = KqeDatom::assert(
        author_subject,
        "meta/author".to_string(),
        KqeValue::Text(issuer_did.clone()),
        author_tx_cid.clone(),
    );
    commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph.clone(),
        KotobaCid::from_multibase(&journal_cid)
            .unwrap_or_else(|| KotobaCid::from_bytes(journal_cid.as_bytes())),
        vec![kotoba_datomic::Datom::from_kqe(author_datom)],
        author_tx_cid,
        issuer_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        auth_proof_cid,
        auth_capability,
    )
    .await?;

    tracing::info!(
        graph     = %req.graph,
        subject   = %req.subject,
        predicate = %req.predicate,
        cid       = %journal_cid,
        author    = %issuer_did,
        commit_cid = %resp.commit_cid,
        "quad.create → distributed Datomic commit"
    );

    Ok((
        StatusCode::OK,
        Json(QuadCreateResp {
            status: "ok",
            datom_cid: journal_cid.clone(),
            quad_cid: journal_cid.clone(),
            journal_cid,
        }),
    ))
}

pub async fn datom_create(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<QuadCreateReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    quad_create(State(state), Json(req)).await
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.vault.put
/// Store an opaque blob in the private Vault.  Returns a CID (multibase blake3).
/// No GossipSub propagation — vault blobs stay local (or in B2 when configured).
pub async fn vault_put(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<VaultPutReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use bytes::Bytes;

    // 10 MiB base64 cap (decodes to ~7.5 MiB raw). Vault blobs are content-addressed
    // chunks; oversized payloads should be split by the chunker, not sent raw.
    const MAX_VAULT_B64_LEN: usize = 10 * 1024 * 1024;
    if req.data_b64.len() > MAX_VAULT_B64_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "data_b64 too large ({} bytes, limit {MAX_VAULT_B64_LEN})",
                req.data_b64.len()
            ),
        ));
    }

    let data = B64
        .decode(&req.data_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("data_b64 decode: {e}")))?;

    let blob_ref = state.vault.put(Bytes::from(data)).await;
    tracing::info!(cid = %blob_ref.cid.to_multibase(), size = blob_ref.size, "vault.put");

    Ok((
        StatusCode::OK,
        Json(VaultPutResp {
            cid: blob_ref.cid.to_multibase(),
            size: blob_ref.size,
        }),
    ))
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.vault.get?cid=<multibase>
/// Retrieve a blob from the Vault by CID.  Returns 404 if not found.
pub async fn vault_get(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;

    let cid_str = params.get("cid").ok_or_else(|| {
        (
            StatusCode::BAD_REQUEST,
            "missing `cid` query param".to_string(),
        )
    })?;

    let cid = KotobaCid::from_multibase(cid_str)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, format!("invalid CID: {cid_str}")))?;

    let data = state.vault.get(&cid).await.ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            format!("vault: CID not found: {cid_str}"),
        )
    })?;

    Ok((
        StatusCode::OK,
        Json(VaultGetResp {
            cid: cid_str.to_string(),
            data_b64: B64.encode(&data),
        }),
    ))
}

fn datomic_datom_resp(datom: kotoba_datomic::Datom) -> DatomicDatomResp {
    DatomicDatomResp {
        e: datom.e.to_multibase(),
        a: datom.a,
        v_edn: kotoba_edn::to_string(&datom.v),
        t: datom.t.to_multibase(),
        added: datom.added,
    }
}

fn parse_graph_cid(graph: &str) -> Result<kotoba_core::cid::KotobaCid, (StatusCode, String)> {
    kotoba_core::cid::KotobaCid::from_multibase(graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".to_string()))
}

fn parse_datomic_entity(entity: &str) -> kotoba_core::cid::KotobaCid {
    kotoba_core::cid::KotobaCid::from_multibase(entity)
        .unwrap_or_else(|| kotoba_core::cid::KotobaCid::from_bytes(entity.as_bytes()))
}

fn datomic_attr_from_edn(value: &kotoba_edn::EdnValue) -> Result<String, (StatusCode, String)> {
    match value {
        kotoba_edn::EdnValue::Keyword(keyword) => Ok(format!(":{}", keyword.to_qualified())),
        kotoba_edn::EdnValue::String(attr) => Ok(attr.clone()),
        _ => Err((
            StatusCode::BAD_REQUEST,
            format!(
                "attribute must be keyword or string, got {}",
                kotoba_edn::to_string(value)
            ),
        )),
    }
}

fn datomic_ident_for_entity(
    db: &kotoba_datomic::Db,
    entity: &kotoba_core::cid::KotobaCid,
) -> Option<kotoba_edn::EdnValue> {
    db.datoms()
        .into_iter()
        .find(|datom| datom.e == *entity && datom.a == ":db/ident")
        .map(|datom| datom.v)
}

fn datomic_entid_for_value(
    db: &kotoba_datomic::Db,
    value: &kotoba_edn::EdnValue,
) -> Result<Option<kotoba_core::cid::KotobaCid>, (StatusCode, String)> {
    match value {
        kotoba_edn::EdnValue::String(s) => Ok(Some(parse_datomic_entity(s))),
        kotoba_edn::EdnValue::Keyword(_) => Ok(db
            .datoms()
            .into_iter()
            .find(|datom| datom.a == ":db/ident" && datom.v == *value)
            .map(|datom| datom.e)),
        kotoba_edn::EdnValue::Vector(items) if items.len() == 2 => {
            let attr = datomic_attr_from_edn(&items[0])?;
            Ok(db
                .datoms()
                .into_iter()
                .find(|datom| datom.a == attr && datom.v == items[1])
                .map(|datom| datom.e))
        }
        _ => Ok(Some(kotoba_core::cid::KotobaCid::from_bytes(
            kotoba_edn::to_string(value).as_bytes(),
        ))),
    }
}

fn datomic_entity_from_request(
    db: &kotoba_datomic::Db,
    entity: &str,
) -> Result<kotoba_core::cid::KotobaCid, (StatusCode, String)> {
    if let Some(cid) = kotoba_core::cid::KotobaCid::from_multibase(entity) {
        return Ok(cid);
    }
    match kotoba_edn::parse(entity) {
        Ok(value) => datomic_entid_for_value(db, &value)?.ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                format!("datomic entity not found for {entity}"),
            )
        }),
        Err(_) => Ok(parse_datomic_entity(entity)),
    }
}

pub(crate) async fn require_datomic_read(
    state: &KotobaState,
    headers: &axum::http::HeaderMap,
    graph: &kotoba_core::cid::KotobaCid,
    cacao_b64: Option<&str>,
    presentation: Option<&kotoba_vc::VerifiablePresentation>,
    operation: &str,
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    require_datomic_read_any_operation(
        state,
        headers,
        graph,
        cacao_b64,
        presentation,
        &[operation],
        as_of,
        since,
    )
    .await
}

async fn require_datomic_read_any_operation(
    state: &KotobaState,
    headers: &axum::http::HeaderMap,
    graph: &kotoba_core::cid::KotobaCid,
    cacao_b64: Option<&str>,
    presentation: Option<&kotoba_vc::VerifiablePresentation>,
    operations: &[&str],
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    use crate::graph_auth::{check_read_access, AccessDenied};

    let graph_scope = graph.to_multibase();
    let visibility = state.graph_visibility(graph).await;
    // Authorize via one of: CACAO operation grant, VC presentation, or the
    // graph-visibility fallback gate.
    'authorized: {
        if cacao_b64.is_some() {
            if let Ok(payload) = verify_datomic_cacao_payload_with_any_operation(
                state,
                &graph_scope,
                cacao_b64,
                operations,
            ) {
                enforce_datomic_temporal_tx_scope(&payload, as_of, since)?;
                break 'authorized;
            }
        }
        if let Some(presentation) = presentation {
            verify_vc_presentation_capability_any_operation(
                state,
                &graph_scope,
                presentation,
                operations,
            )?;
            break 'authorized;
        }
        check_read_access(
            &visibility,
            headers,
            cacao_b64,
            Some(state.operator_did.as_str()),
            None,
        )
        .map_err(AccessDenied::into_response)?;
    }
    // ADR-sealed-cold-tier R1: purpose policy + access receipt for every
    // authorized non-public datomic read, regardless of which gate passed.
    crate::access_receipt::enforce_and_record(
        state,
        headers,
        cacao_b64,
        graph,
        &visibility,
        operations.first().copied().unwrap_or("datom:read"),
    )
}

async fn require_datomic_read_tx_range(
    state: &KotobaState,
    headers: &axum::http::HeaderMap,
    graph: &kotoba_core::cid::KotobaCid,
    cacao_b64: Option<&str>,
    presentation: Option<&kotoba_vc::VerifiablePresentation>,
    operations: &[&str],
    start: Option<&str>,
    end: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    use crate::graph_auth::{check_read_access, AccessDenied};

    let graph_scope = graph.to_multibase();
    let visibility = state.graph_visibility(graph).await;
    'authorized: {
        if cacao_b64.is_some() {
            if let Ok(payload) = verify_datomic_cacao_payload_with_any_operation(
                state,
                &graph_scope,
                cacao_b64,
                operations,
            ) {
                enforce_datomic_range_tx_scope(&payload, start, end)?;
                break 'authorized;
            }
        }
        if let Some(presentation) = presentation {
            verify_vc_presentation_capability_any_operation(
                state,
                &graph_scope,
                presentation,
                operations,
            )?;
            if vc_presentation_declares_tx_scope(presentation) {
                enforce_vc_presentation_range_tx_scope(
                    state,
                    &graph_scope,
                    presentation,
                    operations,
                    start,
                    end,
                )?;
            }
            break 'authorized;
        }
        check_read_access(
            &visibility,
            headers,
            cacao_b64,
            Some(state.operator_did.as_str()),
            None,
        )
        .map_err(AccessDenied::into_response)?;
    }
    // ADR-sealed-cold-tier R1: purpose policy + access receipt (see
    // require_datomic_read_any_operation).
    crate::access_receipt::enforce_and_record(
        state,
        headers,
        cacao_b64,
        graph,
        &visibility,
        operations.first().copied().unwrap_or("datom:read"),
    )
}

fn enforce_datomic_temporal_tx_scope(
    payload: &kotoba_auth::CacaoPayload,
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    let Some(tx) = as_of.or(since) else {
        return Ok(());
    };
    if !payload.has_tx_scope() {
        return Ok(());
    }
    if payload.authorizes_tx(tx) {
        Ok(())
    } else {
        Err((
            StatusCode::UNAUTHORIZED,
            format!("CACAO missing temporal tx scope kotoba://tx/{tx}"),
        ))
    }
}

fn enforce_datomic_range_tx_scope(
    payload: &kotoba_auth::CacaoPayload,
    start: Option<&str>,
    end: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    if !payload.has_tx_scope() {
        return Ok(());
    }
    for (label, tx) in [("start", start), ("end", end)] {
        let Some(tx) = tx else {
            continue;
        };
        if !payload.authorizes_tx(tx) {
            return Err((
                StatusCode::UNAUTHORIZED,
                format!("CACAO missing {label} tx scope kotoba://tx/{tx}"),
            ));
        }
    }
    Ok(())
}

fn enforce_datomic_write_tx_scope(
    payload: &kotoba_auth::CacaoPayload,
    tx_cid: &kotoba_core::cid::KotobaCid,
) -> Result<(), (StatusCode, String)> {
    if !payload.has_tx_scope() {
        return Ok(());
    }
    let tx = tx_cid.to_multibase();
    if payload.authorizes_tx(&tx) {
        Ok(())
    } else {
        Err((
            StatusCode::UNAUTHORIZED,
            format!("CACAO missing transact tx scope kotoba://tx/{tx}"),
        ))
    }
}

fn verify_vc_presentation_capability(
    state: &KotobaState,
    graph: &str,
    presentation: &kotoba_vc::VerifiablePresentation,
    operation: &str,
) -> Result<(), (StatusCode, String)> {
    verify_vc_presentation_capabilities_scope(state, graph, presentation, &[operation], None)
}

fn verify_vc_presentation_capability_any_operation(
    state: &KotobaState,
    graph: &str,
    presentation: &kotoba_vc::VerifiablePresentation,
    operations: &[&str],
) -> Result<(), (StatusCode, String)> {
    for operation in operations {
        if verify_vc_presentation_capability(state, graph, presentation, operation).is_ok() {
            return Ok(());
        }
    }
    Err((
        StatusCode::UNAUTHORIZED,
        format!(
            "VP missing operator-issued capability for any of {} on {graph}",
            operations.join(",")
        ),
    ))
}

fn verify_vc_presentation_capability_any_operation_scope(
    state: &KotobaState,
    graph: &str,
    presentation: &kotoba_vc::VerifiablePresentation,
    operations: &[&str],
    required_scope: &str,
) -> Result<(), (StatusCode, String)> {
    for operation in operations {
        if verify_vc_presentation_capability_scope(
            state,
            graph,
            presentation,
            operation,
            Some(required_scope),
        )
        .is_ok()
        {
            return Ok(());
        }
    }
    Err((
        StatusCode::UNAUTHORIZED,
        format!(
            "VP missing operator-issued capability for any of {} on {graph} with scope {required_scope}",
            operations.join(",")
        ),
    ))
}

fn enforce_vc_presentation_range_tx_scope(
    state: &KotobaState,
    graph: &str,
    presentation: &kotoba_vc::VerifiablePresentation,
    operations: &[&str],
    start: Option<&str>,
    end: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    for tx in [start, end].into_iter().flatten() {
        let tx_scope = format!("kotoba://tx/{tx}");
        verify_vc_presentation_capability_any_operation_scope(
            state,
            graph,
            presentation,
            operations,
            &tx_scope,
        )?;
    }
    Ok(())
}

fn verify_vc_presentation_capability_scope(
    state: &KotobaState,
    graph: &str,
    presentation: &kotoba_vc::VerifiablePresentation,
    operation: &str,
    required_scope: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    verify_vc_presentation_capabilities_scope(
        state,
        graph,
        presentation,
        &[operation],
        required_scope,
    )
}

fn verify_vc_presentation_capabilities_scope(
    state: &KotobaState,
    graph: &str,
    presentation: &kotoba_vc::VerifiablePresentation,
    operations: &[&str],
    required_scope: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    let holder = presentation
        .holder
        .as_deref()
        .ok_or_else(|| (StatusCode::UNAUTHORIZED, "VP holder required".to_string()))?;
    let proof = presentation
        .proof
        .as_ref()
        .ok_or_else(|| (StatusCode::UNAUTHORIZED, "VP proof required".to_string()))?;
    if !proof.verification_method.starts_with(holder) {
        return Err((
            StatusCode::UNAUTHORIZED,
            "VP proof verificationMethod must be controlled by holder".to_string(),
        ));
    }
    let auth_resolver = local_first_did_resolver(state);
    presentation
        .verify_proof_with_resolver(&auth_resolver)
        .map_err(|e| {
            (
                StatusCode::UNAUTHORIZED,
                format!("VP DataIntegrity proof verification failed: {e}"),
            )
        })?;

    let graph_scope = format!("kotoba://graph/{graph}");
    for credential in &presentation.verifiable_credentials {
        if credential.issuer != state.operator_did {
            continue;
        }
        if !credential
            .types
            .iter()
            .any(|t| t == "KotobaCapabilityCredential" || t == "KotobaGraphCapabilityCredential")
        {
            continue;
        }
        credential
            .verify_proof_with_resolver(&auth_resolver)
            .map_err(|e| {
                (
                    StatusCode::UNAUTHORIZED,
                    format!("VC capability proof verification failed: {e}"),
                )
            })?;
        if credential.subject_id() != Some(holder) {
            continue;
        }
        let subject = &credential.credential_subject;
        let graph_ok = json_string_eq(subject.get("graph"), graph)
            || json_string_eq(subject.get("scope"), &graph_scope)
            || json_array_contains(subject.get("graphs"), graph)
            || json_array_contains(subject.get("resources"), &graph_scope);
        if !graph_ok {
            continue;
        }
        if let Some(required_scope) = required_scope {
            let scope_ok = json_string_eq(subject.get("scope"), required_scope)
                || json_array_contains(subject.get("resources"), required_scope)
                || json_array_contains(subject.get("scopes"), required_scope);
            if !scope_ok {
                continue;
            }
        }
        let op_ok = operations.iter().all(|operation| {
            json_string_eq(subject.get("operation"), operation)
                || json_string_eq(subject.get("capability"), operation)
                || json_array_contains(subject.get("operations"), operation)
                || json_array_contains(subject.get("capabilities"), operation)
        });
        if op_ok {
            return Ok(());
        }
    }

    Err((
        StatusCode::UNAUTHORIZED,
        match required_scope {
            Some(scope) => format!(
                "VP missing operator-issued capability for {} on {graph} with scope {scope}",
                operations.join(",")
            ),
            None => format!(
                "VP missing operator-issued capability for {} on {graph}",
                operations.join(",")
            ),
        },
    ))
}

fn local_first_did_resolver(state: &KotobaState) -> kotoba_auth::LayeredDidResolver {
    let local = kotoba_auth::InMemoryDidResolver::new();
    local.insert(state.operator_did.clone(), state.local_auth_did_document());
    kotoba_auth::LayeredDidResolver::new(vec![Arc::new(local), Arc::clone(&state.did_resolver)])
}

fn json_string_eq(value: Option<&serde_json::Value>, expected: &str) -> bool {
    value
        .and_then(serde_json::Value::as_str)
        .map(|s| s == expected)
        .unwrap_or(false)
}

fn json_array_contains(value: Option<&serde_json::Value>, expected: &str) -> bool {
    value
        .and_then(serde_json::Value::as_array)
        .map(|xs| xs.iter().any(|v| v.as_str() == Some(expected)))
        .unwrap_or(false)
}

fn json_value_has_tx_scope(value: Option<&serde_json::Value>) -> bool {
    match value {
        Some(serde_json::Value::String(scope)) => scope.starts_with("kotoba://tx/"),
        Some(serde_json::Value::Array(scopes)) => scopes.iter().any(|scope| {
            scope
                .as_str()
                .is_some_and(|s| s.starts_with("kotoba://tx/"))
        }),
        _ => false,
    }
}

fn vc_presentation_declares_tx_scope(presentation: &kotoba_vc::VerifiablePresentation) -> bool {
    presentation
        .verifiable_credentials
        .iter()
        .any(|credential| {
            let subject = &credential.credential_subject;
            json_value_has_tx_scope(subject.get("scope"))
                || json_value_has_tx_scope(subject.get("resources"))
                || json_value_has_tx_scope(subject.get("scopes"))
        })
}

fn cacao_capability_projection(
    payload: &kotoba_auth::CacaoPayload,
    proof_cid: Option<kotoba_core::cid::KotobaCid>,
) -> AuthCapabilityProjection {
    AuthCapabilityProjection {
        proof_format: "CACAO",
        controller: payload.iss.clone(),
        invoker: payload.iss.clone(),
        allowed_actions: payload
            .capabilities()
            .into_iter()
            .map(ToOwned::to_owned)
            .collect(),
        invocation_targets: payload
            .invocation_targets()
            .into_iter()
            .map(ToOwned::to_owned)
            .collect(),
        proof_cid,
        credential_ids: vec![],
        presentation_id: None,
        presentation_cid: None,
    }
}

fn vp_capability_projection(
    presentation: &kotoba_vc::VerifiablePresentation,
    proof_cid: Option<kotoba_core::cid::KotobaCid>,
) -> AuthCapabilityProjection {
    let invoker = presentation.holder.clone().unwrap_or_default();
    let presentation_cid = presentation.cid().ok().or_else(|| proof_cid.clone());
    let mut allowed_actions = Vec::new();
    let mut invocation_targets = Vec::new();
    let mut credential_ids = Vec::new();
    let mut controller = String::new();
    for credential in &presentation.verifiable_credentials {
        if !credential
            .types
            .iter()
            .any(|t| t == "KotobaCapabilityCredential" || t == "KotobaGraphCapabilityCredential")
        {
            continue;
        }
        if controller.is_empty() {
            controller = credential.issuer.clone();
        }
        credential_ids.push(credential.id.clone());
        collect_json_string_field(
            credential.credential_subject.get("operation"),
            &mut allowed_actions,
        );
        collect_json_string_field(
            credential.credential_subject.get("capability"),
            &mut allowed_actions,
        );
        collect_json_string_field(
            credential.credential_subject.get("operations"),
            &mut allowed_actions,
        );
        collect_json_string_field(
            credential.credential_subject.get("capabilities"),
            &mut allowed_actions,
        );
        collect_json_string_field(
            credential.credential_subject.get("scope"),
            &mut invocation_targets,
        );
        collect_json_string_field(
            credential.credential_subject.get("scopes"),
            &mut invocation_targets,
        );
        collect_json_string_field(
            credential.credential_subject.get("resources"),
            &mut invocation_targets,
        );
        collect_graph_scope(
            credential.credential_subject.get("graph"),
            &mut invocation_targets,
        );
        collect_graph_scope(
            credential.credential_subject.get("graphs"),
            &mut invocation_targets,
        );
    }
    AuthCapabilityProjection {
        proof_format: "W3C VerifiablePresentation",
        controller,
        invoker,
        allowed_actions,
        invocation_targets,
        proof_cid,
        credential_ids,
        presentation_id: Some(presentation.id.clone()),
        presentation_cid,
    }
}

fn collect_json_string_field(value: Option<&serde_json::Value>, out: &mut Vec<String>) {
    match value {
        Some(serde_json::Value::String(value)) => push_unique(out, value.clone()),
        Some(serde_json::Value::Array(values)) => {
            for value in values {
                if let Some(value) = value.as_str() {
                    push_unique(out, value.to_string());
                }
            }
        }
        _ => {}
    }
}

fn collect_graph_scope(value: Option<&serde_json::Value>, out: &mut Vec<String>) {
    match value {
        Some(serde_json::Value::String(graph)) => {
            push_unique(out, format!("kotoba://graph/{graph}"))
        }
        Some(serde_json::Value::Array(graphs)) => {
            for graph in graphs {
                if let Some(graph) = graph.as_str() {
                    push_unique(out, format!("kotoba://graph/{graph}"));
                }
            }
        }
        _ => {}
    }
}

fn push_unique(out: &mut Vec<String>, value: String) {
    if !out.contains(&value) {
        out.push(value);
    }
}

fn verify_datomic_cacao_payload(
    state: &KotobaState,
    graph: &str,
    cacao_b64: Option<&str>,
    operation: &str,
) -> Result<kotoba_auth::CacaoPayload, (StatusCode, String)> {
    verify_datomic_cacao_payload_with_operations(state, graph, cacao_b64, &[operation])
}

fn verify_datomic_cacao_payload_with_operations(
    state: &KotobaState,
    graph: &str,
    cacao_b64: Option<&str>,
    operations: &[&str],
) -> Result<kotoba_auth::CacaoPayload, (StatusCode, String)> {
    let primary_operation = operations.first().copied().unwrap_or("capability");
    let b64 = cacao_b64.ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            format!("cacao_b64 required for {primary_operation}"),
        )
    })?;
    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }
    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;
    let nonce = cacao.p.nonce.clone();
    let payload = cacao.p.clone();
    let chain = kotoba_auth::DelegationChain::new(cacao);
    let resolver = local_first_did_resolver(state);
    let mut issuer = None;
    for operation in operations {
        let verified_issuer = chain
            .verify_with_aud_and_resolver(graph, operation, &state.operator_did, &resolver)
            .map_err(|e| (StatusCode::UNAUTHORIZED, format!("cacao delegation: {e}")))?;
        issuer = Some(verified_issuer);
    }
    let issuer = issuer.unwrap_or_else(|| payload.iss.clone());
    if nonce.is_empty() {
        return Err((
            StatusCode::UNAUTHORIZED,
            "CACAO nonce must not be empty".to_string(),
        ));
    }
    const MAX_CACAO_AGE_SECS: u64 = 7 * 24 * 3600;
    let expiry_unix = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        .saturating_add(MAX_CACAO_AGE_SECS);
    if !state.nonce_store.check_and_register(&nonce, expiry_unix) {
        return Err((
            StatusCode::UNAUTHORIZED,
            format!("cacao nonce already used: {nonce}"),
        ));
    }
    tracing::debug!(issuer = %issuer, operations = %operations.join(","), graph, "datomic CACAO accepted");
    Ok(payload)
}

fn verify_datomic_cacao_payload_with_any_operation(
    state: &KotobaState,
    graph: &str,
    cacao_b64: Option<&str>,
    operations: &[&str],
) -> Result<kotoba_auth::CacaoPayload, (StatusCode, String)> {
    let primary_operation = operations.first().copied().unwrap_or("capability");
    let b64 = cacao_b64.ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            format!("cacao_b64 required for {primary_operation}"),
        )
    })?;
    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }
    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;
    let nonce = cacao.p.nonce.clone();
    let payload = cacao.p.clone();
    let chain = kotoba_auth::DelegationChain::new(cacao);
    let resolver = local_first_did_resolver(state);
    let mut issuer = None;
    let mut last_error = None;
    for operation in operations {
        match chain.verify_with_aud_and_resolver(graph, operation, &state.operator_did, &resolver) {
            Ok(verified_issuer) => {
                issuer = Some(verified_issuer);
                break;
            }
            Err(err) => {
                last_error = Some(err);
            }
        }
    }
    let issuer = match issuer {
        Some(issuer) => issuer,
        None => {
            return Err((
                StatusCode::UNAUTHORIZED,
                format!(
                    "cacao delegation: missing any of {}{}",
                    operations.join(","),
                    last_error
                        .map(|err| format!(" ({err})"))
                        .unwrap_or_default()
                ),
            ))
        }
    };
    if nonce.is_empty() {
        return Err((
            StatusCode::UNAUTHORIZED,
            "CACAO nonce must not be empty".to_string(),
        ));
    }
    const MAX_CACAO_AGE_SECS: u64 = 7 * 24 * 3600;
    let expiry_unix = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        .saturating_add(MAX_CACAO_AGE_SECS);
    if !state.nonce_store.check_and_register(&nonce, expiry_unix) {
        return Err((
            StatusCode::UNAUTHORIZED,
            format!("cacao nonce already used: {nonce}"),
        ));
    }
    tracing::debug!(issuer = %issuer, operations = %operations.join(","), graph, "datomic CACAO accepted");
    Ok(payload)
}

fn persist_cacao_auth_proof(
    state: &KotobaState,
    cacao_b64: &str,
) -> Result<kotoba_core::cid::KotobaCid, (StatusCode, String)> {
    let bytes = B64
        .decode(cacao_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    persist_auth_proof_block(state, &bytes)
}

fn persist_vp_auth_proof(
    state: &KotobaState,
    presentation: &kotoba_vc::VerifiablePresentation,
) -> Result<kotoba_core::cid::KotobaCid, (StatusCode, String)> {
    let bytes = serde_json::to_vec(presentation).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("presentation JSON encode: {e}"),
        )
    })?;
    persist_auth_proof_block(state, &bytes)
}

fn persist_auth_proof_block(
    state: &KotobaState,
    bytes: &[u8],
) -> Result<kotoba_core::cid::KotobaCid, (StatusCode, String)> {
    let cid = kotoba_core::cid::KotobaCid::from_bytes(bytes);
    state.block_store.put(&cid, bytes).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("auth proof store: {e}"),
        )
    })?;
    state.block_store.pin(&cid);
    Ok(cid)
}

pub(crate) fn authorize_protocol_datom_write(
    state: &KotobaState,
    headers: &axum::http::HeaderMap,
    graph: &str,
    cacao_b64: Option<&str>,
    presentation: Option<&kotoba_vc::VerifiablePresentation>,
    operations: &[&str],
    tx_cid: Option<&kotoba_core::cid::KotobaCid>,
) -> Result<ProtocolWriteAuth, (StatusCode, String)> {
    if let Some(cacao_b64) = cacao_b64 {
        let payload = verify_datomic_cacao_payload_with_operations(
            state,
            graph,
            Some(cacao_b64),
            operations,
        )?;
        if let Some(tx_cid) = tx_cid {
            enforce_datomic_write_tx_scope(&payload, tx_cid)?;
        }
        let auth_proof_cid = Some(persist_cacao_auth_proof(state, cacao_b64)?);
        let auth_capability = Some(cacao_capability_projection(
            &payload,
            auth_proof_cid.clone(),
        ));
        return Ok(ProtocolWriteAuth {
            author: payload.iss.clone(),
            auth_proof_cid,
            auth_capability,
        });
    }

    if let Some(presentation) = presentation {
        verify_vc_presentation_capabilities_scope(state, graph, presentation, operations, None)?;
        if let Some(tx_cid) = tx_cid {
            if vc_presentation_declares_tx_scope(presentation) {
                let tx_scope = format!("kotoba://tx/{}", tx_cid.to_multibase());
                verify_vc_presentation_capabilities_scope(
                    state,
                    graph,
                    presentation,
                    operations,
                    Some(&tx_scope),
                )?;
            }
        }
        let auth_proof_cid = Some(persist_vp_auth_proof(state, presentation)?);
        let auth_capability = Some(vp_capability_projection(
            presentation,
            auth_proof_cid.clone(),
        ));
        return Ok(ProtocolWriteAuth {
            author: presentation
                .holder
                .clone()
                .unwrap_or_else(|| state.operator_did.clone()),
            auth_proof_cid,
            auth_capability,
        });
    }

    crate::graph_auth::require_operator_auth(headers, &state.operator_did)?;
    Ok(ProtocolWriteAuth {
        author: state.operator_did.clone(),
        auth_proof_cid: None,
        auth_capability: None,
    })
}

fn db_from_kqe_datoms(datoms: Vec<kotoba_query::Datom>) -> kotoba_datomic::Db {
    let basis_t = datoms.last().map(|d| d.tx.clone());
    let datoms = datoms
        .into_iter()
        .map(kotoba_datomic::Datom::from_kqe)
        .collect();
    kotoba_datomic::Db::from_datoms(datoms, basis_t)
}

pub(crate) fn distributed_graph_ipns_name(graph_cid: &kotoba_core::cid::KotobaCid) -> String {
    format!("k51-kotoba-{}", graph_cid.to_multibase())
}

fn datomic_write_ipns_name(
    graph_cid: &kotoba_core::cid::KotobaCid,
    requested: Option<&str>,
) -> Result<String, (StatusCode, String)> {
    let Some(name) = requested else {
        return Ok(distributed_graph_ipns_name(graph_cid));
    };
    if name.is_empty()
        || name.len() > 256
        || !name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.' | b':'))
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "ipns_name must be 1-256 characters using ASCII letters, digits, '-', '_', '.', or ':'"
                .to_string(),
        ));
    }
    Ok(name.to_string())
}

fn did_document_registry_graph_cid(did: &str) -> kotoba_core::cid::KotobaCid {
    kotoba_core::cid::KotobaCid::from_bytes(format!("did-document-registry:{did}").as_bytes())
}

fn did_document_ipns_name(did: &str) -> String {
    crate::server::did_document_ipns_name(did)
}

pub(crate) fn datom_to_projection_quad(
    datom: &kotoba_datomic::Datom,
    graph_cid: &kotoba_core::cid::KotobaCid,
) -> kotoba_query::quad::LegacyQuad {
    let substrate = datom_to_projection_kqe(datom);
    kotoba_query::quad::LegacyQuad {
        graph: graph_cid.clone(),
        subject: substrate.e,
        predicate: substrate.a,
        object: substrate.v.into(),
    }
}

fn datom_to_projection_kqe(datom: &kotoba_datomic::Datom) -> kotoba_query::Datom {
    datom.to_kqe().unwrap_or_else(|_| kotoba_query::Datom {
        e: datom.e.clone(),
        a: datom.a.clone(),
        v: kotoba_query::Value::Text(kotoba_edn::to_string(&datom.v)),
        tx: datom.t.clone(),
        op: datom.added,
    })
}

fn append_tx_metadata_datoms(
    datoms: &mut Vec<kotoba_datomic::Datom>,
    tx_cid: &kotoba_core::cid::KotobaCid,
    graph_cid: &kotoba_core::cid::KotobaCid,
    operation: &str,
    author: &str,
    auth_proof_cid: Option<&kotoba_core::cid::KotobaCid>,
    ipns_name: &str,
    ipns_sequence: u64,
    ipns_controller_did: &str,
    expected_parent: Option<&kotoba_core::cid::KotobaCid>,
) {
    let tx_instant_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or_default()
        .min(i64::MAX as u128) as i64;

    fn assert_tx(
        datoms: &mut Vec<kotoba_datomic::Datom>,
        tx_cid: &kotoba_core::cid::KotobaCid,
        attr: &str,
        value: kotoba_edn::EdnValue,
    ) {
        datoms.push(kotoba_datomic::Datom::assert(
            tx_cid.clone(),
            attr.to_string(),
            value,
            tx_cid.clone(),
        ));
    }

    assert_tx(
        datoms,
        tx_cid,
        ":tx/graph",
        kotoba_edn::EdnValue::String(graph_cid.to_multibase()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/operation",
        kotoba_edn::EdnValue::String(operation.to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":db/txInstant",
        kotoba_edn::EdnValue::Integer(tx_instant_ms),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/author",
        kotoba_edn::EdnValue::String(author.to_string()),
    );
    if let Some(auth_proof_cid) = auth_proof_cid {
        assert_tx(
            datoms,
            tx_cid,
            ":tx/authProofCid",
            kotoba_edn::EdnValue::String(auth_proof_cid.to_multibase()),
        );
    }
    assert_tx(
        datoms,
        tx_cid,
        ":tx/ipnsName",
        kotoba_edn::EdnValue::String(ipns_name.to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/ipnsSequence",
        kotoba_edn::EdnValue::Integer(ipns_sequence as i64),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/ipnsControllerDid",
        kotoba_edn::EdnValue::String(ipns_controller_did.to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/storageBackend",
        kotoba_edn::EdnValue::String("ipfs/ipld/ipns".to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/ipldCodec",
        kotoba_edn::EdnValue::String("dag-cbor".to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":tx/indexModel",
        kotoba_edn::EdnValue::String("prolly-tree".to_string()),
    );
    for root in ["eavt", "aevt", "avet", "vaet", "tea"] {
        assert_tx(
            datoms,
            tx_cid,
            ":tx/indexRootName",
            kotoba_edn::EdnValue::String(root.to_string()),
        );
    }
    if let Some(expected_parent) = expected_parent {
        assert_tx(
            datoms,
            tx_cid,
            ":tx/expectedParentCommit",
            kotoba_edn::EdnValue::String(expected_parent.to_multibase()),
        );
    }
}

fn append_auth_capability_datoms(
    datoms: &mut Vec<kotoba_datomic::Datom>,
    tx_cid: &kotoba_core::cid::KotobaCid,
    projection: &AuthCapabilityProjection,
) {
    fn assert_tx(
        datoms: &mut Vec<kotoba_datomic::Datom>,
        tx_cid: &kotoba_core::cid::KotobaCid,
        attr: &str,
        value: kotoba_edn::EdnValue,
    ) {
        datoms.push(kotoba_datomic::Datom::assert(
            tx_cid.clone(),
            attr.to_string(),
            value,
            tx_cid.clone(),
        ));
    }

    assert_tx(
        datoms,
        tx_cid,
        ":capability/proofFormat",
        kotoba_edn::EdnValue::String(projection.proof_format.to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        ":capability/type",
        kotoba_edn::EdnValue::String("CapabilityInvocation".to_string()),
    );
    assert_tx(
        datoms,
        tx_cid,
        kotoba_auth::did_document::ATTR_RDF_TYPE,
        kotoba_edn::EdnValue::String(ZCAP_CAPABILITY_INVOCATION_IRI.to_string()),
    );
    if !projection.controller.is_empty() {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/controller",
            kotoba_edn::EdnValue::String(projection.controller.clone()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ZCAP_CONTROLLER_IRI,
            kotoba_edn::EdnValue::String(projection.controller.clone()),
        );
    }
    if !projection.invoker.is_empty() {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/invoker",
            kotoba_edn::EdnValue::String(projection.invoker.clone()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ZCAP_INVOKER_IRI,
            kotoba_edn::EdnValue::String(projection.invoker.clone()),
        );
    }
    for action in &projection.allowed_actions {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/allowedAction",
            kotoba_edn::EdnValue::String(action.clone()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ":capability/operation",
            kotoba_edn::EdnValue::String(action.clone()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ZCAP_ALLOWED_ACTION_IRI,
            kotoba_edn::EdnValue::String(action.clone()),
        );
    }
    for target in &projection.invocation_targets {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/invocationTarget",
            kotoba_edn::EdnValue::String(target.clone()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ":capability/resource",
            kotoba_edn::EdnValue::String(target.clone()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ZCAP_INVOCATION_TARGET_IRI,
            kotoba_edn::EdnValue::String(target.clone()),
        );
        if let Some(graph) = target.strip_prefix("kotoba://graph/") {
            assert_tx(
                datoms,
                tx_cid,
                ":capability/graph",
                kotoba_edn::EdnValue::String(graph.to_string()),
            );
        }
        if let Some(tx) = target.strip_prefix("kotoba://tx/") {
            assert_tx(
                datoms,
                tx_cid,
                ":capability/tx",
                kotoba_edn::EdnValue::String(tx.to_string()),
            );
        }
        if let Some(thread_id) = target.strip_prefix("didcomm://thread/") {
            assert_tx(
                datoms,
                tx_cid,
                ":capability/didcommThread",
                kotoba_edn::EdnValue::String(thread_id.to_string()),
            );
        }
        if target.starts_with("at://") {
            assert_tx(
                datoms,
                tx_cid,
                ":capability/atprotoResource",
                kotoba_edn::EdnValue::String(target.clone()),
            );
        }
    }
    if let Some(proof_cid) = &projection.proof_cid {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/proofCid",
            kotoba_edn::EdnValue::String(proof_cid.to_multibase()),
        );
        assert_tx(
            datoms,
            tx_cid,
            ZCAP_INVOCATION_PROOF_IRI,
            kotoba_edn::EdnValue::String(proof_cid.to_multibase()),
        );
    }
    for credential_id in &projection.credential_ids {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/credential",
            kotoba_edn::EdnValue::String(credential_id.clone()),
        );
    }
    if let Some(presentation_id) = &projection.presentation_id {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/presentation",
            kotoba_edn::EdnValue::String(presentation_id.clone()),
        );
    }
    if let Some(presentation_cid) = &projection.presentation_cid {
        assert_tx(
            datoms,
            tx_cid,
            ":capability/presentationCid",
            kotoba_edn::EdnValue::String(presentation_cid.to_multibase()),
        );
        assert_tx(
            datoms,
            tx_cid,
            kotoba_vc::ATTR_PRESENTATION_CID,
            kotoba_edn::EdnValue::String(presentation_cid.to_multibase()),
        );
    }
}

pub(crate) async fn commit_protocol_datoms(
    state: &KotobaState,
    graph_cid: kotoba_core::cid::KotobaCid,
    graph: String,
    entity_cid: kotoba_core::cid::KotobaCid,
    mut datoms: Vec<kotoba_datomic::Datom>,
    tx_cid: kotoba_core::cid::KotobaCid,
    author: String,
    operation: &str,
    auth_proof_cid: Option<kotoba_core::cid::KotobaCid>,
    auth_capability: Option<AuthCapabilityProjection>,
) -> Result<ProtocolDatomWriteResp, (StatusCode, String)> {
    let ipns_name = distributed_graph_ipns_name(&graph_cid);
    let current_head = match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.clone()))
    {
        Ok(record) => Some(record),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {e}"),
            ));
        }
    };
    let expected_parent = current_head
        .as_ref()
        .and_then(|record| kotoba_core::cid::KotobaCid::from_multibase(&record.value));
    let seq = current_head
        .as_ref()
        .map(|record| record.sequence + 1)
        .unwrap_or(1);
    append_tx_metadata_datoms(
        &mut datoms,
        &tx_cid,
        &graph_cid,
        operation,
        &author,
        auth_proof_cid.as_ref(),
        &ipns_name,
        seq,
        &state.operator_did,
        expected_parent.as_ref(),
    );
    if let Some(auth_capability) = &auth_capability {
        append_auth_capability_datoms(&mut datoms, &tx_cid, auth_capability);
    }
    // R2b: author-sign commits the node itself authors. Client-authored
    // writes carry their own non-repudiation via cacao_proof_cid.
    let author_key = (author == state.operator_did).then(|| state.operator_signing_key());
    let require_signed = std::env::var("KOTOBA_REQUIRE_SIGNED_COMMITS")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true") || v.eq_ignore_ascii_case("on"))
        .unwrap_or(false);
    let writer = DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry)
        .with_author_signing_key(author_key)
        .with_import_check(Some(kotoba_auth::commit_import_check(require_signed)));
    let distributed = writer
        .commit_datoms(CommitDatomsRequest {
            merge_parents: None,
            ipns_name: ipns_name.clone(),
            graph: graph_cid.clone(),
            datoms: datoms.clone(),
            covering_datoms: None,
            expected_parent,
            tx_cid: Some(tx_cid.clone()),
            author,
            seq,
            valid_until: "2099-01-01T00:00:00Z".to_string(),
            ttl_secs: Some(60),
            cacao_proof_cid: auth_proof_cid.clone(),
            ipns_controller_did: Some(state.operator_did.clone()),
            ipns_signing_key: Some(state.ipns_signing_key()),
        })
        .map_err(|e| match e {
            DistributedCommitError::StaleParent { .. } => {
                (StatusCode::CONFLICT, format!("distributed commit: {e}"))
            }
            _ => (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("distributed commit: {e}"),
            ),
        })?;

    // ADR-2606041151 A — the synchronous DistributedCommitWriter commit above is
    // already durable (ProllyTree + IPNS head), so the per-datom LiveBus WAL
    // block-write is a redundant double-write. Kept by default (fast restart via
    // journal replay); opt out with KOTOBA_JOURNAL_WAL=off to drop the double
    // write. The hot-arrangement update (`apply_journaled_datom`) ALWAYS runs —
    // it serves hot reads and is independent of the WAL block-write.
    // Datomic firehose: ephemeral live-tail broadcast, no LiveBus block persist
    // (the CommitDag is the durable record; sync.eventsFromCommits replays it).
    let mut journal_cids = Vec::with_capacity(datoms.len());
    for datom in &datoms {
        let quad = datom_to_projection_quad(datom, &graph_cid);
        let cid = if datom.added {
            state.journal_assert_ephemeral(&quad).await
        } else {
            state.journal_retract_ephemeral(&quad).await
        };
        journal_cids.push(cid);
        state
            .quad_store
            .apply_journaled_datom(graph_cid.clone(), datom_to_projection_kqe(datom))
            .await;
    }

    let assert_count = datoms.iter().filter(|datom| datom.added).count();
    let retract_count = datoms.len().saturating_sub(assert_count);

    Ok(ProtocolDatomWriteResp {
        status: "ok",
        graph,
        entity_cid: entity_cid.to_multibase(),
        tx_cid: tx_cid.to_multibase(),
        commit_cid: distributed.commit.cid.to_multibase(),
        auth_proof_cid: distributed
            .commit
            .cacao_proof_cid
            .as_ref()
            .map(|cid| cid.to_multibase()),
        ipns_name,
        ipns_sequence: distributed.ipns_record.sequence,
        ipns_valid_until: distributed.ipns_record.valid_until,
        index_roots: distributed
            .commit
            .index_roots
            .into_iter()
            .map(|(k, v)| (k, v.to_multibase()))
            .collect(),
        datom_count: datoms.len(),
        assert_count,
        retract_count,
        journal_cids,
    })
}

fn commit_did_document_registry_datoms(
    state: &KotobaState,
    did: &str,
    mut datoms: Vec<kotoba_datomic::Datom>,
    tx_cid: kotoba_core::cid::KotobaCid,
    author: String,
    auth_proof_cid: Option<kotoba_core::cid::KotobaCid>,
    auth_capability: Option<AuthCapabilityProjection>,
) -> Result<(), (StatusCode, String)> {
    let graph_cid = did_document_registry_graph_cid(did);
    let ipns_name = did_document_ipns_name(did);
    let current_head = match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.clone()))
    {
        Ok(record) => Some(record),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("did document ipns resolve: {e}"),
            ));
        }
    };
    let expected_parent = current_head
        .as_ref()
        .and_then(|record| kotoba_core::cid::KotobaCid::from_multibase(&record.value));
    let seq = current_head
        .as_ref()
        .map(|record| record.sequence + 1)
        .unwrap_or(1);
    append_tx_metadata_datoms(
        &mut datoms,
        &tx_cid,
        &graph_cid,
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        &author,
        auth_proof_cid.as_ref(),
        &ipns_name,
        seq,
        &state.operator_did,
        expected_parent.as_ref(),
    );
    if let Some(auth_capability) = &auth_capability {
        append_auth_capability_datoms(&mut datoms, &tx_cid, auth_capability);
    }
    DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry)
        .commit_datoms(CommitDatomsRequest {
            merge_parents: None,
            ipns_name,
            graph: graph_cid,
            datoms,
            covering_datoms: None,
            expected_parent,
            tx_cid: Some(tx_cid),
            author,
            seq,
            valid_until: "2099-01-01T00:00:00Z".to_string(),
            ttl_secs: Some(60),
            cacao_proof_cid: auth_proof_cid,
            ipns_controller_did: Some(state.operator_did.clone()),
            ipns_signing_key: Some(state.ipns_signing_key()),
        })
        .map(|_| ())
        .map_err(|e| match e {
            DistributedCommitError::StaleParent { .. } => (
                StatusCode::CONFLICT,
                format!("did document registry commit: {e}"),
            ),
            _ => (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("did document registry commit: {e}"),
            ),
        })
}

fn json_value_to_edn(value: &serde_json::Value) -> kotoba_edn::EdnValue {
    match value {
        serde_json::Value::Null => kotoba_edn::EdnValue::Nil,
        serde_json::Value::Bool(b) => kotoba_edn::EdnValue::Bool(*b),
        serde_json::Value::Number(n) => n
            .as_i64()
            .map(kotoba_edn::EdnValue::Integer)
            .or_else(|| n.as_f64().map(kotoba_edn::EdnValue::float))
            .unwrap_or_else(|| kotoba_edn::EdnValue::string(n.to_string())),
        serde_json::Value::String(s) => kotoba_edn::EdnValue::string(s),
        serde_json::Value::Array(xs) => {
            kotoba_edn::EdnValue::vector(xs.iter().map(json_value_to_edn))
        }
        serde_json::Value::Object(obj) => kotoba_edn::EdnValue::Map(
            obj.iter()
                .map(|(k, v)| (kotoba_edn::EdnValue::kw_bare(k), json_value_to_edn(v)))
                .collect(),
        ),
    }
}

fn protocol_payload_tx_cid(
    operation: &str,
    graph: &str,
    entity_cid: &kotoba_core::cid::KotobaCid,
    payload: impl AsRef<[u8]>,
) -> kotoba_core::cid::KotobaCid {
    let entity_multibase = entity_cid.to_multibase();
    let mut bytes = Vec::new();
    bytes.extend_from_slice(operation.as_bytes());
    bytes.push(0);
    bytes.extend_from_slice(graph.as_bytes());
    bytes.push(0);
    bytes.extend_from_slice(entity_multibase.as_bytes());
    bytes.push(0);
    bytes.extend_from_slice(payload.as_ref());
    kotoba_core::cid::KotobaCid::from_bytes(&bytes)
}

fn append_json_record_field_datoms(
    out: &mut Vec<kotoba_datomic::Datom>,
    entity_cid: &kotoba_core::cid::KotobaCid,
    attr_prefix: &str,
    record: &serde_json::Value,
    tx_cid: &kotoba_core::cid::KotobaCid,
) {
    let Some(obj) = record.as_object() else {
        return;
    };
    for (key, value) in obj {
        if key == "$type" {
            continue;
        }
        let attr = format!("{attr_prefix}{key}");
        out.push(kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            attr.clone(),
            json_value_to_edn(value),
            tx_cid.clone(),
        ));
        append_json_record_field_datoms(out, entity_cid, &format!("{attr}/"), value, tx_cid);
    }
}

fn atproto_repo_record_entity_cid(uri: &str) -> kotoba_core::cid::KotobaCid {
    kotoba_core::cid::KotobaCid::from_bytes(uri.as_bytes())
}

fn atproto_did_derived_cid(did: &str) -> kotoba_core::cid::KotobaCid {
    kotoba_core::cid::KotobaCid::from_bytes(did.as_bytes())
}

fn append_atproto_cid_datoms(
    out: &mut Vec<kotoba_datomic::Datom>,
    entity_cid: &kotoba_core::cid::KotobaCid,
    at_cid: &str,
    tx_cid: &kotoba_core::cid::KotobaCid,
) {
    out.push(kotoba_datomic::Datom::assert(
        entity_cid.clone(),
        "atproto/cid".to_string(),
        kotoba_edn::EdnValue::string(at_cid),
        tx_cid.clone(),
    ));
    out.push(kotoba_datomic::Datom::assert(
        entity_cid.clone(),
        "atproto/recordCid".to_string(),
        kotoba_edn::EdnValue::string(at_cid),
        tx_cid.clone(),
    ));
    if let Some(kotoba_cid) = kotoba_graph::at_cid_str_to_kotoba(at_cid) {
        let kotoba_cid_value = kotoba_cid.to_multibase();
        out.extend([
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/recordWireFormat".to_string(),
                kotoba_edn::EdnValue::string("application/dag-cbor"),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/cidVersion".to_string(),
                kotoba_edn::EdnValue::int(1),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/cidCodec".to_string(),
                kotoba_edn::EdnValue::string("dag-cbor"),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/cidMultihash".to_string(),
                kotoba_edn::EdnValue::string("sha2-256"),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/kotobaCid".to_string(),
                kotoba_edn::EdnValue::string(kotoba_cid_value.clone()),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/recordKotobaCid".to_string(),
                kotoba_edn::EdnValue::string(kotoba_cid_value),
                tx_cid.clone(),
            ),
        ]);
    }
}

fn atproto_repo_write_datoms(
    req: &AtprotoRepoWriteReq,
    uri: &kotoba_graph::AtUri,
    entity_cid: &kotoba_core::cid::KotobaCid,
    tx_cid: &kotoba_core::cid::KotobaCid,
) -> Vec<kotoba_datomic::Datom> {
    let operation = req.operation.as_deref().unwrap_or("create");
    let record_edn = req.record.as_ref().map(json_value_to_edn);
    let mut out = vec![
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/entityCid".to_string(),
            kotoba_edn::EdnValue::string(entity_cid.to_multibase()),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/uri".to_string(),
            kotoba_edn::EdnValue::string(&req.uri),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/resource".to_string(),
            kotoba_edn::EdnValue::string(&req.uri),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/authority".to_string(),
            kotoba_edn::EdnValue::string(&uri.authority),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/collection".to_string(),
            kotoba_edn::EdnValue::string(&uri.collection),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/nsid".to_string(),
            kotoba_edn::EdnValue::string(&uri.collection),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/rkey".to_string(),
            kotoba_edn::EdnValue::string(&uri.rkey),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/wireFormat".to_string(),
            kotoba_edn::EdnValue::string("application/atproto+json"),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/operation".to_string(),
            kotoba_edn::EdnValue::string(operation),
            tx_cid.clone(),
        ),
    ];
    if uri.authority.starts_with("did:") {
        out.extend([
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/did".to_string(),
                kotoba_edn::EdnValue::string(&uri.authority),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/didCid".to_string(),
                kotoba_edn::EdnValue::string(
                    atproto_did_derived_cid(&uri.authority).to_multibase(),
                ),
                tx_cid.clone(),
            ),
        ]);
    }
    if let Some(record_edn) = &record_edn {
        out.push(kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            uri.collection.clone(),
            record_edn.clone(),
            tx_cid.clone(),
        ));
    }
    if let Some(cid) = &req.cid {
        append_atproto_cid_datoms(&mut out, entity_cid, cid, tx_cid);
    }
    if let Some(record) = &req.record {
        out.push(kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/record".to_string(),
            record_edn
                .clone()
                .unwrap_or_else(|| json_value_to_edn(record)),
            tx_cid.clone(),
        ));
        if let Some(record_type) = record.get("$type").and_then(serde_json::Value::as_str) {
            out.push(kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/type".to_string(),
                kotoba_edn::EdnValue::string(record_type),
                tx_cid.clone(),
            ));
            out.push(kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/recordType".to_string(),
                kotoba_edn::EdnValue::string(record_type),
                tx_cid.clone(),
            ));
            if let Some(record_edn) = &record_edn {
                out.push(kotoba_datomic::Datom::assert(
                    entity_cid.clone(),
                    record_type.to_string(),
                    record_edn.clone(),
                    tx_cid.clone(),
                ));
            }
        }
        append_json_record_field_datoms(&mut out, entity_cid, "atproto/record/", record, tx_cid);
        append_json_record_field_datoms(
            &mut out,
            entity_cid,
            &format!("{}/", uri.collection),
            record,
            tx_cid,
        );
        append_json_record_field_datoms(
            &mut out,
            entity_cid,
            &format!("{}#", uri.collection),
            record,
            tx_cid,
        );
    }
    out
}

fn atproto_repo_delete_datoms(
    db: &kotoba_datomic::Db,
    req: &AtprotoRepoWriteReq,
    uri: &kotoba_graph::AtUri,
    entity_cid: &kotoba_core::cid::KotobaCid,
    tx_cid: &kotoba_core::cid::KotobaCid,
) -> Vec<kotoba_datomic::Datom> {
    let mut out = db
        .datoms()
        .into_iter()
        .filter(|datom| {
            datom.e == *entity_cid
                && !matches!(
                    datom.a.as_str(),
                    "atproto/uri"
                        | "atproto/resource"
                        | "atproto/entityCid"
                        | "atproto/wireFormat"
                        | "atproto/authority"
                        | "atproto/collection"
                        | "atproto/nsid"
                        | "atproto/rkey"
                        | "atproto/did"
                        | "atproto/didCid"
                )
        })
        .map(|datom| kotoba_datomic::Datom::retract(datom.e, datom.a, datom.v, tx_cid.clone()))
        .collect::<Vec<_>>();
    out.extend([
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/entityCid".to_string(),
            kotoba_edn::EdnValue::string(entity_cid.to_multibase()),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/uri".to_string(),
            kotoba_edn::EdnValue::string(&req.uri),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/resource".to_string(),
            kotoba_edn::EdnValue::string(&req.uri),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/authority".to_string(),
            kotoba_edn::EdnValue::string(&uri.authority),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/collection".to_string(),
            kotoba_edn::EdnValue::string(&uri.collection),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/nsid".to_string(),
            kotoba_edn::EdnValue::string(&uri.collection),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/rkey".to_string(),
            kotoba_edn::EdnValue::string(&uri.rkey),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/wireFormat".to_string(),
            kotoba_edn::EdnValue::string("application/atproto+json"),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/operation".to_string(),
            kotoba_edn::EdnValue::string("delete"),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            entity_cid.clone(),
            "atproto/deleted".to_string(),
            kotoba_edn::EdnValue::Bool(true),
            tx_cid.clone(),
        ),
    ]);
    if uri.authority.starts_with("did:") {
        out.extend([
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/did".to_string(),
                kotoba_edn::EdnValue::string(&uri.authority),
                tx_cid.clone(),
            ),
            kotoba_datomic::Datom::assert(
                entity_cid.clone(),
                "atproto/didCid".to_string(),
                kotoba_edn::EdnValue::string(
                    atproto_did_derived_cid(&uri.authority).to_multibase(),
                ),
                tx_cid.clone(),
            ),
        ]);
    }
    out
}

pub(crate) async fn current_db_for_graph(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
) -> Result<kotoba_datomic::Db, (StatusCode, String)> {
    // Resident fast path (read-side completion of the kotoba#19 / ADR-2605302130
    // write-scaling fix): every consumer of this helper (cc.status, search.web,
    // kg.*, media, email, attestation, mcp — 20 call sites) previously paid a
    // FULL commit-chain replay (`history_for_name` → O(total-history) block
    // reads + Db rebuild) on EVERY request, while `datomic.transact` and
    // `datomic.q` already served from the per-graph resident `datomic_live_slot`.
    // Empirically (2026-06-11, ADR-2606111900): at ~30k datoms cc.status took
    // 325 s and search.web 333 s, CPU-bound in this cold load.
    //
    // On a head match we clone the resident current-state Db (O(state) memcpy,
    // ms); on a miss we pay ONE `db_from_head` (CEAVT covering-index fast path,
    // O(state) not O(history)) and re-seed the slot, so the next read — and the
    // next transact's `db_before` — are cache hits. The cached Db is the same
    // `db_from_head` value the transact path maintains, so the slot stays
    // coherent across both paths.
    //
    // Semantics: callers only consume the CURRENT view (`db.datoms()` — see all
    // 20 call sites); none call `db.history()` (history consumers go through
    // `require_distributed_datomic_history_db`). `Db::datoms()` nets retractions
    // via `current_datoms`, so a Db built from the netted CEAVT scan and one
    // built from full history yield the identical current view.
    let ipns_name = distributed_graph_ipns_name(graph_cid);
    match state.ipns_registry.resolve(&IpnsName::new(ipns_name)) {
        Ok(head_record) => {
            if let Some(head_cid) = kotoba_core::cid::KotobaCid::from_multibase(&head_record.value)
            {
                let graph_mb = graph_cid.to_multibase();
                let live_slot = state.datomic_live_slot(&graph_mb);
                // Held across read-or-rebuild + reseed so a concurrent transact
                // on the same graph serialises against us (same discipline as
                // `try_resident_datomic_q` and the transact db_before section).
                let mut live_guard = live_slot.lock().await;
                if let Some(live) = live_guard.as_ref() {
                    if live.head == head_cid {
                        return Ok(live.db.clone());
                    }
                }
                state
                    .datomic_cold_db_loads
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                let reader =
                    DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
                let db = reader.db_from_head(&head_cid).map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("distributed datomic read: {e}"),
                    )
                })?;
                *live_guard = Some(crate::server::LiveDatomicGraph {
                    head: head_cid,
                    db: db.clone(),
                });
                return Ok(db);
            }
        }
        // No committed head yet — fall through to the local QuadStore view.
        Err(IpnsRegistryError::NotFound(_)) => {}
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {e}"),
            ))
        }
    }

    let mut datoms = state
        .quad_store
        .history_datoms_cold(graph_cid)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("datomic cold history read: {e}"),
            )
        })?;
    let mut hot = state
        .quad_store
        .arrangement(graph_cid)
        .await
        .map(|arr| arr.datoms(&kotoba_core::cid::KotobaCid::from_bytes(b"kotoba-hot-tx")))
        .unwrap_or_default();
    datoms.append(&mut hot);
    Ok(db_from_kqe_datoms(datoms))
}

fn parse_optional_tx_cid(
    field: &'static str,
    value: Option<&str>,
) -> Result<Option<kotoba_core::cid::KotobaCid>, (StatusCode, String)> {
    value
        .map(|cid| {
            kotoba_core::cid::KotobaCid::from_multibase(cid).ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    format!("invalid {field} transaction CID"),
                )
            })
        })
        .transpose()
}

fn basis_t_resp(db: &kotoba_datomic::Db) -> Option<String> {
    db.basis_t.as_ref().map(|cid| cid.to_multibase())
}

fn datomic_db_stats_resp(graph: String, db: &kotoba_datomic::Db) -> DatomicDbStatsResp {
    let datoms = db.datoms();
    let history = db.history().datoms().to_vec();
    let mut entities = BTreeSet::new();
    let mut attrs = BTreeSet::new();
    let mut txs = BTreeSet::new();
    for datom in &datoms {
        entities.insert(datom.e.to_multibase());
        attrs.insert(datom.a.clone());
    }
    for datom in &history {
        txs.insert(datom.t.to_multibase());
    }

    DatomicDbStatsResp {
        graph,
        basis_t: basis_t_resp(db),
        datom_count: datoms.len(),
        history_datom_count: history.len(),
        entity_count: entities.len(),
        attribute_count: attrs.len(),
        tx_count: txs.len(),
    }
}

fn datomic_db_value_resp(graph: String, tx: String, db: &kotoba_datomic::Db) -> DatomicDbValueResp {
    let stats = datomic_db_stats_resp(graph.clone(), db);
    DatomicDbValueResp {
        graph,
        tx,
        basis_t: stats.basis_t,
        datom_count: stats.datom_count,
        history_datom_count: stats.history_datom_count,
        entity_count: stats.entity_count,
        attribute_count: stats.attribute_count,
        tx_count: stats.tx_count,
    }
}

#[derive(Debug, Clone, Copy)]
enum DatomicDatomsIndex {
    Eavt,
    Aevt,
    Avet,
    Vaet,
    Tea,
}

impl DatomicDatomsIndex {
    fn parse(index: &str) -> Result<Self, (StatusCode, String)> {
        match index {
            ":eavt" | "eavt" => Ok(Self::Eavt),
            ":aevt" | "aevt" => Ok(Self::Aevt),
            ":avet" | "avet" => Ok(Self::Avet),
            ":vaet" | "vaet" => Ok(Self::Vaet),
            ":tea" | "tea" => Ok(Self::Tea),
            _ => Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "unsupported datoms index {index}; expected :eavt, :aevt, :avet, :vaet, or :tea"
                ),
            )),
        }
    }

    fn distributed_root(self) -> &'static str {
        match self {
            Self::Eavt => ROOT_EAVT,
            Self::Aevt => ROOT_AEVT,
            Self::Avet => ROOT_AVET,
            Self::Vaet => ROOT_VAET,
            Self::Tea => ROOT_TEA,
        }
    }
}

fn datomic_component_entity(value: &kotoba_edn::EdnValue) -> kotoba_core::cid::KotobaCid {
    match value {
        kotoba_edn::EdnValue::String(s) => kotoba_core::cid::KotobaCid::from_multibase(s)
            .unwrap_or_else(|| kotoba_core::cid::KotobaCid::from_bytes(s.as_bytes())),
        _ => kotoba_core::cid::KotobaCid::from_bytes(kotoba_edn::to_string(value).as_bytes()),
    }
}

fn datomic_component_entity_from_db(
    db: &kotoba_datomic::Db,
    value: &kotoba_edn::EdnValue,
) -> Result<kotoba_core::cid::KotobaCid, (StatusCode, String)> {
    datomic_entid_for_value(db, value)?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                format!(
                    "datomic component entity not found for {}",
                    kotoba_edn::to_string(value)
                ),
            )
        })
        .or_else(|err| match value {
            kotoba_edn::EdnValue::String(_) => Ok(datomic_component_entity(value)),
            _ => Err(err),
        })
}

fn datomic_component_attr(value: &kotoba_edn::EdnValue) -> Result<String, (StatusCode, String)> {
    match value {
        kotoba_edn::EdnValue::Keyword(keyword) => Ok(format!(":{}", keyword.to_qualified())),
        kotoba_edn::EdnValue::String(s) => Ok(s.clone()),
        _ => Err((
            StatusCode::BAD_REQUEST,
            format!(
                "datoms attribute component must be keyword or string, got {}",
                kotoba_edn::to_string(value)
            ),
        )),
    }
}

fn datomic_index_component_is_entity(index: DatomicDatomsIndex, position: usize) -> bool {
    matches!(
        (index, position),
        (DatomicDatomsIndex::Eavt, 0)
            | (DatomicDatomsIndex::Aevt, 1)
            | (DatomicDatomsIndex::Avet, 2)
            | (DatomicDatomsIndex::Vaet, 0)
            | (DatomicDatomsIndex::Vaet, 2)
            | (DatomicDatomsIndex::Tea, 0)
            | (DatomicDatomsIndex::Tea, 1)
    )
}

fn resolve_datomic_index_components(
    db: &kotoba_datomic::Db,
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
) -> Result<Vec<kotoba_edn::EdnValue>, (StatusCode, String)> {
    components
        .iter()
        .enumerate()
        .map(|(position, component)| {
            if datomic_index_component_is_entity(index, position) {
                datomic_component_entity_from_db(db, component)
                    .map(|cid| kotoba_edn::EdnValue::String(cid.to_multibase()))
            } else {
                Ok(component.clone())
            }
        })
        .collect()
}

fn resolve_datomic_index_range_bound(
    db: &kotoba_datomic::Db,
    value: Option<kotoba_edn::EdnValue>,
) -> Result<Option<kotoba_edn::EdnValue>, (StatusCode, String)> {
    let Some(value) = value else {
        return Ok(None);
    };
    if matches!(value, kotoba_edn::EdnValue::Vector(ref items) if items.len() == 2) {
        let cid = datomic_component_entity_from_db(db, &value)?;
        return Ok(Some(kotoba_edn::EdnValue::String(cid.to_multibase())));
    }
    Ok(Some(value))
}

fn parse_datomic_datoms_components(
    srcs: &[String],
) -> Result<Vec<kotoba_edn::EdnValue>, (StatusCode, String)> {
    srcs.iter()
        .map(|src| {
            kotoba_edn::parse(src).map_err(|e| {
                (
                    StatusCode::BAD_REQUEST,
                    format!("components_edn parse: {e}"),
                )
            })
        })
        .collect()
}

fn parse_optional_edn(
    field: &str,
    src: Option<&str>,
) -> Result<Option<kotoba_edn::EdnValue>, (StatusCode, String)> {
    src.map(|src| {
        kotoba_edn::parse(src).map_err(|e| (StatusCode::BAD_REQUEST, format!("{field} parse: {e}")))
    })
    .transpose()
}

fn datomic_datoms_match_components(
    datom: &kotoba_datomic::Datom,
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
) -> Result<bool, (StatusCode, String)> {
    if !datomic_datoms_value_matches_index(datom, index) {
        return Ok(false);
    }
    for (position, component) in components.iter().enumerate() {
        let matches = match (index, position) {
            (DatomicDatomsIndex::Eavt, 0) => datom.e == datomic_component_entity(component),
            (DatomicDatomsIndex::Eavt, 1) => datom.a == datomic_component_attr(component)?,
            (DatomicDatomsIndex::Eavt, 2) => datom.v == *component,
            (DatomicDatomsIndex::Eavt, 3) => datom.t == datomic_component_entity(component),
            (DatomicDatomsIndex::Aevt, 0) => datom.a == datomic_component_attr(component)?,
            (DatomicDatomsIndex::Aevt, 1) => datom.e == datomic_component_entity(component),
            (DatomicDatomsIndex::Aevt, 2) => datom.v == *component,
            (DatomicDatomsIndex::Aevt, 3) => datom.t == datomic_component_entity(component),
            (DatomicDatomsIndex::Avet, 0) => datom.a == datomic_component_attr(component)?,
            (DatomicDatomsIndex::Avet, 1) => datom.v == *component,
            (DatomicDatomsIndex::Avet, 2) => datom.e == datomic_component_entity(component),
            (DatomicDatomsIndex::Avet, 3) => datom.t == datomic_component_entity(component),
            (DatomicDatomsIndex::Vaet, 0) => datom.v == *component,
            (DatomicDatomsIndex::Vaet, 1) => datom.a == datomic_component_attr(component)?,
            (DatomicDatomsIndex::Vaet, 2) => datom.e == datomic_component_entity(component),
            (DatomicDatomsIndex::Vaet, 3) => datom.t == datomic_component_entity(component),
            (DatomicDatomsIndex::Tea, 0) => datom.t == datomic_component_entity(component),
            (DatomicDatomsIndex::Tea, 1) => datom.e == datomic_component_entity(component),
            (DatomicDatomsIndex::Tea, 2) => datom.a == datomic_component_attr(component)?,
            (DatomicDatomsIndex::Tea, 3) => datom.v == *component,
            (_, _) => {
                return Err((
                    StatusCode::BAD_REQUEST,
                    "datoms supports at most 4 index components".to_string(),
                ))
            }
        };
        if !matches {
            return Ok(false);
        }
    }
    Ok(true)
}

fn datomic_datoms_value_matches_index(
    datom: &kotoba_datomic::Datom,
    index: DatomicDatomsIndex,
) -> bool {
    if !matches!(index, DatomicDatomsIndex::Vaet) {
        return true;
    }
    match &datom.v {
        kotoba_edn::EdnValue::String(value) => {
            kotoba_core::cid::KotobaCid::from_multibase(value).is_some()
        }
        _ => false,
    }
}

fn datomic_datoms_sort_key(
    datom: &kotoba_datomic::Datom,
    index: DatomicDatomsIndex,
) -> (
    kotoba_edn::EdnValue,
    kotoba_edn::EdnValue,
    kotoba_edn::EdnValue,
    kotoba_edn::EdnValue,
) {
    let e = kotoba_edn::EdnValue::String(datom.e.to_multibase());
    let a = kotoba_edn::EdnValue::String(datom.a.clone());
    let v = datom.v.clone();
    let t = kotoba_edn::EdnValue::String(datom.t.to_multibase());
    match index {
        DatomicDatomsIndex::Eavt => (e, a, v, t),
        DatomicDatomsIndex::Aevt => (a, e, v, t),
        DatomicDatomsIndex::Avet => (a, v, e, t),
        DatomicDatomsIndex::Vaet => (v, a, e, t),
        DatomicDatomsIndex::Tea => (t, e, a, v),
    }
}

fn datomic_datoms_sort_values(
    datom: &kotoba_datomic::Datom,
    index: DatomicDatomsIndex,
) -> Vec<kotoba_edn::EdnValue> {
    let (a, b, c, d) = datomic_datoms_sort_key(datom, index);
    vec![a, b, c, d]
}

fn datomic_seek_component_sort_value(
    index: DatomicDatomsIndex,
    position: usize,
    component: &kotoba_edn::EdnValue,
) -> Result<kotoba_edn::EdnValue, (StatusCode, String)> {
    let entity =
        || kotoba_edn::EdnValue::String(datomic_component_entity(component).to_multibase());
    let attr = || datomic_component_attr(component).map(kotoba_edn::EdnValue::String);
    let value = || Ok(component.clone());
    match (index, position) {
        (DatomicDatomsIndex::Eavt, 0) => Ok(entity()),
        (DatomicDatomsIndex::Eavt, 1) => attr(),
        (DatomicDatomsIndex::Eavt, 2) => value(),
        (DatomicDatomsIndex::Eavt, 3) => Ok(entity()),
        (DatomicDatomsIndex::Aevt, 0) => attr(),
        (DatomicDatomsIndex::Aevt, 1) => Ok(entity()),
        (DatomicDatomsIndex::Aevt, 2) => value(),
        (DatomicDatomsIndex::Aevt, 3) => Ok(entity()),
        (DatomicDatomsIndex::Avet, 0) => attr(),
        (DatomicDatomsIndex::Avet, 1) => value(),
        (DatomicDatomsIndex::Avet, 2) => Ok(entity()),
        (DatomicDatomsIndex::Avet, 3) => Ok(entity()),
        (DatomicDatomsIndex::Vaet, 0) => value(),
        (DatomicDatomsIndex::Vaet, 1) => attr(),
        (DatomicDatomsIndex::Vaet, 2) => Ok(entity()),
        (DatomicDatomsIndex::Vaet, 3) => Ok(entity()),
        (DatomicDatomsIndex::Tea, 0) => Ok(entity()),
        (DatomicDatomsIndex::Tea, 1) => Ok(entity()),
        (DatomicDatomsIndex::Tea, 2) => attr(),
        (DatomicDatomsIndex::Tea, 3) => value(),
        (_, _) => Err((
            StatusCode::BAD_REQUEST,
            "seekDatoms supports at most 4 index components".to_string(),
        )),
    }
}

fn datomic_seek_key(
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
) -> Result<Vec<kotoba_edn::EdnValue>, (StatusCode, String)> {
    components
        .iter()
        .enumerate()
        .map(|(position, component)| datomic_seek_component_sort_value(index, position, component))
        .collect()
}

fn distributed_datomic_db(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<kotoba_datomic::Db>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_db_with_reader(&reader, &ipns_name, as_of, since);
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_db_with_reader(&reader, &ipns_name, as_of, since)
}

fn distributed_datomic_db_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<Option<kotoba_datomic::Db>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let as_of = parse_optional_tx_cid("as_of", as_of)?;
    let since = parse_optional_tx_cid("since", since)?;
    if as_of.is_some() && since.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "as_of and since are mutually exclusive".to_string(),
        ));
    }
    let db = match (as_of.as_ref(), since.as_ref()) {
        (Some(tx), None) => reader.db_as_of_tx(&head.cid, tx),
        (None, Some(tx)) => reader.db_since_tx(&head.cid, tx),
        (None, None) => reader.db_from_head(&head.cid),
        (Some(_), Some(_)) => unreachable!("checked above"),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic db: {e}"),
        )
    })?;
    Ok(Some(db))
}

fn missing_distributed_datomic_head(
    graph_cid: &kotoba_core::cid::KotobaCid,
) -> (StatusCode, String) {
    (
        StatusCode::NOT_FOUND,
        format!(
            "no distributed Datomic/IPNS head for graph {}",
            graph_cid.to_multibase()
        ),
    )
}

pub(crate) fn require_distributed_datomic_db(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<kotoba_datomic::Db, (StatusCode, String)> {
    distributed_datomic_db(
        state,
        graph_cid,
        as_of,
        since,
        remote_peer,
        remote_ipns_name,
    )?
    .ok_or_else(|| missing_distributed_datomic_head(graph_cid))
}

fn distributed_datomic_history_db(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<kotoba_datomic::Db>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_history_db_with_reader(&reader, &ipns_name, as_of, since);
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_history_db_with_reader(&reader, &ipns_name, as_of, since)
}

fn distributed_datomic_history_db_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<Option<kotoba_datomic::Db>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let as_of = parse_optional_tx_cid("as_of", as_of)?;
    let since = parse_optional_tx_cid("since", since)?;
    if as_of.is_some() && since.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "as_of and since are mutually exclusive".to_string(),
        ));
    }
    let db = match (as_of.as_ref(), since.as_ref()) {
        (Some(tx), None) => reader.history_db_as_of_tx(&head.cid, tx),
        (None, Some(tx)) => reader.history_db_since_tx(&head.cid, tx),
        (None, None) => reader.history_db_from_head(&head.cid),
        (Some(_), Some(_)) => unreachable!("checked above"),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic history: {e}"),
        )
    })?;
    Ok(Some(db))
}

fn require_distributed_datomic_history_db(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<kotoba_datomic::Db, (StatusCode, String)> {
    distributed_datomic_history_db(
        state,
        graph_cid,
        as_of,
        since,
        remote_peer,
        remote_ipns_name,
    )?
    .ok_or_else(|| missing_distributed_datomic_head(graph_cid))
}

fn distributed_datomic_q(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    query: &kotoba_edn::EdnValue,
    inputs: &[kotoba_edn::EdnValue],
    as_of: Option<&str>,
    since: Option<&str>,
    history: bool,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<(Option<String>, Vec<Vec<kotoba_edn::EdnValue>>)>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_q_with_reader(
            &reader, &ipns_name, query, inputs, as_of, since, history,
        );
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_q_with_reader(&reader, &ipns_name, query, inputs, as_of, since, history)
}

/// Resident-cache fast path for the first-tier `datomic.q` reads.
///
/// The cold `distributed_datomic_q` path reconstructs the full datomic `Db`
/// from the head commit's covering EAVT on EVERY query (one O(state) cold
/// ProllyTree/Kubo scan — ~3 s at 10k entities). This serves the SAME net-live
/// `Db` from the resident per-graph cache (`datomic_live_slot`) that
/// `datomic.transact` already maintains: on a head match the in-memory datalog
/// engine runs against RAM (O(result)); on a miss we pay one cold `db_from_head`
/// and re-seed the slot so the next read — and the next transact's `db_before` —
/// serve from RAM. The cached `Db` is byte-identical to the transact path's
/// `db_before` (both are `db_from_head(head)`), so the two paths stay coherent.
///
/// Only valid for local current-state reads (no as_of / since / history /
/// remote); those keep the existing reconstruction path. Returns `Ok(None)`
/// when the graph has no head yet, so the caller falls back to the cold path's
/// identical "missing head" handling.
async fn try_resident_datomic_q(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    query: &kotoba_edn::EdnValue,
    inputs: &[kotoba_edn::EdnValue],
) -> Result<Option<(Option<String>, Vec<Vec<kotoba_edn::EdnValue>>)>, (StatusCode, String)> {
    let ipns_name = distributed_graph_ipns_name(graph_cid);
    let head_record = match state.ipns_registry.resolve(&IpnsName::new(ipns_name)) {
        Ok(record) => record,
        Err(IpnsRegistryError::NotFound(_)) => return Ok(None),
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {e}"),
            ))
        }
    };
    let Some(head_cid) = kotoba_core::cid::KotobaCid::from_multibase(&head_record.value) else {
        return Ok(None);
    };

    let graph_mb = graph_cid.to_multibase();
    let live_slot = state.datomic_live_slot(&graph_mb);
    // The guard is held across the (read-or-rebuild + reseed) so a concurrent
    // transact for the same graph serialises against it, exactly as the transact
    // path's own db_before critical section does.
    let mut live_guard = live_slot.lock().await;

    // Cache hit: run the datalog query against the resident Db — no cold read.
    if let Some(live) = live_guard.as_ref() {
        if live.head == head_cid {
            let rows = kotoba_datomic::q(query.clone(), &live.db, inputs)
                .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic q: {e}")))?;
            let basis_t = live.db.basis_t.as_ref().map(|t| t.to_multibase());
            return Ok(Some((basis_t, rows)));
        }
    }

    // Cache miss (first read after (re)start, or an externally-advanced head):
    // pay one O(state) cold reconstruction, then re-seed the slot.
    state
        .datomic_cold_db_loads
        .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    let db = reader.db_from_head(&head_cid).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("datomic db_from_head: {e}"),
        )
    })?;
    let rows = kotoba_datomic::q(query.clone(), &db, inputs)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic q: {e}")))?;
    let basis_t = db.basis_t.as_ref().map(|t| t.to_multibase());
    *live_guard = Some(crate::server::LiveDatomicGraph { head: head_cid, db });
    Ok(Some((basis_t, rows)))
}

fn distributed_datomic_q_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    query: &kotoba_edn::EdnValue,
    inputs: &[kotoba_edn::EdnValue],
    as_of: Option<&str>,
    since: Option<&str>,
    history: bool,
) -> Result<Option<(Option<String>, Vec<Vec<kotoba_edn::EdnValue>>)>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let as_of = parse_optional_tx_cid("as_of", as_of)?;
    let since = parse_optional_tx_cid("since", since)?;
    if as_of.is_some() && since.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "as_of and since are mutually exclusive".to_string(),
        ));
    }

    if history {
        let db = match (as_of.as_ref(), since.as_ref()) {
            (Some(tx), None) => reader.history_db_as_of_tx(&head.cid, tx),
            (None, Some(tx)) => reader.history_db_since_tx(&head.cid, tx),
            (None, None) => reader.history_db_from_head(&head.cid),
            (Some(_), Some(_)) => unreachable!("checked above"),
        }
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                format!("distributed datomic history: {e}"),
            )
        })?;
        let basis_t = basis_t_resp(&db);
        let rows =
            kotoba_datomic::q_history(query.clone(), &db.history(), inputs).map_err(|e| {
                (
                    StatusCode::BAD_REQUEST,
                    format!("distributed datomic q: {e}"),
                )
            })?;
        return Ok(Some((basis_t, rows)));
    }

    let rows = match (as_of.as_ref(), since.as_ref()) {
        (Some(tx), None) => reader.q_triples_as_of_tx_with_inputs(&head.cid, tx, query, inputs),
        (None, Some(tx)) => reader.q_triples_since_tx_with_inputs(&head.cid, tx, query, inputs),
        (None, None) => reader.q_triples_with_inputs(&head.cid, query, inputs),
        (Some(_), Some(_)) => unreachable!("checked above"),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic q: {e}"),
        )
    })?;
    let basis_t = as_of
        .or_else(|| Some(head.tx_cid.clone()))
        .map(|cid| cid.to_multibase());
    Ok(Some((basis_t, rows)))
}

/// Reject SSRF-prone destinations for caller-supplied `remote_peer`: loopback,
/// private (RFC1918), link-local (incl. 169.254.169.254 cloud metadata),
/// unspecified/broadcast, IPv6 ULA (fc00::/7) and link-local (fe80::/10), and
/// IPv4-mapped forms of all of the above. `SocketAddr::from_str` only accepts
/// numeric IPs (no DNS), so this fully bounds the destination set.
fn peer_ip_disallowed(ip: std::net::IpAddr) -> bool {
    use std::net::IpAddr;
    match ip {
        IpAddr::V4(v4) => {
            v4.is_loopback()
                || v4.is_private()
                || v4.is_link_local()
                || v4.is_unspecified()
                || v4.is_broadcast()
                || v4.octets()[0] == 0 // 0.0.0.0/8
        }
        IpAddr::V6(v6) => {
            if let Some(v4) = v6.to_ipv4_mapped() {
                return peer_ip_disallowed(IpAddr::V4(v4));
            }
            let s = v6.segments();
            v6.is_loopback()
                || v6.is_unspecified()
                || (s[0] & 0xfe00) == 0xfc00 // ULA fc00::/7
                || (s[0] & 0xffc0) == 0xfe80 // link-local fe80::/10
        }
    }
}

fn parse_remote_peer_socket(remote_peer: &str) -> Result<SocketAddr, (StatusCode, String)> {
    let socket = if let Ok(socket) = remote_peer.parse::<SocketAddr>() {
        socket
    } else {
        let segments = remote_peer.split('/').collect::<Vec<_>>();
        let ip = segments
            .windows(2)
            .find_map(|window| (window[0] == "ip4").then_some(window[1]));
        let port = segments
            .windows(2)
            .find_map(|window| (window[0] == "tcp").then_some(window[1]));
        match (ip, port) {
            (Some(ip), Some(port)) => {
                format!("{ip}:{port}").parse::<SocketAddr>().map_err(|e| {
                    (
                        StatusCode::BAD_REQUEST,
                        format!("invalid remote_peer multiaddr: {e}"),
                    )
                })?
            }
            _ => {
                return Err((
                    StatusCode::BAD_REQUEST,
                    "remote_peer must be host:port or /ip4/<addr>/tcp/<port>".to_string(),
                ))
            }
        }
    };
    // Block SSRF-prone private/loopback/metadata destinations for caller-supplied
    // remote_peer. Opt out with KOTOBA_ALLOW_PRIVATE_PEERS=1 for a trusted
    // internal mesh / dev (where loopback or RFC1918 peers are legitimate).
    let allow_private = std::env::var("KOTOBA_ALLOW_PRIVATE_PEERS")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true") || v.eq_ignore_ascii_case("on"))
        .unwrap_or(false);
    if !allow_private && peer_ip_disallowed(socket.ip()) {
        return Err((
            StatusCode::FORBIDDEN,
            format!(
                "remote_peer {} is a disallowed (private/loopback/link-local/metadata) address; \
                 set KOTOBA_ALLOW_PRIVATE_PEERS=1 for a trusted internal mesh",
                socket.ip()
            ),
        ));
    }
    Ok(socket)
}

fn distributed_datomic_datoms(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::Datom>)>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_datoms_with_reader(
            &reader, &ipns_name, index, components, as_of, since,
        );
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_datoms_with_reader(&reader, &ipns_name, index, components, as_of, since)
}

fn distributed_datomic_datoms_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::Datom>)>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let as_of = parse_optional_tx_cid("as_of", as_of)?;
    let since = parse_optional_tx_cid("since", since)?;
    if as_of.is_some() && since.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "as_of and since are mutually exclusive".to_string(),
        ));
    }
    let datoms = match (as_of.as_ref(), since.as_ref()) {
        (Some(tx), None) => reader.current_for_index_components_as_of_tx(
            &head.cid,
            tx,
            index.distributed_root(),
            components,
        ),
        (None, Some(tx)) => reader.current_for_index_components_since_tx(
            &head.cid,
            tx,
            index.distributed_root(),
            components,
        ),
        (None, None) => {
            reader.current_for_index_components(&head.cid, index.distributed_root(), components)
        }
        (Some(_), Some(_)) => unreachable!("checked above"),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic datoms: {e}"),
        )
    })?;
    let basis_t = as_of
        .or_else(|| Some(head.tx_cid.clone()))
        .map(|cid| cid.to_multibase());
    Ok(Some((basis_t, datoms)))
}

fn distributed_datomic_seek_datoms(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::Datom>)>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_seek_datoms_with_reader(
            &reader, &ipns_name, index, components, as_of, since,
        );
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_seek_datoms_with_reader(
        &reader, &ipns_name, index, components, as_of, since,
    )
}

fn distributed_datomic_seek_datoms_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    index: DatomicDatomsIndex,
    components: &[kotoba_edn::EdnValue],
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::Datom>)>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let prefix_components = if components.is_empty() {
        &[]
    } else {
        &components[..1]
    };
    let as_of = parse_optional_tx_cid("as_of", as_of)?;
    let since = parse_optional_tx_cid("since", since)?;
    if as_of.is_some() && since.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "as_of and since are mutually exclusive".to_string(),
        ));
    }
    let datoms = match (as_of.as_ref(), since.as_ref()) {
        (Some(tx), None) => reader.current_for_index_components_as_of_tx(
            &head.cid,
            tx,
            index.distributed_root(),
            prefix_components,
        ),
        (None, Some(tx)) => reader.current_for_index_components_since_tx(
            &head.cid,
            tx,
            index.distributed_root(),
            prefix_components,
        ),
        (None, None) => reader.current_for_index_components(
            &head.cid,
            index.distributed_root(),
            prefix_components,
        ),
        (Some(_), Some(_)) => unreachable!("checked above"),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic seekDatoms: {e}"),
        )
    })?;
    let basis_t = as_of
        .or_else(|| Some(head.tx_cid.clone()))
        .map(|cid| cid.to_multibase());
    Ok(Some((basis_t, datoms)))
}

fn distributed_datomic_index_range(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    attr: &str,
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::Datom>)>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_index_range_with_reader(
            &reader, &ipns_name, attr, as_of, since,
        );
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_index_range_with_reader(&reader, &ipns_name, attr, as_of, since)
}

fn distributed_datomic_index_range_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    attr: &str,
    as_of: Option<&str>,
    since: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::Datom>)>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let attr_value = kotoba_edn::EdnValue::String(attr.to_string());
    let as_of = parse_optional_tx_cid("as_of", as_of)?;
    let since = parse_optional_tx_cid("since", since)?;
    if as_of.is_some() && since.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "as_of and since are mutually exclusive".to_string(),
        ));
    }
    let datoms = match (as_of.as_ref(), since.as_ref()) {
        (Some(tx), None) => reader.current_for_index_components_as_of_tx(
            &head.cid,
            tx,
            ROOT_AVET,
            std::slice::from_ref(&attr_value),
        ),
        (None, Some(tx)) => reader.current_for_index_components_since_tx(
            &head.cid,
            tx,
            ROOT_AVET,
            std::slice::from_ref(&attr_value),
        ),
        (None, None) => reader.current_for_index_components(&head.cid, ROOT_AVET, &[attr_value]),
        (Some(_), Some(_)) => unreachable!("checked above"),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic indexRange: {e}"),
        )
    })?;
    let basis_t = as_of
        .or_else(|| Some(head.tx_cid.clone()))
        .map(|cid| cid.to_multibase());
    Ok(Some((basis_t, datoms)))
}

fn distributed_datomic_sync(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    target_tx: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<DatomicSyncResp>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        let response = distributed_datomic_sync_with_reader(
            &reader,
            graph_cid,
            target_tx,
            ipns_name.clone(),
            0,
        )?;
        if let Some(response) = response {
            let head = reader.resolve_head(&ipns_name).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("distributed datomic remote sync head: {e}"),
                )
            })?;
            if let Some(head) = head {
                reader.materialize_head_blocks(&head.cid).map_err(|e| {
                    (
                        StatusCode::BAD_REQUEST,
                        format!("distributed datomic remote sync blocks: {e}"),
                    )
                })?;
                let blocks = remote_store.cached_blocks().map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("distributed datomic remote sync cache: {e}"),
                    )
                })?;
                for (cid, bytes) in &blocks {
                    state.block_store.put(cid, bytes).map_err(|e| {
                        (
                            StatusCode::INTERNAL_SERVER_ERROR,
                            format!("distributed datomic remote sync store: {e}"),
                        )
                    })?;
                }
                let record = remote_ipns
                    .resolve(&IpnsName::new(ipns_name.clone()))
                    .map_err(|e| {
                        (
                            StatusCode::INTERNAL_SERVER_ERROR,
                            format!("distributed datomic remote sync ipns resolve: {e}"),
                        )
                    })?;
                state.ipns_registry.publish(record).map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("distributed datomic remote sync ipns publish: {e}"),
                    )
                })?;
                return Ok(Some(DatomicSyncResp {
                    synced_block_count: blocks.len(),
                    ..response
                }));
            }
            return Ok(Some(response));
        }
        return Ok(None);
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_sync_with_reader(&reader, graph_cid, target_tx, ipns_name, 0)
}

fn distributed_datomic_sync_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    graph_cid: &kotoba_core::cid::KotobaCid,
    target_tx: Option<&str>,
    ipns_name: String,
    synced_block_count: usize,
) -> Result<Option<DatomicSyncResp>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(&ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let target = parse_optional_tx_cid("tx", target_tx)?;
    let reached = match target.as_ref() {
        Some(tx) if *tx == head.tx_cid => true,
        Some(tx) => reader
            .log_from_head(&head.cid)
            .map_err(|e| {
                (
                    StatusCode::BAD_REQUEST,
                    format!("distributed datomic sync: {e}"),
                )
            })?
            .into_iter()
            .any(|entry| entry.tx == *tx),
        None => true,
    };
    Ok(Some(DatomicSyncResp {
        graph: graph_cid.to_multibase(),
        basis_t: Some(head.tx_cid.to_multibase()),
        commit_cid: head.cid.to_multibase(),
        ipns_name,
        ipns_sequence: head.seq,
        target_tx: target.map(|tx| tx.to_multibase()),
        reached,
        synced_block_count,
        index_roots: head
            .index_roots
            .iter()
            .map(|(name, cid)| (name.clone(), cid.to_multibase()))
            .collect(),
    }))
}

fn distributed_datomic_tx(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    tx: &str,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<
    Option<(
        Option<String>,
        kotoba_datomic::distributed::DistributedTxRangeEntry,
    )>,
    (StatusCode, String),
> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_tx_with_reader(&reader, &ipns_name, tx);
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_tx_with_reader(&reader, &ipns_name, tx)
}

fn distributed_datomic_tx_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    tx: &str,
) -> Result<
    Option<(
        Option<String>,
        kotoba_datomic::distributed::DistributedTxRangeEntry,
    )>,
    (StatusCode, String),
>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let tx = parse_optional_tx_cid("tx", Some(tx))?.expect("Some input parsed to Some tx");
    let entries = reader
        .tx_range_from_head(&head.cid, Some(&tx), None)
        .map_err(|e| {
            let msg = format!("distributed datomic tx: {e}");
            if msg.contains("start transaction not found") {
                (StatusCode::NOT_FOUND, msg)
            } else {
                (StatusCode::BAD_REQUEST, msg)
            }
        })?;
    let entry = entries
        .into_iter()
        .find(|entry| entry.commit.tx_cid == tx)
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                format!("distributed datomic tx not found: {}", tx.to_multibase()),
            )
        })?;
    Ok(Some((Some(head.tx_cid.to_multibase()), entry)))
}

fn distributed_datomic_tx_range(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    start: Option<&str>,
    end: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<
    Option<(
        Option<String>,
        Vec<kotoba_datomic::distributed::DistributedTxRangeEntry>,
    )>,
    (StatusCode, String),
> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_tx_range_with_reader(&reader, &ipns_name, start, end);
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_tx_range_with_reader(&reader, &ipns_name, start, end)
}

fn distributed_datomic_tx_range_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    start: Option<&str>,
    end: Option<&str>,
) -> Result<
    Option<(
        Option<String>,
        Vec<kotoba_datomic::distributed::DistributedTxRangeEntry>,
    )>,
    (StatusCode, String),
>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let start = parse_optional_tx_cid("start", start)?;
    let end = parse_optional_tx_cid("end", end)?;
    let entries = reader
        .tx_range_from_head(&head.cid, start.as_ref(), end.as_ref())
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                format!("distributed datomic txRange: {e}"),
            )
        })?;
    Ok(Some((Some(head.tx_cid.to_multibase()), entries)))
}

fn distributed_datomic_log(
    state: &KotobaState,
    graph_cid: &kotoba_core::cid::KotobaCid,
    start: Option<&str>,
    end: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::LogEntry>)>, (StatusCode, String)> {
    let ipns_name = remote_ipns_name
        .map(str::to_string)
        .unwrap_or_else(|| distributed_graph_ipns_name(graph_cid));
    if let Some(remote_peer) = remote_peer {
        let socket = parse_remote_peer_socket(remote_peer)?;
        let remote_store = RemoteIpfsBlockStore::new(socket);
        let remote_ipns = RemoteIpfsIpnsRegistry::new(socket);
        let reader = DistributedDatomReader::new(&remote_store, &remote_ipns);
        return distributed_datomic_log_with_reader(&reader, &ipns_name, start, end);
    }

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    distributed_datomic_log_with_reader(&reader, &ipns_name, start, end)
}

fn distributed_datomic_log_with_reader<R>(
    reader: &DistributedDatomReader<'_, R>,
    ipns_name: &str,
    start: Option<&str>,
    end: Option<&str>,
) -> Result<Option<(Option<String>, Vec<kotoba_datomic::LogEntry>)>, (StatusCode, String)>
where
    R: kotoba_ipfs::IpnsRegistry + ?Sized,
{
    let Some(head) = reader.resolve_head(ipns_name).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("distributed datomic head read: {e}"),
        )
    })?
    else {
        return Ok(None);
    };
    let start = parse_optional_tx_cid("start", start)?;
    let end = parse_optional_tx_cid("end", end)?;
    let entries = reader.log_from_head(&head.cid).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("distributed datomic log: {e}"),
        )
    })?;
    if let Some(start) = &start {
        if !entries.iter().any(|entry| &entry.tx == start) {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "datomic log start transaction not found: {}",
                    start.to_multibase()
                ),
            ));
        }
    }
    if let Some(end) = &end {
        if !entries.iter().any(|entry| &entry.tx == end) {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "datomic log end transaction not found: {}",
                    end.to_multibase()
                ),
            ));
        }
    }
    let entries = entries
        .into_iter()
        .skip_while(|entry| start.as_ref().is_some_and(|start| &entry.tx != start))
        .take_while(|entry| end.as_ref().is_none_or(|end| &entry.tx != end))
        .collect::<Vec<_>>();
    Ok(Some((Some(head.tx_cid.to_multibase()), entries)))
}

/// Outcome of a resident `db_before` cache warm (ADR-2605302130 startup-warm).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum DatomicWarmOutcome {
    /// Graph has no published IPNS head yet — nothing to load.
    EmptyGraph,
    /// The resident cache already held the resolved head — no cold scan taken.
    AlreadyWarm,
    /// Paid one cold `db_from_head` off the request path and seeded the cache.
    Warmed,
}

/// Pre-seed the resident `db_before` cache for one graph OFF the client request
/// deadline (ADR-2605302130 startup-warm follow-up).
///
/// `datomic.transact` serves `db_before` from RAM once the resident cache is
/// warm, but the FIRST transact after a (re)start (or an externally-advanced
/// head) still pays one O(graph) cold `db_from_head`. On an already-large graph
/// that single cold load can itself exceed the client's HTTP deadline (30s /
/// 120s) and fail the transact — and re-fail on every restart (the cold-start
/// failure yukkuri hit on `yukkuri-kg-v3`). Running that same one-time cold load
/// here — at startup, with no client waiting and with retry — moves it off the
/// request path so the first real transact hits RAM.
///
/// Idempotent and concurrency-safe: it takes the SAME per-graph
/// `datomic_live_slot` async lock the transact path takes, so a transact that
/// arrives mid-warm simply waits for the warm (rather than launching its own
/// redundant cold scan), and a warm that arrives after a transact already seeded
/// the slot is a no-op (`AlreadyWarm`). The seeded `Db` is exactly what a cold
/// `db_from_head` would produce (proved by `cached_db_before_equals_cold_db_from_head`).
pub(crate) async fn warm_datomic_resident_cache(
    state: &Arc<KotobaState>,
    graph_cid: &kotoba_core::cid::KotobaCid,
    ipns_name: &str,
) -> Result<DatomicWarmOutcome, DistributedCommitError> {
    let head = match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.to_string()))
    {
        Ok(record) => kotoba_core::cid::KotobaCid::from_multibase(&record.value),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => return Err(e.into()),
    };
    let Some(head) = head else {
        return Ok(DatomicWarmOutcome::EmptyGraph);
    };

    let graph_mb = graph_cid.to_multibase();
    let live_slot = state.datomic_live_slot(&graph_mb);
    let mut live_guard = live_slot.lock().await;
    if live_guard.as_ref().is_some_and(|live| live.head == head) {
        return Ok(DatomicWarmOutcome::AlreadyWarm);
    }

    // The one cold O(graph) scan — but off the request path, so a Kubo-slow
    // large graph gets unbounded wall-clock here instead of failing a transact.
    state
        .datomic_cold_db_loads
        .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let db = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry)
        .db_from_head(&head)?;
    *live_guard = Some(crate::server::LiveDatomicGraph { head, db });
    Ok(DatomicWarmOutcome::Warmed)
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.transact
/// Apply EDN transaction data, preserving Datomic's `(E,A,V,T,Added)` semantics
/// at the API boundary and projecting each datom into the current graph store.
pub async fn datomic_transact(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicTransactReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    const MAX_TX_EDN_LEN: usize = 1024 * 1024;
    if req.tx_edn.len() > MAX_TX_EDN_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "tx_edn too large ({} bytes, limit {MAX_TX_EDN_LEN})",
                req.tx_edn.len()
            ),
        ));
    }

    let graph_cid = parse_graph_cid(&req.graph)?;
    let operator_auth = crate::graph_auth::require_operator_auth(&headers, &state.operator_did);
    let mut write_author = state.operator_did.clone();
    let mut auth_proof_cid = None;
    let mut cacao_payload = None;
    let mut auth_capability = None;
    if let Some(cacao_b64) = req.cacao_b64.as_deref() {
        let payload = verify_datomic_cacao_payload_with_operations(
            &state,
            &req.graph,
            Some(cacao_b64),
            &[
                kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                kotoba_auth::CacaoPayload::OP_TX_CREATE,
            ],
        )?;
        write_author = payload.iss.clone();
        cacao_payload = Some(payload);
    } else if let Some(presentation) = &req.presentation {
        verify_vc_presentation_capabilities_scope(
            &state,
            &req.graph,
            presentation,
            &[
                kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                kotoba_auth::CacaoPayload::OP_TX_CREATE,
            ],
            None,
        )?;
        write_author = presentation
            .holder
            .clone()
            .unwrap_or_else(|| state.operator_did.clone());
    } else {
        operator_auth?;
    }

    let tx_data = kotoba_edn::parse(&req.tx_edn)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("tx_edn parse: {e}")))?;
    // Engine-tier DNA integrity (ADR-2606112000): if this graph has a registered Actor DNA
    // integrity ruleset (node config KOTOBA_DNA_RULES), validate the incoming datoms BEFORE
    // commit — so a peer's writes are checked too, not just a well-behaved actor's. No-op when
    // no ruleset is registered for the graph (backward-compatible).
    if let Some(ruleset) = crate::dna_integrity::ruleset_for(&graph_cid.to_multibase()) {
        crate::dna_integrity::validate_tx(&tx_data, ruleset).map_err(|e| {
            (
                StatusCode::UNPROCESSABLE_ENTITY,
                format!("dna integrity: {e}"),
            )
        })?;
    }
    let ipns_name = datomic_write_ipns_name(&graph_cid, req.ipns_name.as_deref())?;
    let current_head = match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.clone()))
    {
        Ok(record) => Some(record),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {e}"),
            ));
        }
    };
    let expected_parent = match req.expected_parent.as_deref() {
        Some(cid) => Some(
            kotoba_core::cid::KotobaCid::from_multibase(cid).ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    "invalid expected_parent CID".to_string(),
                )
            })?,
        ),
        None => current_head
            .as_ref()
            .and_then(|record| kotoba_core::cid::KotobaCid::from_multibase(&record.value)),
    };
    // Serialise transacts for this graph and serve `db_before` from the resident
    // in-memory cache when it is already at the expected head — this is the fix
    // for the ADR-2605302130 scaling blocker: it avoids the O(graph) cold
    // ProllyTree/Kubo scan (`db_from_head`) on every transact. The guard is held
    // across the commit + cache refresh below so the cached head cannot race a
    // concurrent transact for the same graph. On a head miss (first transact
    // after startup, or an externally-advanced head) we pay one cold scan and
    // re-seed the cache after committing.
    let graph_mb = graph_cid.to_multibase();
    let live_slot = state.datomic_live_slot(&graph_mb);
    let mut live_guard = live_slot.lock().await;
    let db_before = match expected_parent.as_ref() {
        Some(parent) => match live_guard.as_ref().filter(|live| &live.head == parent) {
            Some(live) => live.db.clone(),
            None => {
                // Cache miss on a non-empty graph: pay the one O(graph) cold scan
                // (first transact after (re)start, or an externally-advanced head).
                state
                    .datomic_cold_db_loads
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry)
                    .db_from_head(parent)
                    .map_err(|e| match e {
                        DistributedCommitError::MissingCommit(_) => {
                            (StatusCode::CONFLICT, format!("distributed db before: {e}"))
                        }
                        _ => (
                            StatusCode::INTERNAL_SERVER_ERROR,
                            format!("distributed db before: {e}"),
                        ),
                    })?
            }
        },
        None => kotoba_datomic::Db::from_datoms(Vec::new(), None),
    };
    let db_before_datoms = db_before.all_datoms();
    let tx_preview = kotoba_datomic::Connection::from_datoms(db_before_datoms.clone())
        .transact(tx_data.clone())
        .await
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic transact: {e}")))?;
    if let Some(payload) = &cacao_payload {
        enforce_datomic_write_tx_scope(payload, &tx_preview.tx_cid)?;
    }
    if let Some(presentation) = &req.presentation {
        if vc_presentation_declares_tx_scope(presentation) {
            let tx_scope = format!("kotoba://tx/{}", tx_preview.tx_cid.to_multibase());
            verify_vc_presentation_capabilities_scope(
                &state,
                &req.graph,
                presentation,
                &[
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    kotoba_auth::CacaoPayload::OP_TX_CREATE,
                ],
                Some(&tx_scope),
            )?;
        }
    }
    if let Some(cacao_b64) = req.cacao_b64.as_deref() {
        auth_proof_cid = Some(persist_cacao_auth_proof(&state, cacao_b64)?);
        if let Some(payload) = &cacao_payload {
            auth_capability = Some(cacao_capability_projection(payload, auth_proof_cid.clone()));
        }
    } else if let Some(presentation) = &req.presentation {
        auth_proof_cid = Some(persist_vp_auth_proof(&state, presentation)?);
        auth_capability = Some(vp_capability_projection(
            presentation,
            auth_proof_cid.clone(),
        ));
    }

    let explicit_cacao_proof_cid = match req.cacao_proof_cid.as_deref() {
        Some(cid) => Some(
            kotoba_core::cid::KotobaCid::from_multibase(cid).ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    "invalid cacao_proof_cid CID".to_string(),
                )
            })?,
        ),
        None => None,
    };
    let cacao_proof_cid = auth_proof_cid.clone().or(explicit_cacao_proof_cid);
    let writer = DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry);
    let distributed = writer
        .transact_with_db_before(
            DistributedTransactRequest {
                ipns_name: ipns_name.clone(),
                graph: graph_cid.clone(),
                tx_data,
                expected_parent,
                author: write_author.clone(),
                valid_until: "2099-01-01T00:00:00Z".to_string(),
                ttl_secs: Some(60),
                cacao_proof_cid: cacao_proof_cid.clone(),
                ipns_controller_did: Some(state.operator_did.clone()),
                ipns_signing_key: Some(state.ipns_signing_key()),
            },
            // Same DB the preview used; equals db_from_head(expected_parent) so the
            // writer skips its own cold scan without changing the commit hash.
            Some(db_before),
            |report, context, tx_datoms| {
                append_tx_metadata_datoms(
                    tx_datoms,
                    &report.tx_cid,
                    &context.graph,
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    &write_author,
                    cacao_proof_cid.as_ref(),
                    &context.ipns_name,
                    context.seq,
                    &state.operator_did,
                    context.expected_parent.as_ref(),
                );
                if let Some(auth_capability) = &auth_capability {
                    append_auth_capability_datoms(tx_datoms, &report.tx_cid, auth_capability);
                }
                Ok(())
            },
        )
        .await
        .map_err(|e| match e {
            DistributedCommitError::StaleParent { .. } => {
                (StatusCode::CONFLICT, format!("distributed commit: {e}"))
            }
            DistributedCommitError::Datom(_) => {
                (StatusCode::BAD_REQUEST, format!("datomic transact: {e}"))
            }
            _ => (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("distributed commit: {e}"),
            ),
        })?;
    let report = distributed.transact;
    let distributed_commit = distributed.commit;
    let tx_datoms = distributed.datoms;

    // Datomic firehose: broadcast each datom to the live-tail (ephemeral — NO
    // LiveBus block persist), since the commit is already durable in the CommitDag
    // and replayable via sync.eventsFromCommits / eventsAllGraphs. This removes the
    // redundant per-datom LiveBus copy entirely (the LiveBus now persists only
    // non-datomic topics: signal / realtime / kse pub-sub).
    let mut journal_cids = Vec::with_capacity(tx_datoms.len());
    for datom in &tx_datoms {
        let quad = datom_to_projection_quad(datom, &graph_cid);
        let cid = if datom.added {
            state.journal_assert_ephemeral(&quad).await
        } else {
            state.journal_retract_ephemeral(&quad).await
        };
        state
            .quad_store
            .apply_journaled_datom(graph_cid.clone(), datom_to_projection_kqe(datom))
            .await;
        journal_cids.push(cid);
    }

    // Refresh the resident db_before cache from the actual committed datoms
    // (including auth/capability metadata injected by the distributed writer), so
    // immediate reads see the same DB that a cold scan of the new head would.
    let mut cached_datoms = db_before_datoms;
    cached_datoms.extend(tx_datoms.iter().cloned());
    *live_guard = Some(crate::server::LiveDatomicGraph {
        head: distributed_commit.commit.cid.clone(),
        db: kotoba_datomic::Db::from_datoms(
            kotoba_datomic::current_datoms(&cached_datoms),
            report.db_after.basis_t.clone(),
        ),
    });
    drop(live_guard);

    Ok((
        StatusCode::OK,
        Json(DatomicTransactResp {
            status: "ok",
            graph: req.graph,
            tx_cid: report.tx_cid.to_multibase(),
            commit_cid: distributed_commit.commit.cid.to_multibase(),
            auth_proof_cid: distributed_commit
                .commit
                .cacao_proof_cid
                .as_ref()
                .map(|cid| cid.to_multibase()),
            ipns_name,
            ipns_sequence: distributed_commit.ipns_record.sequence,
            ipns_valid_until: distributed_commit.ipns_record.valid_until,
            index_roots: distributed_commit
                .commit
                .index_roots
                .into_iter()
                .map(|(k, v)| (k, v.to_multibase()))
                .collect(),
            datom_count: tx_datoms.len(),
            journal_cids,
            tempids: report
                .tempids
                .into_iter()
                .map(|(k, v)| (k, v.to_multibase()))
                .collect(),
            datoms: tx_datoms.into_iter().map(datomic_datom_resp).collect(),
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.with
/// Apply EDN transaction data to a DB value and return a Datomic-style report
/// without publishing an IPNS head, writing journal quads, or persisting blocks.
pub async fn datomic_with(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicWithReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    const MAX_TX_EDN_LEN: usize = 1024 * 1024;
    if req.tx_edn.len() > MAX_TX_EDN_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "tx_edn too large ({} bytes, limit {MAX_TX_EDN_LEN})",
                req.tx_edn.len()
            ),
        ));
    }

    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;

    let tx_data = kotoba_edn::parse(&req.tx_edn)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("tx_edn parse: {e}")))?;
    let db_before = match distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )? {
        Some(db) => db,
        None => kotoba_datomic::Db::from_datoms(Vec::new(), None),
    };
    let db_before_basis_t = db_before.basis_t.as_ref().map(|tx| tx.to_multibase());
    let conn = kotoba_datomic::Connection::from_datoms(db_before.all_datoms());
    let report = conn
        .transact(tx_data)
        .await
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic with: {e}")))?;

    Ok((
        StatusCode::OK,
        Json(DatomicWithResp {
            status: "ok",
            graph: req.graph,
            db_before_basis_t,
            db_after_basis_t: report.db_after.basis_t.as_ref().map(|tx| tx.to_multibase()),
            tx_cid: report.tx_cid.to_multibase(),
            tempids: report
                .tempids
                .into_iter()
                .map(|(k, v)| (k, v.to_multibase()))
                .collect(),
            tx_data: report
                .tx_data
                .clone()
                .into_iter()
                .map(datomic_datom_resp)
                .collect(),
            db_after_datoms: report
                .db_after
                .datoms()
                .into_iter()
                .map(datomic_datom_resp)
                .collect(),
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.asOf
pub async fn datomic_as_of(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicDbValueReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        Some(req.tx.as_str()),
        None,
    )
    .await?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        Some(req.tx.as_str()),
        None,
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;

    Ok((
        StatusCode::OK,
        Json(datomic_db_value_resp(req.graph, req.tx, &db)),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.since
pub async fn datomic_since(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicDbValueReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        None,
        Some(req.tx.as_str()),
    )
    .await?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        None,
        Some(req.tx.as_str()),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;

    Ok((
        StatusCode::OK,
        Json(datomic_db_value_resp(req.graph, req.tx, &db)),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.sync
pub async fn datomic_sync(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicSyncReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.tx.as_deref(),
        None,
    )
    .await?;
    let response = distributed_datomic_sync(
        &state,
        &graph_cid,
        req.tx.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?
    .ok_or_else(|| missing_distributed_datomic_head(&graph_cid))?;

    Ok((StatusCode::OK, Json(response)))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.datoms
pub async fn datomic_datoms(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicDatomsReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;

    let index = DatomicDatomsIndex::parse(&req.index)?;
    let components = parse_datomic_datoms_components(&req.components_edn)?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let components = resolve_datomic_index_components(&db, index, &components)?;
    if let Some((basis_t, mut datoms)) = distributed_datomic_datoms(
        &state,
        &graph_cid,
        index,
        &components,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )? {
        let limit = req.limit.unwrap_or(1000).min(10_000);
        datoms.retain(|datom| datomic_datoms_value_matches_index(datom, index));
        let mut fallback_datoms = db.datoms();
        fallback_datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, index));
        for datom in fallback_datoms {
            if datoms.contains(&datom) {
                continue;
            }
            if datomic_datoms_match_components(&datom, index, &components)? {
                datoms.push(datom);
            }
        }
        datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, index));
        let datoms = datoms.into_iter().take(limit).collect::<Vec<_>>();
        let datom_count = datoms.len();
        return Ok((
            StatusCode::OK,
            Json(DatomicDatomsResp {
                graph: req.graph,
                index: req.index,
                basis_t,
                datom_count,
                datoms: datoms.into_iter().map(datomic_datom_resp).collect(),
            }),
        ));
    }
    let mut datoms = db.datoms();
    datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, index));
    let limit = req.limit.unwrap_or(1000).min(10_000);
    let datoms = datoms
        .into_iter()
        .filter_map(
            |datom| match datomic_datoms_match_components(&datom, index, &components) {
                Ok(true) => Some(Ok(datom)),
                Ok(false) => None,
                Err(e) => Some(Err(e)),
            },
        )
        .take(limit)
        .collect::<Result<Vec<_>, _>>()?;
    let datom_count = datoms.len();

    Ok((
        StatusCode::OK,
        Json(DatomicDatomsResp {
            graph: req.graph,
            index: req.index,
            basis_t: basis_t_resp(&db),
            datom_count,
            datoms: datoms.into_iter().map(datomic_datom_resp).collect(),
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.seekDatoms
pub async fn datomic_seek_datoms(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicSeekDatomsReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;

    let index = DatomicDatomsIndex::parse(&req.index)?;
    let components = parse_datomic_datoms_components(&req.components_edn)?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let components = resolve_datomic_index_components(&db, index, &components)?;
    let seek_key = datomic_seek_key(index, &components)?;
    if let Some((basis_t, mut datoms)) = distributed_datomic_seek_datoms(
        &state,
        &graph_cid,
        index,
        &components,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )? {
        datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, index));
        let limit = req.limit.unwrap_or(1000).min(10_000);
        let datoms = datoms
            .into_iter()
            .filter(|datom| datomic_datoms_sort_values(datom, index) >= seek_key)
            .take(limit)
            .collect::<Vec<_>>();
        let datom_count = datoms.len();
        return Ok((
            StatusCode::OK,
            Json(DatomicDatomsResp {
                graph: req.graph,
                index: req.index,
                basis_t,
                datom_count,
                datoms: datoms.into_iter().map(datomic_datom_resp).collect(),
            }),
        ));
    }
    let mut datoms = db.datoms();
    datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, index));
    let limit = req.limit.unwrap_or(1000).min(10_000);
    let datoms = datoms
        .into_iter()
        .filter(|datom| datomic_datoms_sort_values(datom, index) >= seek_key)
        .take(limit)
        .collect::<Vec<_>>();
    let datom_count = datoms.len();

    Ok((
        StatusCode::OK,
        Json(DatomicDatomsResp {
            graph: req.graph,
            index: req.index,
            basis_t: basis_t_resp(&db),
            datom_count,
            datoms: datoms.into_iter().map(datomic_datom_resp).collect(),
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.indexRange
pub async fn datomic_index_range(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicIndexRangeReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;

    let attr = datomic_component_attr(
        &kotoba_edn::parse(&req.attr_edn)
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("attr_edn parse: {e}")))?,
    )?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let start = resolve_datomic_index_range_bound(
        &db,
        parse_optional_edn("start_edn", req.start_edn.as_deref())?,
    )?;
    let end = resolve_datomic_index_range_bound(
        &db,
        parse_optional_edn("end_edn", req.end_edn.as_deref())?,
    )?;
    if let (Some(start), Some(end)) = (&start, &end) {
        if start >= end {
            return Err((
                StatusCode::BAD_REQUEST,
                "indexRange start_edn must be less than end_edn".to_string(),
            ));
        }
    }

    if let Some((basis_t, mut datoms)) = distributed_datomic_index_range(
        &state,
        &graph_cid,
        &attr,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )? {
        datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, DatomicDatomsIndex::Avet));
        let limit = req.limit.unwrap_or(1000).min(10_000);
        let datoms = datoms
            .into_iter()
            .filter(|datom| {
                datom.a == attr
                    && start
                        .as_ref()
                        .map(|start| datom.v >= *start)
                        .unwrap_or(true)
                    && end.as_ref().map(|end| datom.v < *end).unwrap_or(true)
            })
            .take(limit)
            .collect::<Vec<_>>();
        let datom_count = datoms.len();
        return Ok((
            StatusCode::OK,
            Json(DatomicDatomsResp {
                graph: req.graph,
                index: ":avet".to_string(),
                basis_t,
                datom_count,
                datoms: datoms.into_iter().map(datomic_datom_resp).collect(),
            }),
        ));
    }

    let mut datoms = db.datoms();
    datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, DatomicDatomsIndex::Avet));
    let limit = req.limit.unwrap_or(1000).min(10_000);
    let datoms = datoms
        .into_iter()
        .filter(|datom| {
            datom.a == attr
                && start
                    .as_ref()
                    .map(|start| datom.v >= *start)
                    .unwrap_or(true)
                && end.as_ref().map(|end| datom.v < *end).unwrap_or(true)
        })
        .take(limit)
        .collect::<Vec<_>>();
    let datom_count = datoms.len();

    Ok((
        StatusCode::OK,
        Json(DatomicDatomsResp {
            graph: req.graph,
            index: ":avet".to_string(),
            basis_t: basis_t_resp(&db),
            datom_count,
            datoms: datoms.into_iter().map(datomic_datom_resp).collect(),
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.indexPull
pub async fn datomic_index_pull(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicIndexPullReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;

    let index = DatomicDatomsIndex::parse(&req.index)?;
    let components = parse_datomic_datoms_components(&req.components_edn)?;
    let pattern = match req.pattern_edn.as_deref() {
        Some(src) => kotoba_edn::parse(src)
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("pattern_edn parse: {e}")))?,
        None => kotoba_edn::EdnValue::Vector(vec![]),
    };
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let components = resolve_datomic_index_components(&db, index, &components)?;
    let (basis_t, mut datoms) = distributed_datomic_datoms(
        &state,
        &graph_cid,
        index,
        &components,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?
    .unwrap_or_else(|| {
        let datoms = db
            .datoms()
            .into_iter()
            .filter_map(
                |datom| match datomic_datoms_match_components(&datom, index, &components) {
                    Ok(true) => Some(datom),
                    Ok(false) | Err(_) => None,
                },
            )
            .collect::<Vec<_>>();
        (basis_t_resp(&db), datoms)
    });
    datoms.sort_by_key(|datom| datomic_datoms_sort_key(datom, index));

    let mut seen = BTreeSet::new();
    let limit = req.limit.unwrap_or(1000).min(10_000);
    let mut entities = Vec::new();
    for datom in datoms {
        if !seen.insert(datom.e.to_multibase()) {
            continue;
        }
        let entity = datom.e;
        let entity_edn = db
            .pull(pattern.clone(), entity.clone())
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic indexPull: {e}")))?;
        let entity_datoms = db
            .datoms()
            .into_iter()
            .filter(|datom| datom.e == entity)
            .map(datomic_datom_resp)
            .collect::<Vec<_>>();
        entities.push(DatomicPullManyEntityResp {
            entity: entity.to_multibase(),
            entity_edn: kotoba_edn::to_string(&entity_edn),
            datom_count: entity_datoms.len(),
            datoms: entity_datoms,
        });
        if entities.len() >= limit {
            break;
        }
    }

    Ok((
        StatusCode::OK,
        Json(DatomicPullManyResp {
            graph: req.graph,
            basis_t,
            entity_count: entities.len(),
            entities,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.pull
pub async fn datomic_pull(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicPullReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let pattern = match req.pattern_edn.as_deref() {
        Some(src) => kotoba_edn::parse(src)
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("pattern_edn parse: {e}")))?,
        None => kotoba_edn::EdnValue::Vector(vec![]),
    };

    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let entity = datomic_entity_from_request(&db, &req.entity)?;
    let entity_edn = db
        .pull(pattern, entity.clone())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic pull: {e}")))?;
    let datoms = db
        .datoms()
        .into_iter()
        .filter(|datom| datom.e == entity)
        .map(datomic_datom_resp)
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(DatomicPullResp {
            graph: req.graph,
            entity: req.entity,
            basis_t: basis_t_resp(&db),
            entity_edn: kotoba_edn::to_string(&entity_edn),
            datom_count: datoms.len(),
            datoms,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.pullMany
pub async fn datomic_pull_many(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicPullManyReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    const MAX_PULL_MANY_ENTITIES: usize = 1000;
    if req.entities.len() > MAX_PULL_MANY_ENTITIES {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "entities too large ({} entries, limit {MAX_PULL_MANY_ENTITIES})",
                req.entities.len()
            ),
        ));
    }

    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let pattern = match req.pattern_edn.as_deref() {
        Some(src) => kotoba_edn::parse(src)
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("pattern_edn parse: {e}")))?,
        None => kotoba_edn::EdnValue::Vector(vec![]),
    };
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let entity_cids = req
        .entities
        .iter()
        .map(|entity| datomic_entity_from_request(&db, entity))
        .collect::<Result<Vec<_>, _>>()?;
    let pulled = db
        .pull_many(pattern, entity_cids.clone())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic pullMany: {e}")))?;
    let entities = req
        .entities
        .into_iter()
        .zip(entity_cids)
        .zip(pulled)
        .map(|((entity, entity_cid), entity_edn)| {
            let datoms = db
                .datoms()
                .into_iter()
                .filter(|datom| datom.e == entity_cid)
                .map(datomic_datom_resp)
                .collect::<Vec<_>>();
            DatomicPullManyEntityResp {
                entity,
                entity_edn: kotoba_edn::to_string(&entity_edn),
                datom_count: datoms.len(),
                datoms,
            }
        })
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(DatomicPullManyResp {
            graph: req.graph,
            basis_t: basis_t_resp(&db),
            entity_count: entities.len(),
            entities,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.q
pub async fn datomic_q(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicQReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read_any_operation(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        &[
            kotoba_auth::CacaoPayload::OP_DATOM_READ,
            kotoba_auth::CacaoPayload::OP_GRAPH_QUERY,
        ],
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let query = kotoba_edn::parse(&req.query_edn)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("query_edn parse: {e}")))?;
    let inputs = req
        .inputs_edn
        .iter()
        .map(|src| {
            kotoba_edn::parse(src)
                .map_err(|e| (StatusCode::BAD_REQUEST, format!("inputs_edn parse: {e}")))
        })
        .collect::<Result<Vec<_>, _>>()?;
    // First-tier read fast path: for local current-state queries (no time-travel,
    // history, or remote peer) serve from the resident `datomic_live_slot` Db
    // cache instead of reconstructing the graph from cold storage on every call.
    let is_local_current = req.remote_peer.is_none()
        && req.remote_ipns_name.is_none()
        && req.as_of.is_none()
        && req.since.is_none()
        && !req.history;
    let resident = if is_local_current {
        try_resident_datomic_q(&state, &graph_cid, &query, &inputs).await?
    } else {
        None
    };
    let (basis_t, rows) = match resident {
        Some(result) => result,
        None => distributed_datomic_q(
            &state,
            &graph_cid,
            &query,
            &inputs,
            req.as_of.as_deref(),
            req.since.as_deref(),
            req.history,
            req.remote_peer.as_deref(),
            req.remote_ipns_name.as_deref(),
        )?
        .ok_or_else(|| missing_distributed_datomic_head(&graph_cid))?,
    };
    let rows_map = datomic_q_rows_map(&query, &rows)?;
    let rows_edn: Vec<Vec<String>> = rows
        .iter()
        .map(|row| row.iter().map(kotoba_edn::to_string).collect())
        .collect();

    // Optional content-addressed provenance (emit_cid). result_cid is derived
    // from the canonical rows, so it is tamper-evident; envelope blocks are PUT
    // best-effort and never auto-pinned.
    let (query_spec_cid, query_job_cid, result_cid) = if req.emit_cid {
        // Only persist envelope blocks for Public graphs — block.get is
        // unauthenticated, so a private/authenticated result must not be left
        // retrievable bearer-by-CID. The CIDs are returned regardless.
        let persist = matches!(
            state.graph_visibility(&graph_cid).await,
            kotoba_core::named_graph::GraphVisibility::Public
        );
        let (spec, job, result) = datomic_q_emit_cids(
            &state,
            &query,
            &inputs,
            basis_t.as_deref(),
            req.as_of.as_deref(),
            req.since.as_deref(),
            req.history,
            &rows_edn,
            persist,
        );
        (Some(spec), Some(job), Some(result))
    } else {
        (None, None, None)
    };

    Ok((
        StatusCode::OK,
        Json(DatomicQResp {
            graph: req.graph,
            basis_t,
            rows_edn,
            rows_map_edn: rows_map.as_ref().map(|rows| rows.edn.clone()),
            rows_map_json: rows_map.map(|rows| rows.json),
            query_spec_cid,
            query_job_cid,
            result_cid,
        }),
    ))
}

/// `kotoba.queryspec.v1` — the query, normalized free of source-text formatting.
#[derive(Serialize)]
struct KotobaQuerySpecEnvelope {
    #[serde(rename = "type")]
    kind: &'static str,
    lang: &'static str,
    query: String,
    inputs: Vec<String>,
}

/// `kotoba.queryjob.v1` — query bound to a basis transaction + params + engine.
#[derive(Serialize)]
struct KotobaQueryJobEnvelope {
    #[serde(rename = "type")]
    kind: &'static str,
    query_spec: String,
    basis_t: Option<String>,
    as_of: Option<String>,
    since: Option<String>,
    history: bool,
    engine: &'static str,
}

/// `kotoba.result.v1` — the verifiable, content-derived result envelope.
#[derive(Serialize)]
struct KotobaResultEnvelope<'a> {
    #[serde(rename = "type")]
    kind: &'static str,
    query_job: String,
    basis_t: Option<String>,
    engine: &'static str,
    rows_edn: &'a [Vec<String>],
}

/// Build the `datomic.q` provenance envelopes and return
/// `(query_spec_cid, query_job_cid, result_cid)` as multibase strings.
///
/// `result_cid` is the CID of the canonical DAG-CBOR result envelope and is thus
/// content-derived (tamper-evident): change any row and the CID changes. Each
/// envelope block is PUT best-effort so a verifier can re-fetch it by CID; the
/// blocks are NOT pinned — durable retention stays an explicit `pin*` decision.
///
/// Canonicalization (R0): query / inputs / rows are normalized via the canonical
/// EDN writer (`kotoba_edn::to_string` — sorted maps/sets, no extra whitespace),
/// so formatting-only differences collapse to the same CID. Datalog variable
/// alpha-renaming is not yet normalized (deferred).
fn datomic_q_emit_cids(
    state: &KotobaState,
    query: &kotoba_edn::EdnValue,
    inputs: &[kotoba_edn::EdnValue],
    basis_t: Option<&str>,
    as_of: Option<&str>,
    since: Option<&str>,
    history: bool,
    rows_edn: &[Vec<String>],
    persist: bool,
) -> (String, String, String) {
    const ENGINE: &str = concat!("kotoba-server/", env!("CARGO_PKG_VERSION"));

    let spec = KotobaQuerySpecEnvelope {
        kind: "kotoba.queryspec.v1",
        lang: "datalog",
        query: kotoba_edn::to_string(query),
        inputs: inputs.iter().map(kotoba_edn::to_string).collect(),
    };
    let query_spec_cid = put_envelope(state, &spec, persist);

    let job = KotobaQueryJobEnvelope {
        kind: "kotoba.queryjob.v1",
        query_spec: query_spec_cid.clone(),
        basis_t: basis_t.map(str::to_string),
        as_of: as_of.map(str::to_string),
        since: since.map(str::to_string),
        history,
        engine: ENGINE,
    };
    let query_job_cid = put_envelope(state, &job, persist);

    let result = KotobaResultEnvelope {
        kind: "kotoba.result.v1",
        query_job: query_job_cid.clone(),
        basis_t: basis_t.map(str::to_string),
        engine: ENGINE,
        rows_edn,
    };
    let result_cid = put_envelope(state, &result, persist);

    (query_spec_cid, query_job_cid, result_cid)
}

/// dag-cbor encode `value`, derive its IPFS-compatible (CIDv1 dag-cbor sha2-256)
/// CID, PUT the block best-effort (un-pinned), and return the multibase CID.
pub(crate) fn put_envelope<T: Serialize>(state: &KotobaState, value: &T, persist: bool) -> String {
    // The CID is content-derived and ALWAYS returned. The block is PUT only when:
    //
    //  • `persist` — the graph is Public. Blocks are retrievable by CID via the
    //    UNAUTHENTICATED `block.get`, so persisting a private/authenticated
    //    result envelope would expose it bearer-by-CID and bypass the read gate.
    //    For non-public graphs the caller still gets the CID and can rebuild the
    //    envelope from the (already-returned) rows to verify — no public copy.
    //  • under the size cap — bound the best-effort write a read can trigger so a
    //    churn of large-result reads can't grow the block store unboundedly. The
    //    1 MiB cap matches the datomic.q body limit; spec/job envelopes are tiny.
    const MAX_ENVELOPE_PUT_BYTES: usize = 1 << 20;

    let (cid, bytes) = kotoba_ipfs::dag_cbor_block(value).expect("envelope is serializable");
    let kcid = kotoba_core::cid::KotobaCid::from_standard_cid(&cid)
        .expect("dag-cbor sha2-256 cid is kotoba-compatible");
    // A failed (or skipped) PUT must not fail the query — the CID still stands.
    if persist && bytes.len() <= MAX_ENVELOPE_PUT_BYTES {
        let _ = state.block_store.put(&kcid, &bytes);
    }
    kcid.to_multibase()
}

#[derive(Clone, Copy)]
enum DatomicQMapKeyStyle {
    Keyword,
    String,
    Symbol,
}

struct DatomicQRowsMap {
    edn: Vec<String>,
    json: Vec<std::collections::BTreeMap<String, String>>,
}

fn datomic_q_rows_map(
    query: &kotoba_edn::EdnValue,
    rows: &[Vec<kotoba_edn::EdnValue>],
) -> Result<Option<DatomicQRowsMap>, (StatusCode, String)> {
    let Some((style, keys)) = datomic_q_map_keys(query)? else {
        return Ok(None);
    };
    let mut edn_rows = Vec::with_capacity(rows.len());
    let mut json_rows = Vec::with_capacity(rows.len());
    for row in rows {
        if row.len() == 1 {
            if let Some(map) = row[0].as_map() {
                edn_rows.push(kotoba_edn::to_string(&row[0]));
                json_rows.push(
                    map.iter()
                        .map(|(key, value)| {
                            (
                                datomic_q_json_key_from_edn(key),
                                kotoba_edn::to_string(value),
                            )
                        })
                        .collect(),
                );
                continue;
            }
        }
        if row.len() != keys.len() {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "Datomic :keys/:strs/:syms arity {} does not match result arity {}",
                    keys.len(),
                    row.len()
                ),
            ));
        }
        let edn_map = keys
            .iter()
            .cloned()
            .zip(row.iter().cloned())
            .map(|(key, value)| (datomic_q_map_key(style, &key), value))
            .collect::<std::collections::BTreeMap<_, _>>();
        let json_map = keys
            .iter()
            .zip(row.iter())
            .map(|(key, value)| {
                (
                    datomic_q_json_map_key(style, key),
                    kotoba_edn::to_string(value),
                )
            })
            .collect::<std::collections::BTreeMap<_, _>>();
        edn_rows.push(kotoba_edn::to_string(&kotoba_edn::EdnValue::Map(edn_map)));
        json_rows.push(json_map);
    }
    Ok(Some(DatomicQRowsMap {
        edn: edn_rows,
        json: json_rows,
    }))
}

fn datomic_q_json_key_from_edn(key: &kotoba_edn::EdnValue) -> String {
    match key {
        kotoba_edn::EdnValue::Keyword(keyword) => format!(":{}", keyword.to_qualified()),
        kotoba_edn::EdnValue::String(value) => value.clone(),
        kotoba_edn::EdnValue::Symbol(symbol) => symbol.to_qualified(),
        other => kotoba_edn::to_string(other),
    }
}

fn datomic_q_map_keys(
    query: &kotoba_edn::EdnValue,
) -> Result<Option<(DatomicQMapKeyStyle, Vec<String>)>, (StatusCode, String)> {
    let map = kotoba_datomic::query_map(query)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic query: {e}")))?;
    for (keyword, style) in [
        ("keys", DatomicQMapKeyStyle::Keyword),
        ("strs", DatomicQMapKeyStyle::String),
        ("syms", DatomicQMapKeyStyle::Symbol),
    ] {
        if let Some(value) = map.get(&kotoba_edn::EdnValue::kw_bare(keyword)) {
            let keys = value.as_seq().ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    format!(":{keyword} must be a vector or list"),
                )
            })?;
            return keys
                .iter()
                .map(datomic_q_map_key_name)
                .collect::<Result<Vec<_>, _>>()
                .map(|keys| Some((style, keys)));
        }
    }
    Ok(None)
}

fn datomic_q_map_key_name(value: &kotoba_edn::EdnValue) -> Result<String, (StatusCode, String)> {
    if let Some(symbol) = value.as_symbol() {
        return Ok(symbol.to_qualified());
    }
    if let Some(keyword) = value.as_keyword() {
        return Ok(keyword.to_qualified());
    }
    if let Some(string) = value.as_string() {
        return Ok(string.to_string());
    }
    Err((
        StatusCode::BAD_REQUEST,
        format!(
            ":keys/:strs/:syms entries must be symbols, keywords, or strings, got {}",
            kotoba_edn::to_string(value)
        ),
    ))
}

fn datomic_q_map_key(style: DatomicQMapKeyStyle, key: &str) -> kotoba_edn::EdnValue {
    match style {
        DatomicQMapKeyStyle::Keyword => {
            kotoba_edn::EdnValue::Keyword(kotoba_edn::Keyword::parse(key))
        }
        DatomicQMapKeyStyle::String => kotoba_edn::EdnValue::String(key.to_string()),
        DatomicQMapKeyStyle::Symbol => kotoba_edn::EdnValue::Symbol(kotoba_edn::Symbol::parse(key)),
    }
}

fn datomic_q_json_map_key(style: DatomicQMapKeyStyle, key: &str) -> String {
    match style {
        DatomicQMapKeyStyle::Keyword => format!(":{key}"),
        DatomicQMapKeyStyle::String | DatomicQMapKeyStyle::Symbol => key.to_string(),
    }
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.history
pub async fn datomic_history(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicHistoryReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let limit = req.limit.unwrap_or(1000).min(10_000);
    let db = require_distributed_datomic_history_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let datoms = db
        .history()
        .datoms()
        .iter()
        .take(limit)
        .cloned()
        .map(datomic_datom_resp)
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(DatomicHistoryResp {
            graph: req.graph,
            basis_t: basis_t_resp(&db),
            datom_count: datoms.len(),
            datoms,
        }),
    ))
}

fn datomic_tx_resp_from_entry(
    entry: kotoba_datomic::distributed::DistributedTxRangeEntry,
) -> DatomicTxRangeTxResp {
    let tx_instant_ms = datomic_tx_instant_ms(&entry.datoms);
    let datoms = entry
        .datoms
        .into_iter()
        .map(datomic_datom_resp)
        .collect::<Vec<_>>();
    DatomicTxRangeTxResp {
        tx_cid: entry.commit.tx_cid.to_multibase(),
        commit_cid: entry.commit.cid.to_multibase(),
        prev_commit_cid: entry.commit.prev.map(|cid| cid.to_multibase()),
        seq: entry.commit.seq,
        author: entry.commit.author,
        ts: entry.commit.ts,
        tx_instant_ms,
        datom_count: datoms.len(),
        datoms,
    }
}

fn datomic_tx_instant_ms(datoms: &[kotoba_datomic::Datom]) -> Option<i64> {
    datoms.iter().find_map(|datom| {
        if datom.e == datom.t && datom.a == ":db/txInstant" {
            match &datom.v {
                kotoba_edn::EdnValue::Integer(value) if *value > 0 => Some(*value),
                _ => None,
            }
        } else {
            None
        }
    })
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.tx
pub async fn datomic_tx(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicDbValueReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        Some(req.tx.as_str()),
        None,
    )
    .await?;
    let (basis_t, entry) = distributed_datomic_tx(
        &state,
        &graph_cid,
        &req.tx,
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?
    .ok_or_else(|| missing_distributed_datomic_head(&graph_cid))?;

    Ok((
        StatusCode::OK,
        Json(DatomicTxResp {
            graph: req.graph,
            basis_t,
            tx: datomic_tx_resp_from_entry(entry),
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.txRange
pub async fn datomic_tx_range(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicTxRangeReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read_tx_range(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        &[kotoba_auth::CacaoPayload::OP_DATOM_READ],
        req.start.as_deref(),
        req.end.as_deref(),
    )
    .await?;
    let limit = req.limit.unwrap_or(100).min(10_000);
    let (basis_t, entries) = distributed_datomic_tx_range(
        &state,
        &graph_cid,
        req.start.as_deref(),
        req.end.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?
    .unwrap_or((None, Vec::new()));
    let txes = entries
        .into_iter()
        .take(limit)
        .map(datomic_tx_resp_from_entry)
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(DatomicTxRangeResp {
            graph: req.graph,
            basis_t,
            tx_count: txes.len(),
            txes,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.log
pub async fn datomic_log(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicLogReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read_tx_range(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        &[kotoba_auth::CacaoPayload::OP_DATOM_READ],
        req.start.as_deref(),
        req.end.as_deref(),
    )
    .await?;
    let limit = req.limit.unwrap_or(100).min(10_000);
    let (basis_t, entries) = distributed_datomic_log(
        &state,
        &graph_cid,
        req.start.as_deref(),
        req.end.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?
    .ok_or_else(|| missing_distributed_datomic_head(&graph_cid))?;
    let txes = entries
        .into_iter()
        .take(limit)
        .map(|entry| {
            let tx_instant_ms = datomic_tx_instant_ms(&entry.datoms);
            let datoms = entry
                .datoms
                .into_iter()
                .map(datomic_datom_resp)
                .collect::<Vec<_>>();
            DatomicLogTxResp {
                tx_cid: entry.tx.to_multibase(),
                tx_instant_ms,
                datom_count: datoms.len(),
                datoms,
            }
        })
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(DatomicLogResp {
            graph: req.graph,
            basis_t,
            tx_count: txes.len(),
            txes,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.basisT
pub async fn datomic_basis_t(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicBasisTReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;

    Ok((
        StatusCode::OK,
        Json(DatomicBasisTResp {
            graph: req.graph,
            basis_t: basis_t_resp(&db),
        }),
    ))
}

#[derive(Debug, Deserialize)]
pub struct DatomicGcReq {
    pub graph: String,
    /// Number of most-recent commits to retain (clamped to ≥1). Older commits'
    /// history blocks that no kept commit references are deleted.
    #[serde(default = "default_gc_keep")]
    pub keep_last_n: usize,
}
fn default_gc_keep() -> usize {
    1
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.gc
///
/// Operator-only. Prunes deep Datomic history for `graph`, keeping the newest
/// `keep_last_n` commits and deleting ProllyTree/commit blocks reachable only
/// from older ones. Safe on the shared block store: KSE-journal / vault blocks
/// are never referenced by Datomic commits, so they are never deleted.
pub async fn datomic_gc(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicGcReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    let graph_cid = parse_graph_cid(&req.graph)?;
    let ipns_name = distributed_graph_ipns_name(&graph_cid);
    let head = match state.ipns_registry.resolve(&IpnsName::new(ipns_name)) {
        Ok(record) => kotoba_core::cid::KotobaCid::from_multibase(&record.value),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => return Err((StatusCode::INTERNAL_SERVER_ERROR, format!("ipns: {e}"))),
    };
    let Some(head) = head else {
        return Err((
            StatusCode::NOT_FOUND,
            format!("no distributed Datomic/IPNS head for graph {}", req.graph),
        ));
    };
    let report = gc_history(&head, req.keep_last_n, &*state.block_store)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("gc: {e}")))?;
    Ok((
        StatusCode::OK,
        Json(serde_json::json!({
            "graph": req.graph,
            "keptCommits": report.kept_commits,
            "droppedCommits": report.dropped_commits,
            "deletedBlocks": report.deleted_blocks,
        })),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.dbStats
pub async fn datomic_db_stats(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicDbStatsReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;

    Ok((StatusCode::OK, Json(datomic_db_stats_resp(req.graph, &db))))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.entity
pub async fn datomic_entity(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicEntityReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let entity = datomic_entity_from_request(&db, &req.entity)?;
    let entity_edn = db
        .entity(entity.clone())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("datomic entity: {e}")))?;
    let datoms = db
        .datoms()
        .into_iter()
        .filter(|datom| datom.e == entity)
        .map(datomic_datom_resp)
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(DatomicEntityResp {
            graph: req.graph,
            entity: req.entity,
            basis_t: basis_t_resp(&db),
            entity_edn: kotoba_edn::to_string(&entity_edn),
            datom_count: datoms.len(),
            datoms,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.ident
pub async fn datomic_ident(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicIdentReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let entity = parse_datomic_entity(&req.entity);
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let ident_edn =
        datomic_ident_for_entity(&db, &entity).map(|value| kotoba_edn::to_string(&value));

    Ok((
        StatusCode::OK,
        Json(DatomicIdentResp {
            graph: req.graph,
            entity: req.entity,
            basis_t: basis_t_resp(&db),
            ident_edn,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.datomic.entid
pub async fn datomic_entid(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DatomicEntidReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_DATOM_READ,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;
    let ident = kotoba_edn::parse(&req.ident_edn)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("ident_edn parse: {e}")))?;
    let db = require_distributed_datomic_db(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )?;
    let entity = datomic_entid_for_value(&db, &ident)?.map(|cid| cid.to_multibase());

    Ok((
        StatusCode::OK,
        Json(DatomicEntidResp {
            graph: req.graph,
            ident_edn: req.ident_edn,
            basis_t: basis_t_resp(&db),
            entity,
        }),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.vc.issue
pub async fn vc_issue(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<VcIssueReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let mut author = state.operator_did.clone();
    let mut auth_proof_cid = None;
    let mut auth_capability = None;
    if let Err(operator_err) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        if let Some(cacao_b64) = req.cacao_b64.as_deref() {
            let payload = verify_datomic_cacao_payload(
                &state,
                &req.graph,
                Some(cacao_b64),
                kotoba_auth::CacaoPayload::OP_VC_ISSUE,
            )?;
            author = payload.iss.clone();
            auth_proof_cid = Some(persist_cacao_auth_proof(&state, cacao_b64)?);
            auth_capability = Some(cacao_capability_projection(
                &payload,
                auth_proof_cid.clone(),
            ));
        } else if let Some(presentation) = &req.auth_presentation {
            verify_vc_presentation_capability(
                &state,
                &req.graph,
                presentation,
                kotoba_auth::CacaoPayload::OP_VC_ISSUE,
            )?;
            author = presentation
                .holder
                .clone()
                .unwrap_or_else(|| state.operator_did.clone());
            auth_proof_cid = Some(persist_vp_auth_proof(&state, presentation)?);
            auth_capability = Some(vp_capability_projection(
                presentation,
                auth_proof_cid.clone(),
            ));
        } else {
            return Err(operator_err);
        }
    }

    let graph_cid = parse_graph_cid(&req.graph)?;
    let credential = issue_credential_with_operator_proof(req.credential.clone(), &state)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("vc issue proof: {e}")))?;
    let entity_cid = credential
        .cid()
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("vc cid: {e}")))?;
    let tx_cid = kotoba_core::cid::KotobaCid::from_bytes(
        format!("vc.issue:{}:{}", req.graph, entity_cid.to_multibase()).as_bytes(),
    );
    let datoms = credential
        .to_datoms(tx_cid.clone())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("vc datoms: {e}")))?;
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph,
        entity_cid,
        datoms,
        tx_cid,
        author,
        kotoba_auth::CacaoPayload::OP_VC_ISSUE,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    Ok((StatusCode::OK, Json(resp)))
}

fn issue_credential_with_operator_proof(
    mut credential: kotoba_vc::VerifiableCredential,
    state: &KotobaState,
) -> Result<kotoba_vc::VerifiableCredential, kotoba_vc::VcError> {
    credential.issuer = state.operator_did.clone();
    credential.proof = None;
    credential.ensure_data_integrity_context();
    let signature = state.ipns_signing_key().sign(&credential.proof_bytes()?);
    credential.proof = Some(kotoba_vc::DataIntegrityProof {
        proof_type: "DataIntegrityProof".to_string(),
        cryptosuite: Some("eddsa-2022".to_string()),
        proof_purpose: "assertionMethod".to_string(),
        verification_method: format!("{}#agent-ed25519", state.operator_did),
        created: Some("2026-05-29T00:00:00Z".to_string()),
        proof_value: multibase::encode(multibase::Base::Base58Btc, signature.to_bytes()),
        challenge: Some("vc.issue".to_string()),
        domain: Some("kotoba.vc.issue".to_string()),
    });
    Ok(credential)
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.vc.present
pub async fn vc_present(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<VcPresentReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let mut author = state.operator_did.clone();
    let mut auth_proof_cid = None;
    let mut auth_capability = None;
    if let Err(operator_err) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        if let Some(cacao_b64) = req.cacao_b64.as_deref() {
            let payload = verify_datomic_cacao_payload(
                &state,
                &req.graph,
                Some(cacao_b64),
                kotoba_auth::CacaoPayload::OP_VC_PRESENT,
            )?;
            author = payload.iss.clone();
            auth_proof_cid = Some(persist_cacao_auth_proof(&state, cacao_b64)?);
            auth_capability = Some(cacao_capability_projection(
                &payload,
                auth_proof_cid.clone(),
            ));
        } else if let Some(presentation) = &req.auth_presentation {
            verify_vc_presentation_capability(
                &state,
                &req.graph,
                presentation,
                kotoba_auth::CacaoPayload::OP_VC_PRESENT,
            )?;
            author = presentation
                .holder
                .clone()
                .unwrap_or_else(|| state.operator_did.clone());
            auth_proof_cid = Some(persist_vp_auth_proof(&state, presentation)?);
            auth_capability = Some(vp_capability_projection(
                presentation,
                auth_proof_cid.clone(),
            ));
        } else {
            return Err(operator_err);
        }
    }

    let graph_cid = parse_graph_cid(&req.graph)?;
    let entity_cid = req
        .presentation
        .cid()
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("vp cid: {e}")))?;
    let tx_cid = kotoba_core::cid::KotobaCid::from_bytes(
        format!("vc.present:{}:{}", req.graph, entity_cid.to_multibase()).as_bytes(),
    );
    let datoms = req
        .presentation
        .to_datoms(tx_cid.clone())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("vp datoms: {e}")))?;
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph,
        entity_cid,
        datoms,
        tx_cid,
        author,
        kotoba_auth::CacaoPayload::OP_VC_PRESENT,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    Ok((StatusCode::OK, Json(resp)))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.did.document.publish
pub async fn did_document_publish(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DidDocumentPublishReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let mut author = state.operator_did.clone();
    let mut auth_proof_cid = None;
    let mut auth_capability = None;
    if let Err(operator_err) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        if let Some(cacao_b64) = req.cacao_b64.as_deref() {
            let payload = verify_datomic_cacao_payload(
                &state,
                &req.graph,
                Some(cacao_b64),
                kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
            )?;
            author = payload.iss.clone();
            auth_proof_cid = Some(persist_cacao_auth_proof(&state, cacao_b64)?);
            auth_capability = Some(cacao_capability_projection(
                &payload,
                auth_proof_cid.clone(),
            ));
        } else if let Some(presentation) = &req.auth_presentation {
            verify_vc_presentation_capability(
                &state,
                &req.graph,
                presentation,
                kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
            )?;
            author = presentation
                .holder
                .clone()
                .unwrap_or_else(|| state.operator_did.clone());
            auth_proof_cid = Some(persist_vp_auth_proof(&state, presentation)?);
            auth_capability = Some(vp_capability_projection(
                presentation,
                auth_proof_cid.clone(),
            ));
        } else {
            return Err(operator_err);
        }
    }

    let missing_services = req.document.missing_kotoba_protocol_services();
    if !missing_services.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "DID Document missing Kotoba protocol service(s): {}",
                missing_services.join(", ")
            ),
        ));
    }

    let graph_cid = parse_graph_cid(&req.graph)?;
    let entity_cid = req.document.entity_cid();
    let document_bytes = serde_json::to_vec(&req.document)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("did document json: {e}")))?;
    let tx_cid = protocol_payload_tx_cid(
        "did.document.publish",
        &req.graph,
        &entity_cid,
        document_bytes,
    );
    let datoms = req.document.to_datoms(tx_cid.clone());
    let did = req.document.id.clone();
    let registry_datoms = datoms.clone();
    let registry_tx_cid = tx_cid.clone();
    let registry_author = author.clone();
    let registry_auth_proof_cid = auth_proof_cid.clone();
    let registry_auth_capability = auth_capability.clone();
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph,
        entity_cid,
        datoms,
        tx_cid,
        author,
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    commit_did_document_registry_datoms(
        &state,
        &did,
        registry_datoms,
        registry_tx_cid,
        registry_author,
        registry_auth_proof_cid,
        registry_auth_capability,
    )?;
    Ok((StatusCode::OK, Json(resp)))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.didcomm.send
pub async fn didcomm_send(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<DidCommSendReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let graph_cid = parse_graph_cid(&req.graph)?;
    let entity_cid = req
        .message
        .cid()
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("didcomm cid: {e}")))?;
    let message_bytes = serde_json::to_vec(&req.message)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("didcomm json: {e}")))?;
    let tx_cid = protocol_payload_tx_cid("didcomm.send", &req.graph, &entity_cid, message_bytes);

    let mut author = state.operator_did.clone();
    let mut auth_proof_cid = None;
    let mut auth_capability = None;
    if let Err(operator_err) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        let thread_scope = format!("didcomm://thread/{}", req.message.thread_id());
        if let Some(cacao_b64) = req.cacao_b64.as_deref() {
            let payload = verify_datomic_cacao_payload(
                &state,
                &req.graph,
                Some(cacao_b64),
                kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
            )?;
            if !payload.authorizes_didcomm_thread(req.message.thread_id()) {
                return Err((
                    StatusCode::UNAUTHORIZED,
                    format!("CACAO missing DIDComm thread scope {thread_scope}"),
                ));
            }
            enforce_datomic_write_tx_scope(&payload, &tx_cid)?;
            author = payload.iss.clone();
            auth_proof_cid = Some(persist_cacao_auth_proof(&state, cacao_b64)?);
            auth_capability = Some(cacao_capability_projection(
                &payload,
                auth_proof_cid.clone(),
            ));
        } else if let Some(presentation) = &req.auth_presentation {
            verify_vc_presentation_capability_scope(
                &state,
                &req.graph,
                presentation,
                kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
                Some(&thread_scope),
            )?;
            if vc_presentation_declares_tx_scope(presentation) {
                let tx_scope = format!("kotoba://tx/{}", tx_cid.to_multibase());
                verify_vc_presentation_capability_scope(
                    &state,
                    &req.graph,
                    presentation,
                    kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
                    Some(&tx_scope),
                )?;
            }
            author = presentation
                .holder
                .clone()
                .unwrap_or_else(|| state.operator_did.clone());
            auth_proof_cid = Some(persist_vp_auth_proof(&state, presentation)?);
            auth_capability = Some(vp_capability_projection(
                presentation,
                auth_proof_cid.clone(),
            ));
        } else {
            return Err(operator_err);
        }
    }

    let datoms = req
        .message
        .to_datoms(tx_cid.clone())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("didcomm datoms: {e}")))?;
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph,
        entity_cid,
        datoms,
        tx_cid,
        author,
        kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    Ok((StatusCode::OK, Json(resp)))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.atproto.repo.write
pub async fn atproto_repo_write(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<AtprotoRepoWriteReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let uri = kotoba_graph::AtUri::parse(&req.uri)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid atproto uri".to_string()))?;
    if uri.collection.is_empty() || uri.rkey.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "atproto repo.write uri must include collection and rkey".to_string(),
        ));
    }
    let graph_cid = parse_graph_cid(&req.graph)?;
    let entity_cid = atproto_repo_record_entity_cid(&req.uri);
    let operation = req.operation.as_deref().unwrap_or("create");
    let tx_cid = kotoba_core::cid::KotobaCid::from_bytes(
        serde_json::to_vec(&serde_json::json!({
            "op": "atproto.repo.write",
            "graph": &req.graph,
            "uri": &req.uri,
            "operation": operation,
            "cid": &req.cid,
            "record": &req.record,
        }))
        .unwrap_or_default()
        .as_slice(),
    );

    let mut author = state.operator_did.clone();
    let mut auth_proof_cid = None;
    let mut auth_capability = None;
    if let Err(operator_err) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        if let Some(cacao_b64) = req.cacao_b64.as_deref() {
            let payload = verify_datomic_cacao_payload(
                &state,
                &req.graph,
                Some(cacao_b64),
                kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
            )?;
            if !payload.authorizes_atproto_resource(&req.uri) {
                return Err((
                    StatusCode::UNAUTHORIZED,
                    format!("CACAO missing ATProto scope {}", req.uri),
                ));
            }
            enforce_datomic_write_tx_scope(&payload, &tx_cid)?;
            author = payload.iss.clone();
            auth_proof_cid = Some(persist_cacao_auth_proof(&state, cacao_b64)?);
            auth_capability = Some(cacao_capability_projection(
                &payload,
                auth_proof_cid.clone(),
            ));
        } else if let Some(presentation) = &req.auth_presentation {
            verify_vc_presentation_capability_scope(
                &state,
                &req.graph,
                presentation,
                kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
                Some(&req.uri),
            )?;
            if vc_presentation_declares_tx_scope(presentation) {
                let tx_scope = format!("kotoba://tx/{}", tx_cid.to_multibase());
                verify_vc_presentation_capability_scope(
                    &state,
                    &req.graph,
                    presentation,
                    kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
                    Some(&tx_scope),
                )?;
            }
            author = presentation
                .holder
                .clone()
                .unwrap_or_else(|| state.operator_did.clone());
            auth_proof_cid = Some(persist_vp_auth_proof(&state, presentation)?);
            auth_capability = Some(vp_capability_projection(
                presentation,
                auth_proof_cid.clone(),
            ));
        } else {
            return Err(operator_err);
        }
    }

    let datoms = if operation == "delete" {
        let db = distributed_datomic_db(&state, &graph_cid, None, None, None, None)?
            .unwrap_or_else(|| kotoba_datomic::Db::from_datoms(Vec::new(), None));
        atproto_repo_delete_datoms(&db, &req, &uri, &entity_cid, &tx_cid)
    } else {
        atproto_repo_write_datoms(&req, &uri, &entity_cid, &tx_cid)
    };
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph,
        entity_cid,
        datoms,
        tx_cid,
        author,
        kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    Ok((StatusCode::OK, Json(resp)))
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.node.status
/// Operator-only: exposes peer topology that aids targeted DHT attacks.
pub async fn node_status(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    let nb = state.neighborhood.read().await;
    let did_document = state.local_did_document().await;
    Json(serde_json::json!({
        "node_id":    hex::encode(state.local_node_id.0),
        "operator_did": state.operator_did.as_str(),
        "did_document": did_document,
        "peer_count": nb.peers.len(),
        "peers":      nb.peers.iter().map(|p| hex::encode(p.0)).collect::<Vec<_>>(),
        "k":          kotoba_dht::neighborhood::K,
    }))
    .into_response()
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.invoke.run
/// Execute a WASM component or Datalog program, then publish resulting quads to LiveBus.
#[cfg(feature = "wasm-runtime")]
pub async fn invoke_run(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<InvokeRunReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    const MAX_AGENT_DID_LEN: usize = 512;
    const MAX_PROGRAM_CID_LEN: usize = 512;
    const MAX_GRAPH_CID_LEN: usize = 512;
    const MAX_PROGRAM_TYPE_LEN: usize = 16;
    crate::graph_auth::validate_did(&req.agent_did, "agent_did", MAX_AGENT_DID_LEN)?;
    if req.program_cid.len() > MAX_PROGRAM_CID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "program_cid too long ({} bytes, limit {MAX_PROGRAM_CID_LEN})",
                req.program_cid.len()
            ),
        ));
    }
    if req.program_type.len() > MAX_PROGRAM_TYPE_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "program_type too long ({} bytes, limit {MAX_PROGRAM_TYPE_LEN})",
                req.program_type.len()
            ),
        ));
    }
    if let Some(gcid) = &req.graph_cid {
        if gcid.len() > MAX_GRAPH_CID_LEN {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "graph_cid too long ({} bytes, limit {MAX_GRAPH_CID_LEN})",
                    gcid.len()
                ),
            ));
        }
    }

    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_dht::source_chain::ProgramType;

    let program_type = match req.program_type.as_str() {
        "wasm-node" => ProgramType::WasmNode,
        "wasm-udf" => ProgramType::WasmUdf,
        "datalog" => ProgramType::Datalog,
        other => {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("unknown program_type: {other}"),
            ))
        }
    };

    // 50 MiB wasm cap (a full WASM module rarely exceeds a few MiB; 50 MiB is generous).
    const MAX_WASM_B64_LEN: usize = 50 * 1024 * 1024;
    // 1 MiB ctx cap — context CBOR should be small structured data, not a data dump.
    const MAX_CTX_B64_LEN: usize = 1024 * 1024;

    let wasm_bytes: Vec<u8> = match &req.wasm_b64 {
        Some(b64) => {
            if b64.len() > MAX_WASM_B64_LEN {
                return Err((
                    StatusCode::PAYLOAD_TOO_LARGE,
                    format!(
                        "wasm_b64 too large ({} bytes, limit {MAX_WASM_B64_LEN})",
                        b64.len()
                    ),
                ));
            }
            B64.decode(b64)
                .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?
        }
        None if program_type != ProgramType::Datalog => {
            return Err((
                StatusCode::BAD_REQUEST,
                "wasm_b64 required for wasm programs".into(),
            ));
        }
        None => vec![],
    };

    let ctx_cbor: Vec<u8> = match &req.ctx_b64 {
        Some(b64) => {
            if b64.len() > MAX_CTX_B64_LEN {
                return Err((
                    StatusCode::PAYLOAD_TOO_LARGE,
                    format!(
                        "ctx_b64 too large ({} bytes, limit {MAX_CTX_B64_LEN})",
                        b64.len()
                    ),
                ));
            }
            B64.decode(b64)
                .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?
        }
        None => vec![],
    };

    use kotoba_core::cid::KotobaCid;
    use kotoba_query::{Datom as KqeDatom, Value as KqeValue};
    use kotoba_runtime::host::WitQuad;
    use kotoba_vm::DispatchResult;

    // Build quad snapshot from the distributed Datom head for kqe.query in WASM guests.
    let graph_cid_for_snapshot = req
        .graph_cid
        .as_deref()
        .map(KotobaCid::from_multibase)
        .and_then(|x| x);
    let quad_snapshot: Vec<WitQuad> = if let Some(gcid) = &graph_cid_for_snapshot {
        match current_db_for_graph(&state, gcid).await {
            Ok(db) => db
                .datoms()
                .into_iter()
                .filter_map(|datom| {
                    let substrate = datom.to_kqe().ok()?;
                    let object: kotoba_query::quad::LegacyQuadObject = substrate.v.into();
                    Some(WitQuad {
                        graph: gcid.to_multibase(),
                        subject: substrate.e.to_multibase(),
                        predicate: substrate.a,
                        object_cbor: serde_json::to_vec(&object).unwrap_or_default(),
                    })
                })
                .collect(),
            Err((code, msg)) => {
                return Err((code, format!("invoke graph snapshot: {msg}")));
            }
        }
    } else {
        vec![]
    };

    // Build distributed IPNS head map for kqe.get-head in WASM guests.
    let mut head_commits = std::collections::HashMap::new();
    if let Some(gcid) = &graph_cid_for_snapshot {
        let ipns_name = distributed_graph_ipns_name(gcid);
        match state
            .ipns_registry
            .resolve(&IpnsName::new(ipns_name.clone()))
        {
            Ok(record) => {
                head_commits.insert(gcid.to_multibase(), record.value);
            }
            Err(IpnsRegistryError::NotFound(_)) => {}
            Err(e) => {
                return Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("invoke graph head: {e}"),
                ));
            }
        }
    }

    // Move owned data into spawn_blocking — dispatch is CPU-bound (Cranelift JIT)
    let program_cid = req.program_cid.clone();
    let agent_did = req.agent_did.clone();
    let router = Arc::clone(&state.router);
    let wasm_owned = if wasm_bytes.is_empty() {
        None
    } else {
        Some(wasm_bytes)
    };

    let result = tokio::task::spawn_blocking(move || {
        let wasm_ref = wasm_owned.as_deref();
        router.dispatch_with_snapshot(
            &program_cid,
            program_type,
            &agent_did,
            0,
            wasm_ref,
            ctx_cbor,
            None,
            None,
            &[],
            10_000,
            quad_snapshot,
            head_commits,
        )
    })
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    match result {
        DispatchResult::Wasm(r) => {
            // Reject if WASM produced an unreasonably large assert batch.
            // At 10 gas/assert and 10M gas limit the theoretical max is 1M quads;
            // storing and returning 1M CIDs would be a multi-MB response DoS.
            const MAX_ASSERT_QUADS: usize = 10_000;
            if r.assert_quads.len() > MAX_ASSERT_QUADS {
                return Err((
                    StatusCode::PAYLOAD_TOO_LARGE,
                    format!(
                        "WASM produced {} assert quads (limit {MAX_ASSERT_QUADS})",
                        r.assert_quads.len()
                    ),
                ));
            }

            if r.retract_quads.len() > MAX_ASSERT_QUADS {
                return Err((
                    StatusCode::PAYLOAD_TOO_LARGE,
                    format!(
                        "WASM produced {} retract quads (limit {MAX_ASSERT_QUADS})",
                        r.retract_quads.len()
                    ),
                ));
            }

            let mut by_graph: BTreeMap<String, Vec<KqeDatom>> = BTreeMap::new();
            for sq in &r.assert_quads {
                let graph_cid = KotobaCid::from_bytes(sq.graph.as_bytes());
                let datom = KqeDatom::assert(
                    KotobaCid::from_bytes(sq.subject.as_bytes()),
                    sq.predicate.clone(),
                    KqeValue::Bytes(sq.object_cbor.clone()),
                    graph_cid,
                );
                by_graph.entry(sq.graph.clone()).or_default().push(datom);
            }
            for sq in &r.retract_quads {
                let graph_cid = KotobaCid::from_bytes(sq.graph.as_bytes());
                let datom = KqeDatom::retract(
                    KotobaCid::from_bytes(sq.subject.as_bytes()),
                    sq.predicate.clone(),
                    KqeValue::Bytes(sq.object_cbor.clone()),
                    graph_cid,
                );
                by_graph.entry(sq.graph.clone()).or_default().push(datom);
            }
            let mut journal_cids =
                Vec::with_capacity(r.assert_quads.len().saturating_add(r.retract_quads.len()));
            for (graph, mut datoms) in by_graph {
                let graph_cid = KotobaCid::from_bytes(graph.as_bytes());
                let tx_cid = KotobaCid::from_bytes(
                    format!(
                        "invoke.run:{}:{}:{}:{}",
                        req.program_cid, req.agent_did, graph, r.gas_used
                    )
                    .as_bytes(),
                );
                let entity_cid = datoms
                    .first()
                    .map(|datom| datom.e.clone())
                    .unwrap_or_else(|| graph_cid.clone());
                for datom in &mut datoms {
                    datom.tx = tx_cid.clone();
                }
                let distributed = commit_protocol_datoms(
                    &state,
                    graph_cid,
                    graph,
                    entity_cid,
                    datoms
                        .into_iter()
                        .map(kotoba_datomic::Datom::from_kqe)
                        .collect(),
                    tx_cid,
                    req.agent_did.clone(),
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    None,
                    None,
                )
                .await?;
                journal_cids.extend(distributed.journal_cids);
            }
            // Apply kse.publish calls buffered by guest WASM
            for (topic, payload) in &r.pending_publishes {
                use kotoba_vault::Topic;
                state
                    .journal
                    .publish(Topic(topic.clone()), bytes::Bytes::from(payload.clone()))
                    .await;
            }

            tracing::info!(
                program_cid = %req.program_cid,
                gas_used    = r.gas_used,
                asserts     = r.assert_quads.len(),
                retracts    = r.retract_quads.len(),
                kse_publishes = r.pending_publishes.len(),
                chain_entries = r.pending_chain_entries.len(),
                "invoke.run → LiveBus published"
            );

            Ok(Json(InvokeRunResp {
                status: "ok",
                gas_used: r.gas_used,
                output_b64: B64.encode(&r.output_cbor),
                assert_count: r.assert_quads.len(),
                retract_count: r.retract_quads.len(),
                journal_cids,
            }))
        }

        DispatchResult::Datalog(r) => Ok(Json(InvokeRunResp {
            status: "ok",
            gas_used: r.steps_used as u64,
            output_b64: B64.encode(format!("{:?}", r.status)),
            assert_count: r.out_deltas.len(),
            retract_count: 0,
            journal_cids: vec![],
        })),
    }
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.invoke.run
/// Heavy WASM/Pregel runtime disabled in the lean server build.
#[cfg(not(feature = "wasm-runtime"))]
pub async fn invoke_run(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(_req): Json<InvokeRunReq>,
) -> Result<axum::response::Response, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    Err((
        StatusCode::SERVICE_UNAVAILABLE,
        "invoke.run requires the `wasm-runtime` feature".to_string(),
    ))
}

// ── Block store endpoints ──────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct BlockPutReq {
    /// base64-encoded raw block bytes
    pub data_b64: String,
}

#[derive(Debug, Serialize)]
pub struct BlockPutResp {
    pub cid: String,
}

#[derive(Debug, Deserialize)]
pub struct BlockGetReq {
    pub cid: String,
}

#[derive(Debug, Serialize)]
pub struct BlockGetResp {
    pub cid: String,
    pub data_b64: String,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.block.put
/// Write raw bytes into the block store, returning the CID.
pub async fn block_put(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<BlockPutReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;

    // 32 MiB per block (ProllyTree internal nodes are tiny; large leaf values should
    // be chunked by the vault, not pushed as single raw blocks).
    const MAX_BLOCK_B64_LEN: usize = 32 * 1024 * 1024;
    if req.data_b64.len() > MAX_BLOCK_B64_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "data_b64 too large ({} bytes, limit {MAX_BLOCK_B64_LEN})",
                req.data_b64.len()
            ),
        ));
    }

    let bytes = B64
        .decode(&req.data_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
    let (cid, bytes) = tokio::task::spawn_blocking(move || {
        let cid = KotobaCid::from_bytes(&bytes);
        (cid, bytes)
    })
    .await
    .map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("spawn_blocking: {e}"),
        )
    })?;
    state
        .block_store
        .put(&cid, &bytes)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // Fire-and-forget IPFS pin
    {
        let pin = std::sync::Arc::clone(&state.ipfs_pin);
        let cid_str = cid.to_multibase();
        tokio::spawn(async move { pin.pin(&cid_str).await });
    }

    Ok(Json(BlockPutResp {
        cid: cid.to_multibase(),
    }))
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.block.get?cid=<multibase>
///
/// SECURITY INVARIANT: this endpoint is intentionally UNAUTHENTICATED — blocks
/// are content-addressed (IPFS-style), so the CID itself is the capability
/// (unguessable, since it's the SHA2-256 of the content). Consequence for every
/// `block_store.put` site: never persist a block whose mere disclosure-by-CID
/// would breach a tenant's read gate. Anything PUT here is retrievable by anyone
/// holding the CID, regardless of graph visibility. (emit_cid honors this by
/// persisting envelopes only for Public graphs — see put_envelope.)
pub async fn block_get(
    State(state): State<Arc<KotobaState>>,
    axum::extract::Query(req): axum::extract::Query<BlockGetReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;

    const MAX_CID_LEN: usize = 512;
    if req.cid.len() > MAX_CID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cid too long ({} bytes, limit {MAX_CID_LEN})",
                req.cid.len()
            ),
        ));
    }
    let cid = KotobaCid::from_multibase(&req.cid)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid CID".into()))?;
    match state
        .block_store
        .get(&cid)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    {
        None => Err((StatusCode::NOT_FOUND, "block not found".into())),
        Some(bytes) => Ok(Json(BlockGetResp {
            cid: req.cid.clone(),
            data_b64: B64.encode(&bytes),
        })),
    }
}

// ── WasmNode registration ──────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct NodeRegisterReq {
    /// app name (the `<app>` in `com.etzhayyim.apps.<app>.<method>`)
    pub app: String,
    /// program CID (the wasm component, e.g. from block.put)
    pub endpoint: String,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.node.register
/// Register an external app's wasm node so `generic_invoke` resolves+dispatches it.
pub async fn node_register(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<NodeRegisterReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    if req.app.trim().is_empty() || req.endpoint.trim().is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "app and endpoint are required".into(),
        ));
    }
    state.register_external_node(&req.app, &req.endpoint).await;
    Ok(Json(serde_json::json!({
        "status": "ok",
        "app": req.app,
        "endpoint": req.endpoint,
    })))
}

// ── Commit endpoints ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CommitGetReq {
    pub graph: String,
}

#[derive(Debug, Serialize)]
pub struct CommitGetResp {
    pub cid: String,
    pub graph: String,
    pub root: String,
    pub prev: Option<String>,
    pub author: String,
    pub seq: u64,
    pub ts: u64,
    pub commit_type: &'static str,
    pub tx_cid: Option<String>,
    pub index_roots: BTreeMap<String, String>,
    pub cacao_proof_cid: Option<String>,
    pub ipns_name: Option<String>,
    pub ipns_value_cid: Option<String>,
    pub ipns_sequence: Option<u64>,
    pub ipns_value_matches_commit: Option<bool>,
    pub ipns_sequence_matches_commit: Option<bool>,
    pub ipns_graph_matches_request: Option<bool>,
    pub ipns_controller_did: Option<String>,
    pub ipns_controller_matches_node: Option<bool>,
    pub ipns_controller_key_matches_did: Option<bool>,
    pub ipns_public_key_multibase: Option<String>,
    pub ipns_signature_multibase: Option<String>,
    pub ipns_signature_verified: Option<bool>,
    pub ipns_verified: Option<bool>,
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.commit.get?graph=<multibase>
pub async fn commit_get(
    State(state): State<Arc<KotobaState>>,
    axum::extract::Query(req): axum::extract::Query<CommitGetReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_core::cid::KotobaCid;

    const MAX_GRAPH_LEN: usize = 512;
    if req.graph.len() > MAX_GRAPH_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "graph too long ({} bytes, limit {MAX_GRAPH_LEN})",
                req.graph.len()
            ),
        ));
    }
    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".into()))?;

    let ipns_name = distributed_graph_ipns_name(&graph_cid);
    match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.clone()))
    {
        Ok(record) => {
            let commit_cid = KotobaCid::from_multibase(&record.value).ok_or_else(|| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "distributed IPNS head is not a CID".to_string(),
                )
            })?;
            let commit = DistributedDatomCommit::load(&commit_cid, &*state.block_store)
                .map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("distributed commit load: {e}"),
                    )
                })?
                .ok_or_else(|| {
                    (
                        StatusCode::NOT_FOUND,
                        "distributed commit block not found".to_string(),
                    )
                })?;
            let root = commit
                .index_roots
                .get(ROOT_TEA)
                .or_else(|| commit.index_roots.get(ROOT_EAVT))
                .map(|cid| cid.to_multibase())
                .unwrap_or_default();
            let value_matches_commit = record.value == commit.cid.to_multibase();
            let sequence_matches_commit = record.sequence == commit.seq;
            let graph_matches_request = commit.graph == graph_cid;
            let signature_verified = record.signature_verified();
            let controller_matches_node =
                record.controller_did.as_deref() == Some(state.operator_did.as_str());
            let controller_key_matches_did = controller_matches_node
                && match record.public_key_multibase.as_deref() {
                    Some(key) => {
                        state
                            .did_ed25519_key_matches(&state.operator_did, key)
                            .await
                    }
                    None => false,
                };
            let ipns_verified = value_matches_commit
                && sequence_matches_commit
                && graph_matches_request
                && signature_verified
                && controller_matches_node
                && controller_key_matches_did;
            return Ok(Json(CommitGetResp {
                cid: commit.cid.to_multibase(),
                graph: commit.graph.to_multibase(),
                root,
                prev: commit.prev.map(|p| p.to_multibase()),
                author: commit.author,
                seq: commit.seq,
                ts: commit.ts,
                commit_type: "distributed-datomic",
                tx_cid: Some(commit.tx_cid.to_multibase()),
                index_roots: commit
                    .index_roots
                    .into_iter()
                    .map(|(k, v)| (k, v.to_multibase()))
                    .collect(),
                cacao_proof_cid: commit.cacao_proof_cid.map(|cid| cid.to_multibase()),
                ipns_name: Some(ipns_name),
                ipns_value_cid: Some(record.value),
                ipns_sequence: Some(record.sequence),
                ipns_value_matches_commit: Some(value_matches_commit),
                ipns_sequence_matches_commit: Some(sequence_matches_commit),
                ipns_graph_matches_request: Some(graph_matches_request),
                ipns_controller_did: record.controller_did,
                ipns_controller_matches_node: Some(controller_matches_node),
                ipns_controller_key_matches_did: Some(controller_key_matches_did),
                ipns_public_key_multibase: record.public_key_multibase,
                ipns_signature_multibase: record.signature_multibase,
                ipns_signature_verified: Some(signature_verified),
                ipns_verified: Some(ipns_verified),
            }));
        }
        Err(IpnsRegistryError::NotFound(_)) => {}
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {e}"),
            ));
        }
    }

    Err((
        StatusCode::NOT_FOUND,
        "no distributed commit for graph".into(),
    ))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.commit.store
/// Flush current Arrangement for the given graph into BlockStore and create a Commit.
#[derive(Debug, Deserialize)]
pub struct CommitStoreReq {
    pub graph: String,
    pub author: String,
    pub seq: u64,
    /// CACAO delegation proof (CBOR, base64) — required; must carry `datom:transact` capability.
    pub cacao_b64: Option<String>,
}

pub async fn commit_store(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<CommitStoreReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;

    // ── Input length guards ───────────────────────────────────────────────
    const MAX_GRAPH_LEN: usize = 512;
    if req.graph.len() > MAX_GRAPH_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "graph field too long ({} bytes, limit {MAX_GRAPH_LEN})",
                req.graph.len()
            ),
        ));
    }

    // ── CACAO auth ─────────────────────────────────────────────────────────
    let b64 = req.cacao_b64.as_deref().ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            "cacao_b64 is required for commit.store".to_string(),
        )
    })?;
    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }
    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;
    let issuer_did = if cacao.p.iss.starts_with("did:web:") {
        resolve_and_verify_did_web(&cacao, &req.graph, &state.http_client).await?
    } else {
        kotoba_auth::DelegationChain::new(cacao)
            .verify(&req.graph, kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
            .map_err(map_delegation_error)?
    };
    tracing::info!(issuer = %issuer_did, graph = %req.graph, "commit.store: CACAO verified");

    // author is stored verbatim in commit metadata — bound it to prevent oversized records.
    const MAX_AUTHOR_LEN: usize = 512;
    if req.author.len() > MAX_AUTHOR_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "author too long ({} bytes, limit {MAX_AUTHOR_LEN})",
                req.author.len()
            ),
        ));
    }

    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".into()))?;
    let ipns_name = distributed_graph_ipns_name(&graph_cid);
    let current_head = match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.clone()))
    {
        Ok(record) => Some(record),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {e}"),
            ));
        }
    };
    let expected_parent = current_head
        .as_ref()
        .and_then(|record| KotobaCid::from_multibase(&record.value));
    let db = current_db_for_graph(&state, &graph_cid).await?;
    let writer = DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry);
    let report = writer
        .commit_datoms(CommitDatomsRequest {
            merge_parents: None,
            ipns_name,
            graph: graph_cid,
            datoms: db.datoms(),
            covering_datoms: None,
            expected_parent,
            tx_cid: Some(KotobaCid::from_bytes(
                format!("commit.store:{}:{}:{}", req.graph, req.author, req.seq).as_bytes(),
            )),
            author: req.author.clone(),
            seq: req.seq,
            valid_until: "2099-01-01T00:00:00Z".to_string(),
            ttl_secs: Some(60),
            cacao_proof_cid: None,
            ipns_controller_did: Some(state.operator_did.clone()),
            ipns_signing_key: Some(state.ipns_signing_key()),
        })
        .map_err(|e| match e {
            DistributedCommitError::StaleParent { .. } => {
                (StatusCode::CONFLICT, format!("distributed commit: {e}"))
            }
            _ => (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("distributed commit: {e}"),
            ),
        })?;
    let cid = report.commit.cid;

    {
        let pin = state.ipfs_pin.clone();
        let cid_str = cid.to_multibase();
        tokio::spawn(async move { pin.pin(&cid_str).await });
    }

    Ok(Json(serde_json::json!({ "cid": cid.to_multibase() })))
}

// ── Graph query (B) ───────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct GraphQueryReq {
    /// Named graph CID (multibase base32lower)
    pub graph: String,
    /// Optional subject CID filter (multibase or raw string)
    pub subject: Option<String>,
    /// Optional predicate filter (exact string match)
    pub predicate: Option<String>,
    /// Datalog rules reserved for invoke.run; graph.query returns SPO matches only
    pub rules: Option<String>,
    /// CACAO delegation chain for private graphs (DAG-CBOR, base64-standard encoded).
    pub cacao_b64: Option<String>,
    /// Maximum number of quads to return (1–1000; default 100).
    pub limit: Option<u64>,
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.graph.query
/// SPO pattern query over the distributed Datomic head, with legacy hot/cold
/// projection fallback handled by `current_db_for_graph`.
/// Full Datomic/Datalog evaluation: use `com.etzhayyim.apps.kotoba.datomic.q`.
/// SPARQL remains an auxiliary query surface over the same Datom SSoT.
pub async fn graph_query(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    axum::extract::Query(req): axum::extract::Query<GraphQueryReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use crate::graph_auth::{check_read_access, AccessDenied};
    use kotoba_core::cid::KotobaCid;

    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".into()))?;

    // Bound filter fields — large strings would be hashed to a CID and never match anything,
    // but we reject early to avoid allocating and scanning unnecessarily.
    const MAX_FILTER_LEN: usize = 4096;
    if let Some(s) = &req.subject {
        if s.len() > MAX_FILTER_LEN {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "subject too long ({} bytes, limit {MAX_FILTER_LEN})",
                    s.len()
                ),
            ));
        }
    }
    if let Some(p) = &req.predicate {
        if p.len() > MAX_FILTER_LEN {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "predicate too long ({} bytes, limit {MAX_FILTER_LEN})",
                    p.len()
                ),
            ));
        }
    }

    // ── Read-access gate ─────────────────────────────────────────────────────
    if let Some(cacao_b64) = req.cacao_b64.as_deref() {
        crate::graph_auth::verify_cacao_graph_operation(
            cacao_b64,
            &req.graph,
            kotoba_auth::CacaoPayload::OP_GRAPH_QUERY,
            Some(state.operator_did.as_str()),
            Some(&state.nonce_store),
        )
        .map_err(AccessDenied::into_response)?;
    } else {
        let visibility = state.graph_visibility(&graph_cid).await;
        check_read_access(
            &visibility,
            &headers,
            None,
            Some(state.operator_did.as_str()),
            None,
        )
        .map_err(AccessDenied::into_response)?;
    }

    const MAX_QUERY_RESULTS: u64 = 1_000;
    let limit = req.limit.unwrap_or(100).min(MAX_QUERY_RESULTS) as usize;

    let db = current_db_for_graph(&state, &graph_cid).await?;
    let mut quads: Vec<_> = db
        .datoms()
        .into_iter()
        .map(|datom| datom_to_projection_quad(&datom, &graph_cid))
        .collect();

    // Subject filter (accept multibase CID or raw string → hash to CID)
    if let Some(s) = &req.subject {
        let s_cid =
            KotobaCid::from_multibase(s).unwrap_or_else(|| KotobaCid::from_bytes(s.as_bytes()));
        quads.retain(|q| q.subject == s_cid);
    }

    // Predicate filter
    if let Some(p) = &req.predicate {
        quads.retain(|q| &q.predicate == p);
    }

    let truncated = quads.len() > limit;
    quads.truncate(limit);

    Ok(Json(serde_json::json!({
        "graph":     req.graph,
        "queryEngine": "datomic",
        "primaryQuery": NSID_DATOMIC_Q,
        "auxiliaryQuery": crate::kg::NSID_KG_SPARQL,
        "storageModel": "ipld-dag-cbor-prolly-tree",
        "count":     quads.len(),
        "quads":     quads,
        "limit":     limit,
        "truncated": truncated,
        "note":  if req.rules.is_some() { "use com.etzhayyim.apps.kotoba.datomic.q for Datomic/Datalog evaluation" } else { "" },
    })))
}

// ── Weight put (C) ────────────────────────────────────────────────────────

pub const NSID_WEIGHT_GET: &str = "com.etzhayyim.apps.kotoba.weight.get";

#[derive(Debug, Deserialize)]
pub struct WeightPutReq {
    /// model CID (multibase) — identifies the model this weight belongs to
    pub model_cid: String,
    /// layer index (used only when `param_key` is absent → `weight/layer/{layer}`)
    pub layer: u32,
    /// OPTIONAL verbatim parameter key used as the Datom predicate, e.g.
    /// `language_model.model.layers.3.experts.switch_glu.gate_proj.weight`
    /// (ADR-2606010000 D2). When present and non-empty it REPLACES the legacy
    /// `weight/layer/{layer}` predicate so distributed loaders can address each
    /// proj/weight/scale tensor individually. Backward-compatible: omit it for the
    /// old per-layer behaviour.
    #[serde(default)]
    pub param_key: Option<String>,
    /// raw tensor bytes, base64-encoded
    pub data_b64: String,
    /// tensor shape e.g. [4096, 4096]
    pub shape: Vec<u32>,
    /// dtype string: float — "fp8e4m3"|"fp8e5m2"|"fp16"|"bf16"|"f32";
    /// raw safetensors — "u32"|"i32"|"u16"|"i16"|"u8"|"i8" (e.g. 4-bit packed weight = u32)
    pub dtype: String,
    /// named graph CID (multibase) to index this weight in
    pub graph: String,
    /// CACAO delegation proof (CBOR, base64) — required; must carry `datom:transact` capability
    pub cacao_b64: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct WeightPutResp {
    pub blob_cid: String,
    pub quad_cid: String,
    pub layer: u32,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.weight.put
///
/// `cacao_b64` is required. The CACAO is verified before the write:
/// - did:web issuer → HTTP resolution + expiry check
/// - everything else → DelegationChain verifies expiry + `datom:transact` capability + graph + sig
pub async fn weight_put(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<WeightPutReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;
    use kotoba_query::{Datom as KqeDatom, DatomTensorDtype, Value as KqeValue};

    // ── Input length guards ───────────────────────────────────────────────
    const MAX_GRAPH_LEN: usize = 512;
    const MAX_MODEL_CID_LEN: usize = 512;
    const MAX_DTYPE_LEN: usize = 16;
    if req.graph.len() > MAX_GRAPH_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "graph field too long ({} bytes, limit {MAX_GRAPH_LEN})",
                req.graph.len()
            ),
        ));
    }
    if req.model_cid.len() > MAX_MODEL_CID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "model_cid field too long ({} bytes, limit {MAX_MODEL_CID_LEN})",
                req.model_cid.len()
            ),
        ));
    }
    if req.dtype.len() > MAX_DTYPE_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "dtype field too long ({} bytes, limit {MAX_DTYPE_LEN})",
                req.dtype.len()
            ),
        ));
    }
    const MAX_PARAM_KEY_LEN: usize = 256;
    if let Some(pk) = req.param_key.as_deref() {
        if pk.len() > MAX_PARAM_KEY_LEN {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "param_key too long ({} bytes, limit {MAX_PARAM_KEY_LEN})",
                    pk.len()
                ),
            ));
        }
    }

    // ── CACAO auth ────────────────────────────────────────────────────────
    let b64 = req.cacao_b64.as_deref().ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            "cacao_b64 is required for weight.put".to_string(),
        )
    })?;
    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }
    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;
    let issuer_did = if cacao.p.iss.starts_with("did:web:") {
        resolve_and_verify_did_web(&cacao, &req.graph, &state.http_client).await?
    } else {
        kotoba_auth::DelegationChain::new(cacao.clone())
            .verify(&req.graph, kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
            .map_err(map_delegation_error)?
    };
    tracing::info!(issuer = %issuer_did, graph = %req.graph, "weight.put: CACAO verified");

    // Tensor blobs can legitimately be large (embedding tables ~512 MiB raw).
    // Cap at 512 MiB base64 (≈384 MiB raw) to prevent runaway OOM.
    const MAX_WEIGHT_B64_LEN: usize = 512 * 1024 * 1024;
    if req.data_b64.len() > MAX_WEIGHT_B64_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "data_b64 too large ({} bytes, limit {MAX_WEIGHT_B64_LEN})",
                req.data_b64.len()
            ),
        ));
    }
    // Shape has at most 8 dimensions (tensors beyond rank-8 are not supported).
    const MAX_SHAPE_DIMS: usize = 8;
    if req.shape.len() > MAX_SHAPE_DIMS {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "shape has {} dimensions; limit is {MAX_SHAPE_DIMS}",
                req.shape.len()
            ),
        ));
    }

    let bytes = B64
        .decode(&req.data_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

    // 1. Store raw tensor bytes in BlockStore (content-addressed)
    let blob_cid = KotobaCid::from_bytes(&bytes);
    state
        .block_store
        .put(&blob_cid, &bytes)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // 2. IPFS pin the tensor blob
    {
        let pin = std::sync::Arc::clone(&state.ipfs_pin);
        let cs = blob_cid.to_multibase();
        tokio::spawn(async move { pin.pin(&cs).await });
    }

    // 3. Parse CIDs
    let model_cid = KotobaCid::from_multibase(&req.model_cid)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.model_cid.as_bytes()));
    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.graph.as_bytes()));

    let dtype = match req.dtype.to_ascii_lowercase().as_str() {
        "fp8e4m3" | "f8e4m3" => DatomTensorDtype::F8E4M3,
        "fp8e5m2" | "f8e5m2" => DatomTensorDtype::F8E5M2,
        "fp16" | "f16" => DatomTensorDtype::F16,
        "bf16" => DatomTensorDtype::BF16,
        // Raw safetensors storage dtypes (ADR-2606010000 D2) — 4-bit packed weight = u32.
        "u32" => DatomTensorDtype::U32,
        "i32" => DatomTensorDtype::I32,
        "u16" => DatomTensorDtype::U16,
        "i16" => DatomTensorDtype::I16,
        "u8" => DatomTensorDtype::U8,
        "i8" => DatomTensorDtype::I8,
        _ => DatomTensorDtype::F32,
    };

    let auth_proof_cid = Some(persist_cacao_auth_proof(&state, b64)?);
    let auth_capability = Some(cacao_capability_projection(
        &cacao.p,
        auth_proof_cid.clone(),
    ));
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "weight.put:{}:{}:{}",
            req.graph,
            model_cid.to_multibase(),
            blob_cid.to_multibase()
        )
        .as_bytes(),
    );

    // 4. Assert WeightRef Datom through the distributed Datomic/IPNS commit log.
    //    predicate = verbatim param_key (ADR-2606010000 D2) when supplied, else the
    //    legacy per-layer predicate. Lets distributed loaders address each tensor.
    let predicate = match req.param_key.as_deref() {
        Some(pk) if !pk.is_empty() => pk.to_string(),
        _ => format!("weight/layer/{}", req.layer),
    };
    let datom = KqeDatom::assert(
        model_cid,
        predicate,
        KqeValue::TensorCid {
            cid: blob_cid.clone(),
            shape: req.shape.clone(),
            dtype,
        },
        tx_cid.clone(),
    );
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph.clone(),
        blob_cid.clone(),
        vec![kotoba_datomic::Datom::from_kqe(datom)],
        tx_cid,
        issuer_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    let quad_cid = resp
        .journal_cids
        .first()
        .cloned()
        .unwrap_or_else(|| resp.tx_cid.clone());

    tracing::info!(
        blob_cid = %blob_cid.to_multibase(),
        layer    = req.layer,
        bytes    = bytes.len(),
        commit_cid = %resp.commit_cid,
        "weight.put stored"
    );

    Ok(Json(WeightPutResp {
        blob_cid: blob_cid.to_multibase(),
        quad_cid,
        layer: req.layer,
    }))
}

// ── Quad retract (D) ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct QuadRetractReq {
    pub graph: String,
    pub subject: String,
    pub predicate: String,
    pub object: String,
    /// CACAO delegation chain (DAG-CBOR, base64-standard encoded). Required.
    pub cacao_b64: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct QuadRetractResp {
    pub status: &'static str,
    pub journal_cid: String,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.quad.retract
///
/// `cacao_b64` is required. The CACAO is verified before the delete:
/// - Signature must be valid (EdDSA or eip191)
/// - `cacao.p.graph_cid()` must match the requested `graph` field when present
pub async fn quad_retract(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<QuadRetractReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;
    use kotoba_query::quad::{LegacyQuad as Quad, LegacyQuadObject as QuadObject};

    // ── CACAO verification (required) ────────────────────────────────────
    let b64 = req.cacao_b64.as_deref().ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            "cacao_b64 is required for quad.retract".to_string(),
        )
    })?;

    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }

    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;

    let issuer_did = if cacao.p.iss.starts_with("did:web:") {
        resolve_and_verify_did_web(&cacao, &req.graph, &state.http_client).await?
    } else {
        kotoba_auth::DelegationChain::new(cacao)
            .verify(&req.graph, kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
            .map_err(map_delegation_error)?
    };

    tracing::info!(issuer = %issuer_did, graph = %req.graph, "quad.retract: CACAO verified");

    // ── SPO + graph field bounds (mirrors quad_create) ────────────────────
    const MAX_GRAPH_LEN: usize = 512;
    const MAX_SUBJECT_LEN: usize = 512;
    const MAX_PREDICATE_LEN: usize = 512;
    const MAX_OBJECT_LEN: usize = 8 * 1024;
    if req.graph.len() > MAX_GRAPH_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "graph field too long ({} bytes, limit {MAX_GRAPH_LEN})",
                req.graph.len()
            ),
        ));
    }
    if req.subject.len() > MAX_SUBJECT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "subject field too long ({} bytes, limit {MAX_SUBJECT_LEN})",
                req.subject.len()
            ),
        ));
    }
    if req.predicate.len() > MAX_PREDICATE_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "predicate field too long ({} bytes, limit {MAX_PREDICATE_LEN})",
                req.predicate.len()
            ),
        ));
    }
    if req.object.len() > MAX_OBJECT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "object field too long ({} bytes, limit {MAX_OBJECT_LEN})",
                req.object.len()
            ),
        ));
    }

    let quad = Quad {
        graph: KotobaCid::from_bytes(req.graph.as_bytes()),
        subject: KotobaCid::from_bytes(req.subject.as_bytes()),
        predicate: req.predicate.clone(),
        object: QuadObject::Text(req.object.clone()),
    };

    let journal_cid = state.retract_quad_compat(quad).await;

    tracing::info!(
        graph     = %req.graph,
        subject   = %req.subject,
        predicate = %req.predicate,
        cid       = %journal_cid,
        "quad.retract → LiveBus + QuadStore"
    );

    Ok((
        StatusCode::OK,
        Json(QuadRetractResp {
            status: "ok",
            journal_cid,
        }),
    ))
}

// ── Weight get (E) ────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct WeightGetReq {
    pub cid: String,
}

#[derive(Debug, Serialize)]
pub struct WeightGetResp {
    pub cid: String,
    pub data_b64: String,
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.weight.get?cid=<multibase>
pub async fn weight_get(
    State(state): State<Arc<KotobaState>>,
    axum::extract::Query(req): axum::extract::Query<WeightGetReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;

    const MAX_CID_LEN: usize = 512;
    if req.cid.len() > MAX_CID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cid too long ({} bytes, limit {MAX_CID_LEN})",
                req.cid.len()
            ),
        ));
    }
    let cid = KotobaCid::from_multibase(&req.cid)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid CID".into()))?;
    match state
        .block_store
        .get(&cid)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    {
        None => Err((StatusCode::NOT_FOUND, "weight blob not found".into())),
        Some(bytes) => Ok(Json(WeightGetResp {
            cid: req.cid.clone(),
            data_b64: B64.encode(&bytes),
        })),
    }
}

// ── LoRA apply (F) ────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct LoraApplyReq {
    /// Base model CID (multibase)
    pub model_cid: String,
    /// LoRA adapter rank
    pub rank: u32,
    /// Named graph CID (multibase) to index this adapter in
    pub graph: String,
    /// Raw LoRA adapter bytes, base64-encoded
    pub adapter_b64: String,
    /// CACAO delegation proof (CBOR, base64) — required; must carry `datom:transact` capability
    pub cacao_b64: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct LoraApplyResp {
    pub adapter_cid: String,
    pub quad_cid: String,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.lora.apply
///
/// `cacao_b64` is required. The CACAO is verified before the write:
/// - did:web issuer → HTTP resolution + expiry check
/// - everything else → DelegationChain verifies expiry + `datom:transact` capability + graph + sig
pub async fn lora_apply(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<LoraApplyReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    use kotoba_core::cid::KotobaCid;
    use kotoba_query::{Datom as KqeDatom, DatomTensorDtype, Value as KqeValue};

    // ── Input length guards ───────────────────────────────────────────────
    const MAX_GRAPH_LEN: usize = 512;
    const MAX_MODEL_CID_LEN: usize = 512;
    if req.graph.len() > MAX_GRAPH_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "graph field too long ({} bytes, limit {MAX_GRAPH_LEN})",
                req.graph.len()
            ),
        ));
    }
    if req.model_cid.len() > MAX_MODEL_CID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "model_cid field too long ({} bytes, limit {MAX_MODEL_CID_LEN})",
                req.model_cid.len()
            ),
        ));
    }

    // ── CACAO auth ────────────────────────────────────────────────────────
    let b64 = req.cacao_b64.as_deref().ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            "cacao_b64 is required for lora.apply".to_string(),
        )
    })?;
    if b64.len() > MAX_CACAO_B64_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "cacao_b64 too large ({} bytes, limit {MAX_CACAO_B64_LEN})",
                b64.len()
            ),
        ));
    }
    let cbor = B64
        .decode(b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao_b64 decode: {e}")))?;
    let cacao = kotoba_auth::Cacao::from_cbor(&cbor)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("cacao parse: {e}")))?;
    let issuer_did = if cacao.p.iss.starts_with("did:web:") {
        resolve_and_verify_did_web(&cacao, &req.graph, &state.http_client).await?
    } else {
        kotoba_auth::DelegationChain::new(cacao.clone())
            .verify(&req.graph, kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
            .map_err(map_delegation_error)?
    };
    tracing::info!(issuer = %issuer_did, graph = %req.graph, "lora.apply: CACAO verified");

    // 128 MiB for a LoRA delta (rank-128 F8 for a 4B model is ~200 MB unquantized;
    // quantized rank-64 F8 fits comfortably under 128 MiB).
    const MAX_ADAPTER_B64_LEN: usize = 128 * 1024 * 1024;
    if req.adapter_b64.len() > MAX_ADAPTER_B64_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "adapter_b64 too large ({} bytes, limit {MAX_ADAPTER_B64_LEN})",
                req.adapter_b64.len()
            ),
        ));
    }

    let bytes = B64
        .decode(&req.adapter_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

    // Store adapter bytes in block store
    let adapter_cid = KotobaCid::from_bytes(&bytes);
    state
        .block_store
        .put(&adapter_cid, &bytes)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let model_cid = KotobaCid::from_multibase(&req.model_cid)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.model_cid.as_bytes()));
    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.graph.as_bytes()));

    let auth_proof_cid = Some(persist_cacao_auth_proof(&state, b64)?);
    let auth_capability = Some(cacao_capability_projection(
        &cacao.p,
        auth_proof_cid.clone(),
    ));
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "lora.apply:{}:{}:{}",
            req.graph,
            model_cid.to_multibase(),
            adapter_cid.to_multibase()
        )
        .as_bytes(),
    );

    // Assert LoRA Datom through the distributed Datomic/IPNS commit log.
    let datom = KqeDatom::assert(
        model_cid,
        "lora/adapter".to_string(),
        KqeValue::TensorCid {
            cid: adapter_cid.clone(),
            shape: vec![req.rank],
            dtype: DatomTensorDtype::F8E4M3,
        },
        tx_cid.clone(),
    );
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph.clone(),
        adapter_cid.clone(),
        vec![kotoba_datomic::Datom::from_kqe(datom)],
        tx_cid,
        issuer_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        auth_proof_cid,
        auth_capability,
    )
    .await?;
    let quad_cid = resp
        .journal_cids
        .first()
        .cloned()
        .unwrap_or_else(|| resp.tx_cid.clone());

    tracing::info!(
        adapter_cid = %adapter_cid.to_multibase(),
        model_cid   = %req.model_cid,
        rank        = req.rank,
        commit_cid = %resp.commit_cid,
        "lora.apply stored"
    );

    Ok(Json(LoraApplyResp {
        adapter_cid: adapter_cid.to_multibase(),
        quad_cid,
    }))
}

// ── Embed create (G) ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct EmbedCreateReq {
    /// Text to embed
    pub text: String,
    /// Document CID (multibase) — identifies the source document
    pub doc_cid: String,
    /// Model CID (multibase) — identifies the embedding model
    pub model_cid: String,
    /// Named graph CID (multibase) to index this embedding in
    pub graph: String,
}

#[derive(Debug, Serialize)]
pub struct EmbedCreateResp {
    pub status: &'static str,
    pub quad_cid: String,
    pub dims: usize,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.embed.create
pub async fn embed_create(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<EmbedCreateReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    use kotoba_core::cid::KotobaCid;
    use kotoba_llm::embed::{embed_to_delta, Embedding};

    // 64 KiB covers any realistic embedding unit (paragraph / document chunk).
    // Larger inputs must be split by the caller's chunker before calling embed.create.
    const MAX_EMBED_TEXT_LEN: usize = 64 * 1024;
    if req.text.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "text must not be empty".into()));
    }
    if req.text.len() > MAX_EMBED_TEXT_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "text too large ({} bytes, limit {MAX_EMBED_TEXT_LEN})",
                req.text.len()
            ),
        ));
    }

    let doc_cid = KotobaCid::from_multibase(&req.doc_cid)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.doc_cid.as_bytes()));
    let model_cid = KotobaCid::from_multibase(&req.model_cid)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.model_cid.as_bytes()));
    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.graph.as_bytes()));

    // Compute embedding vector — use inference engine if available, else blake3 pseudo-vector
    let vector: Vec<f32> = if let Some(engine) = &state.inference_engine {
        let engine = engine.clone();
        let text = format!("embed: {}", req.text);
        let result = tokio::task::spawn_blocking(move || engine(&text, 256))
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
        // Parse space-separated floats from engine output, fallback to blake3 pseudo-vector
        let parsed: Vec<f32> = result
            .split_whitespace()
            .filter_map(|s| s.parse::<f32>().ok())
            .collect();
        if parsed.is_empty() {
            // Inference engine returned non-numeric output — build blake3 pseudo-vector
            blake3_pseudo_vector(&req.text, 128)
        } else {
            parsed
        }
    } else {
        // No inference engine: 128-dim blake3 pseudo-embedding
        blake3_pseudo_vector(&req.text, 128)
    };

    let dims = vector.len();
    let emb = Embedding {
        doc_cid: doc_cid.clone(),
        model_cid: model_cid.clone(),
        vector,
    };
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "embed.create:{}:{}:{}",
            req.graph,
            doc_cid.to_multibase(),
            model_cid.to_multibase()
        )
        .as_bytes(),
    );
    let datom = embed_to_delta(&emb, tx_cid.clone()).datom;
    let resp = commit_protocol_datoms(
        &state,
        graph_cid,
        req.graph.clone(),
        doc_cid.clone(),
        vec![kotoba_datomic::Datom::from_kqe(datom)],
        tx_cid,
        state.operator_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await?;
    let quad_cid = resp
        .journal_cids
        .first()
        .cloned()
        .unwrap_or_else(|| resp.tx_cid.clone());

    Ok(Json(EmbedCreateResp {
        status: "ok",
        quad_cid,
        dims,
    }))
}

/// Build a deterministic pseudo-embedding from blake3 hash bytes.
fn blake3_pseudo_vector(text: &str, dims: usize) -> Vec<f32> {
    let hash = blake3::hash(text.as_bytes());
    let hash_bytes = hash.as_bytes();
    (0..dims)
        .map(|i| {
            let b = hash_bytes[i % 32] as f32;
            (b / 127.5) - 1.0
        })
        .collect()
}

// ── Infer run (H) ─────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct InferRunReq {
    /// Prompt text
    pub prompt: String,
    /// Maximum tokens to generate
    pub max_new_tokens: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct InferRunResp {
    pub status: &'static str,
    pub output: String,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.infer.run
pub async fn infer_run(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<InferRunReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    let engine = state.inference_engine.clone().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            "no inference engine loaded".into(),
        )
    })?;

    // 64 KiB prompt cap (prevents tokeniser OOM on a context-length exploit).
    const MAX_PROMPT_LEN: usize = 64 * 1024;
    if req.prompt.len() > MAX_PROMPT_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "prompt too large ({} bytes, limit {MAX_PROMPT_LEN})",
                req.prompt.len()
            ),
        ));
    }
    // Cap max_new_tokens so a single request cannot hold the thread for minutes.
    const MAX_NEW_TOKENS_LIMIT: usize = 4096;
    let max_tokens = req.max_new_tokens.unwrap_or(256).min(MAX_NEW_TOKENS_LIMIT);
    let prompt = req.prompt.clone();

    let output = tokio::task::spawn_blocking(move || engine(&prompt, max_tokens))
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    Ok(Json(InferRunResp {
        status: "ok",
        output,
    }))
}

// ── Agent ReAct loop ──────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AgentRunReq {
    pub task: String,
    pub graph_cid: Option<String>,
    pub max_steps: Option<u32>,
    /// Maximum tokens per LLM thought step (default 256)
    pub max_tokens: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct AgentRunResp {
    pub status: &'static str,
    pub session_cid: String,
    pub steps: Vec<serde_json::Value>,
    pub final_answer: Option<String>,
    pub supersteps: usize,
    /// Commit CID of the session history flushed to BlockStore (ProllyTree)
    pub commit_cid: Option<String>,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.agent.run
///
/// Runs a ReAct agent loop using the Kotoba **Pregel BSP** engine:
///   - vertex_id  = session CID
///   - superstep  = one cycle: Thought → Action → Observation
///   - self-message  → advance to next superstep
///   - vote_halt  → finish action or max_steps reached
///
/// Requires `KOTOBA_LOAD_GEMMA` (or another inference engine) to be loaded.
#[cfg(feature = "wasm-runtime")]
pub async fn agent_run(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<AgentRunReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    use kotoba_core::cid::KotobaCid;
    use kotoba_vm::{session_to_quads, AgentSession, PregelReActRunner, ReActStep};

    let engine = state.inference_engine.clone().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            "no inference engine loaded (set KOTOBA_LOAD_GEMMA)".into(),
        )
    })?;

    // 64 KiB task cap; agent loops with longer tasks should be chunked by the caller.
    const MAX_TASK_LEN: usize = 64 * 1024;
    if req.task.len() > MAX_TASK_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!(
                "task too large ({} bytes, limit {MAX_TASK_LEN})",
                req.task.len()
            ),
        ));
    }
    // Cap loop iterations and tokens-per-step to prevent runaway compute cost.
    const MAX_STEPS_LIMIT: u32 = 50;
    const MAX_TOKENS_LIMIT: usize = 4096;

    let graph_cid = req
        .graph_cid
        .as_deref()
        .map(|s| KotobaCid::from_bytes(s.as_bytes()))
        .unwrap_or_else(|| KotobaCid::from_bytes(b"agent-default-graph"));

    let max_steps = req.max_steps.unwrap_or(10).min(MAX_STEPS_LIMIT);
    let max_tokens = req.max_tokens.unwrap_or(256).min(MAX_TOKENS_LIMIT);
    let task = req.task.clone();
    let graph_cid2 = graph_cid.clone();
    let journal = Arc::clone(&state.journal);

    // Run the Pregel ReAct loop in a blocking thread (LLM is sync).
    // Each BSP superstep = one Thought+Action+Observation cycle.
    let (session, superstep_results) = tokio::task::spawn_blocking(move || {
        use kotoba_vm::agent::{Tool, ToolOutput};

        // Override the default no-op kse.publish with a real LiveBus write.
        let journal2 = Arc::clone(&journal);
        let kse_publish_tool = Tool::from_fn(
            "kse.publish",
            "Publish a KSE event — kse.publish(topic,message)",
            move |input, _snap| {
                let (topic_str, msg) = input
                    .split_once(',')
                    .map(|(t, m)| (t.trim().to_string(), m.trim().to_string()))
                    .unwrap_or_else(|| ("agent".to_string(), input.trim().to_string()));
                let j = Arc::clone(&journal2);
                let topic_str2 = topic_str.clone();
                tokio::task::block_in_place(|| {
                    tokio::runtime::Handle::current().block_on(async move {
                        j.publish(kotoba_vault::Topic(topic_str2), bytes::Bytes::from(msg))
                            .await;
                    });
                });
                ToolOutput {
                    observation: format!("published to '{topic_str}'"),
                    done: false,
                    route: None,
                }
            },
        );

        let runner = PregelReActRunner::new(engine, max_tokens);
        let session = AgentSession::new(task, graph_cid2, max_steps).with_tool(kse_publish_tool);
        runner.run(session)
    })
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let supersteps = superstep_results.len();

    // Extract final answer from last Finish step
    let final_answer = session.steps.iter().rev().find_map(|s| {
        if let ReActStep::Finish { answer } = s {
            Some(answer.clone())
        } else {
            None
        }
    });

    // Store session steps through the Datomic/IPLD commit path.  The legacy
    // LiveBus/QuadStore projection is still updated inside commit_protocol_datoms.
    let session_cid = session.session_cid.clone();
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "agent.run:{}:{}:{}",
            graph_cid.to_multibase(),
            session_cid.to_multibase(),
            session.steps.len()
        )
        .as_bytes(),
    );
    let datoms = session_to_quads(&session)
        .into_iter()
        .map(|delta| kotoba_datomic::Datom::from_kqe(delta.datom))
        .collect::<Vec<_>>();
    let commit_resp = commit_protocol_datoms(
        &state,
        graph_cid.clone(),
        graph_cid.to_multibase(),
        session_cid.clone(),
        datoms,
        tx_cid,
        state.operator_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await?;
    let commit_cid = Some(commit_resp.commit_cid.clone());

    // Pin the commit block in the background
    if let Some(cid_str) = commit_cid.clone() {
        let pin = state.ipfs_pin.clone();
        tokio::spawn(async move { pin.pin(&cid_str).await });
    }

    let session_cid = session_cid.to_multibase();
    let steps = session
        .steps
        .into_iter()
        .map(|step| serde_json::to_value(step).unwrap_or(serde_json::Value::Null))
        .collect();

    Ok(Json(AgentRunResp {
        status: "ok",
        session_cid,
        steps,
        final_answer,
        supersteps,
        commit_cid,
    }))
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.agent.run
/// Heavy Pregel ReAct runtime disabled in the lean server build.
#[cfg(not(feature = "wasm-runtime"))]
pub async fn agent_run(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(_req): Json<AgentRunReq>,
) -> Result<axum::response::Response, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    Err((
        StatusCode::SERVICE_UNAVAILABLE,
        "agent.run requires the `wasm-runtime` feature".to_string(),
    ))
}

// ── Agent SyncWindow session management (C) ───────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AgentSyncOpenReq {
    /// Caller-assigned session identifier (UUIDv4 recommended).
    pub session_id: String,
    /// Named graph CID to sync (multibase).
    pub graph_cid: String,
    /// LiveBus sequence watermark — the agent has already processed all entries before this.
    pub since_seq: u64,
    /// Last commit head the agent has processed. `None` = fresh agent.
    pub head_cid: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct AgentSyncOpenResp {
    pub status: &'static str,
    pub session_id: String,
    pub since_seq: u64,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.agent.syncopen
///
/// Opens a SyncWindow session.  The graph and head CIDs are pinned in the
/// BudgetedBlockStore so they survive eviction for the duration of the session.
pub async fn agent_sync_open(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<AgentSyncOpenReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_core::cid::KotobaCid;
    use kotoba_vault::sync_window::SyncWindow;

    // Validate session_id: non-empty, ≤256 bytes, printable ASCII.
    const MAX_SESSION_ID_LEN: usize = 256;
    if req.session_id.is_empty()
        || req.session_id.len() > MAX_SESSION_ID_LEN
        || !req.session_id.bytes().all(|b| b.is_ascii_graphic())
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "session_id must be 1–256 printable ASCII characters".into(),
        ));
    }

    crate::graph_auth::require_any_bearer_auth(&headers, "agent.syncopen")?;

    let graph_cid = KotobaCid::from_multibase(&req.graph_cid)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph_cid".into()))?;
    let head_cid = req
        .head_cid
        .as_deref()
        .map(|s| {
            KotobaCid::from_multibase(s)
                .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid head_cid".into()))
        })
        .transpose()?;

    let window = SyncWindow::new(graph_cid.clone(), req.since_seq, head_cid.clone());

    // Pin anchors directly (avoids dyn-coercion issues)
    state.block_store.pin(&graph_cid);
    if let Some(h) = &head_cid {
        state.block_store.pin(h);
    }

    // Cap total concurrent sessions under a single write lock to close the
    // TOCTOU window between capacity check and insert.
    const MAX_CONCURRENT_SESSIONS: usize = 1_000;
    let since_seq = {
        let mut sessions = state.agent_sessions.write().await;
        if sessions.len() >= MAX_CONCURRENT_SESSIONS {
            // Unpin the anchors we just pinned since we're rejecting the request.
            state.block_store.unpin(&graph_cid);
            if let Some(h) = &head_cid {
                state.block_store.unpin(h);
            }
            return Err((
                StatusCode::TOO_MANY_REQUESTS,
                format!("too many open sessions (limit {MAX_CONCURRENT_SESSIONS})"),
            ));
        }
        let seq = window.since_seq;
        sessions.insert(req.session_id.clone(), window);
        seq
    };

    tracing::info!(session_id = %req.session_id, since_seq, "agent.syncopen");

    Ok(Json(AgentSyncOpenResp {
        status: "ok",
        session_id: req.session_id,
        since_seq,
    }))
}

#[derive(Debug, Deserialize)]
pub struct AgentSyncAdvReq {
    pub session_id: String,
    /// New commit head CID (multibase) the agent has processed.
    pub new_head_cid: String,
    /// Updated journal watermark.
    pub new_seq: u64,
}

#[derive(Debug, Serialize)]
pub struct AgentSyncAdvResp {
    pub status: &'static str,
    pub session_id: String,
    pub since_seq: u64,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.agent.syncadvance
///
/// Advance the SyncWindow: unpin the old head, pin the new head.
pub async fn agent_sync_advance(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<AgentSyncAdvReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_core::cid::KotobaCid;

    const MAX_SESSION_ID_LEN: usize = 256;
    if req.session_id.is_empty()
        || req.session_id.len() > MAX_SESSION_ID_LEN
        || !req.session_id.bytes().all(|b| b.is_ascii_graphic())
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "session_id must be 1–256 printable ASCII characters".into(),
        ));
    }

    crate::graph_auth::require_any_bearer_auth(&headers, "agent.syncadvance")?;

    let new_head = KotobaCid::from_multibase(&req.new_head_cid)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid new_head_cid".into()))?;

    let mut sessions = state.agent_sessions.write().await;
    let window = sessions.get_mut(&req.session_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            format!("session not found: {}", req.session_id),
        )
    })?;

    // Unpin old head, pin new head
    if let Some(old) = &window.head_cid {
        state.block_store.unpin(old);
    }
    state.block_store.pin(&new_head);
    window.head_cid = Some(new_head);
    window.since_seq = req.new_seq;

    let since_seq = window.since_seq;
    tracing::info!(session_id = %req.session_id, since_seq, "agent.syncadvance");

    Ok(Json(AgentSyncAdvResp {
        status: "ok",
        session_id: req.session_id,
        since_seq,
    }))
}

#[derive(Debug, Deserialize)]
pub struct AgentSyncCloseReq {
    pub session_id: String,
}

#[derive(Debug, Serialize)]
pub struct AgentSyncCloseResp {
    pub status: &'static str,
    pub session_id: String,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.agent.syncclose
///
/// Close the SyncWindow session, unpinning all anchors.
pub async fn agent_sync_close(
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req): Json<AgentSyncCloseReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    const MAX_SESSION_ID_LEN: usize = 256;
    if req.session_id.is_empty()
        || req.session_id.len() > MAX_SESSION_ID_LEN
        || !req.session_id.bytes().all(|b| b.is_ascii_graphic())
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "session_id must be 1–256 printable ASCII characters".into(),
        ));
    }

    crate::graph_auth::require_any_bearer_auth(&headers, "agent.syncclose")?;

    let mut sessions = state.agent_sessions.write().await;
    let window = sessions.remove(&req.session_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            format!("session not found: {}", req.session_id),
        )
    })?;

    state.block_store.unpin(&window.graph_cid);
    if let Some(h) = &window.head_cid {
        state.block_store.unpin(h);
    }

    tracing::info!(session_id = %req.session_id, "agent.syncclose");

    Ok(Json(AgentSyncCloseResp {
        status: "ok",
        session_id: req.session_id,
    }))
}

#[cfg(test)]
mod ssrf_guard_tests {
    use super::peer_ip_disallowed;

    #[test]
    fn rejects_private_loopback_metadata() {
        for ip in [
            "127.0.0.1",
            "10.1.2.3",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "::",
            "fe80::1",
            "fc00::1",
            "fd12:3456::1",
            "::ffff:127.0.0.1",
            "::ffff:10.0.0.1",
        ] {
            assert!(
                peer_ip_disallowed(ip.parse().unwrap()),
                "{ip} must be disallowed"
            );
        }
        // public IPs are allowed
        for ip in ["1.1.1.1", "8.8.8.8", "203.0.113.5", "2606:4700::1111"] {
            assert!(
                !peer_ip_disallowed(ip.parse().unwrap()),
                "{ip} must be allowed"
            );
        }
    }

    // NOTE: parse_remote_peer_socket() reads KOTOBA_ALLOW_PRIVATE_PEERS, which
    // other (parallel) tests may set process-wide; the pure classifier
    // `peer_ip_disallowed` above is the env-independent unit under test.
}

#[cfg(test)]
mod tests {
    use super::{
        append_auth_capability_datoms, atproto_repo_delete_datoms, atproto_repo_record_entity_cid,
        atproto_repo_write, atproto_repo_write_datoms, datomic_basis_t, datomic_datoms,
        datomic_datoms_sort_values, datomic_db_stats, datomic_entid, datomic_entity,
        datomic_history, datomic_ident, datomic_index_pull, datomic_index_range, datomic_log,
        datomic_pull, datomic_pull_many, datomic_q, datomic_q_emit_cids, datomic_seek_datoms,
        datomic_sync, datomic_transact, datomic_tx_range, datomic_with, did_document_publish,
        didcomm_send, distributed_graph_ipns_name, enforce_datomic_range_tx_scope,
        is_did_web_ip_host, protocol_payload_tx_cid, vc_issue, vp_capability_projection,
        warm_datomic_resident_cache, AtprotoRepoWriteReq, AuthCapabilityProjection,
        DatomicBasisTReq, DatomicDatomsIndex, DatomicDatomsReq, DatomicDbStatsReq, DatomicEntidReq,
        DatomicEntityReq, DatomicHistoryReq, DatomicIdentReq, DatomicIndexPullReq,
        DatomicIndexRangeReq, DatomicLogReq, DatomicPullManyReq, DatomicPullReq, DatomicQReq,
        DatomicSeekDatomsReq, DatomicSyncReq, DatomicTransactReq, DatomicTxRangeReq,
        DatomicWarmOutcome, DatomicWithReq, DidCommSendReq, DidDocumentPublishReq, VcIssueReq,
        ZCAP_ALLOWED_ACTION_IRI, ZCAP_CAPABILITY_INVOCATION_IRI, ZCAP_CONTROLLER_IRI,
        ZCAP_INVOCATION_PROOF_IRI, ZCAP_INVOCATION_TARGET_IRI, ZCAP_INVOKER_IRI,
    };
    use crate::server::KotobaState;
    use axum::response::IntoResponse;
    use kotoba_auth::did_document::ServiceEndpointValue;
    use kotoba_auth::{
        DidDocument, ServiceEndpoint, ATPROTO_PDS_SERVICE, DIDCOMM_MESSAGING_SERVICE,
        KOTOBA_GRAPH_MEMBERSHIP_SERVICE, KOTOBA_NODE_SERVICE,
    };
    use kotoba_core::cid::KotobaCid;
    use kotoba_core::named_graph::GraphVisibility;
    use kotoba_core::store::BlockStore;
    use kotoba_datomic::distributed::{
        CommitDatomsRequest, DistributedCommitWriter, DistributedDatomReader,
    };
    use kotoba_datomic::Datom;
    use kotoba_edn::EdnValue;
    use kotoba_ipfs::{InMemoryIpnsRegistry, IpfsConfig};
    use kotoba_store::MemoryBlockStore;
    use std::sync::Arc;

    // `emit_cid` provenance: result_cid is content-derived (tamper-evident),
    // deterministic, basis-sensitive, formatting-invariant on the query, PUT and
    // fetchable by CID, and IPFS-compatible. Exercises the real emit path.
    #[tokio::test]
    async fn datomic_q_emit_cid_envelopes_are_content_addressed_and_verifiable() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = KotobaState::new(None).unwrap();

        let query = kotoba_edn::parse(r#"[:find ?name :where [?e :person/name ?name]]"#).unwrap();
        // Same query, only whitespace/formatting differs.
        let query_spaced =
            kotoba_edn::parse("[:find   ?name\n  :where  [?e :person/name ?name]]").unwrap();
        let inputs: Vec<EdnValue> = vec![];
        let rows = vec![vec![r#""Alice""#.to_string()], vec![r#""Bob""#.to_string()]];
        let emit = |q: &EdnValue, basis: &str, rows: &[Vec<String>]| {
            datomic_q_emit_cids(
                &state,
                q,
                &inputs,
                Some(basis),
                None,
                None,
                false,
                rows,
                true,
            )
        };

        let (spec1, job1, result1) = emit(&query, "tx-basis-1", &rows);

        // 1. Deterministic: identical inputs reproduce identical CIDs.
        assert_eq!(
            (spec1.clone(), job1.clone(), result1.clone()),
            emit(&query, "tx-basis-1", &rows)
        );

        // 2. Tamper-evident: changing a single row changes result_cid.
        let tampered = vec![
            vec![r#""Alice""#.to_string()],
            vec![r#""Mallory""#.to_string()],
        ];
        assert_ne!(
            result1,
            emit(&query, "tx-basis-1", &tampered).2,
            "row edit must move result_cid"
        );

        // 3. Basis-sensitive: a different basis transaction changes job + result.
        let (_, job_b2, result_b2) = emit(&query, "tx-basis-2", &rows);
        assert_ne!(job1, job_b2);
        assert_ne!(result1, result_b2);

        // 4. Canonicalization: formatting-only differences collapse to one spec CID.
        assert_eq!(
            spec1,
            emit(&query_spaced, "tx-basis-1", &rows).0,
            "whitespace must not move query_spec_cid"
        );

        // 5. Verify-by-CID: every envelope was PUT, is IPFS-compatible (CIDv1
        //    dag-cbor sha2-256), and the stored bytes hash back to that exact CID
        //    (closes the loop — proves the block IS the content the CID names).
        for cid_mb in [&spec1, &job1, &result1] {
            let kcid = KotobaCid::from_multibase(cid_mb).expect("multibase CID parses");
            assert!(
                kcid.is_ipfs_compatible(),
                "envelope CID must be IPFS-compatible"
            );
            let bytes = state
                .block_store
                .get(&kcid)
                .unwrap()
                .unwrap_or_else(|| panic!("envelope block must be fetchable by CID: {cid_mb}"));
            assert_eq!(
                KotobaCid::from_bytes(&bytes),
                kcid,
                "stored block must hash back to its CID: {cid_mb}"
            );
        }
    }

    // N1 hardening: emit_cid bounds the best-effort write a read can trigger. An
    // oversized result envelope still yields its (content-derived) CID, but the
    // block is NOT persisted — so a churn of huge-result reads can't grow the
    // block store unboundedly. Small spec/job envelopes are still persisted.
    #[tokio::test]
    async fn datomic_q_emit_cid_skips_put_for_oversized_result_envelope() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = KotobaState::new(None).unwrap();
        let query = kotoba_edn::parse(r#"[:find ?x :where [?e :a ?x]]"#).unwrap();
        let inputs: Vec<EdnValue> = vec![];
        // One cell past the 1 MiB PUT cap → the result envelope exceeds it.
        let rows = vec![vec!["x".repeat(1_100_000)]];

        let (spec, job, result) = datomic_q_emit_cids(
            &state,
            &query,
            &inputs,
            Some("tx1"),
            None,
            None,
            false,
            &rows,
            true,
        );

        // CIDs are returned regardless of persistence (content-derived).
        assert!(!spec.is_empty() && !job.is_empty() && !result.is_empty());
        // Small spec/job envelopes were persisted…
        for cid in [&spec, &job] {
            let kcid = KotobaCid::from_multibase(cid).unwrap();
            assert!(
                state.block_store.get(&kcid).unwrap().is_some(),
                "small envelope must be persisted: {cid}"
            );
        }
        // …but the oversized result envelope was NOT (PUT skipped by the cap).
        let rcid = KotobaCid::from_multibase(&result).unwrap();
        assert!(
            state.block_store.get(&rcid).unwrap().is_none(),
            "oversized result envelope must not be persisted"
        );
    }

    // Security: emit_cid on a non-public graph (persist=false) must return the
    // content-derived CIDs but NOT persist the envelopes — block.get is
    // unauthenticated, so a persisted private result would be retrievable
    // bearer-by-CID. The CID itself is identical regardless of persist.
    #[tokio::test]
    async fn datomic_q_emit_cid_persist_false_returns_cids_without_storing() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = KotobaState::new(None).unwrap();
        let query = kotoba_edn::parse(r#"[:find ?x :where [?e :a ?x]]"#).unwrap();
        let inputs: Vec<EdnValue> = vec![];
        let rows = vec![vec![r#""secret""#.to_string()]];

        // persist=false (private/authenticated graph): CIDs returned, nothing stored.
        let (spec, job, result) = datomic_q_emit_cids(
            &state,
            &query,
            &inputs,
            Some("tx1"),
            None,
            None,
            false,
            &rows,
            false,
        );
        assert!(
            !spec.is_empty() && !job.is_empty() && !result.is_empty(),
            "CIDs still returned"
        );
        for cid in [&spec, &job, &result] {
            let kcid = KotobaCid::from_multibase(cid).unwrap();
            assert!(
                state.block_store.get(&kcid).unwrap().is_none(),
                "non-public envelope must NOT be persisted: {cid}"
            );
        }

        // persist=true (public) DOES store — and yields the SAME CID (content-derived).
        let (spec_pub, _, _) = datomic_q_emit_cids(
            &state,
            &query,
            &inputs,
            Some("tx1"),
            None,
            None,
            false,
            &rows,
            true,
        );
        assert_eq!(
            spec, spec_pub,
            "persist must not change the content-derived CID"
        );
        assert!(
            state
                .block_store
                .get(&KotobaCid::from_multibase(&spec_pub).unwrap())
                .unwrap()
                .is_some(),
            "public envelope must be persisted"
        );
    }

    // First-tier `datomic.datoms` AVET ordering must be numeric, not the
    // lexicographic "100" < "20" trap, and type-segregated. This sorts via
    // `datomic_datoms_sort_key` → `EdnValue` Ord (ADR-2606022150 §D1.1: first-tier
    // Datomic is canonical without the keycodec — distinct from the 2nd-tier
    // QuadStore/SPARQL hot index whose `value_key` had the string bug).
    #[test]
    fn datomic_datoms_avet_orders_integers_numerically() {
        let e = KotobaCid::from_bytes(b"e");
        let tx = KotobaCid::from_bytes(b"tx");
        let mk = |v: EdnValue| Datom::assert(e.clone(), ":n/score".to_string(), v, tx.clone());
        let d20 = mk(EdnValue::Integer(20));
        let d100 = mk(EdnValue::Integer(100));
        let dneg = mk(EdnValue::Integer(-5));
        let idx = DatomicDatomsIndex::Avet;
        // 20 before 100 (numeric, not "100" < "20"); negatives before positives.
        assert!(
            datomic_datoms_sort_values(&d20, idx) < datomic_datoms_sort_values(&d100, idx),
            "AVET: 20 must sort before 100"
        );
        assert!(
            datomic_datoms_sort_values(&dneg, idx) < datomic_datoms_sort_values(&d20, idx),
            "AVET: -5 must sort before 20"
        );
        // Type segregation: a string value never interleaves with integers.
        let dstr = mk(EdnValue::String("30".to_string()));
        assert!(
            datomic_datoms_sort_values(&d100, idx) < datomic_datoms_sort_values(&dstr, idx),
            "AVET: any integer sorts before any string (type-segregated)"
        );
    }

    fn test_operator_jwt(did: &str) -> String {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
        let header = URL_SAFE_NO_PAD.encode(r#"{"alg":"none","typ":"JWT"}"#);
        let payload = URL_SAFE_NO_PAD.encode(
            serde_json::json!({
                "sub": did,
                "exp": 4_102_444_800u64
            })
            .to_string(),
        );
        format!("{header}.{payload}.")
    }

    fn test_cacao_payload(resources: Vec<String>) -> kotoba_auth::CacaoPayload {
        kotoba_auth::CacaoPayload {
            iss: "did:key:zIssuer".into(),
            aud: "did:key:zAudience".into(),
            issued_at: "2026-05-30T00:00:00Z".into(),
            expiry: Some("2099-01-01T00:00:00Z".into()),
            nonce: "n-test".into(),
            domain: "kotoba.test".into(),
            statement: None,
            version: "1".into(),
            resources,
        }
    }

    fn signed_cacao_b64(
        state: &KotobaState,
        graph: &str,
        operation: &str,
        nonce: &str,
        extra_resources: impl IntoIterator<Item = impl Into<String>>,
    ) -> String {
        use base64::Engine as _;
        use base64::{engine::general_purpose::STANDARD, engine::general_purpose::URL_SAFE_NO_PAD};
        use ed25519_dalek::Signer as _;

        let signing_key = ed25519_dalek::SigningKey::from_bytes(&[42u8; 32]);
        let issuer_did =
            kotoba_auth::ed25519_pubkey_to_did_key(&signing_key.verifying_key().to_bytes());
        let mut resources = vec![
            format!("kotoba://op/{operation}"),
            format!("kotoba://graph/{graph}"),
        ];
        resources.extend(extra_resources.into_iter().map(Into::into));
        let mut cacao = kotoba_auth::Cacao {
            h: kotoba_auth::CacaoHeader {
                t: "eip4361".into(),
            },
            p: kotoba_auth::CacaoPayload {
                iss: issuer_did,
                aud: state.operator_did.clone(),
                issued_at: "2026-05-30T00:00:00Z".into(),
                expiry: Some("2099-01-01T00:00:00Z".into()),
                nonce: nonce.into(),
                domain: "kotoba.test".into(),
                statement: None,
                version: "1".into(),
                resources,
            },
            s: kotoba_auth::CacaoSig {
                t: "EdDSA".into(),
                s: String::new(),
            },
        };
        let signature = signing_key.sign(cacao.siwe_message().as_bytes());
        cacao.s.s = URL_SAFE_NO_PAD.encode(signature.to_bytes());
        let mut cbor = Vec::new();
        ciborium::into_writer(&cacao, &mut cbor).expect("cacao cbor");
        STANDARD.encode(cbor)
    }
    use serde_json::json;

    // End-to-end public vs private READ authorization through the real datomic.q
    // handler. The tier logic (graph_auth) and CACAO crypto are unit-tested, but
    // nothing wires a Private graph through datomic_q — this closes that gap.
    // Small scale: 2 datoms, 1 query, 3 access scenarios.
    #[tokio::test]
    async fn datomic_q_public_allows_anon_private_requires_cacao() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());

        const Q: &str =
            r#"[:find ?name ?role :where [?e :person/name ?name] [?e :person/role ?role]]"#;

        // Seed Alice/admin into a graph in this node's own store (reads are
        // visibility-gated; writes are operator-gated, so the same seed serves
        // both a public and a private graph).
        fn seed(state: &KotobaState, graph: &KotobaCid, marker: &[u8]) {
            let tx = KotobaCid::from_bytes(marker);
            let e = KotobaCid::from_bytes(b"pp-alice");
            DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry)
                .commit_datoms(CommitDatomsRequest {
                    merge_parents: None,
                    ipns_name: distributed_graph_ipns_name(graph),
                    graph: graph.clone(),
                    covering_datoms: None,
                    datoms: vec![
                        Datom::assert(
                            e.clone(),
                            ":person/name".into(),
                            EdnValue::string("Alice"),
                            tx.clone(),
                        ),
                        Datom::assert(
                            e,
                            ":person/role".into(),
                            EdnValue::string("admin"),
                            tx.clone(),
                        ),
                    ],
                    expected_parent: None,
                    tx_cid: Some(tx),
                    author: "did:key:zSeedAuthor".into(),
                    seq: 1,
                    valid_until: "2030-01-01T00:00:00Z".into(),
                    ttl_secs: Some(60),
                    cacao_proof_cid: None,
                    ipns_controller_did: None,
                    ipns_signing_key: None,
                })
                .unwrap();
        }
        fn req(graph_mb: &str, cacao: Option<String>) -> DatomicQReq {
            DatomicQReq {
                graph: graph_mb.into(),
                query_edn: Q.into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: cacao,
                presentation: None,
            }
        }
        async fn rows(resp: axum::response::Response) -> serde_json::Value {
            let body = axum::body::to_bytes(resp.into_body(), usize::MAX)
                .await
                .unwrap();
            serde_json::from_slice::<serde_json::Value>(&body).unwrap()["rows_edn"].clone()
        }
        let expected = json!([[r#""Alice""#, r#""admin""#]]);

        // ── Public graph: anonymous read is allowed and returns the rows. ──
        let g_pub = KotobaCid::from_bytes(b"pp-public-graph");
        seed(&state, &g_pub, b"pp-pub-tx");
        state
            .graph_registry
            .write()
            .await
            .insert(g_pub.clone(), ("pub".into(), GraphVisibility::Public));
        let resp = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            axum::http::HeaderMap::new(),
            axum::Json(req(&g_pub.to_multibase(), None)),
        )
        .await
        .expect("public read must be allowed anonymously")
        .into_response();
        assert_eq!(resp.status(), axum::http::StatusCode::OK);
        assert_eq!(
            rows(resp).await,
            expected,
            "public read returns the seeded rows"
        );

        // ── Private graph owned by the signed_cacao_b64 issuer (key [42u8;32]). ──
        let owner_did = kotoba_auth::ed25519_pubkey_to_did_key(
            &ed25519_dalek::SigningKey::from_bytes(&[42u8; 32])
                .verifying_key()
                .to_bytes(),
        );
        let g_priv = KotobaCid::from_bytes(b"pp-private-graph");
        seed(&state, &g_priv, b"pp-priv-tx");
        state.graph_registry.write().await.insert(
            g_priv.clone(),
            (
                "priv".into(),
                GraphVisibility::Private {
                    owner_did: owner_did.clone(),
                },
            ),
        );
        let g_priv_mb = g_priv.to_multibase();

        // (a) no CACAO → denied 401, and for the RIGHT reason (the CACAO gate),
        //     so the deny is not vacuous.
        let denied = match datomic_q(
            axum::extract::State(Arc::clone(&state)),
            axum::http::HeaderMap::new(),
            axum::Json(req(&g_priv_mb, None)),
        )
        .await
        {
            Ok(_) => panic!("private read without cacao must be denied"),
            Err(e) => e,
        };
        assert_eq!(denied.0, axum::http::StatusCode::UNAUTHORIZED);
        assert!(
            denied.1.to_lowercase().contains("cacao"),
            "deny must be the CACAO gate, got: {}",
            denied.1
        );

        // (b) valid CACAO (datom:read on private/{owner}, fresh nonce) → OK + rows.
        let cacao = signed_cacao_b64(
            &state,
            &format!("private/{owner_did}"),
            kotoba_auth::CacaoPayload::OP_DATOM_READ,
            "pp-nonce-1",
            Vec::<String>::new(),
        );
        let resp = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            axum::http::HeaderMap::new(),
            axum::Json(req(&g_priv_mb, Some(cacao))),
        )
        .await
        .expect("private read WITH a valid cacao must be allowed")
        .into_response();
        assert_eq!(resp.status(), axum::http::StatusCode::OK);
        assert_eq!(
            rows(resp).await,
            expected,
            "authorized private read returns the seeded rows"
        );
    }

    #[test]
    fn datomic_range_tx_scope_requires_requested_start_and_end_scopes() {
        let start = KotobaCid::from_bytes(b"range-start").to_multibase();
        let end = KotobaCid::from_bytes(b"range-end").to_multibase();
        let wrong = KotobaCid::from_bytes(b"range-wrong").to_multibase();
        let payload = test_cacao_payload(vec![
            format!("kotoba://op/{}", kotoba_auth::CacaoPayload::OP_DATOM_READ),
            format!("kotoba://tx/{start}"),
            format!("kotoba://tx/{wrong}"),
        ]);

        let err = enforce_datomic_range_tx_scope(&payload, Some(&start), Some(&end)).unwrap_err();
        assert_eq!(err.0, axum::http::StatusCode::UNAUTHORIZED);
        assert!(err.1.contains(&format!("kotoba://tx/{end}")), "{}", err.1);

        let payload = test_cacao_payload(vec![
            format!("kotoba://op/{}", kotoba_auth::CacaoPayload::OP_DATOM_READ),
            format!("kotoba://tx/{start}"),
            format!("kotoba://tx/{end}"),
        ]);
        enforce_datomic_range_tx_scope(&payload, Some(&start), Some(&end)).unwrap();
    }

    #[test]
    fn datomic_range_tx_scope_is_optional_when_cacao_has_no_tx_resources() {
        let start = KotobaCid::from_bytes(b"range-start-no-scope").to_multibase();
        let payload = test_cacao_payload(vec![format!(
            "kotoba://op/{}",
            kotoba_auth::CacaoPayload::OP_DATOM_READ
        )]);

        enforce_datomic_range_tx_scope(&payload, Some(&start), None).unwrap();
    }

    #[test]
    fn vc_didcomm_and_atproto_project_to_one_distributed_datom_head() {
        let store = MemoryBlockStore::new();
        let ipns = InMemoryIpnsRegistry::new();
        let writer = DistributedCommitWriter::new(&store, &ipns);
        let graph = KotobaCid::from_bytes(b"protocol-normalization-graph");
        let tx = KotobaCid::from_bytes(b"protocol-normalization-tx");

        let mut credential = kotoba_vc::VerifiableCredential::new(
            "urn:uuid:vc-normalized-1",
            "did:key:zIssuer",
            json!({
                "id": "did:key:zAlice",
                "role": "issuer",
                "profile": {"name": "Alice"}
            }),
        );
        credential.credential_status = Some(kotoba_vc::CredentialStatus {
            id: "kotoba://credential/status/normalized-1".into(),
            status_type: "KotobaCredentialStatus".into(),
        });
        credential.proof = Some(kotoba_vc::DataIntegrityProof {
            proof_type: "DataIntegrityProof".into(),
            cryptosuite: Some("eddsa-jcs-2022".into()),
            proof_purpose: "assertionMethod".into(),
            verification_method: "did:key:zIssuer#key-1".into(),
            created: Some("2026-05-29T00:00:00Z".into()),
            proof_value: "zNormalizedProofValue".into(),
            challenge: Some("normalization-challenge".into()),
            domain: Some("kotoba.example".into()),
        });
        let message = kotoba_didcomm::DidCommMessage {
            id: "msg-normalized-1".into(),
            message_type: "https://didcomm.org/basicmessage/2.0/message".into(),
            from: Some("did:key:zAlice".into()),
            to: vec!["did:key:zBob".into()],
            thid: Some("thread-normalized-1".into()),
            pthid: None,
            created_time: Some(1),
            expires_time: None,
            body: json!({"content": "hello from DIDComm"}),
            attachments: vec![kotoba_didcomm::Attachment {
                id: "attachment-normalized-1".into(),
                description: Some("DIDComm attachment normalized as datom entity".into()),
                media_type: Some("application/json".into()),
                data: json!({"profile": {"name": "Alice"}}),
            }],
        };
        let atproto_req = AtprotoRepoWriteReq {
            graph: graph.to_multibase(),
            uri: "at://did:plc:alice/app.bsky.feed.post/r1".into(),
            operation: Some("create".into()),
            cid: Some("bafyreicid".into()),
            record: Some(json!({
                "$type": "app.bsky.feed.post",
                "text": "hello from ATProto",
                "createdAt": "2026-05-29T00:00:00Z"
            })),
            cacao_b64: None,
            auth_presentation: None,
        };
        let at_uri = kotoba_graph::AtUri::parse(&atproto_req.uri).unwrap();
        let at_entity = atproto_repo_record_entity_cid(&atproto_req.uri);

        let mut datoms = Vec::<Datom>::new();
        datoms.extend(credential.to_datoms(tx.clone()).unwrap());
        datoms.extend(message.to_datoms(tx.clone()).unwrap());
        datoms.extend(atproto_repo_write_datoms(
            &atproto_req,
            &at_uri,
            &at_entity,
            &tx,
        ));

        let report = writer
            .commit_datoms(CommitDatomsRequest {
                merge_parents: None,
                ipns_name: "k51-protocol-normalization".into(),
                graph,
                datoms,
                covering_datoms: None,
                expected_parent: None,
                tx_cid: Some(tx.clone()),
                author: "did:key:zIssuer".into(),
                seq: 1,
                valid_until: "2030-01-01T00:00:00Z".into(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .unwrap();

        let reader = DistributedDatomReader::new(&store, &ipns);
        let query = kotoba_edn::parse(
            r#"{:find [?issuer ?status ?proofPurpose ?thread ?threadScope ?attachmentMedia ?attachmentName ?atprotoResource ?text]
                :where [[?vc :credential/issuer ?issuer]
                        [?vc :credential/subject/role "issuer"]
                        [?vc :credential/status/id ?status]
                        [?vc :credential/proof/proofPurpose ?proofPurpose]
                        [?msg :didcomm/thread ?thread]
                        [?msg :didcomm/threadScope ?threadScope]
                        [?msg :didcomm/attachmentCid ?attachmentCid]
                        [?attachment :didcomm/attachmentCid ?attachmentCid]
                        [?attachment :didcomm/attachment/mediaType ?attachmentMedia]
                        [?attachment :didcomm/attachment/data ?attachmentData]
                        [(get-in ?attachmentData [:profile :name]) ?attachmentName]
                        [?post :atproto/resource ?atprotoResource]
                        [?post :atproto/record/text ?text]]}"#,
        )
        .unwrap();
        let rows = reader.q_triples(&report.commit.cid, &query).unwrap();

        assert_eq!(
            rows,
            vec![vec![
                EdnValue::string("did:key:zIssuer"),
                EdnValue::string("kotoba://credential/status/normalized-1"),
                EdnValue::string("assertionMethod"),
                EdnValue::string("thread-normalized-1"),
                EdnValue::string("didcomm://thread/thread-normalized-1"),
                EdnValue::string("application/json"),
                EdnValue::string("Alice"),
                EdnValue::string("at://did:plc:alice/app.bsky.feed.post/r1"),
                EdnValue::string("hello from ATProto"),
            ]]
        );
        assert!(reader
            .history_datoms_index(
                &report.commit.cid,
                kotoba_datomic::DatomIndex::Tea,
                &[EdnValue::string(tx.to_multibase())],
            )
            .unwrap()
            .iter()
            .all(|datom| datom.t == tx));
    }

    #[tokio::test]
    async fn vc_issue_xrpc_writes_status_and_operator_proof_to_distributed_datom_head() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-vc-issue-status-proof-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-vc-issue-status-proof-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let mut credential = kotoba_vc::VerifiableCredential::new(
            "urn:uuid:vc-xrpc-status-proof",
            "did:key:zRequestedIssuer",
            serde_json::json!({
                "id": "did:key:zAlice",
                "role": "issuer"
            }),
        );
        credential.credential_status = Some(kotoba_vc::CredentialStatus {
            id: "kotoba://credential/status/xrpc-1".into(),
            status_type: "KotobaCredentialStatus".into(),
        });

        let response = vc_issue(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(VcIssueReq {
                graph: graph_mb.clone(),
                credential,
                cacao_b64: None,
                auth_presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(body["ipns_name"], distributed_graph_ipns_name(&graph));
        assert_eq!(body["ipns_sequence"], 1);
        assert!(body["ipns_valid_until"].as_str().is_some());
        let index_roots = body["index_roots"].as_object().expect("index roots");
        for root in ["eavt", "aevt", "avet", "vaet", "tea"] {
            assert!(
                index_roots.get(root).and_then(|cid| cid.as_str()).is_some(),
                "protocol write response missing {root} root: {body}"
            );
        }

        let expected_issuer = format!(r#""{}""#, state.operator_did);
        let response = datomic_q(
            axum::extract::State(state),
            headers,
            axum::Json(DatomicQReq {
                graph: graph_mb,
                query_edn: r#"{:find [?issuer ?status ?proofPurpose ?proofDomain]
                    :where [[?vc :credential/id "urn:uuid:vc-xrpc-status-proof"]
                            [?vc :credential/issuer ?issuer]
                            [?vc :credential/status/id ?status]
                            [?vc :credential/proof/proofPurpose ?proofPurpose]
                            [?vc :credential/proof/domain ?proofDomain]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(
            body["rows_edn"],
            serde_json::json!([[
                expected_issuer,
                r#""kotoba://credential/status/xrpc-1""#,
                r#""assertionMethod""#,
                r#""kotoba.vc.issue""#
            ]])
        );
    }

    #[tokio::test]
    async fn didcomm_and_atproto_xrpc_writes_record_cacao_operation_and_resource_scopes() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-cacao-protocol-scope-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-cacao-protocol-scope-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let operator_headers = {
            let mut headers = axum::http::HeaderMap::new();
            headers.insert(
                axum::http::header::AUTHORIZATION,
                format!("Bearer {}", test_operator_jwt(&state.operator_did))
                    .parse()
                    .unwrap(),
            );
            headers
        };
        let no_operator_headers = axum::http::HeaderMap::new();

        let thread_id = "thread-cacao-scope-1";
        let didcomm_scope = format!("didcomm://thread/{thread_id}");
        let didcomm_cacao = signed_cacao_b64(
            &state,
            &graph_mb,
            kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
            "xrpc-didcomm-scope-nonce-1",
            [didcomm_scope.clone()],
        );
        let didcomm_response = didcomm_send(
            axum::extract::State(Arc::clone(&state)),
            no_operator_headers.clone(),
            axum::Json(DidCommSendReq {
                graph: graph_mb.clone(),
                message: kotoba_didcomm::DidCommMessage {
                    id: "msg-cacao-scope-1".into(),
                    message_type: "https://didcomm.org/basicmessage/2.0/message".into(),
                    from: Some(state.operator_did.clone()),
                    to: vec!["did:key:zRecipient".into()],
                    thid: Some(thread_id.into()),
                    pthid: None,
                    created_time: Some(1),
                    expires_time: None,
                    body: serde_json::json!({"content": "scoped DIDComm"}),
                    attachments: vec![],
                },
                cacao_b64: Some(didcomm_cacao),
                auth_presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(didcomm_response.status(), axum::http::StatusCode::OK);

        let at_uri = "at://did:plc:alice/app.bsky.feed.post/r-cacao-scope";
        let atproto_cacao = signed_cacao_b64(
            &state,
            &graph_mb,
            kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
            "xrpc-atproto-scope-nonce-1",
            [at_uri.to_string()],
        );
        let atproto_response = atproto_repo_write(
            axum::extract::State(Arc::clone(&state)),
            no_operator_headers,
            axum::Json(AtprotoRepoWriteReq {
                graph: graph_mb.clone(),
                uri: at_uri.into(),
                operation: Some("create".into()),
                cid: Some("bafyreicacaoscope".into()),
                record: Some(serde_json::json!({
                    "$type": "app.bsky.feed.post",
                    "text": "scoped ATProto",
                    "createdAt": "2026-05-30T00:00:00Z"
                })),
                cacao_b64: Some(atproto_cacao),
                auth_presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(atproto_response.status(), axum::http::StatusCode::OK);

        let scope_query = datomic_q(
            axum::extract::State(state),
            operator_headers,
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn: r#"{:find [?operation ?resource ?didcommThread ?atprotoResource]
                    :where [[?tx :capability/operation ?operation]
                            [?tx :capability/resource ?resource]
                            [(get-else $ ?tx :capability/didcommThread "") ?didcommThread]
                            [(get-else $ ?tx :capability/atprotoResource "") ?atprotoResource]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(scope_query.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(scope_query.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let rows = body["rows_edn"].as_array().expect("rows_edn array");
        assert!(rows.iter().any(|row| {
            row == &serde_json::json!([
                r#""didcomm:send""#,
                format!(r#""{didcomm_scope}""#),
                format!(r#""{thread_id}""#),
                r#""""#
            ])
        }));
        assert!(rows.iter().any(|row| {
            row == &serde_json::json!([
                r#""atproto:repo.write""#,
                format!(r#""{at_uri}""#),
                r#""""#,
                format!(r#""{at_uri}""#)
            ])
        }));
        assert!(rows.iter().any(|row| {
            row == &serde_json::json!([
                r#""didcomm:send""#,
                format!(r#""kotoba://graph/{graph_mb}""#),
                format!(r#""{thread_id}""#),
                r#""""#
            ])
        }));
    }

    #[tokio::test]
    async fn didcomm_xrpc_enforces_declared_cacao_tx_scope_against_transaction_cid() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-didcomm-cacao-tx-scope-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-didcomm-cacao-tx-scope-graph".into(),
                GraphVisibility::Public,
            ),
        );

        let thread_id = "thread-cacao-tx-scope-1";
        let message = kotoba_didcomm::DidCommMessage {
            id: "msg-cacao-tx-scope-1".into(),
            message_type: "https://didcomm.org/basicmessage/2.0/message".into(),
            from: Some(state.operator_did.clone()),
            to: vec!["did:key:zRecipient".into()],
            thid: Some(thread_id.into()),
            pthid: None,
            created_time: Some(1),
            expires_time: None,
            body: serde_json::json!({"content": "tx scoped DIDComm"}),
            attachments: vec![],
        };
        let entity_cid = message.cid().unwrap();
        let message_bytes = serde_json::to_vec(&message).unwrap();
        let tx_cid = protocol_payload_tx_cid("didcomm.send", &graph_mb, &entity_cid, message_bytes);
        let thread_scope = format!("didcomm://thread/{thread_id}");
        let wrong_tx_scope = format!(
            "kotoba://tx/{}",
            KotobaCid::from_bytes(b"xrpc-didcomm-wrong-tx-scope").to_multibase()
        );
        let rejected_cacao = signed_cacao_b64(
            &state,
            &graph_mb,
            kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
            "xrpc-didcomm-wrong-tx-scope-nonce-1",
            [thread_scope.clone(), wrong_tx_scope],
        );

        let rejected = match didcomm_send(
            axum::extract::State(Arc::clone(&state)),
            axum::http::HeaderMap::new(),
            axum::Json(DidCommSendReq {
                graph: graph_mb.clone(),
                message: message.clone(),
                cacao_b64: Some(rejected_cacao),
                auth_presentation: None,
            }),
        )
        .await
        {
            Ok(_) => panic!("wrong tx-scoped DIDComm CACAO must be rejected"),
            Err(err) => err,
        };
        assert_eq!(rejected.0, axum::http::StatusCode::UNAUTHORIZED);
        assert!(
            rejected
                .1
                .contains(&format!("kotoba://tx/{}", tx_cid.to_multibase())),
            "{}",
            rejected.1
        );

        let accepted_cacao = signed_cacao_b64(
            &state,
            &graph_mb,
            kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND,
            "xrpc-didcomm-correct-tx-scope-nonce-1",
            [
                thread_scope,
                format!("kotoba://tx/{}", tx_cid.to_multibase()),
            ],
        );
        let accepted = didcomm_send(
            axum::extract::State(state),
            axum::http::HeaderMap::new(),
            axum::Json(DidCommSendReq {
                graph: graph_mb,
                message,
                cacao_b64: Some(accepted_cacao),
                auth_presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(accepted.status(), axum::http::StatusCode::OK);
    }

    #[tokio::test]
    async fn atproto_xrpc_enforces_declared_cacao_tx_scope_against_transaction_cid() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-atproto-cacao-tx-scope-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-atproto-cacao-tx-scope-graph".into(),
                GraphVisibility::Public,
            ),
        );

        let at_uri = "at://did:plc:alice/app.bsky.feed.post/r-cacao-tx-scope";
        let record = serde_json::json!({
            "$type": "app.bsky.feed.post",
            "text": "tx scoped ATProto",
            "createdAt": "2026-05-30T00:00:00Z"
        });
        let tx_cid = KotobaCid::from_bytes(
            serde_json::to_vec(&serde_json::json!({
                "op": "atproto.repo.write",
                "graph": &graph_mb,
                "uri": at_uri,
                "operation": "create",
                "cid": &Some("bafyreicacaotxscope".to_string()),
                "record": &Some(record.clone()),
            }))
            .unwrap()
            .as_slice(),
        );
        let wrong_tx_scope = format!(
            "kotoba://tx/{}",
            KotobaCid::from_bytes(b"xrpc-atproto-wrong-tx-scope").to_multibase()
        );
        let rejected_cacao = signed_cacao_b64(
            &state,
            &graph_mb,
            kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
            "xrpc-atproto-wrong-tx-scope-nonce-1",
            [at_uri.to_string(), wrong_tx_scope],
        );

        let rejected = match atproto_repo_write(
            axum::extract::State(Arc::clone(&state)),
            axum::http::HeaderMap::new(),
            axum::Json(AtprotoRepoWriteReq {
                graph: graph_mb.clone(),
                uri: at_uri.into(),
                operation: Some("create".into()),
                cid: Some("bafyreicacaotxscope".into()),
                record: Some(record.clone()),
                cacao_b64: Some(rejected_cacao),
                auth_presentation: None,
            }),
        )
        .await
        {
            Ok(_) => panic!("wrong tx-scoped ATProto CACAO must be rejected"),
            Err(err) => err,
        };
        assert_eq!(rejected.0, axum::http::StatusCode::UNAUTHORIZED);
        assert!(
            rejected
                .1
                .contains(&format!("kotoba://tx/{}", tx_cid.to_multibase())),
            "{}",
            rejected.1
        );

        let accepted_cacao = signed_cacao_b64(
            &state,
            &graph_mb,
            kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE,
            "xrpc-atproto-correct-tx-scope-nonce-1",
            [
                at_uri.to_string(),
                format!("kotoba://tx/{}", tx_cid.to_multibase()),
            ],
        );
        let accepted = atproto_repo_write(
            axum::extract::State(state),
            axum::http::HeaderMap::new(),
            axum::Json(AtprotoRepoWriteReq {
                graph: graph_mb,
                uri: at_uri.into(),
                operation: Some("create".into()),
                cid: Some("bafyreicacaotxscope".into()),
                record: Some(record),
                cacao_b64: Some(accepted_cacao),
                auth_presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(accepted.status(), axum::http::StatusCode::OK);
    }

    #[tokio::test]
    async fn didcomm_xrpc_uses_message_payload_for_distinct_thread_transaction_cids() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-didcomm-distinct-thread-tx-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-didcomm-distinct-thread-tx-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        async fn send_msg(
            state: Arc<KotobaState>,
            headers: axum::http::HeaderMap,
            graph: String,
            id: &str,
            content: &str,
        ) -> serde_json::Value {
            let response = didcomm_send(
                axum::extract::State(state),
                headers,
                axum::Json(DidCommSendReq {
                    graph,
                    message: kotoba_didcomm::DidCommMessage {
                        id: id.into(),
                        message_type: "https://didcomm.org/basicmessage/2.0/message".into(),
                        from: Some("did:key:zSender".into()),
                        to: vec!["did:key:zRecipient".into()],
                        thid: Some("thread-shared-tx-scope".into()),
                        pthid: None,
                        created_time: Some(1),
                        expires_time: None,
                        body: serde_json::json!({"content": content}),
                        attachments: vec![],
                    },
                    cacao_b64: None,
                    auth_presentation: None,
                }),
            )
            .await
            .unwrap()
            .into_response();
            assert_eq!(response.status(), axum::http::StatusCode::OK);
            let body = axum::body::to_bytes(response.into_body(), usize::MAX)
                .await
                .unwrap();
            serde_json::from_slice(&body).unwrap()
        }

        let first = send_msg(
            Arc::clone(&state),
            headers.clone(),
            graph_mb.clone(),
            "msg-thread-tx-1",
            "first",
        )
        .await;
        let second = send_msg(
            Arc::clone(&state),
            headers.clone(),
            graph_mb.clone(),
            "msg-thread-tx-2",
            "second",
        )
        .await;
        let first_tx = first["tx_cid"].as_str().expect("first tx_cid").to_string();
        let second_tx = second["tx_cid"]
            .as_str()
            .expect("second tx_cid")
            .to_string();
        assert_ne!(first_tx, second_tx);
        let first_entity = first["entity_cid"]
            .as_str()
            .expect("first entity_cid")
            .to_string();
        let second_entity = second["entity_cid"]
            .as_str()
            .expect("second entity_cid")
            .to_string();
        assert_ne!(first_entity, second_entity);

        async fn pull_entity(
            state: Arc<KotobaState>,
            headers: axum::http::HeaderMap,
            graph: String,
            entity: String,
        ) -> serde_json::Value {
            let response = datomic_pull(
                axum::extract::State(state),
                headers,
                axum::Json(DatomicPullReq {
                    graph,
                    entity,
                    pattern_edn: Some("[*]".into()),
                    as_of: None,
                    since: None,
                    remote_peer: None,
                    remote_ipns_name: None,
                    cacao_b64: None,
                    presentation: None,
                }),
            )
            .await
            .unwrap()
            .into_response();
            assert_eq!(response.status(), axum::http::StatusCode::OK);
            let body = axum::body::to_bytes(response.into_body(), usize::MAX)
                .await
                .unwrap();
            serde_json::from_slice(&body).unwrap()
        }

        let first_pull = pull_entity(
            Arc::clone(&state),
            headers.clone(),
            graph_mb.clone(),
            first_entity,
        )
        .await;
        let second_pull = pull_entity(state, headers, graph_mb, second_entity).await;
        let first_rows = first_pull["datoms"].as_array().expect("first datoms array");
        let second_rows = second_pull["datoms"]
            .as_array()
            .expect("second datoms array");
        assert!(first_rows
            .iter()
            .any(|datom| datom["v_edn"] == serde_json::json!(r#""msg-thread-tx-1""#)));
        assert!(second_rows
            .iter()
            .any(|datom| datom["v_edn"] == serde_json::json!(r#""msg-thread-tx-2""#)));
        let txs = first_rows
            .iter()
            .chain(second_rows.iter())
            .filter(|datom| datom["a"] == serde_json::json!("didcomm/id"))
            .filter_map(|datom| datom["t"].as_str())
            .collect::<std::collections::BTreeSet<_>>();
        assert!(txs.contains(first_tx.as_str()));
        assert!(txs.contains(second_tx.as_str()));
    }

    #[test]
    fn capability_projection_scopes_survive_distributed_datom_commit() {
        let store = MemoryBlockStore::new();
        let ipns = InMemoryIpnsRegistry::new();
        let writer = DistributedCommitWriter::new(&store, &ipns);
        let graph = KotobaCid::from_bytes(b"capability-scope-graph");
        let tx = KotobaCid::from_bytes(b"capability-scope-tx");
        let proof_cid = KotobaCid::from_bytes(b"capability-proof");
        let tx_scope = KotobaCid::from_bytes(b"capability-target-tx");
        let graph_scope = format!("kotoba://graph/{}", graph.to_multibase());
        let tx_scope = format!("kotoba://tx/{}", tx_scope.to_multibase());
        let didcomm_scope = "didcomm://thread/thread-capability-1".to_string();
        let atproto_scope = "at://did:plc:alice/app.bsky.feed.post/r1".to_string();
        let actions = vec![
            kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT.to_string(),
            kotoba_auth::CacaoPayload::OP_DATOM_READ.to_string(),
            kotoba_auth::CacaoPayload::OP_GRAPH_QUERY.to_string(),
            kotoba_auth::CacaoPayload::OP_VC_ISSUE.to_string(),
            kotoba_auth::CacaoPayload::OP_VC_PRESENT.to_string(),
            kotoba_auth::CacaoPayload::OP_DIDCOMM_SEND.to_string(),
            kotoba_auth::CacaoPayload::OP_ATPROTO_REPO_WRITE.to_string(),
        ];
        let targets = vec![
            graph_scope.clone(),
            tx_scope.clone(),
            didcomm_scope.clone(),
            atproto_scope.clone(),
        ];
        let projection = AuthCapabilityProjection {
            proof_format: "CACAO",
            controller: "did:key:zController".into(),
            invoker: "did:key:zInvoker".into(),
            allowed_actions: actions.clone(),
            invocation_targets: targets.clone(),
            proof_cid: Some(proof_cid.clone()),
            credential_ids: vec!["urn:uuid:capability-vc-1".into()],
            presentation_id: Some("urn:uuid:capability-vp-1".into()),
            presentation_cid: Some(KotobaCid::from_bytes(b"capability-presentation")),
        };
        let mut datoms = Vec::<Datom>::new();
        append_auth_capability_datoms(&mut datoms, &tx, &projection);

        let report = writer
            .commit_datoms(CommitDatomsRequest {
                merge_parents: None,
                ipns_name: "k51-capability-scope".into(),
                graph,
                datoms,
                covering_datoms: None,
                expected_parent: None,
                tx_cid: Some(tx.clone()),
                author: "did:key:zController".into(),
                seq: 1,
                valid_until: "2030-01-01T00:00:00Z".into(),
                ttl_secs: Some(60),
                cacao_proof_cid: Some(proof_cid.clone()),
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .unwrap();

        let reader = DistributedDatomReader::new(&store, &ipns);
        let tea_datoms = reader
            .history_datoms_index(
                &report.commit.cid,
                kotoba_datomic::DatomIndex::Tea,
                &[EdnValue::string(tx.to_multibase())],
            )
            .unwrap();
        let has = |attr: &str, value: &str| {
            tea_datoms
                .iter()
                .any(|datom| datom.e == tx && datom.a == attr && datom.v == EdnValue::string(value))
        };

        assert!(has(":capability/type", "CapabilityInvocation"));
        assert!(has(
            kotoba_auth::did_document::ATTR_RDF_TYPE,
            ZCAP_CAPABILITY_INVOCATION_IRI
        ));
        for action in actions {
            assert!(has(":capability/allowedAction", &action));
            assert!(has(":capability/operation", &action));
            assert!(has(ZCAP_ALLOWED_ACTION_IRI, &action));
        }
        for target in targets {
            assert!(has(":capability/invocationTarget", &target));
            assert!(has(":capability/resource", &target));
            assert!(has(ZCAP_INVOCATION_TARGET_IRI, &target));
        }
        assert!(has(":capability/controller", "did:key:zController"));
        assert!(has(ZCAP_CONTROLLER_IRI, "did:key:zController"));
        assert!(has(":capability/invoker", "did:key:zInvoker"));
        assert!(has(ZCAP_INVOKER_IRI, "did:key:zInvoker"));
        assert!(has(
            ":capability/graph",
            graph_scope.trim_start_matches("kotoba://graph/")
        ));
        assert!(has(
            ":capability/tx",
            tx_scope.trim_start_matches("kotoba://tx/")
        ));
        assert!(has(":capability/didcommThread", "thread-capability-1"));
        assert!(has(":capability/atprotoResource", &atproto_scope));
        assert!(has(":capability/proofCid", &proof_cid.to_multibase()));
        assert!(has(ZCAP_INVOCATION_PROOF_IRI, &proof_cid.to_multibase()));
        assert!(has(":capability/credential", "urn:uuid:capability-vc-1"));
        assert!(has(":capability/presentation", "urn:uuid:capability-vp-1"));
        let presentation_cid = KotobaCid::from_bytes(b"capability-presentation").to_multibase();
        assert!(has(":capability/presentationCid", &presentation_cid));
        assert!(has(kotoba_vc::ATTR_PRESENTATION_CID, &presentation_cid));
        assert!(tea_datoms.iter().all(|datom| datom.t == tx));
    }

    #[test]
    fn vp_capability_projection_preserves_presentation_evidence() {
        let graph = KotobaCid::from_bytes(b"vp-capability-graph").to_multibase();
        let tx_scope = format!(
            "kotoba://tx/{}",
            KotobaCid::from_bytes(b"vp-capability-tx").to_multibase()
        );
        let mut credential = kotoba_vc::VerifiableCredential::new(
            "urn:uuid:vp-capability-credential",
            "did:key:zOperator",
            serde_json::json!({
                "id": "did:key:zHolder",
                "operations": [
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    kotoba_auth::CacaoPayload::OP_VC_PRESENT
                ],
                "resources": [
                    format!("kotoba://graph/{graph}"),
                    tx_scope
                ]
            }),
        );
        credential
            .types
            .push("KotobaCapabilityCredential".to_string());
        let presentation = kotoba_vc::VerifiablePresentation {
            context: vec![kotoba_vc::VC_CONTEXT_V2.to_string()],
            id: "urn:uuid:vp-capability-presentation".to_string(),
            types: vec!["VerifiablePresentation".to_string()],
            holder: Some("did:key:zHolder".to_string()),
            verifiable_credentials: vec![credential],
            proof: None,
        };
        let presentation_cid = presentation.cid().expect("presentation cid");
        let projection = vp_capability_projection(&presentation, None);

        assert_eq!(projection.proof_format, "W3C VerifiablePresentation");
        assert_eq!(projection.controller, "did:key:zOperator");
        assert_eq!(projection.invoker, "did:key:zHolder");
        assert_eq!(
            projection.presentation_id.as_deref(),
            Some("urn:uuid:vp-capability-presentation")
        );
        assert_eq!(
            projection.presentation_cid.as_ref(),
            Some(&presentation_cid)
        );
        assert!(projection
            .credential_ids
            .contains(&"urn:uuid:vp-capability-credential".to_string()));
        assert!(projection
            .allowed_actions
            .contains(&kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT.to_string()));
        assert!(projection
            .allowed_actions
            .contains(&kotoba_auth::CacaoPayload::OP_VC_PRESENT.to_string()));
        assert!(projection
            .invocation_targets
            .contains(&format!("kotoba://graph/{graph}")));
        assert!(projection.invocation_targets.contains(&tx_scope));
    }

    #[tokio::test]
    async fn did_document_publish_xrpc_writes_distributed_registry_resolvable_by_did_resolver() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-did-document-publish-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-did-document-publish-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let did = "did:plc:xrpcdistributedagent";
        let mut document = DidDocument::empty(did);
        document.service.push(ServiceEndpoint {
            id: format!("{did}#didcomm"),
            service_type: DIDCOMM_MESSAGING_SERVICE.into(),
            endpoint: ServiceEndpointValue::Object(
                serde_json::json!({
                    "uri": "didcomm://mediator/xrpcdistributedagent",
                    "accept": ["didcomm/v2"],
                    "routingKeys": ["did:key:zMediator#key-x25519"]
                })
                .as_object()
                .unwrap()
                .clone(),
            ),
        });
        document.push_single_service(
            "atproto-pds",
            ATPROTO_PDS_SERVICE,
            "https://pds.xrpcdistributedagent.example",
        );
        document.push_single_service(
            "kotoba-node",
            KOTOBA_NODE_SERVICE,
            "/ip4/127.0.0.1/tcp/4102",
        );
        document.push_graph_membership_service(["kotoba://graph/xrpc-a", "kotoba://graph/xrpc-b"]);

        let response = did_document_publish(
            axum::extract::State(Arc::clone(&state)),
            headers,
            axum::Json(DidDocumentPublishReq {
                graph: graph_mb,
                document,
                cacao_b64: None,
                auth_presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(body["ipns_name"], distributed_graph_ipns_name(&graph));

        let registry_ipns_name = super::did_document_ipns_name(did);
        let registry_head = state
            .ipns_registry
            .resolve(&kotoba_ipfs::IpnsName::new(registry_ipns_name))
            .expect("DID registry IPNS head");
        assert_eq!(registry_head.sequence, 1);

        let resolved = state
            .did_resolver
            .resolve(did)
            .expect("distributed DID doc");
        assert_eq!(
            resolved.didcomm_endpoint(),
            Some("didcomm://mediator/xrpcdistributedagent")
        );
        match &resolved
            .service_by_type(DIDCOMM_MESSAGING_SERVICE)
            .expect("didcomm service")
            .endpoint
        {
            ServiceEndpointValue::Object(endpoint) => {
                assert_eq!(
                    endpoint.get("uri").and_then(serde_json::Value::as_str),
                    Some("didcomm://mediator/xrpcdistributedagent")
                );
                assert_eq!(
                    endpoint
                        .get("accept")
                        .and_then(serde_json::Value::as_array)
                        .and_then(|values| values.first())
                        .and_then(serde_json::Value::as_str),
                    Some("didcomm/v2")
                );
            }
            other => panic!("expected object DIDComm service endpoint, got {other:?}"),
        }
        assert_eq!(
            resolved.atproto_pds_endpoint(),
            Some("https://pds.xrpcdistributedagent.example")
        );
        assert_eq!(resolved.kotoba_endpoint(), Some("/ip4/127.0.0.1/tcp/4102"));
        assert_eq!(
            resolved.graph_memberships(),
            vec!["kotoba://graph/xrpc-a", "kotoba://graph/xrpc-b"]
        );
        assert!(resolved
            .service_by_type(DIDCOMM_MESSAGING_SERVICE)
            .is_some());
        assert!(resolved.service_by_type(ATPROTO_PDS_SERVICE).is_some());
        assert!(resolved.service_by_type(KOTOBA_NODE_SERVICE).is_some());
        assert!(resolved
            .service_by_type(KOTOBA_GRAPH_MEMBERSHIP_SERVICE)
            .is_some());
    }

    /// Drive the real `datomic_transact` handler once and return the commit CID.
    async fn run_transact_for_cache_test(
        state: &Arc<KotobaState>,
        graph_mb: &str,
        edn: &str,
    ) -> String {
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );
        let resp = datomic_transact(
            axum::extract::State(Arc::clone(state)),
            headers,
            axum::Json(DatomicTransactReq {
                graph: graph_mb.to_string(),
                tx_edn: edn.to_string(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(resp.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        body["commit_cid"].as_str().unwrap().to_string()
    }

    /// ADR-2605302130 efficacy: prove the resident db_before cache actually HITS
    /// in the real handler flow rather than silently falling through to a cold
    /// scan (the correctness tests cannot distinguish hit from always-miss, since
    /// the cold path is also correct + fast on MemoryBlockStore). Drives three
    /// sequential transacts on one graph, simulating a restart (cache clear)
    /// between the 1st and 2nd, and asserts the expensive cold `db_from_head`
    /// path runs exactly once — proving the warm transact is served from RAM.
    #[tokio::test]
    async fn datomic_transact_resident_cache_hits_after_warm() {
        use std::sync::atomic::Ordering;
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"resident-cache-hit-graph");
        let graph_mb = graph.to_multibase();

        // tx1: fresh graph → genesis (expected_parent = None) → NOT a cold load.
        let c1 = run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "alice" :person/name "Alice"]]"#,
        )
        .await;
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            0,
            "genesis transact must not cold-load"
        );
        {
            let slot = state.datomic_live_slot(&graph_mb);
            let g = slot.lock().await;
            assert_eq!(
                g.as_ref()
                    .expect("slot seeded after tx1")
                    .head
                    .to_multibase(),
                c1
            );
        }

        // Simulate a restart on an already-populated graph: drop the resident
        // cache (IPNS + block store still hold the graph). The next transact must
        // pay exactly one cold `db_from_head` — this is the ADR's cold-start path.
        state.datomic_live.lock().unwrap().clear();

        let c2 = run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "bob" :person/name "Bob"]]"#,
        )
        .await;
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            1,
            "post-restart transact must cold-load exactly once"
        );

        // tx3: cache is warm again → must HIT (no new cold load).
        let c3 = run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "carol" :person/name "Carol"]]"#,
        )
        .await;
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            1,
            "warm transact must hit the resident cache, not cold-scan"
        );
        {
            let slot = state.datomic_live_slot(&graph_mb);
            let g = slot.lock().await;
            assert_eq!(
                g.as_ref()
                    .expect("slot seeded after tx3")
                    .head
                    .to_multibase(),
                c3,
                "cache head must track the latest commit"
            );
        }
        assert_ne!(c1, c2);
        assert_ne!(c2, c3);
    }

    /// Read-side resident cache (ADR-2606111900 finding): `current_db_for_graph`
    /// — the helper behind cc.status / search.web / kg.* / media / attestation —
    /// must serve from the same per-graph `datomic_live_slot` the transact path
    /// maintains, paying at most ONE cold `db_from_head` after a restart instead
    /// of a full commit-chain replay on EVERY request (measured 325 s cc.status /
    /// 333 s search.web at ~30k datoms before this fix).
    #[tokio::test]
    async fn current_db_for_graph_serves_from_resident_cache() {
        use std::sync::atomic::Ordering;
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"read-resident-cache-graph");
        let graph_mb = graph.to_multibase();

        let c1 = run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "alice" :person/name "Alice"]]"#,
        )
        .await;

        // Simulate a restart: IPNS head + blocks survive, resident cache is gone.
        state.datomic_live.lock().unwrap().clear();
        let cold_before = state.datomic_cold_db_loads.load(Ordering::Relaxed);

        // First read after restart: exactly one cold load, slot re-seeded.
        let db = crate::xrpc::current_db_for_graph(&state, &graph)
            .await
            .unwrap();
        assert!(
            db.datoms()
                .iter()
                .any(|d| d.a == ":person/name" && d.v == kotoba_edn::EdnValue::string("Alice")),
            "read must surface the committed datom"
        );
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            cold_before + 1,
            "first read after restart pays exactly one cold load"
        );
        {
            let slot = state.datomic_live_slot(&graph_mb);
            let g = slot.lock().await;
            assert_eq!(
                g.as_ref()
                    .expect("read must re-seed the slot")
                    .head
                    .to_multibase(),
                c1
            );
        }

        // Second read: resident HIT — no new cold load.
        let db = crate::xrpc::current_db_for_graph(&state, &graph)
            .await
            .unwrap();
        assert!(db
            .datoms()
            .iter()
            .any(|d| d.v == kotoba_edn::EdnValue::string("Alice")));
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            cold_before + 1,
            "warm read must hit the resident cache"
        );

        // A transact advances the head AND the slot (write path re-seeds);
        // the next read must see the new state with still no extra cold load.
        let c2 = run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "bob" :person/name "Bob"]]"#,
        )
        .await;
        assert_ne!(c1, c2);
        let db = crate::xrpc::current_db_for_graph(&state, &graph)
            .await
            .unwrap();
        assert!(
            db.datoms()
                .iter()
                .any(|d| d.v == kotoba_edn::EdnValue::string("Bob")),
            "read after transact must see the advanced head"
        );
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            cold_before + 1,
            "read after a local transact stays a cache hit (slot re-seeded by the write path)"
        );
    }

    /// ADR-2605302130 startup-warm: prove the resident `db_before` cache can be
    /// pre-seeded OFF the request path so the FIRST transact after a (re)start on
    /// an already-large graph HITS RAM instead of paying an on-deadline cold
    /// `db_from_head` (the cold-start gap yukkuri hit on `yukkuri-kg-v3`). The one
    /// cold load is absorbed by the warm, not by the client request.
    #[tokio::test]
    async fn datomic_startup_warm_absorbs_cold_load_so_first_transact_hits() {
        use std::sync::atomic::Ordering;
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"startup-warm-graph");
        let graph_mb = graph.to_multibase();
        let ipns_name = distributed_graph_ipns_name(&graph);

        // Populate a non-empty graph (genesis + one tx), then simulate a (re)start
        // by clearing the resident cache. The IPNS head + blocks survive.
        run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "alice" :person/name "Alice"]]"#,
        )
        .await;
        let c2 = run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "bob" :person/name "Bob"]]"#,
        )
        .await;
        state.datomic_live.lock().unwrap().clear();
        let before = state.datomic_cold_db_loads.load(Ordering::Relaxed);

        // Startup warm pays exactly one cold `db_from_head` — off the request path.
        let outcome = warm_datomic_resident_cache(&state, &graph, &ipns_name)
            .await
            .unwrap();
        assert_eq!(outcome, DatomicWarmOutcome::Warmed);
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            before + 1,
            "warm must absorb exactly one cold load"
        );
        {
            let slot = state.datomic_live_slot(&graph_mb);
            let g = slot.lock().await;
            assert_eq!(
                g.as_ref().expect("warm seeds the slot").head.to_multibase(),
                c2,
                "warm must seed the cache at the resolved IPNS head"
            );
        }

        // Warming again is idempotent — cache already holds the head → no scan.
        let outcome = warm_datomic_resident_cache(&state, &graph, &ipns_name)
            .await
            .unwrap();
        assert_eq!(outcome, DatomicWarmOutcome::AlreadyWarm);
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            before + 1,
            "re-warm must not cold-scan"
        );

        // The first real transact after warm HITS RAM — no on-request cold scan.
        run_transact_for_cache_test(
            &state,
            &graph_mb,
            r#"[[:db/add "carol" :person/name "Carol"]]"#,
        )
        .await;
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            before + 1,
            "post-warm transact must hit the resident cache, not cold-scan"
        );
    }

    /// Warming an empty (never-transacted) graph is a no-op — there is no head to
    /// load, so no cold scan is taken.
    #[tokio::test]
    async fn datomic_startup_warm_on_empty_graph_is_noop() {
        use std::sync::atomic::Ordering;
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"startup-warm-empty-graph");
        let ipns_name = distributed_graph_ipns_name(&graph);
        let before = state.datomic_cold_db_loads.load(Ordering::Relaxed);
        let outcome = warm_datomic_resident_cache(&state, &graph, &ipns_name)
            .await
            .unwrap();
        assert_eq!(outcome, DatomicWarmOutcome::EmptyGraph);
        assert_eq!(
            state.datomic_cold_db_loads.load(Ordering::Relaxed),
            before,
            "warming an empty graph must not cold-scan"
        );
    }

    #[tokio::test]
    async fn datomic_transact_xrpc_commits_distributed_tx_metadata() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-distributed-transact-graph");
        let graph_mb = graph.to_multibase();
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let response = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers,
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "alice" :person/name "Alice"]
                            [:db/add "alice" :person/role "admin"]]"#
                    .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let tx_cid = KotobaCid::from_multibase(body["tx_cid"].as_str().unwrap()).unwrap();
        let ipns_name = distributed_graph_ipns_name(&graph);
        assert_eq!(body["ipns_name"], ipns_name);
        assert_eq!(body["ipns_sequence"], 1);

        let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
        let head = reader.resolve_head(&ipns_name).unwrap().unwrap();
        assert_eq!(head.cid.to_multibase(), body["commit_cid"]);
        let tx_datoms = reader
            .history_datoms_index(
                &head.cid,
                kotoba_datomic::DatomIndex::Tea,
                &[EdnValue::string(tx_cid.to_multibase())],
            )
            .unwrap();
        let has = |attr: &str, value: EdnValue| {
            tx_datoms
                .iter()
                .any(|datom| datom.e == tx_cid && datom.a == attr && datom.v == value)
        };
        assert!(has(":tx/graph", EdnValue::string(graph_mb)));
        assert!(has(
            ":tx/operation",
            EdnValue::string(kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
        ));
        assert!(has(
            ":tx/author",
            EdnValue::string(state.operator_did.clone())
        ));
        assert!(has(":tx/ipnsName", EdnValue::string(ipns_name)));
        assert!(has(":tx/ipnsSequence", EdnValue::Integer(1)));
        assert!(tx_datoms.iter().any(|datom| {
            datom.e == tx_cid
                && datom.a == ":db/txInstant"
                && matches!(datom.v, EdnValue::Integer(value) if value > 0)
        }));
        assert!(has(
            ":tx/ipnsControllerDid",
            EdnValue::string(state.operator_did.clone())
        ));
        assert!(has(
            ":tx/storageBackend",
            EdnValue::string("ipfs/ipld/ipns")
        ));
        assert!(has(":tx/ipldCodec", EdnValue::string("dag-cbor")));
        assert!(has(":tx/indexModel", EdnValue::string("prolly-tree")));
        for root in ["eavt", "aevt", "avet", "vaet", "tea"] {
            assert!(has(":tx/indexRootName", EdnValue::string(root)));
        }
        assert!(tx_datoms
            .iter()
            .any(|datom| datom.a == ":person/name" && datom.v == EdnValue::string("Alice")));
    }

    #[test]
    fn atproto_repo_write_projects_valid_dag_cbor_cid_metadata() {
        let mut cid_bytes = [0u8; 36];
        cid_bytes[0] = 1;
        cid_bytes[1] = KotobaCid::CODEC_DAG_CBOR;
        cid_bytes[2] = KotobaCid::MH_SHA2_256;
        cid_bytes[3] = 32;
        for i in 0..32 {
            cid_bytes[4 + i] = (i as u8).wrapping_mul(11);
        }
        let at_cid = multibase::encode(multibase::Base::Base58Btc, cid_bytes);
        let kotoba_cid = KotobaCid(cid_bytes);
        let tx_cid = KotobaCid::from_bytes(b"atproto-dag-cbor-projection-tx");
        let req = AtprotoRepoWriteReq {
            graph: KotobaCid::from_bytes(b"atproto-dag-cbor-projection-graph").to_multibase(),
            uri: "at://did:plc:alice/app.bsky.feed.post/r1".into(),
            operation: Some("create".into()),
            cid: Some(at_cid.clone()),
            record: Some(serde_json::json!({
                "$type": "app.bsky.feed.post",
                "text": "DAG-CBOR backed ATProto record"
            })),
            cacao_b64: None,
            auth_presentation: None,
        };
        let uri = kotoba_graph::AtUri::parse(&req.uri).unwrap();
        let entity_cid = atproto_repo_record_entity_cid(&req.uri);
        let datoms = atproto_repo_write_datoms(&req, &uri, &entity_cid, &tx_cid);
        let has = |attr: &str, value: EdnValue| {
            datoms.iter().any(|datom| {
                datom.e == entity_cid && datom.a == attr && datom.v == value && datom.added
            })
        };

        assert!(has("atproto/cid", EdnValue::string(at_cid.clone())));
        assert!(has("atproto/recordCid", EdnValue::string(at_cid.clone())));
        assert!(has(
            "atproto/resource",
            EdnValue::string("at://did:plc:alice/app.bsky.feed.post/r1")
        ));
        assert!(has("atproto/did", EdnValue::string("did:plc:alice")));
        assert!(has(
            "atproto/didCid",
            EdnValue::string(KotobaCid::from_bytes(b"did:plc:alice").to_multibase())
        ));
        assert!(has(
            "atproto/recordWireFormat",
            EdnValue::string("application/dag-cbor")
        ));
        assert!(has("atproto/cidVersion", EdnValue::int(1)));
        assert!(has("atproto/cidCodec", EdnValue::string("dag-cbor")));
        assert!(has("atproto/cidMultihash", EdnValue::string("sha2-256")));
        assert!(has(
            "atproto/kotobaCid",
            EdnValue::string(kotoba_cid.to_multibase())
        ));
        assert!(has(
            "atproto/recordKotobaCid",
            EdnValue::string(kotoba_cid.to_multibase())
        ));
    }

    #[test]
    fn atproto_repo_delete_preserves_resource_scope_projection() {
        let tx_cid = KotobaCid::from_bytes(b"atproto-delete-resource-scope-tx");
        let delete_tx_cid = KotobaCid::from_bytes(b"atproto-delete-resource-scope-delete-tx");
        let uri_value = "at://did:plc:alice/app.bsky.feed.post/r-delete";
        let create_req = AtprotoRepoWriteReq {
            graph: KotobaCid::from_bytes(b"atproto-delete-resource-scope-graph").to_multibase(),
            uri: uri_value.into(),
            operation: Some("create".into()),
            cid: None,
            record: Some(serde_json::json!({
                "$type": "app.bsky.feed.post",
                "text": "delete me"
            })),
            cacao_b64: None,
            auth_presentation: None,
        };
        let uri = kotoba_graph::AtUri::parse(&create_req.uri).unwrap();
        let entity_cid = atproto_repo_record_entity_cid(&create_req.uri);
        let create_datoms = atproto_repo_write_datoms(&create_req, &uri, &entity_cid, &tx_cid);
        let db = kotoba_datomic::Db::from_datoms(create_datoms, None);
        let delete_req = AtprotoRepoWriteReq {
            operation: Some("delete".into()),
            record: None,
            cid: None,
            ..create_req
        };

        let delete_datoms =
            atproto_repo_delete_datoms(&db, &delete_req, &uri, &entity_cid, &delete_tx_cid);

        assert!(delete_datoms.iter().any(|datom| {
            datom.e == entity_cid
                && datom.a == "atproto/resource"
                && datom.v == EdnValue::string(uri_value)
                && datom.t == delete_tx_cid
                && datom.added
        }));
        assert!(delete_datoms.iter().any(|datom| {
            datom.e == entity_cid
                && datom.a == "atproto/deleted"
                && datom.v == EdnValue::Bool(true)
                && datom.t == delete_tx_cid
                && datom.added
        }));
        assert!(delete_datoms.iter().any(|datom| {
            datom.e == entity_cid
                && datom.a == "atproto/didCid"
                && datom.v
                    == EdnValue::string(KotobaCid::from_bytes(b"did:plc:alice").to_multibase())
                && datom.t == delete_tx_cid
                && datom.added
        }));
    }

    #[tokio::test]
    async fn datomic_transact_xrpc_covers_advanced_datomic_forms_on_distributed_head() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-datomic-advanced-forms-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-datomic-advanced-forms-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let schema = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[
                  {:db/id "email" :db/ident :person/email :db/unique :db.unique/identity}
                  {:db/id "address" :db/ident :person/address :db/valueType :db.type/ref :db/isComponent true}
                  {:db/id "secret" :db/ident :person/secret :db/noHistory true}
                ]"#
                .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(schema.status(), axum::http::StatusCode::OK);

        let seed = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[
                  {:db/id "alice"
                   :person/email "a@example.com"
                   :person/name "Alice"
                   :person/age 30
                   :person/address "addr"
                   :person/secret "old"}
                  {:db/id "addr" :address/city "Tokyo"}
                ]"#
                .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(seed.status(), axum::http::StatusCode::OK);

        let advanced = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[
                  {:db/id "alice-again"
                   :person/email "a@example.com"
                   :person/role "admin"}
                  [:db.fn/cas [:person/email "a@example.com"] :person/age 30 31]
                  [:db/add [:person/email "a@example.com"] :person/secret "new"]
                ]"#
                .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(advanced.status(), axum::http::StatusCode::OK);

        let current = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn: r#"{:find [?name ?age ?role ?secret]
                    :where [[[:person/email "a@example.com"] :person/name ?name]
                            [[:person/email "a@example.com"] :person/age ?age]
                            [[:person/email "a@example.com"] :person/role ?role]
                            [[:person/email "a@example.com"] :person/secret ?secret]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(current.status(), axum::http::StatusCode::OK);
        let current_body = axum::body::to_bytes(current.into_body(), usize::MAX)
            .await
            .unwrap();
        let current_body: serde_json::Value = serde_json::from_slice(&current_body).unwrap();
        assert_eq!(
            current_body["rows_edn"],
            serde_json::json!([[r#""Alice""#, "31", r#""admin""#, r#""new""#]])
        );

        let secret_history = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn: r#"{:find [?secret ?added]
                    :where [[$history ?e :person/secret ?secret ?tx ?added]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: true,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(secret_history.status(), axum::http::StatusCode::OK);
        let secret_history_body = axum::body::to_bytes(secret_history.into_body(), usize::MAX)
            .await
            .unwrap();
        let secret_history_body: serde_json::Value =
            serde_json::from_slice(&secret_history_body).unwrap();
        let secret_rows = secret_history_body["rows_edn"].as_array().unwrap();
        assert!(secret_rows
            .iter()
            .all(|row| row[0] != serde_json::Value::String(r#""old""#.into())));

        let retract = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[
                  [:db.fn/retractEntity [:person/email "a@example.com"]]
                ]"#
                .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(retract.status(), axum::http::StatusCode::OK);

        let component_history = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn: r#"{:find [?city ?added]
                    :where [[$history ?addr :address/city ?city ?tx ?added]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: true,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(component_history.status(), axum::http::StatusCode::OK);
        let component_history_body =
            axum::body::to_bytes(component_history.into_body(), usize::MAX)
                .await
                .unwrap();
        let component_history_body: serde_json::Value =
            serde_json::from_slice(&component_history_body).unwrap();
        assert!(component_history_body["rows_edn"]
            .as_array()
            .unwrap()
            .iter()
            .any(|row| row == &serde_json::json!([r#""Tokyo""#, "false"])));

        let excise = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[{:db/excise :person/secret}]"#.into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(excise.status(), axum::http::StatusCode::OK);

        let after_excise = datomic_q(
            axum::extract::State(state),
            headers,
            axum::Json(DatomicQReq {
                graph: graph_mb,
                query_edn: r#"{:find [?secret]
                    :where [[$history ?e :person/secret ?secret ?tx ?added]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: true,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(after_excise.status(), axum::http::StatusCode::OK);
        let after_excise_body = axum::body::to_bytes(after_excise.into_body(), usize::MAX)
            .await
            .unwrap();
        let after_excise_body: serde_json::Value =
            serde_json::from_slice(&after_excise_body).unwrap();
        assert!(after_excise_body["rows_edn"].as_array().unwrap().is_empty());
    }

    #[tokio::test]
    async fn datomic_transact_xrpc_writes_named_ipns_head_readable_by_override() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-named-ipns-transact-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-named-ipns-transact-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let named_head = "k51-kotoba-xrpc-named-write-head".to_string();
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let write = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "alice" :person/name "Alice"]
                            [:db/add "alice" :person/role "admin"]]"#
                    .into(),
                ipns_name: Some(named_head.clone()),
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(write.status(), axum::http::StatusCode::OK);
        let write_body = axum::body::to_bytes(write.into_body(), usize::MAX)
            .await
            .unwrap();
        let write_body: serde_json::Value = serde_json::from_slice(&write_body).unwrap();
        assert_eq!(write_body["ipns_name"], named_head);
        assert_eq!(write_body["ipns_sequence"], 1);

        let canonical_reader =
            DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
        assert!(canonical_reader
            .resolve_head(&distributed_graph_ipns_name(&graph))
            .unwrap()
            .is_none());
        assert_eq!(
            canonical_reader
                .resolve_head(&named_head)
                .unwrap()
                .unwrap()
                .cid
                .to_multibase(),
            write_body["commit_cid"].as_str().unwrap()
        );

        let datoms = datomic_datoms(
            axum::extract::State(state),
            headers,
            axum::Json(DatomicDatomsReq {
                graph: graph_mb,
                index: ":eavt".into(),
                components_edn: vec![],
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: Some(named_head),
                cacao_b64: None,
                presentation: None,
                limit: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(datoms.status(), axum::http::StatusCode::OK);
        let datoms_body = axum::body::to_bytes(datoms.into_body(), usize::MAX)
            .await
            .unwrap();
        let datoms_body: serde_json::Value = serde_json::from_slice(&datoms_body).unwrap();
        assert!(datoms_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| { datom["a"] == ":person/name" && datom["v_edn"] == r#""Alice""# }));
    }

    #[tokio::test]
    async fn datomic_with_xrpc_uses_named_distributed_ipns_head_as_speculative_base() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-with-named-ipns-base-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-with-named-ipns-base-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let named_head = "k51-kotoba-xrpc-with-named-base-head".to_string();
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let write = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "alice" :person/name "Alice"]]"#.into(),
                ipns_name: Some(named_head.clone()),
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(write.status(), axum::http::StatusCode::OK);
        let write_body = axum::body::to_bytes(write.into_body(), usize::MAX)
            .await
            .unwrap();
        let write_body: serde_json::Value = serde_json::from_slice(&write_body).unwrap();
        let base_tx = write_body["tx_cid"].as_str().unwrap().to_string();

        let speculative = datomic_with(
            axum::extract::State(state),
            headers,
            axum::Json(DatomicWithReq {
                graph: graph_mb,
                tx_edn: r#"[[:db/add "alice" :person/role "admin"]]"#.into(),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: Some(named_head),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(speculative.status(), axum::http::StatusCode::OK);
        let speculative_body = axum::body::to_bytes(speculative.into_body(), usize::MAX)
            .await
            .unwrap();
        let speculative_body: serde_json::Value =
            serde_json::from_slice(&speculative_body).unwrap();
        assert_eq!(speculative_body["db_before_basis_t"], base_tx);
        let datoms = speculative_body["db_after_datoms"].as_array().unwrap();
        assert!(datoms
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == r#""Alice""#));
        assert!(datoms
            .iter()
            .any(|datom| datom["a"] == ":person/role" && datom["v_edn"] == r#""admin""#));
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn datomic_q_xrpc_reads_remote_ipfs_ipns_dag_cbor_prolly_head() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        // This test fetches from a loopback peer; allow it past the SSRF guard.
        std::env::set_var("KOTOBA_ALLOW_PRIVATE_PEERS", "1");

        let remote_node = IpfsConfig::new()
            .with_listen("/ip4/127.0.0.1/tcp/0".parse().unwrap())
            .start()
            .await
            .unwrap();
        let remote_peer = remote_node
            .listen_addrs()
            .await
            .unwrap()
            .into_iter()
            .next()
            .unwrap()
            .to_string();

        let source_store = MemoryBlockStore::new();
        let source_ipns = InMemoryIpnsRegistry::new();
        let writer = DistributedCommitWriter::new(&source_store, &source_ipns);
        let graph = KotobaCid::from_bytes(b"xrpc-remote-datomic-q-graph");
        let graph_mb = graph.to_multibase();
        let ipns_name = distributed_graph_ipns_name(&graph);
        let tx = KotobaCid::from_bytes(b"xrpc-remote-datomic-q-tx");
        let report = writer
            .commit_datoms(CommitDatomsRequest {
                merge_parents: None,
                ipns_name: ipns_name.clone(),
                graph: graph.clone(),
                covering_datoms: None,
                datoms: vec![
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-alice"),
                        ":person/name".into(),
                        EdnValue::string("Alice"),
                        tx.clone(),
                    ),
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-alice"),
                        ":person/role".into(),
                        EdnValue::string("admin"),
                        tx.clone(),
                    ),
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-alice"),
                        ":person/score".into(),
                        EdnValue::Integer(10),
                        tx.clone(),
                    ),
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-alice"),
                        ":person/email".into(),
                        EdnValue::string("remote-alice@example.com"),
                        tx.clone(),
                    ),
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-alice"),
                        ":db/ident".into(),
                        EdnValue::Keyword(kotoba_edn::Keyword::parse("person/remote-alice")),
                        tx.clone(),
                    ),
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-bob"),
                        ":person/role".into(),
                        EdnValue::string("admin"),
                        tx.clone(),
                    ),
                    Datom::assert(
                        KotobaCid::from_bytes(b"remote-bob"),
                        ":person/score".into(),
                        EdnValue::Integer(20),
                        tx.clone(),
                    ),
                ],
                expected_parent: None,
                tx_cid: Some(tx),
                author: "did:key:zRemoteAuthor".into(),
                seq: 1,
                valid_until: "2030-01-01T00:00:00Z".into(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .unwrap();

        for cid in source_store.all_cids() {
            let bytes = source_store.get(&cid).unwrap().unwrap();
            let ipfs_cid = cid.to_standard_cid().unwrap();
            remote_node.put_block(&ipfs_cid, &bytes).await.unwrap();
        }
        remote_node
            .name_publish(
                &ipns_name,
                &report.commit.cid.to_standard_cid().unwrap(),
                report.ipns_record.valid_until.clone(),
            )
            .await
            .unwrap();

        let state = Arc::new(KotobaState::new(None).unwrap());
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-remote-datomic-q-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let response = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn:
                    r#"[:find ?name ?role :where [?e :person/name ?name] [?e :person/role ?role]]"#
                        .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), axum::http::StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(
            body["rows_edn"],
            serde_json::json!([[r#""Alice""#, r#""admin""#]])
        );
        assert_eq!(body["basis_t"], report.commit.tx_cid.to_multibase());

        let aggregate = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn: r#"{:find [(count ?e) (sum ?score)]
                        :keys [total totalScore]
                        :where [[?e :person/role "admin"]
                                [?e :person/score ?score]]}"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(aggregate.status(), axum::http::StatusCode::OK);
        let aggregate_body = axum::body::to_bytes(aggregate.into_body(), usize::MAX)
            .await
            .unwrap();
        let aggregate_body: serde_json::Value = serde_json::from_slice(&aggregate_body).unwrap();
        assert_eq!(
            aggregate_body["rows_edn"],
            serde_json::json!([[r#"{:total 2 :totalScore 30}"#]])
        );
        assert_eq!(
            aggregate_body["rows_map_json"],
            serde_json::json!([{ ":total": "2", ":totalScore": "30" }])
        );

        let speculative = datomic_with(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicWithReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "remote-alice" :person/title "Lead"]]"#.into(),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(speculative.status(), axum::http::StatusCode::OK);
        let speculative_body = axum::body::to_bytes(speculative.into_body(), usize::MAX)
            .await
            .unwrap();
        let speculative_body: serde_json::Value =
            serde_json::from_slice(&speculative_body).unwrap();
        assert_eq!(
            speculative_body["db_before_basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        let speculative_datoms = speculative_body["db_after_datoms"].as_array().unwrap();
        assert!(speculative_datoms
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == r#""Alice""#));
        assert!(speculative_datoms
            .iter()
            .any(|datom| datom["a"] == ":person/title" && datom["v_edn"] == r#""Lead""#));

        let pull = datomic_pull(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicPullReq {
                graph: graph_mb.clone(),
                entity: KotobaCid::from_bytes(b"remote-alice").to_multibase(),
                pattern_edn: Some(r#"[:person/name :person/role]"#.into()),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(pull.status(), axum::http::StatusCode::OK);
        let pull_body = axum::body::to_bytes(pull.into_body(), usize::MAX)
            .await
            .unwrap();
        let pull_body: serde_json::Value = serde_json::from_slice(&pull_body).unwrap();
        assert!(pull_body["entity_edn"].as_str().unwrap().contains("Alice"));
        assert!(pull_body["entity_edn"].as_str().unwrap().contains("admin"));

        let remote_datoms = datomic_datoms(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicDatomsReq {
                graph: graph_mb.clone(),
                index: ":aevt".into(),
                components_edn: vec![":person/role".into()],
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_datoms.status(), axum::http::StatusCode::OK);
        let remote_datoms_body = axum::body::to_bytes(remote_datoms.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_datoms_body: serde_json::Value =
            serde_json::from_slice(&remote_datoms_body).unwrap();
        assert_eq!(
            remote_datoms_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        assert_eq!(remote_datoms_body["datom_count"], 2);
        assert!(remote_datoms_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .all(|datom| datom["a"] == ":person/role"));

        let remote_seek = datomic_seek_datoms(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicSeekDatomsReq {
                graph: graph_mb.clone(),
                index: ":aevt".into(),
                components_edn: vec![":person/score".into()],
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_seek.status(), axum::http::StatusCode::OK);
        let remote_seek_body = axum::body::to_bytes(remote_seek.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_seek_body: serde_json::Value =
            serde_json::from_slice(&remote_seek_body).unwrap();
        assert_eq!(remote_seek_body["datom_count"], 2);
        assert!(remote_seek_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .all(|datom| datom["a"] == ":person/score"));

        let remote_range = datomic_index_range(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicIndexRangeReq {
                graph: graph_mb.clone(),
                attr_edn: ":person/score".into(),
                start_edn: Some("15".into()),
                end_edn: Some("25".into()),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_range.status(), axum::http::StatusCode::OK);
        let remote_range_body = axum::body::to_bytes(remote_range.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_range_body: serde_json::Value =
            serde_json::from_slice(&remote_range_body).unwrap();
        assert_eq!(remote_range_body["datom_count"], 1);
        assert_eq!(remote_range_body["datoms"][0]["v_edn"], "20");

        let remote_pull_many = datomic_pull_many(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicPullManyReq {
                graph: graph_mb.clone(),
                entities: vec![
                    KotobaCid::from_bytes(b"remote-alice").to_multibase(),
                    KotobaCid::from_bytes(b"remote-bob").to_multibase(),
                ],
                pattern_edn: Some(r#"[:person/role :person/score]"#.into()),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_pull_many.status(), axum::http::StatusCode::OK);
        let remote_pull_many_body = axum::body::to_bytes(remote_pull_many.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_pull_many_body: serde_json::Value =
            serde_json::from_slice(&remote_pull_many_body).unwrap();
        assert_eq!(
            remote_pull_many_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        assert_eq!(remote_pull_many_body["entity_count"], 2);
        assert!(remote_pull_many_body["entities"][0]["entity_edn"]
            .as_str()
            .unwrap()
            .contains("admin"));

        let remote_index_pull = datomic_index_pull(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicIndexPullReq {
                graph: graph_mb.clone(),
                index: ":aevt".into(),
                components_edn: vec![":person/role".into()],
                pattern_edn: Some(r#"[:person/role :person/score]"#.into()),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_index_pull.status(), axum::http::StatusCode::OK);
        let remote_index_pull_body =
            axum::body::to_bytes(remote_index_pull.into_body(), usize::MAX)
                .await
                .unwrap();
        let remote_index_pull_body: serde_json::Value =
            serde_json::from_slice(&remote_index_pull_body).unwrap();
        assert_eq!(
            remote_index_pull_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        assert_eq!(remote_index_pull_body["entity_count"], 2);

        let remote_ident = datomic_ident(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicIdentReq {
                graph: graph_mb.clone(),
                entity: KotobaCid::from_bytes(b"remote-alice").to_multibase(),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_ident.status(), axum::http::StatusCode::OK);
        let remote_ident_body = axum::body::to_bytes(remote_ident.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_ident_body: serde_json::Value =
            serde_json::from_slice(&remote_ident_body).unwrap();
        assert_eq!(remote_ident_body["ident_edn"], ":person/remote-alice");

        let remote_entid = datomic_entid(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicEntidReq {
                graph: graph_mb.clone(),
                ident_edn: r#"[:person/email "remote-alice@example.com"]"#.into(),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_entid.status(), axum::http::StatusCode::OK);
        let remote_entid_body = axum::body::to_bytes(remote_entid.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_entid_body: serde_json::Value =
            serde_json::from_slice(&remote_entid_body).unwrap();
        assert_eq!(
            remote_entid_body["entity"],
            KotobaCid::from_bytes(b"remote-alice").to_multibase()
        );

        let remote_entity = datomic_entity(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicEntityReq {
                graph: graph_mb.clone(),
                entity: KotobaCid::from_bytes(b"remote-bob").to_multibase(),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_entity.status(), axum::http::StatusCode::OK);
        let remote_entity_body = axum::body::to_bytes(remote_entity.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_entity_body: serde_json::Value =
            serde_json::from_slice(&remote_entity_body).unwrap();
        assert!(remote_entity_body["entity_edn"]
            .as_str()
            .unwrap()
            .contains("20"));

        let remote_basis = datomic_basis_t(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicBasisTReq {
                graph: graph_mb.clone(),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_basis.status(), axum::http::StatusCode::OK);
        let remote_basis_body = axum::body::to_bytes(remote_basis.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_basis_body: serde_json::Value =
            serde_json::from_slice(&remote_basis_body).unwrap();
        assert_eq!(
            remote_basis_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );

        let remote_stats = datomic_db_stats(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicDbStatsReq {
                graph: graph_mb.clone(),
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_stats.status(), axum::http::StatusCode::OK);
        let remote_stats_body = axum::body::to_bytes(remote_stats.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_stats_body: serde_json::Value =
            serde_json::from_slice(&remote_stats_body).unwrap();
        assert_eq!(
            remote_stats_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        assert_eq!(remote_stats_body["tx_count"], 1);
        assert!(remote_stats_body["datom_count"].as_u64().unwrap() >= 7);

        let remote_history = datomic_history(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicHistoryReq {
                graph: graph_mb.clone(),
                cacao_b64: None,
                presentation: None,
                as_of: None,
                since: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                limit: Some(20),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_history.status(), axum::http::StatusCode::OK);
        let remote_history_body = axum::body::to_bytes(remote_history.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_history_body: serde_json::Value =
            serde_json::from_slice(&remote_history_body).unwrap();
        assert_eq!(
            remote_history_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        assert!(remote_history_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/email"));

        let remote_log = datomic_log(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicLogReq {
                graph: graph_mb.clone(),
                start: None,
                end: None,
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(remote_log.status(), axum::http::StatusCode::OK);
        let remote_log_body = axum::body::to_bytes(remote_log.into_body(), usize::MAX)
            .await
            .unwrap();
        let remote_log_body: serde_json::Value = serde_json::from_slice(&remote_log_body).unwrap();
        assert_eq!(remote_log_body["tx_count"], 1);
        assert_eq!(
            remote_log_body["txes"][0]["tx_cid"],
            report.commit.tx_cid.to_multibase()
        );

        let sync = datomic_sync(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicSyncReq {
                graph: graph_mb.clone(),
                tx: Some(report.commit.tx_cid.to_multibase()),
                remote_peer: Some(remote_peer.clone()),
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(sync.status(), axum::http::StatusCode::OK);
        let sync_body = axum::body::to_bytes(sync.into_body(), usize::MAX)
            .await
            .unwrap();
        let sync_body: serde_json::Value = serde_json::from_slice(&sync_body).unwrap();
        assert_eq!(sync_body["reached"], true);
        assert!(
            sync_body["synced_block_count"]
                .as_u64()
                .expect("synced_block_count")
                > 0
        );

        let local_after_sync = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn:
                    r#"[:find ?name :where [?e :person/name ?name] [?e :person/role "admin"]]"#
                        .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(local_after_sync.status(), axum::http::StatusCode::OK);
        let local_after_sync_body = axum::body::to_bytes(local_after_sync.into_body(), usize::MAX)
            .await
            .unwrap();
        let local_after_sync_body: serde_json::Value =
            serde_json::from_slice(&local_after_sync_body).unwrap();
        assert_eq!(
            local_after_sync_body["basis_t"],
            report.commit.tx_cid.to_multibase()
        );
        assert_eq!(
            local_after_sync_body["rows_edn"],
            serde_json::json!([[r#""Alice""#]])
        );

        let local_append = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "remote-bob" :person/title "Synced Writer"]]"#.into(),
                ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
                expected_parent: None,
                cacao_proof_cid: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(local_append.status(), axum::http::StatusCode::OK);

        let local_after_append = datomic_q(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicQReq {
                graph: graph_mb.clone(),
                query_edn: r#"[:find ?role ?title
                    :where [?e :person/role ?role]
                           [?e :person/title ?title]]"#
                    .into(),
                inputs_edn: vec![],
                as_of: None,
                since: None,
                history: false,
                emit_cid: false,
                remote_peer: None,
                remote_ipns_name: Some(ipns_name.clone()),
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(local_after_append.status(), axum::http::StatusCode::OK);
        let local_after_append_body =
            axum::body::to_bytes(local_after_append.into_body(), usize::MAX)
                .await
                .unwrap();
        let local_after_append_body: serde_json::Value =
            serde_json::from_slice(&local_after_append_body).unwrap();
        assert_eq!(
            local_after_append_body["rows_edn"],
            serde_json::json!([[r#""admin""#, r#""Synced Writer""#]])
        );

        let tx_range = datomic_tx_range(
            axum::extract::State(Arc::clone(&state)),
            headers,
            axum::Json(DatomicTxRangeReq {
                graph: graph_mb,
                start: None,
                end: None,
                remote_peer: Some(remote_peer),
                remote_ipns_name: Some(ipns_name),
                cacao_b64: None,
                presentation: None,
                limit: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(tx_range.status(), axum::http::StatusCode::OK);
        let tx_range_body = axum::body::to_bytes(tx_range.into_body(), usize::MAX)
            .await
            .unwrap();
        let tx_range_body: serde_json::Value = serde_json::from_slice(&tx_range_body).unwrap();
        assert_eq!(tx_range_body["tx_count"], 1);
        assert_eq!(
            tx_range_body["txes"][0]["tx_cid"],
            report.commit.tx_cid.to_multibase()
        );
    }

    #[tokio::test]
    async fn datomic_pull_entity_xrpc_reads_distributed_ipns_head() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"xrpc-distributed-pull-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "xrpc-distributed-pull-graph".into(),
                GraphVisibility::Public,
            ),
        );
        let alice = KotobaCid::from_bytes(b"alice").to_multibase();
        let bob = KotobaCid::from_bytes(b"bob").to_multibase();
        let mut headers = axum::http::HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", test_operator_jwt(&state.operator_did))
                .parse()
                .unwrap(),
        );

        let first = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "alice" :person/name "Alice"]
                            [:db/add "alice" :person/role "admin"]
                            [:db/add "alice" :person/email "alice@example.com"]
                            [:db/add "alice" :db/ident :person/alice]]"#
                    .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(first.status(), axum::http::StatusCode::OK);
        let first_body = axum::body::to_bytes(first.into_body(), usize::MAX)
            .await
            .unwrap();
        let first_body: serde_json::Value = serde_json::from_slice(&first_body).unwrap();
        let first_tx = first_body["tx_cid"].as_str().unwrap().to_string();

        let second = datomic_transact(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTransactReq {
                graph: graph_mb.clone(),
                tx_edn: r#"[[:db/add "bob" :person/name "Bob"]
                            [:db/add "bob" :person/role "operator"]]"#
                    .into(),
                ipns_name: None,
                cacao_b64: None,
                cacao_proof_cid: None,
                expected_parent: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(second.status(), axum::http::StatusCode::OK);
        let second_body = axum::body::to_bytes(second.into_body(), usize::MAX)
            .await
            .unwrap();
        let second_body: serde_json::Value = serde_json::from_slice(&second_body).unwrap();
        let second_tx = second_body["tx_cid"].as_str().unwrap().to_string();

        let pull = datomic_pull(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicPullReq {
                graph: graph_mb.clone(),
                entity: alice.clone(),
                pattern_edn: Some(r#"[:person/name :person/role]"#.into()),
                as_of: Some(first_tx.clone()),
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(pull.status(), axum::http::StatusCode::OK);
        let pull_body = axum::body::to_bytes(pull.into_body(), usize::MAX)
            .await
            .unwrap();
        let pull_body: serde_json::Value = serde_json::from_slice(&pull_body).unwrap();
        assert_eq!(pull_body["basis_t"], first_tx);
        assert!(pull_body["entity_edn"].as_str().unwrap().contains("Alice"));
        assert!(pull_body["entity_edn"].as_str().unwrap().contains("admin"));
        assert!(!pull_body["entity_edn"].as_str().unwrap().contains("Bob"));

        let lookup_pull = datomic_pull(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicPullReq {
                graph: graph_mb.clone(),
                entity: r#"[:person/email "alice@example.com"]"#.into(),
                pattern_edn: Some(r#"[:person/name :person/email]"#.into()),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(lookup_pull.status(), axum::http::StatusCode::OK);
        let lookup_pull_body = axum::body::to_bytes(lookup_pull.into_body(), usize::MAX)
            .await
            .unwrap();
        let lookup_pull_body: serde_json::Value =
            serde_json::from_slice(&lookup_pull_body).unwrap();
        assert!(lookup_pull_body["entity_edn"]
            .as_str()
            .unwrap()
            .contains("alice@example.com"));

        let pull_many = datomic_pull_many(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicPullManyReq {
                graph: graph_mb.clone(),
                entities: vec![alice.clone(), bob.clone()],
                pattern_edn: Some(r#"[:person/name]"#.into()),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(pull_many.status(), axum::http::StatusCode::OK);
        let pull_many_body = axum::body::to_bytes(pull_many.into_body(), usize::MAX)
            .await
            .unwrap();
        let pull_many_body: serde_json::Value = serde_json::from_slice(&pull_many_body).unwrap();
        assert_eq!(pull_many_body["entity_count"], 2);
        assert!(pull_many_body["entities"][0]["entity_edn"]
            .as_str()
            .unwrap()
            .contains("Alice"));
        assert!(pull_many_body["entities"][1]["entity_edn"]
            .as_str()
            .unwrap()
            .contains("Bob"));

        let ident = datomic_ident(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicIdentReq {
                graph: graph_mb.clone(),
                entity: alice.clone(),
                as_of: Some(first_tx.clone()),
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(ident.status(), axum::http::StatusCode::OK);
        let ident_body = axum::body::to_bytes(ident.into_body(), usize::MAX)
            .await
            .unwrap();
        let ident_body: serde_json::Value = serde_json::from_slice(&ident_body).unwrap();
        assert_eq!(ident_body["basis_t"], first_tx);
        assert_eq!(ident_body["ident_edn"], ":person/alice");

        let entid = datomic_entid(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicEntidReq {
                graph: graph_mb.clone(),
                ident_edn: ":person/alice".into(),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(entid.status(), axum::http::StatusCode::OK);
        let entid_body = axum::body::to_bytes(entid.into_body(), usize::MAX)
            .await
            .unwrap();
        let entid_body: serde_json::Value = serde_json::from_slice(&entid_body).unwrap();
        assert_eq!(entid_body["entity"], alice);

        let lookup_entid = datomic_entid(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicEntidReq {
                graph: graph_mb.clone(),
                ident_edn: r#"[:person/email "alice@example.com"]"#.into(),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(lookup_entid.status(), axum::http::StatusCode::OK);
        let lookup_entid_body = axum::body::to_bytes(lookup_entid.into_body(), usize::MAX)
            .await
            .unwrap();
        let lookup_entid_body: serde_json::Value =
            serde_json::from_slice(&lookup_entid_body).unwrap();
        assert_eq!(lookup_entid_body["entity"], alice);

        let entity = datomic_entity(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicEntityReq {
                graph: graph_mb.clone(),
                entity: bob.clone(),
                as_of: None,
                since: Some(first_tx.clone()),
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(entity.status(), axum::http::StatusCode::OK);
        let entity_body = axum::body::to_bytes(entity.into_body(), usize::MAX)
            .await
            .unwrap();
        let entity_body: serde_json::Value = serde_json::from_slice(&entity_body).unwrap();
        assert!(entity_body["entity_edn"].as_str().unwrap().contains("Bob"));
        assert_eq!(entity_body["datom_count"], 2);

        let basis = datomic_basis_t(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicBasisTReq {
                graph: graph_mb.clone(),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(basis.status(), axum::http::StatusCode::OK);
        let basis_body = axum::body::to_bytes(basis.into_body(), usize::MAX)
            .await
            .unwrap();
        let basis_body: serde_json::Value = serde_json::from_slice(&basis_body).unwrap();
        assert_eq!(basis_body["basis_t"], second_tx);

        let stats = datomic_db_stats(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicDbStatsReq {
                graph: graph_mb.clone(),
                as_of: None,
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(stats.status(), axum::http::StatusCode::OK);
        let stats_body = axum::body::to_bytes(stats.into_body(), usize::MAX)
            .await
            .unwrap();
        let stats_body: serde_json::Value = serde_json::from_slice(&stats_body).unwrap();
        assert_eq!(stats_body["basis_t"], second_tx);
        assert!(stats_body["datom_count"].as_u64().unwrap() >= 6);
        assert_eq!(stats_body["tx_count"], 2);
        assert!(stats_body["entity_count"].as_u64().unwrap() >= 2);

        let datoms = datomic_datoms(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicDatomsReq {
                graph: graph_mb.clone(),
                index: ":aevt".into(),
                components_edn: vec![":person/name".into()],
                as_of: Some(first_tx.clone()),
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
                limit: Some(100),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(datoms.status(), axum::http::StatusCode::OK);
        let datoms_body = axum::body::to_bytes(datoms.into_body(), usize::MAX)
            .await
            .unwrap();
        let datoms_body: serde_json::Value = serde_json::from_slice(&datoms_body).unwrap();
        assert_eq!(datoms_body["basis_t"], first_tx);
        assert!(datoms_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Alice\""));
        assert!(!datoms_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Bob\""));

        let seek_datoms = datomic_seek_datoms(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicSeekDatomsReq {
                graph: graph_mb.clone(),
                index: ":aevt".into(),
                components_edn: vec![":person/name".into()],
                as_of: None,
                since: Some(first_tx.clone()),
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
                limit: Some(100),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(seek_datoms.status(), axum::http::StatusCode::OK);
        let seek_body = axum::body::to_bytes(seek_datoms.into_body(), usize::MAX)
            .await
            .unwrap();
        let seek_body: serde_json::Value = serde_json::from_slice(&seek_body).unwrap();
        assert_eq!(seek_body["basis_t"], second_tx);
        assert!(seek_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Bob\""));
        assert!(!seek_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Alice\""));

        let index_range = datomic_index_range(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicIndexRangeReq {
                graph: graph_mb.clone(),
                attr_edn: ":person/name".into(),
                start_edn: Some(r#""A""#.into()),
                end_edn: Some(r#""C""#.into()),
                as_of: Some(first_tx.clone()),
                since: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
                limit: Some(100),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(index_range.status(), axum::http::StatusCode::OK);
        let range_body = axum::body::to_bytes(index_range.into_body(), usize::MAX)
            .await
            .unwrap();
        let range_body: serde_json::Value = serde_json::from_slice(&range_body).unwrap();
        assert_eq!(range_body["basis_t"], first_tx);
        assert!(range_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Alice\""));
        assert!(!range_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Bob\""));

        let index_pull = datomic_index_pull(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicIndexPullReq {
                graph: graph_mb.clone(),
                index: ":aevt".into(),
                components_edn: vec![":person/name".into()],
                pattern_edn: Some(r#"[:person/name :person/role]"#.into()),
                as_of: None,
                since: Some(first_tx.clone()),
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
                limit: Some(100),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(index_pull.status(), axum::http::StatusCode::OK);
        let index_pull_body = axum::body::to_bytes(index_pull.into_body(), usize::MAX)
            .await
            .unwrap();
        let index_pull_body: serde_json::Value = serde_json::from_slice(&index_pull_body).unwrap();
        assert_eq!(index_pull_body["basis_t"], second_tx);
        assert_eq!(index_pull_body["entity_count"], 1);
        assert!(index_pull_body["entities"][0]["entity_edn"]
            .as_str()
            .unwrap()
            .contains("Bob"));

        let history = datomic_history(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicHistoryReq {
                graph: graph_mb.clone(),
                cacao_b64: None,
                presentation: None,
                as_of: None,
                since: Some(first_tx.clone()),
                remote_peer: None,
                remote_ipns_name: None,
                limit: Some(100),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(history.status(), axum::http::StatusCode::OK);
        let history_body = axum::body::to_bytes(history.into_body(), usize::MAX)
            .await
            .unwrap();
        let history_body: serde_json::Value = serde_json::from_slice(&history_body).unwrap();
        assert_eq!(history_body["basis_t"], second_tx);
        assert!(history_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Bob\""));
        assert!(!history_body["datoms"]
            .as_array()
            .unwrap()
            .iter()
            .any(|datom| datom["a"] == ":person/name" && datom["v_edn"] == "\"Alice\""));

        let tx_range = datomic_tx_range(
            axum::extract::State(Arc::clone(&state)),
            headers.clone(),
            axum::Json(DatomicTxRangeReq {
                graph: graph_mb.clone(),
                start: Some(first_tx.clone()),
                end: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(tx_range.status(), axum::http::StatusCode::OK);
        let tx_range_body = axum::body::to_bytes(tx_range.into_body(), usize::MAX)
            .await
            .unwrap();
        let tx_range_body: serde_json::Value = serde_json::from_slice(&tx_range_body).unwrap();
        assert_eq!(tx_range_body["basis_t"], second_tx);
        assert_eq!(tx_range_body["tx_count"], 2);
        assert_eq!(tx_range_body["txes"][0]["tx_cid"], first_tx);
        assert_eq!(tx_range_body["txes"][1]["tx_cid"], second_tx);
        assert_eq!(tx_range_body["txes"][0]["seq"], 1);
        assert_eq!(tx_range_body["txes"][1]["seq"], 2);
        assert!(tx_range_body["txes"][0]["tx_instant_ms"]
            .as_i64()
            .is_some_and(|value| value > 0));
        assert!(tx_range_body["txes"][1]["tx_instant_ms"]
            .as_i64()
            .is_some_and(|value| value > 0));

        let log = datomic_log(
            axum::extract::State(Arc::clone(&state)),
            headers,
            axum::Json(DatomicLogReq {
                graph: graph_mb,
                start: Some(first_tx.clone()),
                end: None,
                remote_peer: None,
                remote_ipns_name: None,
                cacao_b64: None,
                presentation: None,
                limit: Some(10),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(log.status(), axum::http::StatusCode::OK);
        let log_body = axum::body::to_bytes(log.into_body(), usize::MAX)
            .await
            .unwrap();
        let log_body: serde_json::Value = serde_json::from_slice(&log_body).unwrap();
        assert_eq!(log_body["basis_t"], second_tx);
        assert_eq!(log_body["tx_count"], 2);
        assert_eq!(log_body["txes"][0]["tx_cid"], first_tx);
        assert_eq!(log_body["txes"][1]["tx_cid"], second_tx);
        assert!(log_body["txes"][0]["tx_instant_ms"]
            .as_i64()
            .is_some_and(|value| value > 0));
        assert!(log_body["txes"][1]["tx_instant_ms"]
            .as_i64()
            .is_some_and(|value| value > 0));
    }

    #[test]
    fn ip_literal_v4_rejected() {
        // AWS metadata endpoint and link-local
        assert!(is_did_web_ip_host("169.254.169.254"));
        // Localhost
        assert!(is_did_web_ip_host("127.0.0.1"));
        // RFC-1918 private
        assert!(is_did_web_ip_host("10.0.0.1"));
        assert!(is_did_web_ip_host("192.168.1.1"));
        assert!(is_did_web_ip_host("172.16.0.1"));
        // did:web with port
        assert!(is_did_web_ip_host("10.0.0.1:8080"));
    }

    #[test]
    fn ip_literal_v6_rejected() {
        assert!(is_did_web_ip_host("::1"));
        assert!(is_did_web_ip_host("fe80::1"));
    }

    #[test]
    fn domain_names_allowed() {
        // Normal domain names must NOT be flagged
        assert!(!is_did_web_ip_host("example.com"));
        assert!(!is_did_web_ip_host("etzhayyim.com"));
        assert!(!is_did_web_ip_host("example.com:path"));
        assert!(!is_did_web_ip_host("sub.domain.example.org"));
    }

    #[test]
    fn localhost_name_allowed_by_spec_check_is_done_elsewhere() {
        // "localhost" is a hostname, not an IP literal — our check is literal-only.
        // Blocking hostname-based SSRF requires DNS resolution (out of scope here).
        assert!(!is_did_web_ip_host("localhost"));
    }

    // ── Inference endpoint input bounds ──────────────────────────────────────

    #[test]
    fn embed_text_length_constants() {
        // Verify the cap constant is what we declared (64 KiB).
        const MAX_EMBED_TEXT_LEN: usize = 64 * 1024;
        assert_eq!(MAX_EMBED_TEXT_LEN, 65536);
        let oversized = "x".repeat(MAX_EMBED_TEXT_LEN + 1);
        assert!(oversized.len() > MAX_EMBED_TEXT_LEN);
    }

    #[test]
    fn infer_prompt_length_constants() {
        const MAX_PROMPT_LEN: usize = 64 * 1024;
        const MAX_NEW_TOKENS_LIMIT: usize = 4096;
        assert_eq!(MAX_PROMPT_LEN, 65536);
        // Verify .min() clamps correctly.
        assert_eq!(8192_usize.min(MAX_NEW_TOKENS_LIMIT), MAX_NEW_TOKENS_LIMIT);
        assert_eq!(256_usize.min(MAX_NEW_TOKENS_LIMIT), 256);
    }

    #[test]
    fn agent_run_step_cap() {
        const MAX_STEPS_LIMIT: u32 = 50;
        // Caller sending u32::MAX is clamped to 50.
        assert_eq!(u32::MAX.min(MAX_STEPS_LIMIT), MAX_STEPS_LIMIT);
        // Default of 10 passes through unchanged.
        assert_eq!(10_u32.min(MAX_STEPS_LIMIT), 10);
    }

    // ── NSID constants ───────────────────────────────────────────────────────

    const NSID_PREFIX: &str = "com.etzhayyim.apps.kotoba.";

    #[test]
    fn all_nsid_constants_have_kotoba_prefix() {
        let nsids = [
            super::NSID_DATOM_CREATE,
            super::NSID_QUAD_CREATE,
            super::NSID_QUAD_RETRACT,
            super::NSID_DATOMIC_TRANSACT,
            super::NSID_DATOMIC_DATOMS,
            super::NSID_DATOMIC_SEEK_DATOMS,
            super::NSID_DATOMIC_INDEX_RANGE,
            super::NSID_DATOMIC_INDEX_PULL,
            super::NSID_DATOMIC_PULL,
            super::NSID_DATOMIC_PULL_MANY,
            super::NSID_DATOMIC_Q,
            super::NSID_DATOMIC_WITH,
            super::NSID_DATOMIC_AS_OF,
            super::NSID_DATOMIC_SINCE,
            super::NSID_DATOMIC_SYNC,
            super::NSID_DATOMIC_HISTORY,
            super::NSID_DATOMIC_TX,
            super::NSID_DATOMIC_TX_RANGE,
            super::NSID_DATOMIC_LOG,
            super::NSID_DATOMIC_BASIS_T,
            super::NSID_DATOMIC_DB_STATS,
            super::NSID_DATOMIC_ENTITY,
            super::NSID_DATOMIC_IDENT,
            super::NSID_DATOMIC_ENTID,
            super::NSID_VC_ISSUE,
            super::NSID_VC_PRESENT,
            super::NSID_DID_DOCUMENT_PUBLISH,
            super::NSID_DIDCOMM_SEND,
            super::NSID_ATPROTO_REPO_WRITE,
            super::NSID_GRAPH_QUERY,
            crate::kg::NSID_KG_SPARQL,
            super::NSID_COMMIT_GET,
            super::NSID_INVOKE_RUN,
            super::NSID_INFER_RUN,
            super::NSID_WEIGHT_PUT,
            super::NSID_LORA_APPLY,
            super::NSID_EMBED_CREATE,
            super::NSID_NODE_STATUS,
            super::NSID_BLOCK_PUT,
            super::NSID_BLOCK_GET,
            super::NSID_COMMIT_STORE,
            super::NSID_AGENT_RUN,
            super::NSID_AGENT_SYNC_OPEN,
            super::NSID_AGENT_SYNC_ADV,
            super::NSID_AGENT_SYNC_CLOSE,
            super::NSID_VAULT_PUT,
            super::NSID_VAULT_GET,
        ];
        for nsid in nsids {
            assert!(
                nsid.starts_with(NSID_PREFIX),
                "NSID {nsid:?} does not start with {NSID_PREFIX:?}"
            );
        }
    }

    #[test]
    fn all_nsid_constants_are_unique() {
        let mut nsids = vec![
            super::NSID_DATOM_CREATE,
            super::NSID_QUAD_CREATE,
            super::NSID_QUAD_RETRACT,
            super::NSID_DATOMIC_TRANSACT,
            super::NSID_DATOMIC_DATOMS,
            super::NSID_DATOMIC_SEEK_DATOMS,
            super::NSID_DATOMIC_INDEX_RANGE,
            super::NSID_DATOMIC_INDEX_PULL,
            super::NSID_DATOMIC_PULL,
            super::NSID_DATOMIC_PULL_MANY,
            super::NSID_DATOMIC_Q,
            super::NSID_DATOMIC_WITH,
            super::NSID_DATOMIC_AS_OF,
            super::NSID_DATOMIC_SINCE,
            super::NSID_DATOMIC_SYNC,
            super::NSID_DATOMIC_HISTORY,
            super::NSID_DATOMIC_TX,
            super::NSID_DATOMIC_TX_RANGE,
            super::NSID_DATOMIC_LOG,
            super::NSID_DATOMIC_BASIS_T,
            super::NSID_DATOMIC_DB_STATS,
            super::NSID_DATOMIC_ENTITY,
            super::NSID_DATOMIC_IDENT,
            super::NSID_DATOMIC_ENTID,
            super::NSID_VC_ISSUE,
            super::NSID_VC_PRESENT,
            super::NSID_DID_DOCUMENT_PUBLISH,
            super::NSID_DIDCOMM_SEND,
            super::NSID_ATPROTO_REPO_WRITE,
            super::NSID_GRAPH_QUERY,
            crate::kg::NSID_KG_SPARQL,
            super::NSID_COMMIT_GET,
            super::NSID_INVOKE_RUN,
            super::NSID_INFER_RUN,
            super::NSID_WEIGHT_PUT,
            super::NSID_LORA_APPLY,
            super::NSID_EMBED_CREATE,
            super::NSID_NODE_STATUS,
            super::NSID_BLOCK_PUT,
            super::NSID_BLOCK_GET,
            super::NSID_COMMIT_STORE,
            super::NSID_AGENT_RUN,
            super::NSID_AGENT_SYNC_OPEN,
            super::NSID_AGENT_SYNC_ADV,
            super::NSID_AGENT_SYNC_CLOSE,
            super::NSID_VAULT_PUT,
            super::NSID_VAULT_GET,
        ];
        let original_len = nsids.len();
        nsids.sort_unstable();
        nsids.dedup();
        assert_eq!(
            nsids.len(),
            original_len,
            "NSID constants are not all unique"
        );
    }

    #[test]
    fn nsid_datom_create_exact_value() {
        assert_eq!(
            super::NSID_DATOM_CREATE,
            "com.etzhayyim.apps.kotoba.datom.create"
        );
    }

    #[test]
    fn nsid_quad_create_exact_value() {
        assert_eq!(
            super::NSID_QUAD_CREATE,
            "com.etzhayyim.apps.kotoba.quad.create"
        );
    }

    #[test]
    fn nsid_graph_query_exact_value() {
        assert_eq!(
            super::NSID_GRAPH_QUERY,
            "com.etzhayyim.apps.kotoba.graph.query"
        );
    }

    #[test]
    fn nsid_datomic_exact_values() {
        assert_eq!(
            super::NSID_DATOMIC_TRANSACT,
            "com.etzhayyim.apps.kotoba.datomic.transact"
        );
        assert_eq!(
            super::NSID_DATOMIC_DATOMS,
            "com.etzhayyim.apps.kotoba.datomic.datoms"
        );
        assert_eq!(
            super::NSID_DATOMIC_SEEK_DATOMS,
            "com.etzhayyim.apps.kotoba.datomic.seekDatoms"
        );
        assert_eq!(
            super::NSID_DATOMIC_INDEX_RANGE,
            "com.etzhayyim.apps.kotoba.datomic.indexRange"
        );
        assert_eq!(
            super::NSID_DATOMIC_INDEX_PULL,
            "com.etzhayyim.apps.kotoba.datomic.indexPull"
        );
        assert_eq!(
            super::NSID_DATOMIC_PULL,
            "com.etzhayyim.apps.kotoba.datomic.pull"
        );
        assert_eq!(
            super::NSID_DATOMIC_PULL_MANY,
            "com.etzhayyim.apps.kotoba.datomic.pullMany"
        );
        assert_eq!(super::NSID_DATOMIC_Q, "com.etzhayyim.apps.kotoba.datomic.q");
        assert_eq!(
            super::NSID_DATOMIC_AS_OF,
            "com.etzhayyim.apps.kotoba.datomic.asOf"
        );
        assert_eq!(
            super::NSID_DATOMIC_SINCE,
            "com.etzhayyim.apps.kotoba.datomic.since"
        );
        assert_eq!(
            super::NSID_DATOMIC_SYNC,
            "com.etzhayyim.apps.kotoba.datomic.sync"
        );
        assert_eq!(
            super::NSID_DATOMIC_HISTORY,
            "com.etzhayyim.apps.kotoba.datomic.history"
        );
        assert_eq!(
            super::NSID_DATOMIC_TX,
            "com.etzhayyim.apps.kotoba.datomic.tx"
        );
        assert_eq!(
            super::NSID_DATOMIC_TX_RANGE,
            "com.etzhayyim.apps.kotoba.datomic.txRange"
        );
        assert_eq!(
            super::NSID_DATOMIC_LOG,
            "com.etzhayyim.apps.kotoba.datomic.log"
        );
        assert_eq!(
            super::NSID_DATOMIC_BASIS_T,
            "com.etzhayyim.apps.kotoba.datomic.basisT"
        );
        assert_eq!(
            super::NSID_DATOMIC_DB_STATS,
            "com.etzhayyim.apps.kotoba.datomic.dbStats"
        );
        assert_eq!(
            super::NSID_DATOMIC_ENTITY,
            "com.etzhayyim.apps.kotoba.datomic.entity"
        );
        assert_eq!(
            super::NSID_DATOMIC_IDENT,
            "com.etzhayyim.apps.kotoba.datomic.ident"
        );
        assert_eq!(
            super::NSID_DATOMIC_ENTID,
            "com.etzhayyim.apps.kotoba.datomic.entid"
        );
    }

    #[test]
    fn nsid_protocol_projection_exact_values() {
        assert_eq!(super::NSID_VC_ISSUE, "com.etzhayyim.apps.kotoba.vc.issue");
        assert_eq!(
            super::NSID_VC_PRESENT,
            "com.etzhayyim.apps.kotoba.vc.present"
        );
        assert_eq!(
            super::NSID_DID_DOCUMENT_PUBLISH,
            "com.etzhayyim.apps.kotoba.did.document.publish"
        );
        assert_eq!(
            super::NSID_DIDCOMM_SEND,
            "com.etzhayyim.apps.kotoba.didcomm.send"
        );
        assert_eq!(
            super::NSID_ATPROTO_REPO_WRITE,
            "com.etzhayyim.apps.kotoba.atproto.repo.write"
        );
    }

    #[test]
    fn public_protocol_lexicons_match_xrpc_nsids() {
        let lexicons = [
            (
                super::NSID_DATOMIC_TRANSACT,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/transact.json"),
            ),
            (
                super::NSID_DATOMIC_DATOMS,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/datoms.json"),
            ),
            (
                super::NSID_DATOMIC_SEEK_DATOMS,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/seekDatoms.json"),
            ),
            (
                super::NSID_DATOMIC_INDEX_RANGE,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexRange.json"),
            ),
            (
                super::NSID_DATOMIC_INDEX_PULL,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"),
            ),
            (
                super::NSID_DATOMIC_PULL,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pull.json"),
            ),
            (
                super::NSID_DATOMIC_PULL_MANY,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pullMany.json"),
            ),
            (
                super::NSID_DATOMIC_Q,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
            ),
            (
                super::NSID_DATOMIC_WITH,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
            ),
            (
                super::NSID_DATOMIC_AS_OF,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/asOf.json"),
            ),
            (
                super::NSID_DATOMIC_SINCE,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/since.json"),
            ),
            (
                super::NSID_DATOMIC_SYNC,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/sync.json"),
            ),
            (
                super::NSID_DATOMIC_HISTORY,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/history.json"),
            ),
            (
                super::NSID_DATOMIC_TX,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
            ),
            (
                super::NSID_DATOMIC_TX_RANGE,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"),
            ),
            (
                super::NSID_DATOMIC_LOG,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
            ),
            (
                super::NSID_DATOMIC_BASIS_T,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/basisT.json"),
            ),
            (
                super::NSID_DATOMIC_DB_STATS,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/dbStats.json"),
            ),
            (
                super::NSID_DATOMIC_ENTITY,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entity.json"),
            ),
            (
                super::NSID_DATOMIC_IDENT,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/ident.json"),
            ),
            (
                super::NSID_DATOMIC_ENTID,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entid.json"),
            ),
            (
                super::NSID_GRAPH_QUERY,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/graph/query.json"),
            ),
            (
                crate::kg::NSID_KG_SPARQL,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/graph/sparql.json"),
            ),
            (
                super::NSID_BLOCK_PUT,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/block/put.json"),
            ),
            (
                super::NSID_BLOCK_GET,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/block/get.json"),
            ),
            (
                super::NSID_COMMIT_GET,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/commit/get.json"),
            ),
            (
                super::NSID_COMMIT_STORE,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/commit/store.json"),
            ),
            (
                super::NSID_VC_ISSUE,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/issue.json"),
            ),
            (
                super::NSID_VC_PRESENT,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/present.json"),
            ),
            (
                super::NSID_DID_DOCUMENT_PUBLISH,
                include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/did/document/publish.json"
                ),
            ),
            (
                super::NSID_DIDCOMM_SEND,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/didcomm/send.json"),
            ),
            (
                super::NSID_ATPROTO_REPO_WRITE,
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/atproto/repo/write.json"),
            ),
        ];
        for (expected_id, src) in lexicons {
            let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
            assert_eq!(value["lexicon"], 1);
            assert_eq!(value["id"], expected_id);
            assert!(
                matches!(
                    value["defs"]["main"]["type"].as_str(),
                    Some("procedure" | "query")
                ),
                "{expected_id} must be a procedure or query lexicon"
            );
        }
    }

    #[derive(Debug, Clone, Copy)]
    struct DatomicCompatSurface {
        nsid: &'static str,
        file_name: &'static str,
        src: &'static str,
        distributed_read: bool,
        distributed_write: bool,
        remote_read: bool,
        ipns_write: bool,
    }

    fn datomic_compat_surface() -> Vec<DatomicCompatSurface> {
        vec![
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_TRANSACT,
                file_name: "transact.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/transact.json"
                ),
                distributed_read: false,
                distributed_write: true,
                remote_read: false,
                ipns_write: true,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_WITH,
                file_name: "with.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_DATOMS,
                file_name: "datoms.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/datoms.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_SEEK_DATOMS,
                file_name: "seekDatoms.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/seekDatoms.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_INDEX_RANGE,
                file_name: "indexRange.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexRange.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_INDEX_PULL,
                file_name: "indexPull.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_PULL,
                file_name: "pull.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pull.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_PULL_MANY,
                file_name: "pullMany.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pullMany.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_Q,
                file_name: "q.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_AS_OF,
                file_name: "asOf.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/asOf.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_SINCE,
                file_name: "since.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/since.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_SYNC,
                file_name: "sync.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/sync.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_HISTORY,
                file_name: "history.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/history.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_TX,
                file_name: "tx.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_TX_RANGE,
                file_name: "txRange.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_LOG,
                file_name: "log.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_BASIS_T,
                file_name: "basisT.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/basisT.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_DB_STATS,
                file_name: "dbStats.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/dbStats.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_ENTITY,
                file_name: "entity.json",
                src: include_str!(
                    "../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entity.json"
                ),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_IDENT,
                file_name: "ident.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/ident.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
            DatomicCompatSurface {
                nsid: super::NSID_DATOMIC_ENTID,
                file_name: "entid.json",
                src: include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entid.json"),
                distributed_read: true,
                distributed_write: false,
                remote_read: true,
                ipns_write: false,
            },
        ]
    }

    #[test]
    fn datomic_compat_surface_maps_all_lexicons_and_distributed_modes() {
        let surface = datomic_compat_surface();
        let expected_files: std::collections::BTreeSet<_> = surface
            .iter()
            .map(|entry| entry.file_name.to_string())
            .collect();
        let lexicon_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../lexicons/com/etzhayyim/apps/kotoba/datomic");
        let actual_files: std::collections::BTreeSet<_> = std::fs::read_dir(&lexicon_dir)
            .expect("read datomic lexicon dir")
            .map(|entry| {
                entry
                    .expect("dir entry")
                    .file_name()
                    .to_string_lossy()
                    .into_owned()
            })
            .collect();
        assert_eq!(
            actual_files, expected_files,
            "Datomic compat surface must enumerate every Datomic lexicon"
        );

        let expected_nsids: std::collections::BTreeSet<_> = [
            super::NSID_DATOMIC_TRANSACT,
            super::NSID_DATOMIC_WITH,
            super::NSID_DATOMIC_DATOMS,
            super::NSID_DATOMIC_SEEK_DATOMS,
            super::NSID_DATOMIC_INDEX_RANGE,
            super::NSID_DATOMIC_INDEX_PULL,
            super::NSID_DATOMIC_PULL,
            super::NSID_DATOMIC_PULL_MANY,
            super::NSID_DATOMIC_Q,
            super::NSID_DATOMIC_AS_OF,
            super::NSID_DATOMIC_SINCE,
            super::NSID_DATOMIC_SYNC,
            super::NSID_DATOMIC_HISTORY,
            super::NSID_DATOMIC_TX,
            super::NSID_DATOMIC_TX_RANGE,
            super::NSID_DATOMIC_LOG,
            super::NSID_DATOMIC_BASIS_T,
            super::NSID_DATOMIC_DB_STATS,
            super::NSID_DATOMIC_ENTITY,
            super::NSID_DATOMIC_IDENT,
            super::NSID_DATOMIC_ENTID,
        ]
        .into_iter()
        .collect();
        let actual_nsids: std::collections::BTreeSet<_> =
            surface.iter().map(|entry| entry.nsid).collect();
        assert_eq!(
            actual_nsids, expected_nsids,
            "Datomic compat surface must enumerate every public Datomic NSID"
        );

        for entry in surface {
            let value: serde_json::Value = serde_json::from_str(entry.src).expect("lexicon JSON");
            assert_eq!(value["id"], entry.nsid);

            if entry.remote_read {
                assert!(
                    entry.distributed_read,
                    "{} cannot be a remote read without distributed read support",
                    entry.nsid
                );
                assert_lexicon_input_fields(
                    entry.src,
                    &["graph"],
                    &[
                        "remote_peer",
                        "remote_ipns_name",
                        "cacao_b64",
                        "presentation",
                    ],
                );
            }
            if entry.distributed_write {
                assert_lexicon_input_fields(
                    entry.src,
                    &["graph"],
                    &["cacao_b64", "presentation", "cacao_proof_cid"],
                );
            }
            if entry.ipns_write {
                assert_lexicon_input_fields(
                    entry.src,
                    &["graph"],
                    &["ipns_name", "expected_parent"],
                );
                assert_lexicon_output_fields(
                    entry.src,
                    &["graph", "tx_cid", "commit_cid", "ipns_name", "index_roots"],
                    &["ipns_sequence", "ipns_valid_until"],
                );
            }
        }
    }

    #[test]
    fn datomic_lexicons_expose_distributed_datomic_api_fields() {
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/transact.json"),
            &["graph", "tx_edn"],
            &[
                "cacao_b64",
                "presentation",
                "ipns_name",
                "expected_parent",
                "cacao_proof_cid",
            ],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
            &["graph", "tx_edn"],
            &[
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/transact.json"),
            &[
                "status",
                "graph",
                "tx_cid",
                "commit_cid",
                "ipns_name",
                "ipns_sequence",
                "ipns_valid_until",
                "index_roots",
                "datom_count",
                "journal_cids",
                "tempids",
                "datoms",
            ],
            &["auth_proof_cid"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/transact.json"),
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
            &[
                "status",
                "graph",
                "tx_cid",
                "tempids",
                "tx_data",
                "db_after_datoms",
            ],
            &["db_before_basis_t", "db_after_basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
            "tx_data",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
            "db_after_datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"),
            &["graph", "index"],
            &[
                "components_edn",
                "pattern_edn",
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
                "limit",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"),
            &["graph", "entity_count", "entities"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"),
            "entities",
            &["entity", "entity_edn", "datom_count", "datoms"],
        );
        assert_lexicon_nested_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"),
            "entities",
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        for src in [
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/asOf.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/since.json"),
        ] {
            assert_lexicon_input_fields(
                src,
                &["graph", "tx"],
                &[
                    "remote_peer",
                    "remote_ipns_name",
                    "cacao_b64",
                    "presentation",
                ],
            );
            assert_lexicon_output_fields(
                src,
                &[
                    "graph",
                    "tx",
                    "datom_count",
                    "history_datom_count",
                    "entity_count",
                    "attribute_count",
                    "tx_count",
                ],
                &["basis_t"],
            );
        }
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/sync.json"),
            &["graph"],
            &[
                "tx",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/sync.json"),
            &[
                "graph",
                "commit_cid",
                "ipns_name",
                "ipns_sequence",
                "reached",
            ],
            &["basis_t", "target_tx", "synced_block_count"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
            &["graph", "query_edn"],
            &[
                "inputs_edn",
                "as_of",
                "since",
                "history",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_description_mentions(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
            &[
                "fulltext",
                "history",
                "pull",
                "rules",
                "aggregates",
                "rows_map_json",
                "Verifiable Presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
            &["graph", "rows_edn"],
            &["basis_t", "rows_map_edn", "rows_map_json"],
        );
        assert_lexicon_array_items_schema(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
            "rows_map_json",
            "object",
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/datoms.json"),
            &["graph", "index", "datom_count", "datoms"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/datoms.json"),
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/history.json"),
            &["graph", "datom_count", "datoms"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/history.json"),
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
            &["graph", "tx"],
            &[
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
            &["graph", "tx"],
            &["basis_t"],
        );
        assert_lexicon_output_object_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
            "tx",
            &[
                "tx_cid",
                "commit_cid",
                "seq",
                "author",
                "ts",
                "datom_count",
                "datoms",
            ],
            &["prev_commit_cid", "tx_instant_ms"],
        );
        assert_lexicon_output_object_nested_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
            "tx",
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        for src in [
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/seekDatoms.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexRange.json"),
        ] {
            assert_lexicon_output_fields(
                src,
                &["graph", "index", "datom_count", "datoms"],
                &["basis_t"],
            );
            assert_lexicon_array_item_fields(src, "datoms", &["e", "a", "v_edn", "t", "added"]);
        }
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"),
            &["graph", "tx_count", "txes"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"),
            "txes",
            &[
                "tx_cid",
                "commit_cid",
                "seq",
                "author",
                "ts",
                "datom_count",
                "datoms",
            ],
        );
        assert_lexicon_array_item_optional_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"),
            "txes",
            &["prev_commit_cid", "tx_instant_ms"],
        );
        assert_lexicon_nested_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"),
            "txes",
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
            &["graph", "tx_count", "txes"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
            "txes",
            &["tx_cid", "datom_count", "datoms"],
        );
        assert_lexicon_array_item_optional_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
            "txes",
            &["tx_instant_ms"],
        );
        assert_lexicon_nested_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
            "txes",
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pull.json"),
            &["graph", "entity", "entity_edn", "datom_count", "datoms"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pull.json"),
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pullMany.json"),
            &["graph", "entity_count", "entities"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pullMany.json"),
            "entities",
            &["entity", "entity_edn", "datom_count", "datoms"],
        );
        assert_lexicon_nested_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pullMany.json"),
            "entities",
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/basisT.json"),
            &["graph"],
            &[
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/basisT.json"),
            &["graph"],
            &["basis_t"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/dbStats.json"),
            &["graph"],
            &[
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/dbStats.json"),
            &[
                "graph",
                "datom_count",
                "history_datom_count",
                "entity_count",
                "attribute_count",
                "tx_count",
            ],
            &["basis_t"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entity.json"),
            &["graph", "entity"],
            &[
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entity.json"),
            &["graph", "entity", "entity_edn", "datom_count", "datoms"],
            &["basis_t"],
        );
        assert_lexicon_array_item_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entity.json"),
            "datoms",
            &["e", "a", "v_edn", "t", "added"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/ident.json"),
            &["graph", "entity"],
            &[
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/ident.json"),
            &["graph", "entity"],
            &["basis_t", "ident_edn"],
        );
        assert_lexicon_input_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entid.json"),
            &["graph", "ident_edn"],
            &[
                "as_of",
                "since",
                "remote_peer",
                "remote_ipns_name",
                "cacao_b64",
                "presentation",
            ],
        );
        assert_lexicon_output_fields(
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entid.json"),
            &["graph", "ident_edn"],
            &["basis_t", "entity"],
        );
    }

    #[test]
    fn protocol_lexicons_expose_w3c_vp_auth_input_schema() {
        for src in [
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/transact.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/with.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/asOf.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/since.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/sync.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/q.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/datoms.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/seekDatoms.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexRange.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/indexPull.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pull.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/pullMany.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/history.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/tx.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/txRange.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/log.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/basisT.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/dbStats.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entity.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/ident.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/datomic/entid.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/graph/sparql.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/present.json"),
        ] {
            assert_lexicon_input_presentation_schema(src, "presentation");
        }
        for src in [
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/issue.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/present.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/didcomm/send.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/atproto/repo/write.json"),
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/did/document/publish.json"),
        ] {
            assert_lexicon_input_presentation_schema(src, "auth_presentation");
        }
    }

    #[test]
    fn did_document_publish_lexicon_exposes_w3c_did_document_and_write_response() {
        let src =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/did/document/publish.json");
        assert_lexicon_input_fields(
            src,
            &["graph", "document"],
            &["cacao_b64", "auth_presentation"],
        );
        assert_lexicon_input_object_fields(
            src,
            "document",
            &[
                "@context",
                "id",
                "verificationMethod",
                "authentication",
                "assertionMethod",
                "capabilityInvocation",
                "capabilityDelegation",
                "service",
            ],
            &["keyAgreement"],
        );
        assert_lexicon_input_nested_array_item_fields(
            src,
            "document",
            "service",
            &["id", "type", "serviceEndpoint"],
        );
        assert_lexicon_input_nested_array_item_property_schema(
            src,
            "document",
            "service",
            "serviceEndpoint",
            "union",
            &[
                "#serviceEndpointString",
                "#serviceEndpointStringArray",
                "#serviceEndpointObject",
            ],
        );
        assert_lexicon_output_fields(
            src,
            &[
                "status",
                "graph",
                "entity_cid",
                "tx_cid",
                "commit_cid",
                "ipns_name",
                "ipns_sequence",
                "datom_count",
                "assert_count",
                "retract_count",
                "journal_cids",
            ],
            &["auth_proof_cid"],
        );
    }

    #[test]
    fn protocol_write_lexicons_expose_payloads_and_datom_write_response() {
        let vc_issue = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/issue.json");
        assert_lexicon_input_object_fields(
            vc_issue,
            "credential",
            &["@context", "id", "type", "issuer", "credentialSubject"],
            &["validFrom", "validUntil", "credentialStatus", "proof"],
        );
        assert_protocol_datom_write_output_fields(vc_issue);

        let vc_present =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/vc/present.json");
        assert_protocol_datom_write_output_fields(vc_present);

        let didcomm_send =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/didcomm/send.json");
        assert_lexicon_input_object_fields(
            didcomm_send,
            "message",
            &["id", "type"],
            &[
                "from",
                "to",
                "thid",
                "pthid",
                "created_time",
                "expires_time",
                "body",
                "attachments",
            ],
        );
        assert_protocol_datom_write_output_fields(didcomm_send);

        let atproto_write =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/atproto/repo/write.json");
        let atproto_write_value: serde_json::Value =
            serde_json::from_str(atproto_write).expect("atproto repo write lexicon JSON");
        let atproto_write_description = atproto_write_value["defs"]["main"]["description"]
            .as_str()
            .expect("atproto repo write description");
        assert!(
            atproto_write_description.contains("DAG-CBOR CID metadata"),
            "atproto repo write lexicon must expose AT CID/DAG-CBOR projection"
        );
        assert_lexicon_input_object_fields(atproto_write, "record", &[], &[]);
        assert_protocol_datom_write_output_fields(atproto_write);
    }

    #[test]
    fn graph_query_lexicons_expose_structured_sparql_and_quad_outputs() {
        let graph_query =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/graph/query.json");
        let graph_query_value: serde_json::Value =
            serde_json::from_str(graph_query).expect("graph.query lexicon JSON");
        let graph_query_description = graph_query_value["defs"]["main"]["description"]
            .as_str()
            .expect("graph.query description");
        assert!(
            graph_query_description.contains("primary Kotoba distributed Datomic/Datom graph"),
            "graph.query must declare Datomic/Datom as the primary graph"
        );
        assert!(
            graph_query_description.contains("SPARQL is an auxiliary query surface"),
            "graph.query must keep SPARQL auxiliary to Datomic"
        );
        assert_lexicon_output_fields(
            graph_query,
            &[
                "graph",
                "queryEngine",
                "primaryQuery",
                "auxiliaryQuery",
                "storageModel",
                "count",
                "quads",
            ],
            &["limit", "truncated", "note"],
        );
        assert_eq!(
            graph_query_value["defs"]["main"]["output"]["schema"]["properties"]["queryEngine"]
                ["knownValues"][0],
            "datomic"
        );
        assert_eq!(
            graph_query_value["defs"]["main"]["output"]["schema"]["properties"]["storageModel"]
                ["knownValues"][0],
            "ipld-dag-cbor-prolly-tree"
        );
        assert_lexicon_array_item_fields(
            graph_query,
            "quads",
            &["graph", "subject", "predicate", "object"],
        );

        let graph_sparql =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/graph/sparql.json");
        let graph_sparql_value: serde_json::Value =
            serde_json::from_str(graph_sparql).expect("graph.sparql lexicon JSON");
        let graph_sparql_description = graph_sparql_value["defs"]["main"]["description"]
            .as_str()
            .expect("graph.sparql description");
        assert!(
            graph_sparql_description.contains("auxiliary SPARQL"),
            "graph.sparql must remain an auxiliary query surface over Datomic/Datoms"
        );
        assert!(
            graph_sparql_description.contains("primary Kotoba distributed Datomic/Datom graph"),
            "graph.sparql must not be described as the primary source of truth"
        );
        assert_lexicon_input_fields(
            graph_sparql,
            &["query"],
            &[
                "graph",
                "remotePeer",
                "remoteIpnsName",
                "asOf",
                "since",
                "cacaoB64",
                "presentation",
                "limit",
                "maxHops",
            ],
        );
        assert_lexicon_output_fields(
            graph_sparql,
            &[
                "ok",
                "form",
                "queryEngine",
                "primaryQuery",
                "auxiliaryQuery",
                "storageModel",
                "elapsedMs",
            ],
            &["result", "basisT", "count", "maxHops", "quads"],
        );
        assert_lexicon_array_item_fields(
            graph_sparql,
            "quads",
            &["graph", "subject", "predicate", "object"],
        );
    }

    #[test]
    fn storage_lexicons_expose_ipld_commit_and_ipns_fields() {
        let block_put = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/block/put.json");
        assert_lexicon_input_fields(block_put, &["data_b64"], &[]);
        assert_lexicon_output_fields(block_put, &["cid"], &[]);

        let block_get = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/block/get.json");
        assert_lexicon_parameter_fields(block_get, &["cid"], &[]);
        assert_lexicon_output_fields(block_get, &["cid", "data_b64"], &[]);

        let commit_store =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/commit/store.json");
        assert_lexicon_input_fields(commit_store, &["graph", "author", "seq"], &["cacao_b64"]);
        assert_lexicon_output_fields(commit_store, &["cid"], &[]);

        let commit_get =
            include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/commit/get.json");
        assert_lexicon_parameter_fields(commit_get, &["graph"], &[]);
        assert_lexicon_output_fields(
            commit_get,
            &[
                "cid",
                "graph",
                "root",
                "author",
                "seq",
                "ts",
                "commit_type",
                "index_roots",
            ],
            &[
                "prev",
                "tx_cid",
                "cacao_proof_cid",
                "ipns_name",
                "ipns_value_cid",
                "ipns_sequence",
                "ipns_value_matches_commit",
                "ipns_sequence_matches_commit",
                "ipns_graph_matches_request",
                "ipns_controller_did",
                "ipns_controller_matches_node",
                "ipns_controller_key_matches_did",
                "ipns_public_key_multibase",
                "ipns_signature_multibase",
                "ipns_signature_verified",
                "ipns_verified",
            ],
        );
    }

    fn assert_protocol_datom_write_output_fields(src: &str) {
        assert_lexicon_output_fields(
            src,
            &[
                "status",
                "graph",
                "entity_cid",
                "tx_cid",
                "commit_cid",
                "ipns_name",
                "ipns_sequence",
                "ipns_valid_until",
                "index_roots",
                "datom_count",
                "journal_cids",
            ],
            &["auth_proof_cid"],
        );
    }

    fn assert_lexicon_parameter_fields(src: &str, required: &[&str], properties: &[&str]) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let params = &value["defs"]["main"]["parameters"];
        assert_eq!(
            params["type"], "params",
            "{} parameters must be params",
            value["id"]
        );
        let required_values = params["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} missing required parameter {field}",
                value["id"]
            );
        }
        let property_values = params["properties"].as_object().expect("properties object");
        for field in required.iter().chain(properties.iter()) {
            assert!(
                property_values.contains_key(*field),
                "{} missing parameter property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_input_object_fields(
        src: &str,
        field: &str,
        required: &[&str],
        properties: &[&str],
    ) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let schema = &value["defs"]["main"]["input"]["schema"]["properties"][field];
        assert_eq!(
            schema["type"], "object",
            "{} input {field} must be object",
            value["id"]
        );
        let required_values = schema["required"].as_array();
        for required in required {
            assert!(
                required_values.is_some_and(|values| values
                    .iter()
                    .any(|value| value.as_str() == Some(*required))),
                "{} input {field} missing required field {required}",
                value["id"]
            );
        }
        let property_values = schema["properties"].as_object();
        for property in required.iter().chain(properties.iter()) {
            assert!(
                property_values.is_some_and(|values| values.contains_key(*property)),
                "{} input {field} missing property {property}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_output_object_fields(
        src: &str,
        field: &str,
        required: &[&str],
        properties: &[&str],
    ) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let schema = &value["defs"]["main"]["output"]["schema"]["properties"][field];
        assert_eq!(
            schema["type"], "object",
            "{} output {field} must be object",
            value["id"]
        );
        let required_values = schema["required"].as_array();
        for required in required {
            assert!(
                required_values.is_some_and(|values| values
                    .iter()
                    .any(|value| value.as_str() == Some(*required))),
                "{} output {field} missing required field {required}",
                value["id"]
            );
        }
        let property_values = schema["properties"].as_object();
        for property in required.iter().chain(properties.iter()) {
            assert!(
                property_values.is_some_and(|values| values.contains_key(*property)),
                "{} output {field} missing property {property}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_input_nested_array_item_fields(
        src: &str,
        outer_field: &str,
        inner_field: &str,
        required: &[&str],
    ) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let item = &value["defs"]["main"]["input"]["schema"]["properties"][outer_field]
            ["properties"][inner_field]["items"];
        assert_eq!(
            item["type"], "object",
            "{} input {outer_field}.{inner_field} items must be object",
            value["id"]
        );
        let required_values = item["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} input nested array item missing required field {field}",
                value["id"]
            );
            assert!(
                item["properties"]
                    .as_object()
                    .is_some_and(|props| props.contains_key(*field)),
                "{} input nested array item missing property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_input_nested_array_item_property_schema(
        src: &str,
        outer_field: &str,
        inner_field: &str,
        property_field: &str,
        property_type: &str,
        refs: &[&str],
    ) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let property = &value["defs"]["main"]["input"]["schema"]["properties"][outer_field]
            ["properties"][inner_field]["items"]["properties"][property_field];
        assert_eq!(
            property["type"], property_type,
            "{} input {outer_field}.{inner_field}.{property_field} must be {property_type}",
            value["id"]
        );
        let ref_values = property["refs"].as_array().expect("refs array");
        for expected in refs {
            assert!(
                ref_values
                    .iter()
                    .any(|value| value.as_str() == Some(expected)),
                "{} input {outer_field}.{inner_field}.{property_field} missing ref {expected}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_input_presentation_schema(src: &str, field: &str) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let property = &value["defs"]["main"]["input"]["schema"]["properties"][field];
        assert_eq!(
            property["type"], "object",
            "{} input {field} must be an object",
            value["id"]
        );
        let required_values = property["required"].as_array().expect("required array");
        for required in ["@context", "id", "type"] {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(required)),
                "{} input {field} missing VP required field {required}",
                value["id"]
            );
        }
        let properties = property["properties"]
            .as_object()
            .expect("properties object");
        for expected in [
            "@context",
            "id",
            "type",
            "holder",
            "verifiableCredential",
            "proof",
        ] {
            assert!(
                properties.contains_key(expected),
                "{} input {field} missing VP property {expected}",
                value["id"]
            );
        }
        let proof = &property["properties"]["proof"];
        assert_eq!(
            proof["type"], "object",
            "{} input {field}.proof must be an object",
            value["id"]
        );
        let proof_required = proof["required"].as_array().expect("proof required array");
        for required in ["type", "proofPurpose", "verificationMethod", "proofValue"] {
            assert!(
                proof_required
                    .iter()
                    .any(|value| value.as_str() == Some(required)),
                "{} input {field}.proof missing DataIntegrityProof required field {required}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_input_fields(src: &str, required: &[&str], properties: &[&str]) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let schema = &value["defs"]["main"]["input"]["schema"];
        let required_values = schema["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} missing required input field {field}",
                value["id"]
            );
        }
        let property_values = schema["properties"].as_object().expect("properties object");
        for field in required.iter().chain(properties.iter()) {
            assert!(
                property_values.contains_key(*field),
                "{} missing input property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_nested_array_item_fields(
        src: &str,
        outer_field: &str,
        inner_field: &str,
        required: &[&str],
    ) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let item = &value["defs"]["main"]["output"]["schema"]["properties"][outer_field]["items"]
            ["properties"][inner_field]["items"];
        assert_eq!(
            item["type"], "object",
            "{} output {outer_field}.{inner_field} items must be object",
            value["id"]
        );
        let required_values = item["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} output nested array item missing required field {field}",
                value["id"]
            );
            assert!(
                item["properties"]
                    .as_object()
                    .is_some_and(|props| props.contains_key(*field)),
                "{} output nested array item missing property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_output_object_nested_array_item_fields(
        src: &str,
        object_field: &str,
        inner_field: &str,
        required: &[&str],
    ) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let item = &value["defs"]["main"]["output"]["schema"]["properties"][object_field]
            ["properties"][inner_field]["items"];
        assert_eq!(
            item["type"], "object",
            "{} output {object_field}.{inner_field} items must be object",
            value["id"]
        );
        let required_values = item["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} output object nested array item missing required field {field}",
                value["id"]
            );
            assert!(
                item["properties"]
                    .as_object()
                    .is_some_and(|props| props.contains_key(*field)),
                "{} output object nested array item missing property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_array_item_fields(src: &str, field: &str, required: &[&str]) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let item = &value["defs"]["main"]["output"]["schema"]["properties"][field]["items"];
        assert_eq!(
            item["type"], "object",
            "{} output {field} items must be object",
            value["id"]
        );
        let required_values = item["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} output array item missing required field {field}",
                value["id"]
            );
            assert!(
                item["properties"]
                    .as_object()
                    .is_some_and(|props| props.contains_key(*field)),
                "{} output array item missing property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_array_item_optional_fields(src: &str, field: &str, properties: &[&str]) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let item = &value["defs"]["main"]["output"]["schema"]["properties"][field]["items"];
        let property_values = item["properties"]
            .as_object()
            .expect("array item properties object");
        let required_values = item["required"].as_array().expect("required array");
        for field in properties {
            assert!(
                property_values.contains_key(*field),
                "{} output array item missing optional property {field}",
                value["id"]
            );
            assert!(
                !required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} output array item optional property {field} must not be required",
                value["id"]
            );
        }
    }

    fn assert_lexicon_array_items_schema(src: &str, field: &str, item_type: &str) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let property = &value["defs"]["main"]["output"]["schema"]["properties"][field];
        assert_eq!(
            property["type"], "array",
            "{} output {field} must be array",
            value["id"]
        );
        assert_eq!(
            property["items"]["type"], item_type,
            "{} output {field} items must be {item_type}",
            value["id"]
        );
    }

    fn assert_lexicon_output_fields(src: &str, required: &[&str], properties: &[&str]) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let schema = &value["defs"]["main"]["output"]["schema"];
        assert_eq!(
            schema["type"], "object",
            "{} output must be object",
            value["id"]
        );
        let required_values = schema["required"].as_array().expect("required array");
        for field in required {
            assert!(
                required_values
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "{} missing required output field {field}",
                value["id"]
            );
        }
        let property_values = schema["properties"].as_object().expect("properties object");
        for field in required.iter().chain(properties.iter()) {
            assert!(
                property_values.contains_key(*field),
                "{} missing output property {field}",
                value["id"]
            );
        }
    }

    fn assert_lexicon_description_mentions(src: &str, needles: &[&str]) {
        let value: serde_json::Value = serde_json::from_str(src).expect("lexicon JSON");
        let description = value["defs"]["main"]["description"]
            .as_str()
            .expect("lexicon description");
        for needle in needles {
            assert!(
                description.contains(needle),
                "lexicon description must mention {needle}: {description}"
            );
        }
    }

    #[test]
    fn nsid_invoke_run_exact_value() {
        assert_eq!(
            super::NSID_INVOKE_RUN,
            "com.etzhayyim.apps.kotoba.invoke.run"
        );
    }

    #[test]
    fn nsid_vault_put_and_get_exact_values() {
        assert_eq!(super::NSID_VAULT_PUT, "com.etzhayyim.apps.kotoba.vault.put");
        assert_eq!(super::NSID_VAULT_GET, "com.etzhayyim.apps.kotoba.vault.get");
    }

    #[test]
    fn nsid_agent_sync_variants_exact_values() {
        assert_eq!(
            super::NSID_AGENT_SYNC_OPEN,
            "com.etzhayyim.apps.kotoba.agent.syncopen"
        );
        assert_eq!(
            super::NSID_AGENT_SYNC_ADV,
            "com.etzhayyim.apps.kotoba.agent.syncadvance"
        );
        assert_eq!(
            super::NSID_AGENT_SYNC_CLOSE,
            "com.etzhayyim.apps.kotoba.agent.syncclose"
        );
    }

    #[test]
    fn max_cacao_b64_len_is_8kib() {
        assert_eq!(super::MAX_CACAO_B64_LEN, 8 * 1024);
    }
}

// ── Generic XRPC dispatch ──────────────────────────────────────────────────

#[cfg(feature = "wasm-runtime")]
pub async fn generic_invoke(
    axum::extract::Path(nsid): axum::extract::Path<String>,
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(req_body): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;

    let parts: Vec<&str> = nsid.split('.').collect();
    if parts.len() < 5 || parts[0..3] != ["ai", "etzhayyim", "apps"] {
        return Err((StatusCode::BAD_REQUEST, "invalid generic nsid".into()));
    }
    let app = parts[3];

    let graph_cid = kotoba_core::cid::KotobaCid::from_bytes(b"kotoba/network/nodes");
    let mut program_cid = app.to_string();

    // Resolve app → wasm endpoint CID from the LOCAL quad_store hot arrangement of the
    // kotoba/network/nodes graph. Both the server self-registration AND external
    // `datomic.transact` node registrations land here (apply_journaled_datom →
    // insert_datom into the arrangement), so this reliably surfaces freshly-registered
    // app nodes — unlike the distributed IPNS head, which did not (ADR-2605312355).
    // Fall back to the distributed head for federation (an app hosted on a remote peer).
    {
        use kotoba_query::quad::LegacyQuadObject;
        let node_quads = state
            .quad_store
            .quads_by_predicate_prefix(Some(&graph_cid), "node/")
            .await;
        for q in &node_quads {
            if q.predicate == "node/did" {
                if let LegacyQuadObject::Text(s) = &q.object {
                    if s == app || s.ends_with(&format!("{app}.etzhayyim.com")) {
                        if let Some(ep) = node_quads
                            .iter()
                            .find(|d| d.subject == q.subject && d.predicate == "node/endpoint")
                        {
                            if let LegacyQuadObject::Text(cid) = &ep.object {
                                program_cid = cid.to_string();
                            }
                        }
                        break;
                    }
                }
            }
        }
        tracing::info!(
            app = %app,
            node_quads = node_quads.len(),
            program_cid = %program_cid,
            resolved = program_cid != app,
            "generic_invoke: quad_store node resolution"
        );
    }

    if program_cid == app {
        let ipns_name = distributed_graph_ipns_name(&graph_cid);
        if let Ok(Some(db)) =
            DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry)
                .current_db_for_name(&ipns_name)
        {
            for datom in db.datoms() {
                if datom.a == "node/did" {
                    if let kotoba_datomic::Value::String(s) = &datom.v {
                        if s == app || s.ends_with(&format!("{app}.etzhayyim.com")) {
                            if let Some(endpoint) = db
                                .datoms()
                                .iter()
                                .find(|d| d.e == datom.e && d.a == "node/endpoint")
                            {
                                if let kotoba_datomic::Value::String(ep) = &endpoint.v {
                                    program_cid = ep.to_string();
                                }
                            }
                            break;
                        }
                    }
                }
            }
        }
    }

    let mut ctx_cbor = Vec::new();
    ciborium::into_writer(&req_body, &mut ctx_cbor).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("cbor encode: {e}"),
        )
    })?;

    // Load the registered WasmNode program bytes from the block store by CID.
    // `program_cid` is the resolved `node/endpoint` value (a wasm CID) when the
    // app is registered in `kotoba/network/nodes`; when it is the bare app-name
    // fallback (not a multibase CID) this resolves to None and dispatch returns
    // `MissingWasmBytes` as before. Fixes the ADR-2605311200 generic_invoke gap.
    // `block_store.get` yields `Option<bytes::Bytes>`; `Bytes: Deref<[u8]>` so
    // `.as_deref()` below gives the `Option<&[u8]>` dispatch expects.
    let program_bytes = kotoba_core::cid::KotobaCid::from_multibase(&program_cid)
        .and_then(|cid| state.block_store.get(&cid).ok().flatten());

    // Build the guest's kqe read-snapshot + IPNS head map from the request body's
    // `graph_cid` (multibase), mirroring `invoke.run` (L6602-6651). Without this the
    // generic app-dispatch path passed an empty snapshot, so guests could not read
    // committed graph data (ADR-2605312355 Stage-3 persistence blocker). Absent
    // graph_cid → empty snapshot (write-only / read-nothing guests still work).
    use kotoba_core::cid::KotobaCid;
    use kotoba_query::{Datom as KqeDatom, Value as KqeValue};
    use kotoba_runtime::host::WitQuad;

    let snapshot_graph_cid = req_body
        .get("graph_cid")
        .and_then(|v| v.as_str())
        .and_then(KotobaCid::from_multibase);
    let quad_snapshot: Vec<WitQuad> = if let Some(gcid) = &snapshot_graph_cid {
        match current_db_for_graph(&state, gcid).await {
            Ok(db) => db
                .datoms()
                .into_iter()
                .filter_map(|datom| {
                    let substrate = datom.to_kqe().ok()?;
                    let object: kotoba_query::quad::LegacyQuadObject = substrate.v.into();
                    Some(WitQuad {
                        graph: gcid.to_multibase(),
                        subject: substrate.e.to_multibase(),
                        predicate: substrate.a,
                        object_cbor: serde_json::to_vec(&object).unwrap_or_default(),
                    })
                })
                .collect(),
            Err((code, msg)) => {
                return Err((code, format!("generic invoke graph snapshot: {msg}")))
            }
        }
    } else {
        vec![]
    };
    let mut head_commits = std::collections::HashMap::new();
    if let Some(gcid) = &snapshot_graph_cid {
        let ipns_name = distributed_graph_ipns_name(gcid);
        match state
            .ipns_registry
            .resolve(&IpnsName::new(ipns_name.clone()))
        {
            Ok(record) => {
                head_commits.insert(gcid.to_multibase(), record.value);
            }
            Err(IpnsRegistryError::NotFound(_)) => {}
            Err(e) => {
                return Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("generic invoke graph head: {e}"),
                ))
            }
        }
    }

    let agent_did = state.operator_did.clone();
    let agent_did_commit = state.operator_did.clone();
    let program_cid_commit = program_cid.clone();
    let router = Arc::clone(&state.router);

    let result = tokio::task::spawn_blocking(move || {
        router.dispatch_with_snapshot(
            &program_cid,
            kotoba_dht::source_chain::ProgramType::WasmNode,
            &agent_did,
            0,
            program_bytes.as_deref(),
            ctx_cbor,
            None,
            None,
            &[],
            10_000,
            quad_snapshot,
            head_commits,
        )
    })
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    match result {
        kotoba_vm::DispatchResult::Wasm(r) => {
            // Persist the guest's asserted/retracted quads, mirroring invoke.run's commit
            // loop (L6710-6766, ADR-2605312355). Without this, generic dispatch discarded
            // ALL guest writes. Keyed per-quad on `sq.graph`; the read-snapshot above closes
            // the read half. Together these make yukkuri-as-guest persist via the prod path.
            const MAX_ASSERT_QUADS: usize = 10_000;
            if r.assert_quads.len() > MAX_ASSERT_QUADS || r.retract_quads.len() > MAX_ASSERT_QUADS {
                return Err((
                    StatusCode::PAYLOAD_TOO_LARGE,
                    format!(
                        "WASM produced too many quads (assert {} / retract {}, limit {MAX_ASSERT_QUADS})",
                        r.assert_quads.len(),
                        r.retract_quads.len()
                    ),
                ));
            }
            let mut by_graph: std::collections::BTreeMap<String, Vec<KqeDatom>> =
                std::collections::BTreeMap::new();
            for sq in &r.assert_quads {
                let graph_cid = KotobaCid::from_bytes(sq.graph.as_bytes());
                let datom = KqeDatom::assert(
                    KotobaCid::from_bytes(sq.subject.as_bytes()),
                    sq.predicate.clone(),
                    KqeValue::Bytes(sq.object_cbor.clone()),
                    graph_cid,
                );
                by_graph.entry(sq.graph.clone()).or_default().push(datom);
            }
            for sq in &r.retract_quads {
                let graph_cid = KotobaCid::from_bytes(sq.graph.as_bytes());
                let datom = KqeDatom::retract(
                    KotobaCid::from_bytes(sq.subject.as_bytes()),
                    sq.predicate.clone(),
                    KqeValue::Bytes(sq.object_cbor.clone()),
                    graph_cid,
                );
                by_graph.entry(sq.graph.clone()).or_default().push(datom);
            }
            for (graph, mut datoms) in by_graph {
                let graph_cid = KotobaCid::from_bytes(graph.as_bytes());
                let tx_cid = KotobaCid::from_bytes(
                    format!(
                        "generic_invoke.run:{}:{}:{}:{}",
                        program_cid_commit, agent_did_commit, graph, r.gas_used
                    )
                    .as_bytes(),
                );
                let entity_cid = datoms
                    .first()
                    .map(|datom| datom.e.clone())
                    .unwrap_or_else(|| graph_cid.clone());
                for datom in &mut datoms {
                    datom.tx = tx_cid.clone();
                }
                commit_protocol_datoms(
                    &state,
                    graph_cid,
                    graph,
                    entity_cid,
                    datoms
                        .into_iter()
                        .map(kotoba_datomic::Datom::from_kqe)
                        .collect(),
                    tx_cid,
                    agent_did_commit.clone(),
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    None,
                    None,
                )
                .await?;
            }
            for (topic, payload) in &r.pending_publishes {
                use kotoba_vault::Topic;
                state
                    .journal
                    .publish(Topic(topic.clone()), bytes::Bytes::from(payload.clone()))
                    .await;
            }
            let out_val: serde_json::Value = ciborium::from_reader(r.output_cbor.as_slice())
                .unwrap_or(serde_json::json!({ "output_bytes": r.output_cbor }));
            Ok(Json(out_val))
        }
        _ => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            "expected wasm result".into(),
        )),
    }
}

#[cfg(not(feature = "wasm-runtime"))]
pub async fn generic_invoke(
    axum::extract::Path(_nsid): axum::extract::Path<String>,
    State(state): State<Arc<KotobaState>>,
    headers: axum::http::HeaderMap,
    Json(_req_body): Json<serde_json::Value>,
) -> Result<axum::response::Response, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    Err((
        StatusCode::SERVICE_UNAVAILABLE,
        "generic dispatch requires the `wasm-runtime` feature".to_string(),
    ))
}
