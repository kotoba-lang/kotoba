//! kotoba-EVM JSON-RPC server (ADR-2606091500 R3-live). A geth/viem-compatible
//! `eth_*` endpoint over kotoba's own Datom-backed EVM: forge/viem/wallets point
//! at this and deploy/call against kotoba-EVM directly — no geth.
//!
//! [`EvmNode`] holds the in-memory EVM world-state (`EvmStateView`) seeded from
//! genesis; [`dispatch`] is the pure JSON-RPC handler (fully unit-testable); the
//! [`router`] wraps it in a single `POST /` axum route over an `Arc<RwLock<EvmNode>>`
//! — a self-contained L2 RPC node.

use std::sync::Arc;

use axum::{extract::State, routing::post, Json, Router};
use serde_json::{json, Value};
use tokio::sync::RwLock;

use kotoba_auth::eth::keccak256;
use kotoba_core::cid::KotobaCid;
use kotoba_evm::{apply_call, tx::apply_raw_tx, RevmU256 as U256};
use kotoba_kqe::delta::Delta;
use kotoba_kqe::evm_state::{
    account_datoms, eth_chain_id, eth_get_balance, eth_get_code, eth_get_storage_at,
    eth_get_transaction_count, EvmStateView, KOTOBA_EVM_CHAIN_ID,
};

/// An in-memory kotoba-EVM node: the world-state view + chain metadata.
pub struct EvmNode {
    pub view: EvmStateView,
    pub chain_id: u64,
    pub block_number: u64,
    graph: KotobaCid,
}

impl EvmNode {
    pub fn new(chain_id: u64, graph: KotobaCid) -> Self {
        Self { view: EvmStateView::new(), chain_id, block_number: 0, graph }
    }

    pub fn default_node() -> Self {
        Self::new(KOTOBA_EVM_CHAIN_ID, KotobaCid::from_bytes(b"g:kotoba-evm"))
    }

    /// Seed genesis accounts (addr, balance-wei, nonce).
    pub fn genesis(&mut self, accounts: &[([u8; 20], [u8; 32], u64)]) {
        let mut datoms = Vec::new();
        for (addr, bal, nonce) in accounts {
            datoms.extend(account_datoms(addr, *nonce, bal, None, &self.graph));
        }
        self.apply(datoms);
    }

    fn apply(&mut self, datoms: Vec<kotoba_kqe::datom::Datom>) {
        self.view
            .apply(&datoms.into_iter().map(Delta::assert_datom).collect::<Vec<_>>());
    }
}

fn parse_addr(v: &Value) -> Option<[u8; 20]> {
    let s = v.as_str()?.strip_prefix("0x").unwrap_or(v.as_str()?);
    let b = hex::decode(s).ok()?;
    (b.len() == 20).then(|| {
        let mut a = [0u8; 20];
        a.copy_from_slice(&b);
        a
    })
}

fn parse_hex_bytes(v: &Value) -> Option<Vec<u8>> {
    let raw = v.as_str()?;
    hex::decode(raw.strip_prefix("0x").unwrap_or(raw)).ok()
}

fn parse_b32(v: &Value) -> Option<[u8; 32]> {
    let s = v.as_str()?;
    let mut b = hex::decode(s.strip_prefix("0x").unwrap_or(s)).ok()?;
    if b.len() > 32 {
        return None;
    }
    while b.len() < 32 {
        b.insert(0, 0);
    }
    let mut a = [0u8; 32];
    a.copy_from_slice(&b);
    Some(a)
}

/// Pure JSON-RPC method dispatch over the node. Returns the `result` value or an
/// `(code, message)` JSON-RPC error.
pub fn dispatch(node: &mut EvmNode, method: &str, params: &Value) -> Result<Value, (i64, String)> {
    let p = |i: usize| params.get(i).cloned().unwrap_or(Value::Null);
    let bad = |m: &str| (-32602i64, m.to_string());
    match method {
        "eth_chainId" => Ok(json!(eth_chain_id(node.chain_id))),
        "net_version" => Ok(json!(node.chain_id.to_string())),
        "web3_clientVersion" => Ok(json!("kotoba-evm/0.1")),
        "eth_blockNumber" => Ok(json!(format!("0x{:x}", node.block_number))),
        "eth_gasPrice" => Ok(json!("0x0")), // Charter §2(b): no gas market
        "eth_getBalance" => {
            let a = parse_addr(&p(0)).ok_or_else(|| bad("invalid address"))?;
            Ok(json!(eth_get_balance(&node.view, &a)))
        }
        "eth_getTransactionCount" => {
            let a = parse_addr(&p(0)).ok_or_else(|| bad("invalid address"))?;
            Ok(json!(eth_get_transaction_count(&node.view, &a)))
        }
        "eth_getCode" => {
            let a = parse_addr(&p(0)).ok_or_else(|| bad("invalid address"))?;
            Ok(json!(eth_get_code(&node.view, &a)))
        }
        "eth_getStorageAt" => {
            let a = parse_addr(&p(0)).ok_or_else(|| bad("invalid address"))?;
            let slot = parse_b32(&p(1)).ok_or_else(|| bad("invalid slot"))?;
            Ok(json!(eth_get_storage_at(&node.view, &a, &slot)))
        }
        "eth_call" => {
            let call = p(0);
            let to = parse_addr(call.get("to").unwrap_or(&Value::Null))
                .ok_or_else(|| bad("eth_call: invalid 'to'"))?;
            let from = call.get("from").and_then(parse_addr).unwrap_or([0u8; 20]);
            let data = call.get("data").and_then(parse_hex_bytes).unwrap_or_default();
            let value = call
                .get("value")
                .and_then(parse_b32)
                .map(U256::from_be_bytes)
                .unwrap_or(U256::ZERO);
            let nonce = node.view.nonce_of(&from);
            let out = apply_call(&node.view, from, to, value, data, nonce, 30_000_000, &node.graph)
                .map_err(|e| (-32000, e))?;
            Ok(json!(format!("0x{}", hex::encode(out.output))))
        }
        "eth_sendRawTransaction" => {
            let raw = parse_hex_bytes(&p(0)).ok_or_else(|| bad("invalid raw tx"))?;
            let (_tx, out) =
                apply_raw_tx(&node.view, &raw, &node.graph).map_err(|e| (-32000, e))?;
            if !out.success {
                return Err((-32000, "transaction reverted".into()));
            }
            // persist the diff into the node state + advance the block number.
            node.apply(out.datoms);
            node.block_number += 1;
            Ok(json!(format!("0x{}", hex::encode(keccak256(&raw))))) // tx hash
        }
        other => Err((-32601, format!("method not found: {other}"))),
    }
}

/// Build the full JSON-RPC response envelope for one request.
pub fn handle(node: &mut EvmNode, req: &Value) -> Value {
    let id = req.get("id").cloned().unwrap_or(Value::Null);
    let method = req.get("method").and_then(|m| m.as_str()).unwrap_or("");
    let params = req.get("params").cloned().unwrap_or(json!([]));
    match dispatch(node, method, &params) {
        Ok(result) => json!({ "jsonrpc": "2.0", "id": id, "result": result }),
        Err((code, message)) => {
            json!({ "jsonrpc": "2.0", "id": id, "error": { "code": code, "message": message } })
        }
    }
}

async fn rpc_handler(State(node): State<Arc<RwLock<EvmNode>>>, Json(req): Json<Value>) -> Json<Value> {
    let mut n = node.write().await;
    Json(handle(&mut n, &req))
}

/// A self-contained kotoba-EVM JSON-RPC server router (`POST /`). Point forge/viem
/// at the address this is served on.
pub fn router(node: Arc<RwLock<EvmNode>>) -> Router {
    Router::new().route("/", post(rpc_handler)).with_state(node)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn addr(t: u8) -> [u8; 20] {
        let mut a = [0u8; 20];
        a[19] = t;
        a
    }
    fn u256(n: u128) -> [u8; 32] {
        U256::from(n).to_be_bytes()
    }
    fn req(method: &str, params: Value) -> Value {
        json!({ "jsonrpc": "2.0", "id": 1, "method": method, "params": params })
    }
    fn result(node: &mut EvmNode, method: &str, params: Value) -> Value {
        let r = handle(node, &req(method, params));
        assert!(r.get("error").is_none(), "rpc error: {r}");
        r["result"].clone()
    }
    // canonical EIP-155 tx (sender 0x9d8a..a4f nonce 9 → to 0x3535.. value 1e18).
    const EIP155_RAW: &str = "0xf86c098504a817c800825208943535353535353535353535353535353535353535880de0b6b3a76400008025a028ef61340bd939bc2195fe537567866003e1a15d3c71ff63e1590620aa636276a067cbe9d8997f761aecb703304b3800ccf555c9f3dc64214b297fb1966a3b6d83";

    #[test]
    fn reads_chainid_and_balance() {
        let mut node = EvmNode::default_node();
        let alice = addr(0xAA);
        node.genesis(&[(alice, u256(1_000_000), 0)]);

        assert_eq!(result(&mut node, "eth_chainId", json!([])), json!("0x6b6f74"));
        assert_eq!(
            result(&mut node, "eth_getBalance", json!(["0x00000000000000000000000000000000000000aa", "latest"])),
            json!("0xf4240") // 1_000_000
        );
        assert_eq!(result(&mut node, "eth_blockNumber", json!([])), json!("0x0"));
    }

    #[test]
    fn send_raw_transaction_advances_state_and_block() {
        let mut node = EvmNode::default_node();
        let mut from = [0u8; 20];
        from.copy_from_slice(&hex::decode("9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f").unwrap());
        node.genesis(&[(from, u256(2_000_000_000_000_000_000), 9)]);

        let txhash = result(&mut node, "eth_sendRawTransaction", json!([EIP155_RAW]));
        assert!(txhash.as_str().unwrap().starts_with("0x"));
        // recipient credited 1e18, block advanced.
        assert_eq!(
            result(&mut node, "eth_getBalance", json!(["0x3535353535353535353535353535353535353535", "latest"])),
            json!("0xde0b6b3a7640000") // 1e18
        );
        assert_eq!(result(&mut node, "eth_blockNumber", json!([])), json!("0x1"));
        // sender nonce 9 → 10
        assert_eq!(
            result(&mut node, "eth_getTransactionCount", json!(["0x9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f", "latest"])),
            json!("0xa")
        );
    }

    #[test]
    fn unknown_method_returns_error() {
        let mut node = EvmNode::default_node();
        let r = handle(&mut node, &req("eth_doesNotExist", json!([])));
        assert_eq!(r["error"]["code"], json!(-32601));
    }

    #[test]
    fn getcode_empty_for_eoa() {
        let mut node = EvmNode::default_node();
        node.genesis(&[(addr(0x01), u256(1), 0)]);
        assert_eq!(
            result(&mut node, "eth_getCode", json!(["0x0000000000000000000000000000000000000001", "latest"])),
            json!("0x")
        );
    }
}
