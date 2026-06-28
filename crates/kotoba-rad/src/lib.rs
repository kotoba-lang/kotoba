//! kotoba-rad: sovereign repository identity and ref authorization over
//! [`kotoba-git`].
//!
//! This crate is the R1 layer from `docs/ADR-kotoba-rad-git-sovereign-repo.md`.
//! It deliberately does **not** reimplement Git storage. `kotoba-git` remains
//! the byte-exact object bridge; `kotoba-rad` validates who may move refs and
//! how repository identity evolves.

use std::collections::{BTreeMap, BTreeSet};

use kotoba_core::cid::KotobaCid;
use kotoba_git::{commit_parents, log, object_cid, resolve_ref, GitOid, GitStore};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum RadError {
    #[error("delegate not found or inactive: {0}")]
    DelegateNotFound(String),
    #[error("delegate {actor} lacks capability {capability}")]
    MissingCapability {
        actor: String,
        capability: Capability,
    },
    #[error("event prev mismatch")]
    PrevMismatch,
    #[error("event sequence mismatch: expected {expected}, got {got}")]
    SeqMismatch { expected: u64, got: u64 },
    #[error("invalid oid: {0}")]
    InvalidOid(String),
    #[error("target object not found: {0}")]
    ObjectNotFound(String),
    #[error("ref update is not fast-forward: {name}")]
    NonFastForward { name: String },
    #[error("force update not allowed for ref: {0}")]
    ForceUpdateDenied(String),
    #[error("private object publish requires ciphertext cid")]
    PrivatePublishWithoutCiphertext,
    #[error("cbor encode error: {0}")]
    Cbor(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Capability {
    IdentityUpdate,
    RefCreate,
    RefUpdate,
    RefDelete,
    RefForceUpdate,
    ObjectPublish,
    GrantWrite,
    GrantRevoke,
}

impl std::fmt::Display for Capability {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{self:?}")
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RepoVisibility {
    Public,
    Private,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Delegate {
    pub did: String,
    pub role: String,
    pub can: BTreeSet<Capability>,
}

impl Delegate {
    pub fn new(
        did: impl Into<String>,
        role: impl Into<String>,
        can: impl IntoIterator<Item = Capability>,
    ) -> Self {
        Self {
            did: did.into(),
            role: role.into(),
            can: can.into_iter().collect(),
        }
    }

    pub fn can(&self, capability: Capability) -> bool {
        self.can.contains(&capability)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RepoIdentity {
    pub version: u32,
    pub name: String,
    pub description: Option<String>,
    pub visibility: RepoVisibility,
    pub default_branch: String,
    pub git_hash_suite: String,
    pub block_hash_suite: String,
    pub delegates: Vec<Delegate>,
    pub created_at: u64,
}

impl RepoIdentity {
    pub fn new(
        name: impl Into<String>,
        visibility: RepoVisibility,
        default_branch: impl Into<String>,
        delegates: Vec<Delegate>,
        created_at: u64,
    ) -> Self {
        Self {
            version: 1,
            name: name.into(),
            description: None,
            visibility,
            default_branch: default_branch.into(),
            git_hash_suite: "git.sha1".to_string(),
            block_hash_suite: "cidv1.dag-cbor.sha2-256".to_string(),
            delegates,
            created_at,
        }
    }

    pub fn rid(&self) -> Result<RepoRid, RadError> {
        canonical_cid(self).map(RepoRid)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct RepoRid(pub KotobaCid);

impl RepoRid {
    pub fn to_multibase(&self) -> String {
        self.0.to_multibase()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RefUpdate {
    pub name: String,
    pub old: Option<String>,
    pub new: String,
    #[serde(default)]
    pub allow_non_fast_forward: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObjectPublish {
    pub git_oid: String,
    pub plaintext_cid: Option<KotobaCid>,
    pub ciphertext_cid: Option<KotobaCid>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RecipientGrant {
    pub epoch: u64,
    pub recipient: String,
    pub kem: Vec<String>,
    pub aead: String,
    pub wrapped_key_cid: KotobaCid,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", content = "body", rename_all = "kebab-case")]
pub enum RepoEventKind {
    IdentityUpdate { identity: RepoIdentity },
    RefCreate { update: RefUpdate },
    RefUpdate { update: RefUpdate },
    RefDelete { name: String, old: String },
    ObjectPublish { publish: ObjectPublish },
    GrantAdd { grant: RecipientGrant },
    GrantRevoke { epoch: u64, recipient: String },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RepoEvent {
    pub rid: RepoRid,
    pub seq: u64,
    pub prev: Option<KotobaCid>,
    pub actor: String,
    pub ts: u64,
    pub kind: RepoEventKind,
    /// Signature bytes are carried by the wire format, but signature verification
    /// is a later integration with `kotoba-auth`. R1 fixes the canonical bytes.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub sig: Vec<u8>,
}

impl RepoEvent {
    pub fn signing_bytes(&self) -> Result<Vec<u8>, RadError> {
        #[derive(Serialize)]
        struct SigningPayload<'a> {
            rid: &'a RepoRid,
            seq: u64,
            prev: &'a Option<KotobaCid>,
            actor: &'a str,
            ts: u64,
            kind: &'a RepoEventKind,
        }
        let payload = SigningPayload {
            rid: &self.rid,
            seq: self.seq,
            prev: &self.prev,
            actor: &self.actor,
            ts: self.ts,
            kind: &self.kind,
        };
        canonical_bytes(&payload)
    }

    pub fn cid(&self) -> Result<KotobaCid, RadError> {
        Ok(KotobaCid::from_bytes(&self.signing_bytes()?))
    }
}

#[derive(Debug, Clone)]
pub struct RepoState {
    pub identity: RepoIdentity,
    pub rid: RepoRid,
    pub journal_head: Option<KotobaCid>,
    pub next_seq: u64,
    pub refs: BTreeMap<String, String>,
}

impl RepoState {
    pub fn new(identity: RepoIdentity) -> Result<Self, RadError> {
        let rid = identity.rid()?;
        Ok(Self {
            identity,
            rid,
            journal_head: None,
            next_seq: 0,
            refs: BTreeMap::new(),
        })
    }

    pub fn delegate(&self, did: &str) -> Option<&Delegate> {
        self.identity.delegates.iter().find(|d| d.did == did)
    }

    pub fn require(&self, actor: &str, capability: Capability) -> Result<(), RadError> {
        let delegate = self
            .delegate(actor)
            .ok_or_else(|| RadError::DelegateNotFound(actor.to_string()))?;
        if !delegate.can(capability) {
            return Err(RadError::MissingCapability {
                actor: actor.to_string(),
                capability,
            });
        }
        Ok(())
    }
}

pub struct RadRepo<'a, 'b> {
    git: &'a GitStore<'b>,
}

impl<'a, 'b> RadRepo<'a, 'b> {
    pub fn new(git: &'a GitStore<'b>) -> Self {
        Self { git }
    }

    pub fn authorize_event(&self, state: &RepoState, event: &RepoEvent) -> Result<(), RadError> {
        if event.seq != state.next_seq {
            return Err(RadError::SeqMismatch {
                expected: state.next_seq,
                got: event.seq,
            });
        }
        if event.prev != state.journal_head {
            return Err(RadError::PrevMismatch);
        }

        match &event.kind {
            RepoEventKind::IdentityUpdate { .. } => {
                state.require(&event.actor, Capability::IdentityUpdate)
            }
            RepoEventKind::RefCreate { update } => {
                state.require(&event.actor, Capability::RefCreate)?;
                self.validate_ref_update(state, update, false, false)
            }
            RepoEventKind::RefUpdate { update } => {
                state.require(&event.actor, Capability::RefUpdate)?;
                let force_allowed = if update.allow_non_fast_forward {
                    state.require(&event.actor, Capability::RefForceUpdate)?;
                    true
                } else {
                    false
                };
                self.validate_ref_update(state, update, true, force_allowed)
            }
            RepoEventKind::RefDelete { .. } => state.require(&event.actor, Capability::RefDelete),
            RepoEventKind::ObjectPublish { publish } => {
                state.require(&event.actor, Capability::ObjectPublish)?;
                self.validate_object_publish(state, publish)
            }
            RepoEventKind::GrantAdd { .. } => state.require(&event.actor, Capability::GrantWrite),
            RepoEventKind::GrantRevoke { .. } => {
                state.require(&event.actor, Capability::GrantRevoke)
            }
        }
    }

    pub fn apply_event(
        &self,
        state: &mut RepoState,
        event: RepoEvent,
    ) -> Result<KotobaCid, RadError> {
        self.authorize_event(state, &event)?;
        let cid = event.cid()?;
        match event.kind {
            RepoEventKind::IdentityUpdate { identity } => {
                state.identity = identity;
                state.rid = state.identity.rid()?;
            }
            RepoEventKind::RefCreate { update } | RepoEventKind::RefUpdate { update } => {
                state.refs.insert(update.name, update.new);
            }
            RepoEventKind::RefDelete { name, .. } => {
                state.refs.remove(&name);
            }
            RepoEventKind::ObjectPublish { .. }
            | RepoEventKind::GrantAdd { .. }
            | RepoEventKind::GrantRevoke { .. } => {}
        }
        state.journal_head = Some(cid.clone());
        state.next_seq += 1;
        Ok(cid)
    }

    fn validate_object_publish(
        &self,
        state: &RepoState,
        publish: &ObjectPublish,
    ) -> Result<(), RadError> {
        let oid = parse_oid(&publish.git_oid)?;
        object_cid(&self.git.db(), oid)
            .map_err(|_| RadError::ObjectNotFound(publish.git_oid.clone()))?;
        if state.identity.visibility == RepoVisibility::Private && publish.ciphertext_cid.is_none()
        {
            return Err(RadError::PrivatePublishWithoutCiphertext);
        }
        Ok(())
    }

    fn validate_ref_update(
        &self,
        state: &RepoState,
        update: &RefUpdate,
        existing_ref_required: bool,
        force_allowed: bool,
    ) -> Result<(), RadError> {
        let new_oid = parse_oid(&update.new)?;
        object_cid(&self.git.db(), new_oid)
            .map_err(|_| RadError::ObjectNotFound(update.new.clone()))?;

        let current = state
            .refs
            .get(&update.name)
            .and_then(|s| GitOid::from_hex(s).ok())
            .or_else(|| resolve_ref(&self.git.db(), &update.name));

        if existing_ref_required && current.is_none() {
            return Err(RadError::ObjectNotFound(update.name.clone()));
        }

        if let Some(old) = &update.old {
            let old_oid = parse_oid(old)?;
            if Some(old_oid) != current {
                return Err(RadError::NonFastForward {
                    name: update.name.clone(),
                });
            }
        }

        if let Some(old_oid) = current {
            if !update.allow_non_fast_forward && !is_ancestor(&self.git.db(), old_oid, new_oid) {
                return Err(RadError::NonFastForward {
                    name: update.name.clone(),
                });
            }
        } else if existing_ref_required {
            return Err(RadError::ObjectNotFound(update.name.clone()));
        }

        if update.allow_non_fast_forward && !force_allowed {
            return Err(RadError::ForceUpdateDenied(update.name.clone()));
        }

        Ok(())
    }
}

fn is_ancestor(db: &kotoba_datomic::Db, ancestor: GitOid, head: GitOid) -> bool {
    if ancestor == head {
        return true;
    }
    log(db, head).contains(&ancestor) || commit_parents(db, head).contains(&ancestor)
}

fn parse_oid(value: &str) -> Result<GitOid, RadError> {
    GitOid::from_hex(value).map_err(|_| RadError::InvalidOid(value.to_string()))
}

fn canonical_cid<T: Serialize>(value: &T) -> Result<KotobaCid, RadError> {
    Ok(KotobaCid::from_bytes(&canonical_bytes(value)?))
}

fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, RadError> {
    let mut buf = Vec::new();
    ciborium::into_writer(value, &mut buf).map_err(|e| RadError::Cbor(e.to_string()))?;
    Ok(buf)
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_datomic::Connection;
    use kotoba_git::{GitObject, GitObjectKind};
    use kotoba_store::MemoryBlockStore;

    async fn fixture() -> (Connection, MemoryBlockStore, String, String, GitOid, GitOid) {
        let conn = Connection::new();
        let store = MemoryBlockStore::new();
        let git = GitStore::new(&conn, &store);
        git.install_schema().await.unwrap();

        let tree = GitObject::new(GitObjectKind::Tree, Vec::new());
        let (tree_oid, _) = git.put_object(&tree).await.unwrap();

        let c1 = GitObject::new(
            GitObjectKind::Commit,
            format!(
                "tree {}\nauthor t <t@t> 1700000000 +0000\ncommitter t <t@t> 1700000000 +0000\n\nfirst\n",
                tree_oid.to_hex()
            )
            .into_bytes(),
        );
        let (c1_oid, _) = git.put_object(&c1).await.unwrap();

        let c2 = GitObject::new(
            GitObjectKind::Commit,
            format!(
                "tree {}\nparent {}\nauthor t <t@t> 1700000001 +0000\ncommitter t <t@t> 1700000001 +0000\n\nsecond\n",
                tree_oid.to_hex(),
                c1_oid.to_hex()
            )
            .into_bytes(),
        );
        let (c2_oid, _) = git.put_object(&c2).await.unwrap();

        git.put_ref("refs/heads/main", c1_oid).await.unwrap();
        let maintainer = "did:key:zmaintainer".to_string();
        let observer = "did:key:zobserver".to_string();
        (conn, store, maintainer, observer, c1_oid, c2_oid)
    }

    fn identity(maintainer: String, observer: String) -> RepoIdentity {
        RepoIdentity::new(
            "test/repo",
            RepoVisibility::Private,
            "refs/heads/main",
            vec![
                Delegate::new(
                    maintainer,
                    "maintainer",
                    [
                        Capability::RefCreate,
                        Capability::RefUpdate,
                        Capability::RefForceUpdate,
                        Capability::ObjectPublish,
                        Capability::GrantWrite,
                        Capability::GrantRevoke,
                    ],
                ),
                Delegate::new(observer, "observer", []),
            ],
            1,
        )
    }

    #[tokio::test]
    async fn rid_is_stable_for_same_identity() {
        let (_conn, _store, maintainer, observer, _c1, _c2) = fixture().await;
        let id = identity(maintainer, observer);
        assert_eq!(id.rid().unwrap(), id.rid().unwrap());
    }

    #[tokio::test]
    async fn applies_fast_forward_ref_update() {
        let (conn, store, maintainer, observer, c1, c2) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let rad = RadRepo::new(&git);
        let mut state = RepoState::new(identity(maintainer.clone(), observer)).unwrap();
        state
            .refs
            .insert("refs/heads/main".to_string(), c1.to_hex());

        let event = RepoEvent {
            rid: state.rid.clone(),
            seq: 0,
            prev: None,
            actor: maintainer,
            ts: 2,
            kind: RepoEventKind::RefUpdate {
                update: RefUpdate {
                    name: "refs/heads/main".to_string(),
                    old: Some(c1.to_hex()),
                    new: c2.to_hex(),
                    allow_non_fast_forward: false,
                },
            },
            sig: Vec::new(),
        };

        rad.apply_event(&mut state, event).unwrap();
        assert_eq!(state.refs["refs/heads/main"], c2.to_hex());
        assert_eq!(state.next_seq, 1);
        assert!(state.journal_head.is_some());
    }

    #[tokio::test]
    async fn rejects_delegate_without_capability() {
        let (conn, store, _maintainer, observer, c1, c2) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let rad = RadRepo::new(&git);
        let mut state = RepoState::new(identity(
            "did:key:zmaintainer".to_string(),
            observer.clone(),
        ))
        .unwrap();
        state
            .refs
            .insert("refs/heads/main".to_string(), c1.to_hex());

        let event = RepoEvent {
            rid: state.rid.clone(),
            seq: 0,
            prev: None,
            actor: observer,
            ts: 2,
            kind: RepoEventKind::RefUpdate {
                update: RefUpdate {
                    name: "refs/heads/main".to_string(),
                    old: Some(c1.to_hex()),
                    new: c2.to_hex(),
                    allow_non_fast_forward: false,
                },
            },
            sig: Vec::new(),
        };

        assert!(matches!(
            rad.apply_event(&mut state, event),
            Err(RadError::MissingCapability { .. })
        ));
    }

    #[tokio::test]
    async fn private_object_publish_requires_ciphertext_cid() {
        let (conn, store, maintainer, observer, c1, _c2) = fixture().await;
        let git = GitStore::new(&conn, &store);
        let rad = RadRepo::new(&git);
        let mut state = RepoState::new(identity(maintainer.clone(), observer)).unwrap();

        let event = RepoEvent {
            rid: state.rid.clone(),
            seq: 0,
            prev: None,
            actor: maintainer,
            ts: 2,
            kind: RepoEventKind::ObjectPublish {
                publish: ObjectPublish {
                    git_oid: c1.to_hex(),
                    plaintext_cid: None,
                    ciphertext_cid: None,
                },
            },
            sig: Vec::new(),
        };

        assert!(matches!(
            rad.apply_event(&mut state, event),
            Err(RadError::PrivatePublishWithoutCiphertext)
        ));
    }

    #[tokio::test]
    async fn signing_bytes_exclude_signature() {
        let (_conn, _store, maintainer, observer, _c1, c2) = fixture().await;
        let state = RepoState::new(identity(maintainer.clone(), observer)).unwrap();
        let mut event = RepoEvent {
            rid: state.rid,
            seq: 0,
            prev: None,
            actor: maintainer,
            ts: 2,
            kind: RepoEventKind::RefCreate {
                update: RefUpdate {
                    name: "refs/heads/dev".to_string(),
                    old: None,
                    new: c2.to_hex(),
                    allow_non_fast_forward: false,
                },
            },
            sig: vec![1, 2, 3],
        };
        let a = event.signing_bytes().unwrap();
        event.sig = vec![9, 9, 9];
        let b = event.signing_bytes().unwrap();
        assert_eq!(a, b);
    }
}
