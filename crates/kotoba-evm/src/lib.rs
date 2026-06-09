//! kotoba-EVM R1 — `revm` execution over a Datom-backed state (ADR-2606091500).
//!
//! [`DatomDatabase`] implements revm's `DatabaseRef` over a `kotoba_kqe::evm_state::
//! EvmStateView` (the EVM world-state projected from the canonical Datom log), so
//! revm executes EVM transactions against kotoba's own state. [`apply_call`] runs a
//! message-call transaction and returns the resulting state diff as `evm/*` Datoms
//! ready to commit to the CommitDag (the block) — closing R1: kotoba EXECUTES EVM.
//!
//! R1 scope: message-call execution (value transfer + contract call) + state→Datom
//! diff. Signed-tx RLP decode + sender recovery (`eth_sendRawTransaction`) and block
//! production / DA / L1 anchor are R1b/R2+ (ADR roadmap).

pub mod anchor;
pub mod block;
pub mod chain;
pub mod logs;
pub mod tx;

use kotoba_core::cid::KotobaCid;
use kotoba_kqe::datom::Datom;
use kotoba_kqe::evm_state::{account_datoms, storage_datom, EvmStateView};

use revm::primitives::{
    AccountInfo, Address, Bytecode, Bytes, ExecutionResult, ResultAndState, TxKind, B256, U256,
};
use revm::{DatabaseRef, Evm};

/// revm `DatabaseRef` reading the EVM world-state from a `EvmStateView`
/// (Datom-projected). Read-only — execution produces a diff that the caller
/// commits as new `evm/*` Datoms.
pub struct DatomDatabase<'a> {
    view: &'a EvmStateView,
}

impl<'a> DatomDatabase<'a> {
    pub fn new(view: &'a EvmStateView) -> Self {
        Self { view }
    }
}

#[derive(Debug)]
pub struct DbError;
impl std::fmt::Display for DbError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "kotoba-evm db error")
    }
}
impl std::error::Error for DbError {}

impl<'a> DatabaseRef for DatomDatabase<'a> {
    type Error = DbError;

    fn basic_ref(&self, address: Address) -> Result<Option<AccountInfo>, Self::Error> {
        let a: [u8; 20] = address.into_array();
        let nonce = self.view.nonce_of(&a);
        let balance = U256::from_be_bytes(self.view.balance_of(&a));
        let codehash = self.view.codehash_of(&a);
        // empty account → None (revm treats absence as a fresh empty account)
        if nonce == 0 && balance.is_zero() && codehash.is_none() {
            return Ok(None);
        }
        let (code_hash, code) = match codehash {
            Some(ch) => {
                let bytes = self.view.code_by_hash(&ch).to_vec();
                (B256::new(ch), Some(Bytecode::new_raw(Bytes::from(bytes))))
            }
            None => (revm::primitives::KECCAK_EMPTY, None),
        };
        Ok(Some(AccountInfo { balance, nonce, code_hash, code }))
    }

    fn code_by_hash_ref(&self, code_hash: B256) -> Result<Bytecode, Self::Error> {
        let ch: [u8; 32] = code_hash.into();
        Ok(Bytecode::new_raw(Bytes::from(self.view.code_by_hash(&ch).to_vec())))
    }

    fn storage_ref(&self, address: Address, index: U256) -> Result<U256, Self::Error> {
        let a: [u8; 20] = address.into_array();
        let slot: [u8; 32] = index.to_be_bytes();
        Ok(U256::from_be_bytes(self.view.storage_of(&a, &slot)))
    }

    fn block_hash_ref(&self, _number: u64) -> Result<B256, Self::Error> {
        // R1: no historical block-hash window yet (BLOCKHASH → 0). R2 wires CommitDag.
        Ok(B256::ZERO)
    }
}

/// An EVM event log emitted during execution (for receipts / `eth_getLogs`, R3).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EvmLog {
    pub address: [u8; 20],
    pub topics: Vec<[u8; 32]>,
    pub data: Vec<u8>,
}

impl EvmLog {
    fn from_revm(log: &revm::primitives::Log) -> Self {
        Self {
            address: log.address.into_array(),
            topics: log.data.topics().iter().map(|t| (*t).into()).collect(),
            data: log.data.data.to_vec(),
        }
    }
}

/// Outcome of executing one message-call transaction over the Datom state.
pub struct ExecOutcome {
    pub success: bool,
    pub gas_used: u64,
    /// The post-state diff as `evm/*` Datoms — commit these to the CommitDag (block).
    pub datoms: Vec<Datom>,
    /// Return data (for `eth_call`).
    pub output: Vec<u8>,
    /// Event logs emitted (for receipts / `eth_getLogs`).
    pub logs: Vec<EvmLog>,
}

/// Execute a message call (`from` → `to`, `value`, `data`) against the
/// Datom-projected state. Gas is metered but priced at 0 (Charter: no gas market,
/// §2(b)); the caller must hold `value` (revm checks balance). Returns the state
/// diff as `evm/*` Datoms under `graph` (commit them = produce the block's state).
#[allow(clippy::too_many_arguments)] // a message-call's natural shape (from/to/value/data/nonce/gas/graph)
pub fn apply_call(
    view: &EvmStateView,
    from: [u8; 20],
    to: [u8; 20],
    value: U256,
    data: Vec<u8>,
    nonce: u64,
    gas_limit: u64,
    graph: &KotobaCid,
) -> Result<ExecOutcome, String> {
    let db = DatomDatabase::new(view);
    let mut evm = Evm::builder()
        .with_ref_db(db)
        .modify_tx_env(|tx| {
            tx.caller = Address::from(from);
            tx.transact_to = TxKind::Call(Address::from(to));
            tx.value = value;
            tx.data = Bytes::from(data);
            tx.gas_limit = gas_limit;
            tx.gas_price = U256::ZERO;
            tx.nonce = Some(nonce);
            tx.chain_id = None; // skip chain-id check at R1
        })
        .build();

    let ResultAndState { result, state } = evm.transact().map_err(|e| format!("{e:?}"))?;

    let (success, gas_used, output) = match &result {
        ExecutionResult::Success { gas_used, output, .. } => {
            (true, *gas_used, output.data().to_vec())
        }
        ExecutionResult::Revert { gas_used, output } => (false, *gas_used, output.to_vec()),
        ExecutionResult::Halt { gas_used, .. } => (false, *gas_used, Vec::new()),
    };

    let logs: Vec<EvmLog> = result.logs().iter().map(EvmLog::from_revm).collect();
    let datoms = state_to_datoms(&state, graph);
    Ok(ExecOutcome { success, gas_used, datoms, output, logs })
}

/// Convert revm's post-execution state into `evm/*` Datoms (the block's state diff).
/// Emits nonce+balance for every touched account, code for newly-created contracts,
/// and each changed storage slot.
pub fn state_to_datoms(
    state: &revm::primitives::HashMap<Address, revm::primitives::Account>,
    graph: &KotobaCid,
) -> Vec<Datom> {
    let mut out = Vec::new();
    for (addr, acct) in state.iter() {
        if !acct.is_touched() {
            continue;
        }
        let a: [u8; 20] = addr.into_array();
        let balance = acct.info.balance.to_be_bytes::<32>();
        // include code only when the account carries bytecode (created/contract).
        let code: Option<([u8; 32], Vec<u8>)> = acct.info.code.as_ref().and_then(|bc| {
            let raw = bc.original_bytes().to_vec();
            (!raw.is_empty()).then(|| {
                let ch: [u8; 32] = acct.info.code_hash.into();
                (ch, raw)
            })
        });
        match &code {
            Some((ch, raw)) => {
                out.extend(account_datoms(&a, acct.info.nonce, &balance, Some((ch, raw)), graph))
            }
            None => out.extend(account_datoms(&a, acct.info.nonce, &balance, None, graph)),
        }
        for (slot, val) in acct.storage.iter() {
            if val.present_value() != val.original_value() {
                let s: [u8; 32] = slot.to_be_bytes();
                let v: [u8; 32] = val.present_value().to_be_bytes();
                out.push(storage_datom(&a, &s, &v, graph));
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_kqe::delta::Delta;
    use kotoba_kqe::evm_state::account_datoms as mk_account;

    fn graph() -> KotobaCid {
        KotobaCid::from_bytes(b"g:evm")
    }
    fn addr(tag: u8) -> [u8; 20] {
        let mut a = [0u8; 20];
        a[19] = tag;
        a
    }
    fn u256(n: u64) -> [u8; 32] {
        let mut a = [0u8; 32];
        a[24..32].copy_from_slice(&n.to_be_bytes());
        a
    }

    fn view_with(datoms: Vec<Datom>) -> EvmStateView {
        let mut v = EvmStateView::new();
        let deltas: Vec<Delta> = datoms.into_iter().map(Delta::assert_datom).collect();
        v.apply(&deltas);
        v
    }

    #[test]
    fn value_transfer_executes_over_datom_state() {
        let alice = addr(0xAA);
        let bob = addr(0xBB);
        // genesis: alice has 1_000_000 wei, nonce 0; bob empty.
        let view = view_with(mk_account(&alice, 0, &u256(1_000_000), None, &graph()));

        // transfer 250_000 alice → bob
        let out = apply_call(
            &view,
            alice,
            bob,
            U256::from(250_000u64),
            vec![],
            0,
            100_000,
            &graph(),
        )
        .expect("exec ok");
        assert!(out.success, "transfer should succeed");

        // apply the produced diff to a fresh view and read the new balances.
        let post = view_with(out.datoms);
        assert_eq!(post.balance_of(&bob), u256(250_000), "bob credited");
        assert_eq!(post.balance_of(&alice), u256(750_000), "alice debited");
        assert_eq!(post.nonce_of(&alice), 1, "alice nonce bumped");
    }

    #[test]
    fn transfer_exceeding_balance_fails() {
        let alice = addr(0x01);
        let bob = addr(0x02);
        let view = view_with(mk_account(&alice, 0, &u256(100), None, &graph()));
        let res = apply_call(&view, alice, bob, U256::from(1_000u64), vec![], 0, 100_000, &graph());
        // revm rejects the tx (insufficient funds) → Err from transact validation.
        assert!(res.is_err(), "over-balance transfer must be rejected");
    }

    #[test]
    fn db_basic_ref_reports_account() {
        let alice = addr(0xAA);
        let view = view_with(mk_account(&alice, 3, &u256(500), None, &graph()));
        let db = DatomDatabase::new(&view);
        let info = db.basic_ref(Address::from(alice)).unwrap().expect("account present");
        assert_eq!(info.nonce, 3);
        assert_eq!(info.balance, U256::from(500u64));
        // unknown account → None
        assert!(db.basic_ref(Address::from(addr(0x99))).unwrap().is_none());
    }

    #[test]
    fn contract_call_captures_logs() {
        // bytecode: PUSH1 0x00, PUSH1 0x00, LOG0, STOP — emits one empty log.
        let code = vec![0x60, 0x00, 0x60, 0x00, 0xa0, 0x00];
        let codehash = kotoba_auth::eth::keccak256(&code);
        let c = addr(0xC0);
        let caller = addr(0xAA);

        let mut datoms = mk_account(&caller, 0, &u256(1_000_000), None, &graph());
        datoms.extend(mk_account(&c, 1, &u256(0), Some((&codehash, &code)), &graph()));
        let view = view_with(datoms);

        let out = apply_call(&view, caller, c, U256::ZERO, vec![], 0, 100_000, &graph())
            .expect("contract call");
        assert!(out.success, "LOG0 contract call should succeed");
        assert_eq!(out.logs.len(), 1, "LOG0 emits exactly one log");
        assert_eq!(out.logs[0].address, c, "log emitted by the contract");
        assert!(out.logs[0].topics.is_empty(), "LOG0 → no topics");
    }
}
