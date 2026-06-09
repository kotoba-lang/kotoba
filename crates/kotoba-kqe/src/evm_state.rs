//! kotoba-EVM state model — EVM accounts/code/storage projected AS Datoms, with a
//! read view + geth/viem-compatible `eth_*` value formatters (ADR-2606091500 R0).
//!
//! This is the state layer of kotoba-as-its-own-EVM-L2: the canonical Datom log IS
//! the EVM world-state. R0 is the deterministic, pure, fully-tested foundation —
//! the projection schema, a [`EvmStateView`] reducer (sibling of `SocialCapitalView`),
//! and the read-side RPC value encodings. Execution (revm over a `DatomDatabase`),
//! block production, DA, and the L1 anchor are R1+ (see the ADR roadmap).
//!
//! Datom schema (entity = the 20-byte address as a CID via `KotobaCid::from_bytes`,
//! or the codehash CID for the code blob):
//!
//! | predicate                       | value          | meaning                    |
//! |---------------------------------|----------------|----------------------------|
//! | `evm/acct/nonce`                | Integer        | account nonce              |
//! | `evm/acct/balance`              | Bytes(u256-be) | balance (wei)              |
//! | `evm/acct/codehash`             | Cid            | keccak256(code) → code blob|
//! | `evm/code`                      | Bytes          | bytecode (on the codehash) |
//! | `evm/storage/<slot-hex>`        | Bytes(32)      | storage slot value         |

use std::collections::HashMap;

use kotoba_core::cid::KotobaCid;

use crate::datom::{Datom, Value};
use crate::delta::Delta;

pub const ACCT_NONCE_PRED: &str = "evm/acct/nonce";
pub const ACCT_BALANCE_PRED: &str = "evm/acct/balance";
pub const ACCT_CODEHASH_PRED: &str = "evm/acct/codehash";
pub const CODE_PRED: &str = "evm/code";
pub const STORAGE_PRED_PREFIX: &str = "evm/storage/";

/// Entity CID for a 20-byte EVM address (the social/EVM convention: `from_bytes`).
pub fn addr_cid(addr: &[u8; 20]) -> KotobaCid {
    KotobaCid::from_bytes(addr)
}

/// Entity CID for a 32-byte code hash (the code blob lives under this).
pub fn codehash_cid(codehash: &[u8; 32]) -> KotobaCid {
    KotobaCid::from_bytes(codehash)
}

/// `evm/storage/<slot-hex>` predicate for a 32-byte storage slot.
pub fn storage_pred(slot: &[u8; 32]) -> String {
    format!("{STORAGE_PRED_PREFIX}{}", hex::encode(slot))
}

fn slot_from_pred(pred: &str) -> Option<[u8; 32]> {
    let body = pred.strip_prefix(STORAGE_PRED_PREFIX)?;
    let bytes = hex::decode(body).ok()?;
    (bytes.len() == 32).then(|| {
        let mut a = [0u8; 32];
        a.copy_from_slice(&bytes);
        a
    })
}

fn bytes32(v: &Value) -> Option<[u8; 32]> {
    if let Value::Bytes(b) = v {
        if b.len() == 32 {
            let mut a = [0u8; 32];
            a.copy_from_slice(b);
            return Some(a);
        }
    }
    None
}

// ── Datom emission (genesis / state-diff projection) ──────────────────────────

/// Project an account's state into `evm/*` Datoms under `graph`. `code` is
/// optional (EOAs have none); when present its keccak256 must be supplied as
/// `codehash` so the code blob is content-addressed under the codehash CID.
pub fn account_datoms(
    addr: &[u8; 20],
    nonce: u64,
    balance: &[u8; 32],
    code: Option<(&[u8; 32], &[u8])>,
    graph: &KotobaCid,
) -> Vec<Datom> {
    let e = addr_cid(addr);
    let mut out = vec![
        Datom::assert(e.clone(), ACCT_NONCE_PRED.to_string(), Value::Integer(nonce as i64), graph.clone()),
        Datom::assert(e.clone(), ACCT_BALANCE_PRED.to_string(), Value::Bytes(balance.to_vec()), graph.clone()),
    ];
    if let Some((codehash, bytecode)) = code {
        let ch = codehash_cid(codehash);
        out.push(Datom::assert(e, ACCT_CODEHASH_PRED.to_string(), Value::Cid(ch.clone()), graph.clone()));
        out.push(Datom::assert(ch, CODE_PRED.to_string(), Value::Bytes(bytecode.to_vec()), graph.clone()));
    }
    out
}

/// Project a single storage write into a Datom.
pub fn storage_datom(addr: &[u8; 20], slot: &[u8; 32], value: &[u8; 32], graph: &KotobaCid) -> Datom {
    Datom::assert(addr_cid(addr), storage_pred(slot), Value::Bytes(value.to_vec()), graph.clone())
}

// ── Read view (a Datom reducer; the EVM world-state for reads) ────────────────

#[derive(Default)]
pub struct EvmStateView {
    nonce: HashMap<KotobaCid, u64>,
    balance: HashMap<KotobaCid, [u8; 32]>,
    codehash: HashMap<KotobaCid, KotobaCid>,
    code: HashMap<KotobaCid, Vec<u8>>,
    storage: HashMap<(KotobaCid, [u8; 32]), [u8; 32]>,
}

impl EvmStateView {
    pub fn new() -> Self {
        Self::default()
    }

    /// Fold `evm/*` Datoms into the world-state. Non-`evm/*` Datoms are ignored.
    /// Last-writer-wins per (entity, field) — matching EVM state-overwrite semantics.
    pub fn apply(&mut self, deltas: &[Delta]) {
        for d in deltas {
            if !d.is_assert() {
                continue;
            }
            let e = d.entity().clone();
            let attr = d.attribute();
            match attr {
                ACCT_NONCE_PRED => {
                    if let Value::Integer(n) = &d.datom.v {
                        self.nonce.insert(e, (*n).max(0) as u64);
                    }
                }
                ACCT_BALANCE_PRED => {
                    if let Some(b) = bytes32(&d.datom.v) {
                        self.balance.insert(e, b);
                    }
                }
                ACCT_CODEHASH_PRED => {
                    if let Value::Cid(ch) = &d.datom.v {
                        self.codehash.insert(e, ch.clone());
                    }
                }
                CODE_PRED => {
                    if let Value::Bytes(b) = &d.datom.v {
                        self.code.insert(e, b.clone());
                    }
                }
                _ if attr.starts_with(STORAGE_PRED_PREFIX) => {
                    if let (Some(slot), Some(val)) = (slot_from_pred(attr), bytes32(&d.datom.v)) {
                        self.storage.insert((e, slot), val);
                    }
                }
                _ => {}
            }
        }
    }

    pub fn nonce_of(&self, addr: &[u8; 20]) -> u64 {
        self.nonce.get(&addr_cid(addr)).copied().unwrap_or(0)
    }

    pub fn balance_of(&self, addr: &[u8; 20]) -> [u8; 32] {
        self.balance.get(&addr_cid(addr)).copied().unwrap_or([0u8; 32])
    }

    /// Contract bytecode (empty for EOAs / unknown accounts).
    pub fn code_of(&self, addr: &[u8; 20]) -> &[u8] {
        self.codehash
            .get(&addr_cid(addr))
            .and_then(|ch| self.code.get(ch))
            .map(Vec::as_slice)
            .unwrap_or(&[])
    }

    pub fn storage_of(&self, addr: &[u8; 20], slot: &[u8; 32]) -> [u8; 32] {
        self.storage.get(&(addr_cid(addr), *slot)).copied().unwrap_or([0u8; 32])
    }

    pub fn account_count(&self) -> usize {
        self.balance.len().max(self.nonce.len())
    }
}

// ── eth_* read-RPC value encodings (geth/viem parity) ─────────────────────────

/// JSON-RPC QUANTITY: minimal big-endian hex, `"0x0"` for zero (geth semantics).
pub fn quantity_hex(be: &[u8]) -> String {
    let first = be.iter().position(|&b| b != 0);
    match first {
        None => "0x0".to_string(),
        Some(i) => {
            let s = hex::encode(&be[i..]);
            // strip a single leading zero nibble if present
            let s = s.trim_start_matches('0');
            format!("0x{}", if s.is_empty() { "0" } else { s })
        }
    }
}

/// JSON-RPC DATA: full `0x`-prefixed hex (no trimming).
pub fn data_hex(bytes: &[u8]) -> String {
    format!("0x{}", hex::encode(bytes))
}

/// `eth_getBalance` → QUANTITY.
pub fn eth_get_balance(view: &EvmStateView, addr: &[u8; 20]) -> String {
    quantity_hex(&view.balance_of(addr))
}

/// `eth_getTransactionCount` (nonce) → QUANTITY.
pub fn eth_get_transaction_count(view: &EvmStateView, addr: &[u8; 20]) -> String {
    quantity_hex(&view.nonce_of(addr).to_be_bytes())
}

/// `eth_getCode` → DATA.
pub fn eth_get_code(view: &EvmStateView, addr: &[u8; 20]) -> String {
    data_hex(view.code_of(addr))
}

/// `eth_getStorageAt` → DATA (always a full 32-byte word).
pub fn eth_get_storage_at(view: &EvmStateView, addr: &[u8; 20], slot: &[u8; 32]) -> String {
    data_hex(&view.storage_of(addr, slot))
}

/// `eth_chainId` → QUANTITY. Default kotoba-EVM chainId `0x6b6f74` ("kot").
pub const KOTOBA_EVM_CHAIN_ID: u64 = 0x6b_6f74;
pub fn eth_chain_id(chain_id: u64) -> String {
    quantity_hex(&chain_id.to_be_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;

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
    fn slot(tag: u8) -> [u8; 32] {
        let mut a = [0u8; 32];
        a[31] = tag;
        a
    }

    fn apply(view: &mut EvmStateView, datoms: Vec<Datom>) {
        let deltas: Vec<Delta> = datoms.into_iter().map(Delta::assert_datom).collect();
        view.apply(&deltas);
    }

    #[test]
    fn quantity_hex_geth_semantics() {
        assert_eq!(quantity_hex(&[0u8; 32]), "0x0");
        assert_eq!(quantity_hex(&u256(255)), "0xff");
        assert_eq!(quantity_hex(&u256(256)), "0x100");
        assert_eq!(quantity_hex(&u256(1)), "0x1");
    }

    #[test]
    fn eoa_account_roundtrips_through_view() {
        let mut v = EvmStateView::new();
        let a = addr(0xAA);
        apply(&mut v, account_datoms(&a, 7, &u256(1_000_000), None, &graph()));
        assert_eq!(v.nonce_of(&a), 7);
        assert_eq!(v.balance_of(&a), u256(1_000_000));
        assert_eq!(v.code_of(&a), &[] as &[u8]); // EOA: no code
        // RPC encodings
        assert_eq!(eth_get_transaction_count(&v, &a), "0x7");
        assert_eq!(eth_get_balance(&v, &a), "0xf4240"); // 1_000_000
        assert_eq!(eth_get_code(&v, &a), "0x");
    }

    #[test]
    fn contract_account_code_and_storage() {
        let mut v = EvmStateView::new();
        let c = addr(0xC0);
        let bytecode = vec![0x60, 0x80, 0x60, 0x40]; // PUSH1 0x80 PUSH1 0x40 …
        // R0 stores code under the codehash CID without re-deriving keccak; a fixed
        // 32-byte codehash suffices (real keccak binding is enforced at R1 execution).
        let codehash = [0x11u8; 32];
        apply(&mut v, account_datoms(&c, 1, &u256(0), Some((&codehash, &bytecode)), &graph()));
        apply(&mut v, vec![storage_datom(&c, &slot(0x05), &u256(42), &graph())]);

        assert_eq!(v.code_of(&c), bytecode.as_slice());
        assert_eq!(eth_get_code(&v, &c), "0x60806040");
        assert_eq!(v.storage_of(&c, &slot(0x05)), u256(42));
        assert_eq!(eth_get_storage_at(&v, &c, &slot(0x05)), data_hex(&u256(42)));
        // unset slot → 32 zero bytes
        assert_eq!(eth_get_storage_at(&v, &c, &slot(0x06)), data_hex(&[0u8; 32]));
    }

    #[test]
    fn unknown_account_defaults() {
        let v = EvmStateView::new();
        let a = addr(0x01);
        assert_eq!(eth_get_balance(&v, &a), "0x0");
        assert_eq!(eth_get_transaction_count(&v, &a), "0x0");
        assert_eq!(eth_get_code(&v, &a), "0x");
        assert_eq!(eth_get_storage_at(&v, &a, &slot(0)), data_hex(&[0u8; 32]));
    }

    #[test]
    fn last_writer_wins_per_field() {
        let mut v = EvmStateView::new();
        let a = addr(0x02);
        apply(&mut v, account_datoms(&a, 1, &u256(100), None, &graph()));
        apply(&mut v, account_datoms(&a, 2, &u256(250), None, &graph()));
        assert_eq!(v.nonce_of(&a), 2);
        assert_eq!(v.balance_of(&a), u256(250));
    }

    #[test]
    fn chain_id_encoding() {
        assert_eq!(eth_chain_id(KOTOBA_EVM_CHAIN_ID), "0x6b6f74");
        assert_eq!(eth_chain_id(1), "0x1");
    }
}
