//! # ENGI mutual-credit on the Source Chain — agent-centric, net-zero EN
//!
//! Puts the **EN (縁) mutual-credit ledger** onto the per-DID [`SourceChain`],
//! Holochain-HoloFuel style, so balances live *in the mesh* (replayed from
//! signed chains) rather than in a single node-local JSON file.
//!
//! ## Why chains instead of a global ledger
//!
//! kotoba's substrate is agent-centric: per-agent Source Chains + neighborhood
//! validation, **no central master, no global consensus** (ADR-001). A single
//! authoritative balance map contradicts that. Instead, exactly like HoloFuel,
//! value has no independent substance — it exists only as a *relation between two
//! agents* ("縁起"). A balance is therefore **derived**: replay an agent's chain
//! and fold its transfers.
//!
//! ## The countersigned transfer
//!
//! A spend is a [`MutualCreditTransfer`]: a [`TransferBody`] (spender, receiver,
//! amount, each side's chain head, nonce, ts) that **both** parties sign. The
//! same transfer is appended to *both* chains — the spender records a debit, the
//! receiver a credit. Net-zero by construction.
//!
//! ## Double-spend prevention (no global order needed)
//!
//! `TransferBody::spender_prev` pins the transfer to the spender's chain head at
//! signing time, and when appended the entry's `prev` must equal it. A Source
//! Chain is **linear** (one entry per seq; [`SourceChain`] enforces seq+prev on
//! append), so spending the same EN twice forces a *fork* — two entries sharing
//! one `prev`. Neighborhood validators holding the chain see the fork and raise a
//! [`Warrant`] ([`ValidationRule::DoubleSpend`]). An overspend below the credit
//! limit is caught by [`validate_chain_transfers`] replaying the chain. No total
//! order, no consensus on a supply — agent-centric integrity, same as the rest of
//! KDHT.
//!
//! ## Finality
//!
//! Countersigning gives **bilateral** finality (both agreed); the neighborhood
//! gives **fraud detection**, not instant global finality — acceptable because
//! the scarce, irreversibly-settled asset lives across the boundary (USDC on Base
//! L2). This layer is internal contribution accounting only.

use crate::source_chain::{ChainContent, ChainEntry, ChainError, SourceChain};
use crate::warrant::{warrant_signing_bytes, ValidationRule, Warrant};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use kotoba_core::cid::KotobaCid;
use kotoba_vault::agent_identity::AgentIdentity;
use serde::{Deserialize, Serialize};
use std::collections::{HashSet, VecDeque};

/// GossipSub **KSE-topic name** carrying countersigned EN transfers across the
/// mesh. This is the bare name (like `firehose` / `rekey/revoke`); the net layer
/// maps it to the wire topic `kotoba/engi/transfer` via `gossipsub_topic`, so it
/// must NOT carry the `kotoba/` prefix itself (that would double it). A node
/// receiving a transfer here projects it into its [`crate::engi_chain`] balance
/// view (after dedup via [`SeenTransfers`]); a *neighborhood validator* holding
/// the spender's chain additionally audits solvency via [`audit_peer_chain`].
pub const ENGI_TRANSFER_TOPIC: &str = "engi/transfer";

/// Default bound for [`SeenTransfers`] (matches the firehose seen-guard cap).
pub const SEEN_TRANSFERS_CAP: usize = 8192;

/// The signed body of a mutual-credit transfer — the bytes both parties sign and
/// the input to its content-address ([`TransferBody::transfer_id`]).
///
/// `amount` is in **EN** and must be `> 0`; direction is explicit in
/// `spender`/`receiver` (the spender is debited, the receiver credited). Each
/// side's `*_prev` is that party's Source Chain head at signing time, binding the
/// transfer to a unique position on each chain (the anti-double-spend pin).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TransferBody {
    /// DID debited by this transfer.
    pub spender: String,
    /// DID credited by this transfer.
    pub receiver: String,
    /// EN moved (must be `> 0`).
    pub amount: i64,
    /// Spender's Source Chain head when they signed (`None` = genesis transfer).
    pub spender_prev: Option<KotobaCid>,
    /// Receiver's Source Chain head when they signed.
    pub receiver_prev: Option<KotobaCid>,
    /// Anti-replay nonce, unique per (spender, receiver) pair.
    pub nonce: u64,
    /// Wall-clock ms at proposal (informational; ordering comes from the chain).
    pub ts: u64,
}

impl TransferBody {
    /// Canonical CBOR — the bytes both parties sign and the transfer is addressed
    /// by. Field order is fixed by declaration order (dag-cbor compatible).
    pub fn signing_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        ciborium::ser::into_writer(self, &mut buf)
            .expect("CBOR serialization of TransferBody is infallible");
        buf
    }

    /// Content address of the transfer — its stable identifier across both
    /// chains and the dedup key for gossip.
    pub fn transfer_id(&self) -> KotobaCid {
        KotobaCid::from_bytes(&self.signing_bytes())
    }

    /// Sign this body with `key` (either party's Ed25519 signing key), returning
    /// the 64-byte signature.
    pub fn sign(&self, key: &SigningKey) -> Vec<u8> {
        key.sign(&self.signing_bytes()).to_bytes().to_vec()
    }
}

/// A countersigned mutual-credit transfer: a [`TransferBody`] plus both parties'
/// Ed25519 signatures over its [`TransferBody::signing_bytes`]. Carried in
/// [`ChainContent::Transfer`] on *both* the spender's and receiver's chains.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MutualCreditTransfer {
    pub body: TransferBody,
    /// Spender's signature over `body.signing_bytes()`.
    pub spender_sig: Vec<u8>,
    /// Receiver's signature over `body.signing_bytes()` (the countersignature).
    pub receiver_sig: Vec<u8>,
}

/// Why a [`MutualCreditTransfer`] (or a chain replay) is invalid. Each maps to a
/// [`ValidationRule`] a validator cites when raising a [`Warrant`].
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum TransferViolation {
    #[error("amount must be > 0, got {0}")]
    NonPositiveAmount(i64),
    #[error("self-transfer: spender == receiver ({0})")]
    SelfTransfer(String),
    #[error("invalid spender signature")]
    BadSpenderSig,
    #[error("invalid receiver (counter) signature")]
    BadReceiverSig,
    #[error("entry prev does not match the spender's declared chain head")]
    PrevNotBound,
    #[error("overspend: balance {balance} − {amount} EN would breach credit limit −{limit}")]
    Overspend {
        balance: i64,
        amount: i64,
        limit: i64,
    },
}

impl TransferViolation {
    /// The [`ValidationRule`] a validator cites for this violation. Overspend ⇒
    /// [`ValidationRule::DoubleSpend`]; everything else ⇒
    /// [`ValidationRule::MutualCreditViolation`].
    pub fn rule(&self) -> ValidationRule {
        match self {
            TransferViolation::Overspend { .. } => ValidationRule::DoubleSpend,
            _ => ValidationRule::MutualCreditViolation,
        }
    }
}

impl MutualCreditTransfer {
    /// Build a fully countersigned transfer from both parties' signing keys.
    ///
    /// `spender_prev` / `receiver_prev` are each party's current Source Chain head
    /// (the values that will become the appended entries' `prev`). The body is
    /// signed by `spender_key` and counter-signed by `receiver_key` over the same
    /// canonical bytes. Returns `Err` for a non-positive amount or self-transfer.
    #[allow(clippy::too_many_arguments)]
    pub fn countersign(
        spender: impl Into<String>,
        receiver: impl Into<String>,
        amount: i64,
        spender_prev: Option<KotobaCid>,
        receiver_prev: Option<KotobaCid>,
        nonce: u64,
        ts: u64,
        spender_key: &SigningKey,
        receiver_key: &SigningKey,
    ) -> Result<Self, TransferViolation> {
        let body = TransferBody {
            spender: spender.into(),
            receiver: receiver.into(),
            amount,
            spender_prev,
            receiver_prev,
            nonce,
            ts,
        };
        if amount <= 0 {
            return Err(TransferViolation::NonPositiveAmount(amount));
        }
        if body.spender == body.receiver {
            return Err(TransferViolation::SelfTransfer(body.spender));
        }
        let spender_sig = body.sign(spender_key);
        let receiver_sig = body.sign(receiver_key);
        Ok(Self {
            body,
            spender_sig,
            receiver_sig,
        })
    }

    /// Verify the transfer is internally valid given both parties' 32-byte Ed25519
    /// public keys: positive amount, distinct parties, and both signatures cover
    /// the body. Does **not** check balance/credit-limit — that needs the
    /// spender's chain (see [`validate_chain_transfers`]).
    pub fn verify(
        &self,
        spender_pubkey: &[u8],
        receiver_pubkey: &[u8],
    ) -> Result<(), TransferViolation> {
        if self.body.amount <= 0 {
            return Err(TransferViolation::NonPositiveAmount(self.body.amount));
        }
        if self.body.spender == self.body.receiver {
            return Err(TransferViolation::SelfTransfer(self.body.spender.clone()));
        }
        let msg = self.body.signing_bytes();
        verify_sig(spender_pubkey, &msg, &self.spender_sig)
            .map_err(|_| TransferViolation::BadSpenderSig)?;
        verify_sig(receiver_pubkey, &msg, &self.receiver_sig)
            .map_err(|_| TransferViolation::BadReceiverSig)?;
        Ok(())
    }
}

fn verify_sig(pubkey_bytes: &[u8], msg: &[u8], sig_bytes: &[u8]) -> Result<(), ()> {
    let key_arr: [u8; 32] = pubkey_bytes.try_into().map_err(|_| ())?;
    let vk = VerifyingKey::from_bytes(&key_arr).map_err(|_| ())?;
    let sig_arr: [u8; 64] = sig_bytes.try_into().map_err(|_| ())?;
    vk.verify(msg, &Signature::from_bytes(&sig_arr))
        .map_err(|_| ())
}

/// Replay a chain's entries into the balance of `agent` (in EN): every
/// [`ChainContent::Transfer`] where `agent` is the spender debits, every one
/// where it is the receiver credits. Non-transfer entries are ignored. Saturating
/// so a malicious chain can't overflow the projection.
///
/// This is the *projection* that replaces the node-local ledger map: an agent's
/// balance is a pure function of its (and its counterparties') signed transfers.
pub fn replay_balance(entries: &[ChainEntry], agent: &str) -> i64 {
    let mut bal: i64 = 0;
    for e in entries {
        if let ChainContent::Transfer(t) = &e.content {
            if t.body.spender == agent {
                bal = bal.saturating_sub(t.body.amount);
            }
            if t.body.receiver == agent {
                bal = bal.saturating_add(t.body.amount);
            }
        }
    }
    bal
}

/// Validate the spend-side of every transfer on `agent`'s own chain, in order,
/// against a `credit_limit` (how far the balance may go negative).
///
/// For each entry where `agent` is the spender this checks, *at that point in the
/// chain*, that the running balance stays `≥ −credit_limit` after the debit, and
/// that the entry's `prev` equals the transfer's declared `spender_prev` (the
/// anti-double-spend pin). Returns the first offending entry's CID + the
/// violation, or `Ok(())` if the whole chain is solvent and well-bound.
///
/// Receiver-side credits never need solvency checks (you can always *receive*).
/// Signature verification needs each counterparty's pubkey and is done separately
/// via [`MutualCreditTransfer::verify`] by a validator that can resolve DIDs.
pub fn validate_chain_transfers(
    entries: &[ChainEntry],
    agent: &str,
    credit_limit: i64,
) -> Result<(), (KotobaCid, TransferViolation)> {
    let mut bal: i64 = 0;
    for e in entries {
        let ChainContent::Transfer(t) = &e.content else {
            continue;
        };
        if t.body.receiver == agent {
            bal = bal.saturating_add(t.body.amount);
        }
        if t.body.spender == agent {
            // The entry must be pinned to the head the spender signed against.
            if e.prev != t.body.spender_prev {
                return Err((e.cid.clone(), TransferViolation::PrevNotBound));
            }
            if t.body.amount <= 0 {
                return Err((
                    e.cid.clone(),
                    TransferViolation::NonPositiveAmount(t.body.amount),
                ));
            }
            let after = bal.saturating_sub(t.body.amount);
            if after < -credit_limit {
                return Err((
                    e.cid.clone(),
                    TransferViolation::Overspend {
                        balance: bal,
                        amount: t.body.amount,
                        limit: credit_limit,
                    },
                ));
            }
            bal = after;
        }
    }
    Ok(())
}

/// Construct and sign a [`Warrant`] accusing `accused` of an invalid transfer.
/// `evidence` is the offending [`ChainEntry`] CID; `rule` comes from
/// [`TransferViolation::rule`]. Signed by the detecting validator's `key` over
/// [`warrant_signing_bytes`], so any peer can verify the accusation.
pub fn mutual_credit_warrant(
    accused: Vec<u8>,
    evidence: KotobaCid,
    rule: ValidationRule,
    validator: Vec<u8>,
    ts: u64,
    key: &SigningKey,
) -> Warrant {
    let mut w = Warrant {
        accused,
        evidence,
        rule_id: rule as u8,
        validator,
        ts,
        sig: Vec::new(),
    };
    w.sig = key.sign(&warrant_signing_bytes(&w)).to_bytes().to_vec();
    w
}

/// A per-agent EN sub-ledger riding the agent's [`SourceChain`] — the
/// mutual-credit analogue of [`crate::commit_chain::CommitChain`]. Appends
/// signed [`ChainContent::Transfer`] entries and exposes the replayed balance.
///
/// This owns the agent's *side* of transfers. A spend is a two-party act: the
/// spender's `EngiChain` records the debit (via [`EngiChain::record_spend`]) and
/// the receiver's records the credit ([`EngiChain::record_receive`]) — both
/// appending the *same* [`MutualCreditTransfer`]. The chain stays one append-only
/// signed lineage shared with commits, datoms, etc.
pub struct EngiChain {
    chain: SourceChain,
    signing_key: SigningKey,
    pubkey: [u8; 32],
    did: String,
    /// Per-agent max negative balance, mirrored from the EN `Engi` credit limit.
    credit_limit: i64,
}

impl EngiChain {
    /// Build over a fresh chain owned by `identity` with the given EN credit limit
    /// (how far this agent's balance may go negative before a spend is rejected).
    pub fn new(identity: &AgentIdentity, credit_limit: i64) -> Self {
        Self {
            chain: SourceChain::new(identity.did.clone()),
            signing_key: SigningKey::from_bytes(&identity.signing_key.to_bytes()),
            pubkey: identity.verifying_key().to_bytes(),
            did: identity.did.clone(),
            credit_limit: credit_limit.max(0),
        }
    }

    /// The agent's current EN balance (replay of its own chain).
    pub fn balance(&self) -> i64 {
        replay_balance(self.chain.entries(), &self.did)
    }

    /// The current chain head CID — the `*_prev` a counterparty must pin against
    /// when proposing a transfer with this agent.
    pub fn head_cid(&self) -> Option<KotobaCid> {
        self.chain.head().map(|e| e.cid.clone())
    }

    /// 32-byte Ed25519 public key verifying this chain's entries.
    pub fn pubkey(&self) -> &[u8; 32] {
        &self.pubkey
    }

    /// The agent DID that owns this chain.
    pub fn did(&self) -> &str {
        &self.did
    }

    /// Number of entries on the chain (transfers + anything else committed).
    pub fn len(&self) -> usize {
        self.chain.len()
    }

    pub fn is_empty(&self) -> bool {
        self.chain.is_empty()
    }

    /// Append the **spend side** of `transfer` to this chain. Rejects unless this
    /// agent is the transfer's spender, the transfer's `spender_prev` pins the
    /// current head, and the resulting balance stays within the credit limit.
    /// Returns the new entry CID. The signature is over the chain entry (not the
    /// transfer body, which is already countersigned inside `transfer`).
    pub fn record_spend(
        &mut self,
        transfer: MutualCreditTransfer,
    ) -> Result<KotobaCid, EngiChainError> {
        if transfer.body.spender != self.did {
            return Err(EngiChainError::NotSpender);
        }
        let prev = self.head_cid();
        if transfer.body.spender_prev != prev {
            return Err(EngiChainError::Violation(TransferViolation::PrevNotBound));
        }
        let after = self.balance().saturating_sub(transfer.body.amount);
        if transfer.body.amount <= 0 {
            return Err(EngiChainError::Violation(
                TransferViolation::NonPositiveAmount(transfer.body.amount),
            ));
        }
        if after < -self.credit_limit {
            return Err(EngiChainError::Violation(TransferViolation::Overspend {
                balance: self.balance(),
                amount: transfer.body.amount,
                limit: self.credit_limit,
            }));
        }
        self.append(ChainContent::Transfer(transfer))
    }

    /// Append the **receive side** of `transfer` to this chain. Rejects unless
    /// this agent is the transfer's receiver. Receiving never breaches a limit.
    pub fn record_receive(
        &mut self,
        transfer: MutualCreditTransfer,
    ) -> Result<KotobaCid, EngiChainError> {
        if transfer.body.receiver != self.did {
            return Err(EngiChainError::NotReceiver);
        }
        self.append(ChainContent::Transfer(transfer))
    }

    fn append(&mut self, content: ChainContent) -> Result<KotobaCid, EngiChainError> {
        let prev = self.head_cid();
        let seq = self.chain.len() as u64;
        let mut entry = ChainEntry::new(prev, self.did.clone(), seq, content, Vec::new());
        let sig = self.signing_key.sign(&entry.signing_bytes());
        entry.sig = sig.to_bytes().to_vec();
        let cid = entry.cid.clone();
        self.chain.append_verified(entry, &self.pubkey)?;
        Ok(cid)
    }
}

/// Failure modes of appending a transfer to an [`EngiChain`].
#[derive(Debug, thiserror::Error)]
pub enum EngiChainError {
    #[error("this agent is not the transfer's spender")]
    NotSpender,
    #[error("this agent is not the transfer's receiver")]
    NotReceiver,
    #[error("transfer violation: {0}")]
    Violation(#[from] TransferViolation),
    #[error("chain error: {0}")]
    Chain(#[from] ChainError),
}

/// A neighborhood validator's accusation against one invalid transfer entry on a
/// peer's chain — the structured input to [`mutual_credit_warrant`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransferAccusation {
    /// DID whose Source Chain holds the offending entry.
    pub accused: String,
    /// CID of the offending [`ChainEntry`] (the warrant's `evidence`).
    pub evidence: KotobaCid,
    /// Rule the validator cites.
    pub rule: ValidationRule,
    /// The specific violation found.
    pub violation: TransferViolation,
}

fn accuse(agent: &str, e: &ChainEntry, v: TransferViolation) -> TransferAccusation {
    TransferAccusation {
        accused: agent.to_string(),
        evidence: e.cid.clone(),
        rule: v.rule(),
        violation: v,
    }
}

/// Audit every transfer on `agent`'s Source Chain the way a **neighborhood
/// validator** does, returning *all* violations found (not just the first) so the
/// caller can raise one [`Warrant`] per accusation via [`mutual_credit_warrant`].
///
/// For each [`ChainContent::Transfer`] entry it:
/// 1. verifies the spender + receiver countersignatures, resolving each DID to a
///    32-byte Ed25519 key via `resolve` (an unresolvable DID is skipped for the
///    signature check — a validator can't accuse without the key);
/// 2. checks the entry's `prev` equals the transfer's declared `spender_prev`
///    (the anti-double-spend pin) — a mismatch is [`ValidationRule::DoubleSpend`];
/// 3. replays the running balance and flags any spend that drives it below
///    `−credit_limit` ([`ValidationRule::DoubleSpend`], the overspend case).
///
/// Pure + deterministic: every validator holding the same chain reaches the same
/// verdict, which is what lets the neighborhood converge on eviction without
/// coordination (same property as [`crate::validation`]).
pub fn audit_peer_chain<R>(
    entries: &[ChainEntry],
    agent: &str,
    credit_limit: i64,
    resolve: R,
) -> Vec<TransferAccusation>
where
    R: Fn(&str) -> Option<[u8; 32]>,
{
    let mut out = Vec::new();
    let mut bal: i64 = 0;
    for e in entries {
        let ChainContent::Transfer(t) = &e.content else {
            continue;
        };
        // (1) Countersignature check, when both keys resolve.
        if let (Some(sk), Some(rk)) = (resolve(&t.body.spender), resolve(&t.body.receiver)) {
            if let Err(v) = t.verify(&sk, &rk) {
                out.push(accuse(agent, e, v));
                // A forged transfer must not move the balance projection.
                continue;
            }
        }
        if t.body.receiver == agent {
            bal = bal.saturating_add(t.body.amount);
        }
        if t.body.spender == agent {
            // (2) prev-binding.
            if e.prev != t.body.spender_prev {
                out.push(accuse(agent, e, TransferViolation::PrevNotBound));
                continue;
            }
            // (3) solvency.
            let after = bal.saturating_sub(t.body.amount);
            if after < -credit_limit {
                out.push(accuse(
                    agent,
                    e,
                    TransferViolation::Overspend {
                        balance: bal,
                        amount: t.body.amount,
                        limit: credit_limit,
                    },
                ));
                // Don't apply an over-limit debit to the running balance.
            } else {
                bal = after;
            }
        }
    }
    out
}

/// Two chain entries from the **same agent at the same `seq` with different
/// CIDs** are a *fork* — the structural fingerprint of a double-spend (the agent
/// signed two different histories at one position). The pair is itself the proof;
/// a validator that holds both raises a [`ValidationRule::DoubleSpend`] warrant
/// (evidence = either entry CID). Returns `false` for the same entry or a genuine
/// linear successor.
pub fn detect_fork(a: &ChainEntry, b: &ChainEntry) -> bool {
    a.agent == b.agent && a.seq == b.seq && a.cid != b.cid
}

/// A solvency violation found by [`audit_transfers`]: spending agent `did`'s
/// running balance fell to `balance_after` — below `−credit_limit` — at the
/// transfer identified by `transfer_id`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InsolvencyFinding {
    /// The overspending agent (the transfer's spender).
    pub did: String,
    /// CID of the offending transfer (its `transfer_id`, the audit evidence).
    pub transfer_id: KotobaCid,
    /// The spender's running balance after this debit (more negative than allowed).
    pub balance_after: i64,
    /// The spender's effective credit limit (max negative) it breached.
    pub credit_limit: i64,
}

/// Audit a flat, time-ordered list of countersigned transfers for **insolvency**:
/// replay every agent's running balance in arrival order and report each spend
/// that drives the spender below `−credit_limit(spender)`.
///
/// Unlike the chain-entry path ([`validate_chain_transfers`]) this needs no
/// `prev`/`seq` — it audits the transfer *record* (e.g. the Engi durable transfer
/// log), which is exactly what the unconditional projection accumulates. It
/// therefore catches **overspend / double-spend-by-accumulation** (an agent that
/// gossiped more spending than its credit allows) but NOT chain *forks* (those
/// need per-DID `ChainEntry`s — see [`detect_fork`] / [`audit_peer_chain`]).
///
/// The over-limit debit is still applied to the running balance (mirroring the
/// projection, which applies unconditionally), so every subsequent over-limit
/// spend by the same agent is also reported. An empty result = solvent.
pub fn audit_transfers<F>(
    transfers: &[MutualCreditTransfer],
    credit_limit: F,
) -> Vec<InsolvencyFinding>
where
    F: Fn(&str) -> i64,
{
    let mut bal: std::collections::HashMap<&str, i64> = std::collections::HashMap::new();
    let mut out = Vec::new();
    for t in transfers {
        if t.body.amount <= 0 || t.body.spender == t.body.receiver {
            continue;
        }
        // Receiver is credited (you can always receive).
        let rb = bal.entry(t.body.receiver.as_str()).or_insert(0);
        *rb = rb.saturating_add(t.body.amount);
        // Spender is debited; flag if the debit breaches its credit limit.
        let limit = credit_limit(&t.body.spender);
        let sb = bal.entry(t.body.spender.as_str()).or_insert(0);
        let after = sb.saturating_sub(t.body.amount);
        if after < -limit {
            out.push(InsolvencyFinding {
                did: t.body.spender.clone(),
                transfer_id: t.body.transfer_id(),
                balance_after: after,
                credit_limit: limit,
            });
        }
        *sb = after;
    }
    out
}

/// Bounded dedup guard for gossiped transfers, keyed by
/// [`TransferBody::transfer_id`]. Mirrors the firehose seen-guard: a transfer
/// re-gossiped around the mesh is projected at most once per node. Ring-buffer
/// eviction keeps the set bounded so a long-running node can't grow it without
/// limit; the same `transfer_id` re-seen after eviction is harmless (projection
/// is idempotent only within a rebuild, so the cap should exceed in-flight churn,
/// which [`SEEN_TRANSFERS_CAP`] does by a wide margin).
#[derive(Debug)]
pub struct SeenTransfers {
    ring: VecDeque<KotobaCid>,
    set: HashSet<KotobaCid>,
    cap: usize,
}

impl SeenTransfers {
    /// New guard holding up to `cap` recent transfer ids (clamped to ≥ 1).
    pub fn with_capacity(cap: usize) -> Self {
        let cap = cap.max(1);
        Self {
            ring: VecDeque::with_capacity(cap),
            set: HashSet::with_capacity(cap),
            cap,
        }
    }

    /// Record `id`. Returns `true` if it was **new** (the caller should project
    /// it), `false` if already seen (a duplicate to drop). Evicts the oldest id
    /// when at capacity.
    pub fn insert(&mut self, id: KotobaCid) -> bool {
        if self.set.contains(&id) {
            return false;
        }
        if self.ring.len() >= self.cap {
            if let Some(old) = self.ring.pop_front() {
                self.set.remove(&old);
            }
        }
        self.ring.push_back(id.clone());
        self.set.insert(id);
        true
    }

    /// Whether `id` is currently remembered.
    pub fn contains(&self, id: &KotobaCid) -> bool {
        self.set.contains(id)
    }

    pub fn len(&self) -> usize {
        self.set.len()
    }

    pub fn is_empty(&self) -> bool {
        self.set.is_empty()
    }
}

impl Default for SeenTransfers {
    fn default() -> Self {
        Self::with_capacity(SEEN_TRANSFERS_CAP)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ident() -> AgentIdentity {
        AgentIdentity::generate_ephemeral()
    }

    /// Sign+countersign a transfer between two identities pinning each side's head.
    fn xfer(
        spender: &AgentIdentity,
        receiver: &AgentIdentity,
        amount: i64,
        sprev: Option<KotobaCid>,
        rprev: Option<KotobaCid>,
        nonce: u64,
    ) -> MutualCreditTransfer {
        let sk = SigningKey::from_bytes(&spender.signing_key.to_bytes());
        let rk = SigningKey::from_bytes(&receiver.signing_key.to_bytes());
        MutualCreditTransfer::countersign(
            spender.did.clone(),
            receiver.did.clone(),
            amount,
            sprev,
            rprev,
            nonce,
            0,
            &sk,
            &rk,
        )
        .expect("countersign")
    }

    #[test]
    fn transfer_id_is_deterministic_and_binds_every_field() {
        let a = ident();
        let b = ident();
        let t = xfer(&a, &b, 100, None, None, 1);
        // Deterministic.
        assert_eq!(t.body.transfer_id(), t.body.transfer_id());
        // amount is bound.
        let mut t2 = t.clone();
        t2.body.amount = 101;
        assert_ne!(t.body.transfer_id(), t2.body.transfer_id());
        // nonce is bound.
        let mut t3 = t.clone();
        t3.body.nonce = 2;
        assert_ne!(t.body.transfer_id(), t3.body.transfer_id());
    }

    #[test]
    fn verify_accepts_a_well_formed_countersigned_transfer() {
        let a = ident();
        let b = ident();
        let t = xfer(&a, &b, 250, None, None, 1);
        assert!(t
            .verify(
                a.verifying_key().to_bytes().as_ref(),
                b.verifying_key().to_bytes().as_ref()
            )
            .is_ok());
    }

    #[test]
    fn verify_rejects_a_forged_countersignature() {
        let a = ident();
        let b = ident();
        let eve = ident();
        // Eve, not the real receiver b, counter-signs.
        let sk = SigningKey::from_bytes(&a.signing_key.to_bytes());
        let ek = SigningKey::from_bytes(&eve.signing_key.to_bytes());
        let t = MutualCreditTransfer::countersign(
            a.did.clone(),
            b.did.clone(),
            100,
            None,
            None,
            1,
            0,
            &sk,
            &ek,
        )
        .unwrap();
        // Against b's real key the counter-signature does not verify.
        assert_eq!(
            t.verify(
                a.verifying_key().to_bytes().as_ref(),
                b.verifying_key().to_bytes().as_ref()
            ),
            Err(TransferViolation::BadReceiverSig)
        );
    }

    #[test]
    fn verify_rejects_tampered_amount() {
        let a = ident();
        let b = ident();
        let mut t = xfer(&a, &b, 100, None, None, 1);
        t.body.amount = 1_000_000; // tamper after signing
        assert_eq!(
            t.verify(
                a.verifying_key().to_bytes().as_ref(),
                b.verifying_key().to_bytes().as_ref()
            ),
            Err(TransferViolation::BadSpenderSig)
        );
    }

    #[test]
    fn countersign_rejects_non_positive_and_self_transfer() {
        let a = ident();
        let b = ident();
        let sk = SigningKey::from_bytes(&a.signing_key.to_bytes());
        let bk = SigningKey::from_bytes(&b.signing_key.to_bytes());
        assert_eq!(
            MutualCreditTransfer::countersign(
                a.did.clone(),
                b.did.clone(),
                0,
                None,
                None,
                1,
                0,
                &sk,
                &bk
            ),
            Err(TransferViolation::NonPositiveAmount(0))
        );
        let ak2 = SigningKey::from_bytes(&a.signing_key.to_bytes());
        assert_eq!(
            MutualCreditTransfer::countersign(
                a.did.clone(),
                a.did.clone(),
                10,
                None,
                None,
                1,
                0,
                &sk,
                &ak2
            ),
            Err(TransferViolation::SelfTransfer(a.did.clone()))
        );
    }

    #[test]
    fn two_party_transfer_is_net_zero_across_both_chains() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 1_000);
        let mut cb = EngiChain::new(&b, 1_000);

        // a spends 300 to b. Pin each side's head (both empty → None).
        let t = xfer(&a, &b, 300, ca.head_cid(), cb.head_cid(), 1);
        ca.record_spend(t.clone()).expect("spend appends");
        cb.record_receive(t).expect("receive appends");

        assert_eq!(ca.balance(), -300, "spender is debited");
        assert_eq!(cb.balance(), 300, "receiver is credited");
        // Net-zero: the two halves cancel.
        assert_eq!(ca.balance() + cb.balance(), 0);
    }

    #[test]
    fn record_spend_pins_prev_and_advances_head() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 10_000);
        let mut cb = EngiChain::new(&b, 10_000);
        assert!(ca.head_cid().is_none());

        let t1 = xfer(&a, &b, 100, ca.head_cid(), cb.head_cid(), 1);
        let e1 = ca.record_spend(t1.clone()).unwrap();
        cb.record_receive(t1).unwrap();
        assert_eq!(ca.head_cid(), Some(e1.clone()));

        // Second spend must pin the NEW head (e1), not the old None.
        let t2 = xfer(&a, &b, 50, ca.head_cid(), cb.head_cid(), 2);
        assert_eq!(t2.body.spender_prev, Some(e1));
        ca.record_spend(t2).unwrap();
        assert_eq!(ca.balance(), -150);
    }

    #[test]
    fn record_spend_rejects_stale_prev_double_spend_attempt() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 10_000);
        let mut cb = EngiChain::new(&b, 10_000);

        let t1 = xfer(&a, &b, 100, ca.head_cid(), cb.head_cid(), 1);
        ca.record_spend(t1.clone()).unwrap();
        cb.record_receive(t1).unwrap();

        // A second transfer still pinned to the ORIGINAL (now stale) head None —
        // this is the double-spend shape; record_spend must refuse to fork.
        let stale = xfer(&a, &b, 100, None, cb.head_cid(), 2);
        let err = ca.record_spend(stale).unwrap_err();
        assert!(matches!(
            err,
            EngiChainError::Violation(TransferViolation::PrevNotBound)
        ));
    }

    #[test]
    fn record_spend_enforces_credit_limit() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 1_000); // a may go to -1000
        let mut cb = EngiChain::new(&b, 1_000);

        let t1 = xfer(&a, &b, 1_000, ca.head_cid(), cb.head_cid(), 1);
        ca.record_spend(t1.clone()).unwrap(); // a now at -1000
        cb.record_receive(t1).unwrap();
        assert_eq!(ca.balance(), -1_000);

        // One more EN over the limit → rejected, chain unchanged.
        let over = xfer(&a, &b, 1, ca.head_cid(), cb.head_cid(), 2);
        let err = ca.record_spend(over).unwrap_err();
        assert!(matches!(
            err,
            EngiChainError::Violation(TransferViolation::Overspend { .. })
        ));
        assert_eq!(ca.balance(), -1_000, "rejected spend must not apply");
    }

    #[test]
    fn record_spend_rejects_wrong_role() {
        let a = ident();
        let b = ident();
        let mut cb = EngiChain::new(&b, 1_000);
        // a is the spender; b's chain must refuse to record it as a spend.
        let t = xfer(&a, &b, 10, None, cb.head_cid(), 1);
        assert!(matches!(
            cb.record_spend(t.clone()).unwrap_err(),
            EngiChainError::NotSpender
        ));
        // …and a (not b) cannot be recorded on b's chain as a receive either-way:
        let mut ca = EngiChain::new(&a, 1_000);
        assert!(matches!(
            ca.record_receive(t).unwrap_err(),
            EngiChainError::NotReceiver
        ));
    }

    #[test]
    fn validate_chain_transfers_flags_first_overspend() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 10_000); // build a solvent chain first
        let mut cb = EngiChain::new(&b, 10_000);
        for n in 1..=3u64 {
            let t = xfer(&a, &b, 100, ca.head_cid(), cb.head_cid(), n);
            ca.record_spend(t.clone()).unwrap();
            cb.record_receive(t).unwrap();
        }
        // Validating a's chain under a TIGHT limit of 150 catches the 2nd debit
        // (running balance -100 → -200 < -150).
        let entries = ca.chain.entries();
        let err = validate_chain_transfers(entries, &a.did, 150).unwrap_err();
        assert!(matches!(err.1, TransferViolation::Overspend { .. }));
        // Under the real 10_000 limit the same chain is solvent.
        assert!(validate_chain_transfers(entries, &a.did, 10_000).is_ok());
    }

    #[test]
    fn replay_balance_ignores_non_transfer_entries() {
        // A chain with only non-transfer content replays to zero.
        let a = ident();
        let chain = SourceChain::new(a.did.clone());
        assert_eq!(replay_balance(chain.entries(), &a.did), 0);
    }

    #[test]
    fn mutual_credit_warrant_is_signed_and_verifiable() {
        let a = ident();
        let validator = ident();
        let evidence = KotobaCid::from_bytes(b"bad-transfer-entry");
        let vk = SigningKey::from_bytes(&validator.signing_key.to_bytes());
        let w = mutual_credit_warrant(
            a.verifying_key().to_bytes().to_vec(),
            evidence.clone(),
            ValidationRule::DoubleSpend,
            validator.verifying_key().to_bytes().to_vec(),
            42,
            &vk,
        );
        assert_eq!(w.rule_id, ValidationRule::DoubleSpend as u8);
        assert_eq!(w.evidence, evidence);
        // The validator's signature verifies over the canonical warrant bytes.
        let sig: [u8; 64] = w.sig.as_slice().try_into().unwrap();
        assert!(validator
            .verifying_key()
            .verify(&warrant_signing_bytes(&w), &Signature::from_bytes(&sig))
            .is_ok());
    }

    #[test]
    fn violation_maps_to_expected_rule() {
        assert_eq!(
            TransferViolation::Overspend {
                balance: 0,
                amount: 1,
                limit: 0
            }
            .rule() as u8,
            ValidationRule::DoubleSpend as u8
        );
        assert_eq!(
            TransferViolation::BadReceiverSig.rule() as u8,
            ValidationRule::MutualCreditViolation as u8
        );
    }

    // ── neighborhood validator: audit_peer_chain / detect_fork ────────────────

    /// DID → Ed25519 pubkey resolver over a fixed set of identities.
    fn resolver(ids: &[&AgentIdentity]) -> impl Fn(&str) -> Option<[u8; 32]> {
        let map: std::collections::HashMap<String, [u8; 32]> = ids
            .iter()
            .map(|i| (i.did.clone(), i.verifying_key().to_bytes()))
            .collect();
        move |did: &str| map.get(did).copied()
    }

    /// A chain entry signed by `id` over arbitrary content (for forging cases the
    /// well-behaved `EngiChain` would refuse to append).
    fn signed_entry(
        id: &AgentIdentity,
        prev: Option<KotobaCid>,
        seq: u64,
        content: ChainContent,
    ) -> ChainEntry {
        let sk = SigningKey::from_bytes(&id.signing_key.to_bytes());
        let mut e = ChainEntry::new(prev, id.did.clone(), seq, content, Vec::new());
        e.sig = sk.sign(&e.signing_bytes()).to_bytes().to_vec();
        e
    }

    #[test]
    fn audit_peer_chain_passes_a_clean_chain() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 10_000);
        let mut cb = EngiChain::new(&b, 10_000);
        for n in 1..=3u64 {
            let t = xfer(&a, &b, 100, ca.head_cid(), cb.head_cid(), n);
            ca.record_spend(t.clone()).unwrap();
            cb.record_receive(t).unwrap();
        }
        let accusations = audit_peer_chain(ca.chain.entries(), &a.did, 10_000, resolver(&[&a, &b]));
        assert!(
            accusations.is_empty(),
            "a solvent, well-signed chain is clean"
        );
    }

    #[test]
    fn audit_peer_chain_flags_forged_countersignature() {
        let a = ident();
        let b = ident();
        let eve = ident();
        // a's chain carries a transfer "to b" but counter-signed by eve.
        let ak = SigningKey::from_bytes(&a.signing_key.to_bytes());
        let ek = SigningKey::from_bytes(&eve.signing_key.to_bytes());
        let forged = MutualCreditTransfer::countersign(
            a.did.clone(),
            b.did.clone(),
            100,
            None,
            None,
            1,
            0,
            &ak,
            &ek,
        )
        .unwrap();
        let entry = signed_entry(&a, None, 0, ChainContent::Transfer(forged));
        let accusations = audit_peer_chain(
            std::slice::from_ref(&entry),
            &a.did,
            10_000,
            resolver(&[&a, &b]),
        );
        assert_eq!(accusations.len(), 1);
        assert_eq!(
            accusations[0].rule as u8,
            ValidationRule::MutualCreditViolation as u8
        );
        assert_eq!(accusations[0].evidence, entry.cid);
    }

    #[test]
    fn audit_peer_chain_flags_overspend_as_double_spend() {
        let a = ident();
        let b = ident();
        let mut ca = EngiChain::new(&a, 10_000);
        let mut cb = EngiChain::new(&b, 10_000);
        for n in 1..=3u64 {
            let t = xfer(&a, &b, 100, ca.head_cid(), cb.head_cid(), n);
            ca.record_spend(t.clone()).unwrap();
            cb.record_receive(t).unwrap();
        }
        // Under a tight 150 limit the running balance is solvent for the 1st
        // debit (-100) but the 2nd and 3rd each drive it to -200 (the over-limit
        // debit is not applied, so both flag). Every flagged spend is a
        // DoubleSpend/Overspend.
        let accusations = audit_peer_chain(ca.chain.entries(), &a.did, 150, resolver(&[&a, &b]));
        assert_eq!(
            accusations.len(),
            2,
            "the 2nd and 3rd spends both overspend"
        );
        for acc in &accusations {
            assert_eq!(acc.rule as u8, ValidationRule::DoubleSpend as u8);
            assert!(matches!(acc.violation, TransferViolation::Overspend { .. }));
        }
    }

    #[test]
    fn audit_peer_chain_flags_unbound_prev() {
        let a = ident();
        let b = ident();
        // First entry is fine; second spends but pins the wrong prev (claims None
        // though the real prev is e0) — the double-spend fork shape.
        let t0 = xfer(&a, &b, 10, None, None, 1);
        let e0 = signed_entry(&a, None, 0, ChainContent::Transfer(t0));
        let t1 = xfer(&a, &b, 10, None, None, 2); // spender_prev = None (stale)
        let e1 = signed_entry(&a, Some(e0.cid.clone()), 1, ChainContent::Transfer(t1));
        let entries = vec![e0, e1.clone()];
        let accusations = audit_peer_chain(&entries, &a.did, 10_000, resolver(&[&a, &b]));
        assert_eq!(accusations.len(), 1);
        assert_eq!(accusations[0].evidence, e1.cid);
        assert!(matches!(
            accusations[0].violation,
            TransferViolation::PrevNotBound
        ));
    }

    #[test]
    fn detect_fork_identifies_same_seq_divergence() {
        let a = ident();
        let b = ident();
        // Two different transfers signed at the SAME seq=0 → a fork.
        let t_x = xfer(&a, &b, 10, None, None, 1);
        let t_y = xfer(&a, &b, 20, None, None, 2);
        let e_x = signed_entry(&a, None, 0, ChainContent::Transfer(t_x));
        let e_y = signed_entry(&a, None, 0, ChainContent::Transfer(t_y));
        assert!(detect_fork(&e_x, &e_y), "same agent+seq, diff cid = fork");
        assert!(!detect_fork(&e_x, &e_x), "an entry never forks itself");
        // A genuine linear successor (seq 1) is not a fork.
        let succ_content = ChainContent::Result {
            call_id: 9,
            status: 0,
            steps_used: 1,
        };
        let e_next = signed_entry(&a, Some(e_x.cid.clone()), 1, succ_content);
        assert!(!detect_fork(&e_x, &e_next));
    }

    // ── gossip dedup guard ────────────────────────────────────────────────────

    #[test]
    fn seen_transfers_dedups_and_evicts() {
        let mut seen = SeenTransfers::with_capacity(2);
        let id1 = KotobaCid::from_bytes(b"t1");
        let id2 = KotobaCid::from_bytes(b"t2");
        let id3 = KotobaCid::from_bytes(b"t3");
        assert!(seen.insert(id1.clone()), "first sighting is new");
        assert!(!seen.insert(id1.clone()), "duplicate is dropped");
        assert!(seen.insert(id2.clone()));
        assert_eq!(seen.len(), 2);
        // Inserting a third evicts the oldest (id1) — cap held at 2.
        assert!(seen.insert(id3.clone()));
        assert_eq!(seen.len(), 2);
        assert!(!seen.contains(&id1), "oldest evicted");
        assert!(seen.contains(&id2) && seen.contains(&id3));
        // id1 re-seen after eviction counts as new again (harmless, idempotent proj).
        assert!(seen.insert(id1));
    }

    // ── transfer-record solvency audit (audit_transfers) ──────────────────────

    /// A transfer with arbitrary parties/amount (sigs irrelevant to the audit).
    fn flat(spender: &str, receiver: &str, amount: i64, nonce: u64) -> MutualCreditTransfer {
        MutualCreditTransfer {
            body: TransferBody {
                spender: spender.to_string(),
                receiver: receiver.to_string(),
                amount,
                spender_prev: None,
                receiver_prev: None,
                nonce,
                ts: 0,
            },
            spender_sig: Vec::new(),
            receiver_sig: Vec::new(),
        }
    }

    #[test]
    fn audit_transfers_flags_overspend_against_per_agent_limit() {
        // a spends 100 three times; under a 150 limit the 2nd and 3rd breach it.
        let transfers = vec![
            flat("a", "b", 100, 1),
            flat("a", "b", 100, 2),
            flat("a", "b", 100, 3),
        ];
        let findings = audit_transfers(&transfers, |did| if did == "a" { 150 } else { 1_000_000 });
        assert_eq!(findings.len(), 2, "2nd and 3rd debits overspend");
        assert!(findings.iter().all(|f| f.did == "a"));
        assert_eq!(findings[0].balance_after, -200);
        assert_eq!(findings[0].credit_limit, 150);
        // A generous limit makes the same record solvent.
        assert!(audit_transfers(&transfers, |_| 1_000_000).is_empty());
    }

    #[test]
    fn audit_transfers_never_flags_a_pure_receiver() {
        // b only ever receives — even at credit limit 0 it is never insolvent
        // (a has headroom to fund the transfer).
        let transfers = vec![flat("a", "b", 500, 1)];
        assert!(audit_transfers(&transfers, |did| if did == "b" { 0 } else { 1_000 }).is_empty());
        // Received EN funds a later spend: b receives 500 then spends 400 at
        // limit 0 — solvent because the received credit covers it.
        let chain = vec![flat("a", "b", 500, 1), flat("b", "c", 400, 2)];
        assert!(
            audit_transfers(&chain, |did| if did == "a" { 1_000 } else { 0 }).is_empty(),
            "spending within received funds is solvent even at limit 0"
        );
        // But b spending 600 (more than the 500 it received) at limit 0 is insolvent.
        let over = vec![flat("a", "b", 500, 1), flat("b", "c", 600, 2)];
        let f = audit_transfers(&over, |did| if did == "a" { 1_000 } else { 0 });
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].did, "b");
        assert_eq!(f[0].balance_after, -100);
    }
}
