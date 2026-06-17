//! Decode anchor-chain `MishmarBondEscrow` event logs (`eth_getLogs` JSON) into
//! the projected Datoms that drive `kotoba_query::social::PinIndex`, plus `Slashed`
//! observations (ADR-2606082100; `docs/MISHMAR-OBSERVATION.md`).
//!
//! kotoba stays **read+verify**: this module only decodes logs the caller fetched
//! read-only. The live `eth_getLogs` RPC dispatch (against geth-private / Base L2
//! via the EVM read surface) is injected by the caller — this is the pure,
//! testable decoding half.
//!
//! On-chain identifiers (`bytes32` pinId/rootCid, 20-byte pinner address) are
//! mapped to `KotobaCid` deterministically via [`KotobaCid::from_bytes`], so the
//! same on-chain id always yields the same CID across the index + settlement.
//! (Reconciling these with the social/origin DIDs — the `did ↔ cid` bridge — is a
//! separate follow-up.)

use kotoba_auth::eth::keccak256;
use kotoba_core::cid::KotobaCid;
use kotoba_query::datom::{Datom, Value};
use kotoba_query::social::{PIN_BOND_PRED, PIN_PINNER_PRED, PIN_ROOT_PRED};

/// `event Pinned(bytes32 indexed pinId, bytes32 indexed rootCid, address indexed pinner, bytes32 didHash, uint256 bond, uint64 expiresAt)`
const PINNED_SIG: &[u8] = b"Pinned(bytes32,bytes32,address,bytes32,uint256,uint64)";
/// `event Slashed(bytes32 indexed pinId, uint256 bond, uint256 toRetainer, uint256 toPublicFund)`
const SLASHED_SIG: &[u8] = b"Slashed(bytes32,uint256,uint256,uint256)";

fn topic0_hex(sig: &[u8]) -> String {
    format!("0x{}", hex::encode(keccak256(sig)))
}

fn hex32(s: &str) -> Option<[u8; 32]> {
    let body = s.strip_prefix("0x").unwrap_or(s);
    let bytes = hex::decode(body).ok()?;
    if bytes.len() != 32 {
        return None;
    }
    let mut a = [0u8; 32];
    a.copy_from_slice(&bytes);
    Some(a)
}

/// Low 128 bits of a 32-byte EVM word, big-endian (amounts assumed < 2^128).
fn word_u128(w: &[u8; 32]) -> u128 {
    let mut a = [0u8; 16];
    a.copy_from_slice(&w[16..32]);
    u128::from_be_bytes(a)
}

/// 20-byte address from a 32-byte (left-padded) indexed-address topic.
fn addr20(t: &[u8; 32]) -> [u8; 20] {
    let mut a = [0u8; 20];
    a.copy_from_slice(&t[12..32]);
    a
}

fn topics_of(log: &serde_json::Value) -> Option<Vec<[u8; 32]>> {
    let arr = log.get("topics")?.as_array()?;
    let mut out = Vec::with_capacity(arr.len());
    for t in arr {
        out.push(hex32(t.as_str()?)?);
    }
    Some(out)
}

/// A decoded `Slashed` observation (a pin's availability proof failed).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ObservedSlash {
    pub pin_id: KotobaCid,
    pub bond: u128,
    pub to_retainer: u128,
    pub to_public_fund: u128,
}

/// Decode `Pinned` logs from an `eth_getLogs` result array → the
/// `mishmar/pin/{pinner,root,bond}` Datoms that feed `PinIndex`. `graph` is the
/// graph CID the projected Datoms are written under. Non-`Pinned` / malformed logs
/// are skipped. `logs` is the JSON array (the `result` field of an `eth_getLogs`
/// reply).
///
/// The indexed topics carry pinId/rootCid/pinner; the non-indexed `data` carries
/// `didHash(32) ++ bond(32) ++ expiresAt(32)`. The bond (`uint256`) is projected
/// as a `mishmar/pin/bond` `Integer` (saturating into i64 — the smic/Mkoto Quad
/// convention) so the replica membrane ([`eligible_replica`]) can gate on it. A
/// log whose `data` is missing/short still yields root+pinner (bond omitted).
pub fn decode_pinned_logs(logs: &serde_json::Value, graph: &KotobaCid) -> Vec<Datom> {
    let want = topic0_hex(PINNED_SIG);
    let mut out = Vec::new();
    let Some(arr) = logs.as_array() else {
        return out;
    };
    for log in arr {
        let Some(topics) = topics_of(log) else {
            continue;
        };
        // Pinned has 4 topics: sig + pinId + rootCid + pinner.
        if topics.len() < 4 {
            continue;
        }
        if !format!("0x{}", hex::encode(topics[0])).eq_ignore_ascii_case(&want) {
            continue;
        }
        let pin_cid = KotobaCid::from_bytes(&topics[1]);
        let root_cid = KotobaCid::from_bytes(&topics[2]);
        let pinner_cid = KotobaCid::from_bytes(&addr20(&topics[3]));
        out.push(Datom::assert(
            pin_cid.clone(),
            PIN_ROOT_PRED.to_string(),
            Value::Cid(root_cid),
            graph.clone(),
        ));
        out.push(Datom::assert(
            pin_cid.clone(),
            PIN_PINNER_PRED.to_string(),
            Value::Cid(pinner_cid),
            graph.clone(),
        ));
        // data = didHash(32) ++ bond(32) ++ expiresAt(32); bond is word(1).
        if let Some(bond) = pinned_bond_mkoto(log) {
            out.push(Datom::assert(
                pin_cid,
                PIN_BOND_PRED.to_string(),
                Value::Integer(bond),
                graph.clone(),
            ));
        }
    }
    out
}

/// Extract the `bond` (`uint256`, mKOTO) from a `Pinned` log's non-indexed `data`,
/// saturating into i64. Returns `None` if `data` is absent / unparseable / too
/// short to contain the bond word.
fn pinned_bond_mkoto(log: &serde_json::Value) -> Option<i64> {
    let data_str = log.get("data").and_then(|d| d.as_str())?;
    let body = data_str.strip_prefix("0x").unwrap_or(data_str);
    let bytes = hex::decode(body).ok()?;
    // need at least didHash(32) + bond(32) = 64 bytes to read word(1).
    if bytes.len() < 64 {
        return None;
    }
    let mut w = [0u8; 32];
    w.copy_from_slice(&bytes[32..64]);
    Some(i64::try_from(word_u128(&w)).unwrap_or(i64::MAX))
}

/// Decode `Slashed` logs from an `eth_getLogs` result array. data layout =
/// `bond(32) ++ toRetainer(32) ++ toPublicFund(32)`.
pub fn decode_slash_logs(logs: &serde_json::Value) -> Vec<ObservedSlash> {
    let want = topic0_hex(SLASHED_SIG);
    let mut out = Vec::new();
    let Some(arr) = logs.as_array() else {
        return out;
    };
    for log in arr {
        let Some(topics) = topics_of(log) else {
            continue;
        };
        if topics.len() < 2 {
            continue;
        }
        if !format!("0x{}", hex::encode(topics[0])).eq_ignore_ascii_case(&want) {
            continue;
        }
        let Some(data_str) = log.get("data").and_then(|d| d.as_str()) else {
            continue;
        };
        let body = data_str.strip_prefix("0x").unwrap_or(data_str);
        let Ok(bytes) = hex::decode(body) else {
            continue;
        };
        if bytes.len() < 96 {
            continue;
        }
        let word = |i: usize| -> [u8; 32] {
            let mut a = [0u8; 32];
            a.copy_from_slice(&bytes[i * 32..i * 32 + 32]);
            a
        };
        out.push(ObservedSlash {
            pin_id: KotobaCid::from_bytes(&topics[1]),
            bond: word_u128(&word(0)),
            to_retainer: word_u128(&word(1)),
            to_public_fund: word_u128(&word(2)),
        });
    }
    out
}

// ── Live observation sources (transport-injected; only the socket is external) ─
//
// `JsonRpcTransport` is the one genuinely-external seam: a real impl POSTs to a
// running EVM JSON-RPC endpoint (geth-private / Base L2). Everything above it —
// request construction, response decoding, Datom projection — is pure + tested.

/// Minimal EVM JSON-RPC transport. The reqwest impl is the live socket; tests
/// inject a fake. `params` is the JSON-RPC `params` array; returns `result`.
pub trait JsonRpcTransport {
    fn call(&self, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String>;
}

/// reqwest-backed transport against an EVM JSON-RPC endpoint. Uses the blocking
/// client, so call it off the async hot path (e.g. from a background job /
/// `spawn_blocking`). Read-only methods only (kotoba stays read+verify).
pub struct ReqwestRpc {
    pub url: String,
}

impl JsonRpcTransport for ReqwestRpc {
    fn call(&self, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
        let body =
            serde_json::json!({"jsonrpc": "2.0", "id": 1, "method": method, "params": params});
        let resp: serde_json::Value = reqwest::blocking::Client::new()
            .post(&self.url)
            .json(&body)
            .send()
            .map_err(|e| format!("rpc send: {e}"))?
            .json()
            .map_err(|e| format!("rpc decode: {e}"))?;
        if let Some(err) = resp.get("error") {
            return Err(format!("rpc error: {err}"));
        }
        Ok(resp
            .get("result")
            .cloned()
            .unwrap_or(serde_json::Value::Null))
    }
}

/// `eth_getLogs` observation source for MishmarBondEscrow pin events, over an
/// injected transport. The only external dependency is `transport.call`'s socket;
/// the filter build + decode (`decode_pinned_logs`/`decode_slash_logs`) are tested.
pub struct EvmLogObservationSource<T: JsonRpcTransport> {
    transport: T,
    escrow_address: String,
    graph: KotobaCid,
}

impl<T: JsonRpcTransport> EvmLogObservationSource<T> {
    pub fn new(transport: T, escrow_address: impl Into<String>, graph: KotobaCid) -> Self {
        Self {
            transport,
            escrow_address: escrow_address.into(),
            graph,
        }
    }

    fn fetch_logs(&self, from_block: &str, to_block: &str) -> Result<serde_json::Value, String> {
        let filter = serde_json::json!({
            "address": self.escrow_address,
            "fromBlock": from_block,
            "toBlock": to_block,
        });
        self.transport
            .call("eth_getLogs", serde_json::json!([filter]))
    }

    /// Fetch + decode `Pinned` logs → `mishmar/pin/{pinner,root}` Datoms (feed PinIndex).
    pub fn pin_datoms(&self, from_block: &str, to_block: &str) -> Result<Vec<Datom>, String> {
        let logs = self.fetch_logs(from_block, to_block)?;
        Ok(decode_pinned_logs(&logs, &self.graph))
    }

    /// Fetch + decode `Slashed` logs → availability-failure observations.
    pub fn slashes(&self, from_block: &str, to_block: &str) -> Result<Vec<ObservedSlash>, String> {
        let logs = self.fetch_logs(from_block, to_block)?;
        Ok(decode_slash_logs(&logs))
    }
}

/// **Provisional (R0)** parser for a KaizenObserver wellbecoming-Δ feed. The real
/// KaizenObserver output schema is not yet pinned (ADR-2605240200) — this parses a
/// documented expected shape and MUST be reconciled against the live feed:
///
/// ```json
/// [ { "did": "did:web:…", "epoch": 12, "delta": 5, "council_attested": true }, … ]
/// ```
///
/// `did` is mapped to the social entity CID via [`crate::did_bridge::did_to_cid`].
/// Entries missing required fields are skipped.
pub fn parse_kaizen_wellbecoming(
    feed: &serde_json::Value,
) -> Vec<kotoba_query::social::ObservedWellbecoming> {
    let mut out = Vec::new();
    let Some(arr) = feed.as_array() else {
        return out;
    };
    for e in arr {
        let (Some(did), Some(epoch), Some(delta)) = (
            e.get("did").and_then(|v| v.as_str()),
            e.get("epoch").and_then(|v| v.as_u64()),
            e.get("delta").and_then(|v| v.as_i64()),
        ) else {
            continue;
        };
        let council_attested = e
            .get("council_attested")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        out.push(kotoba_query::social::ObservedWellbecoming {
            did: crate::did_bridge::did_to_cid(did),
            epoch,
            delta,
            council_attested,
        });
    }
    out
}

/// Observe a graph head's finality via a read-only `eth_call` to
/// `AnchorBridge.committerOf(rootHash)` over an injected transport (GROWTH p8).
/// kotoba stays read+verify — this only reads. Transport errors or an
/// undecodable result resolve to "not anchored" (not final), never panic.
pub fn observe_finality<T: JsonRpcTransport>(
    transport: &T,
    anchor_address: &str,
    head: &KotobaCid,
) -> kotoba_evm::anchor::FinalityStatus {
    let root = kotoba_evm::anchor::root_hash_of(head);
    let calldata = kotoba_evm::anchor::committer_of_calldata(&root);
    let data_hex = format!("0x{}", hex::encode(&calldata));
    let params = serde_json::json!([{ "to": anchor_address, "data": data_hex }, "latest"]);
    let result_bytes = match transport.call("eth_call", params) {
        Ok(v) => v
            .as_str()
            .and_then(|s| hex::decode(s.strip_prefix("0x").unwrap_or(s)).ok())
            .unwrap_or_default(),
        Err(_) => Vec::new(),
    };
    kotoba_evm::anchor::finality_from_call_result(head, &result_bytes)
}

/// Observe finality for a batch of graph `heads` via `committerOf` `eth_call`s
/// over an injected transport (GROWTH p8 checkpoint observation). Returns one
/// `(head, FinalityStatus)` per input; pair with [`kotoba_evm::anchor::finality_summary`]
/// for the node.status counts. Read-only; per-head transport errors are not final.
pub fn observe_finalities<T: JsonRpcTransport>(
    transport: &T,
    anchor_address: &str,
    heads: &[KotobaCid],
) -> Vec<(KotobaCid, kotoba_evm::anchor::FinalityStatus)> {
    heads
        .iter()
        .map(|h| (h.clone(), observe_finality(transport, anchor_address, h)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_query::social::PinIndex;
    use serde_json::json;

    /// Fake transport returning a canned logs array for eth_getLogs.
    struct FakeRpc {
        logs: serde_json::Value,
    }
    impl JsonRpcTransport for FakeRpc {
        fn call(
            &self,
            method: &str,
            _params: serde_json::Value,
        ) -> Result<serde_json::Value, String> {
            assert_eq!(method, "eth_getLogs");
            Ok(self.logs.clone())
        }
    }

    fn topic_str(bytes: &[u8; 32]) -> String {
        format!("0x{}", hex::encode(bytes))
    }

    /// Fake transport returning a canned `eth_call` result word.
    struct FakeCall {
        result: serde_json::Value,
    }
    impl JsonRpcTransport for FakeCall {
        fn call(
            &self,
            method: &str,
            _params: serde_json::Value,
        ) -> Result<serde_json::Value, String> {
            assert_eq!(method, "eth_call");
            Ok(self.result.clone())
        }
    }

    fn address_word(low_byte: u8) -> serde_json::Value {
        let mut w = [0u8; 32];
        w[31] = low_byte;
        json!(format!("0x{}", hex::encode(w)))
    }

    #[test]
    fn observe_finality_reads_committer_over_eth_call() {
        let head = KotobaCid::from_bytes(b"final-head");
        // non-zero committer → final.
        let st = observe_finality(&FakeCall { result: address_word(0xAA) }, "0xanchor", &head);
        assert!(st.is_final);
        assert_eq!(st.root_hash, kotoba_evm::anchor::root_hash_of(&head));
        // zero committer (never anchored) → not final.
        let zero = observe_finality(&FakeCall { result: address_word(0) }, "0xanchor", &head);
        assert!(!zero.is_final);
    }

    #[test]
    fn observe_finality_transport_error_is_not_final() {
        struct ErrRpc;
        impl JsonRpcTransport for ErrRpc {
            fn call(&self, _: &str, _: serde_json::Value) -> Result<serde_json::Value, String> {
                Err("rpc down".into())
            }
        }
        let head = KotobaCid::from_bytes(b"h");
        assert!(!observe_finality(&ErrRpc, "0xanchor", &head).is_final);
    }

    #[test]
    fn observe_finalities_batches_and_summarizes() {
        // a fake where every committerOf returns the same non-zero committer.
        let heads = [
            KotobaCid::from_bytes(b"head-a"),
            KotobaCid::from_bytes(b"head-b"),
        ];
        let pairs =
            observe_finalities(&FakeCall { result: address_word(0xAB) }, "0xanchor", &heads);
        assert_eq!(pairs.len(), 2);
        assert_eq!(pairs[0].0, heads[0]); // order + head preserved
        let statuses: Vec<_> = pairs.iter().map(|(_, s)| *s).collect();
        let summary = kotoba_evm::anchor::finality_summary(&statuses);
        assert_eq!(summary.tracked, 2);
        assert_eq!(summary.finalized, 2);
        assert_eq!(summary.pending, 0);
    }

    // a 32-byte topic from a short label (left-padded), mimicking an indexed bytes32/address.
    fn b32(tag: u8) -> [u8; 32] {
        let mut a = [0u8; 32];
        a[31] = tag;
        a
    }

    #[test]
    fn decodes_pinned_into_pin_index() {
        let graph = KotobaCid::from_bytes(b"g:social");
        let pin = b32(0x11);
        let root = b32(0x22);
        // pinner address in the low 20 bytes of a 32-byte topic.
        let mut pinner_topic = [0u8; 32];
        pinner_topic[31] = 0x33;

        let logs = json!([{
            "address": "0xescrow",
            "topics": [ topic0_hex(PINNED_SIG), topic_str(&pin), topic_str(&root), topic_str(&pinner_topic) ],
            "data": "0x"
        }]);

        let datoms = decode_pinned_logs(&logs, &graph);
        assert_eq!(datoms.len(), 2);

        // feed PinIndex and confirm the mapping resolves to the from_bytes CIDs.
        let mut idx = PinIndex::new();
        let deltas: Vec<_> = datoms
            .into_iter()
            .map(kotoba_query::delta::Delta::assert_datom)
            .collect();
        idx.apply(&deltas);
        let pin_cid = KotobaCid::from_bytes(&pin);
        assert_eq!(idx.root_of(&pin_cid), Some(KotobaCid::from_bytes(&root)));
        assert_eq!(
            idx.pinner_of(&pin_cid),
            Some(KotobaCid::from_bytes(&addr20(&pinner_topic)))
        );
    }

    #[test]
    fn decodes_pinned_bond_from_data_and_gates_eligibility() {
        use kotoba_query::social::eligible_replica;
        // data = didHash(32) ++ bond(32) ++ expiresAt(32); bond is word(1).
        fn word(n: u128) -> String {
            hex::encode({
                let mut a = [0u8; 32];
                a[16..32].copy_from_slice(&n.to_be_bytes());
                a
            })
        }
        let graph = KotobaCid::from_bytes(b"g:social");
        let pin = b32(0x11);
        let root = b32(0x22);
        let mut pinner_topic = [0u8; 32];
        pinner_topic[31] = 0x33;
        let data = format!("0x{}{}{}", word(0xdead), word(5_000), word(99));
        let logs = json!([{
            "topics": [ topic0_hex(PINNED_SIG), topic_str(&pin), topic_str(&root), topic_str(&pinner_topic) ],
            "data": data
        }]);

        let datoms = decode_pinned_logs(&logs, &graph);
        assert_eq!(datoms.len(), 3, "root + pinner + bond");

        let mut idx = PinIndex::new();
        let deltas: Vec<_> = datoms
            .into_iter()
            .map(kotoba_query::delta::Delta::assert_datom)
            .collect();
        idx.apply(&deltas);
        let pin_cid = KotobaCid::from_bytes(&pin);
        let root_cid = KotobaCid::from_bytes(&root);
        let pinner_cid = KotobaCid::from_bytes(&addr20(&pinner_topic));
        assert_eq!(idx.bond_of(&pin_cid), Some(5_000));
        // the observed bond gates replica admission end-to-end.
        assert!(eligible_replica(&pinner_cid, &root_cid, 5_000, &idx));
        assert!(!eligible_replica(&pinner_cid, &root_cid, 5_001, &idx));
    }

    #[test]
    fn ignores_non_pinned_topic() {
        let graph = KotobaCid::from_bytes(b"g");
        let logs = json!([{
            "topics": [ "0xdeadbeef".to_string(), topic_str(&b32(1)), topic_str(&b32(2)), topic_str(&b32(3)) ],
            "data": "0x"
        }]);
        assert!(decode_pinned_logs(&logs, &graph).is_empty());
    }

    #[test]
    fn decodes_slash_amounts() {
        // data = bond(0.9e18-ish placeholder) ++ toRetainer ++ toPublicFund.
        // use small values: bond=1000, toRetainer=900, toPublicFund=100.
        fn word(n: u128) -> String {
            hex::encode({
                let mut a = [0u8; 32];
                a[16..32].copy_from_slice(&n.to_be_bytes());
                a
            })
        }
        let data = format!("0x{}{}{}", word(1000), word(900), word(100));
        let logs = json!([{
            "topics": [ topic0_hex(SLASHED_SIG), topic_str(&b32(0x11)) ],
            "data": data
        }]);
        let slashes = decode_slash_logs(&logs);
        assert_eq!(slashes.len(), 1);
        assert_eq!(slashes[0].pin_id, KotobaCid::from_bytes(&b32(0x11)));
        assert_eq!(slashes[0].bond, 1000);
        assert_eq!(slashes[0].to_retainer, 900);
        assert_eq!(slashes[0].to_public_fund, 100);
    }

    #[test]
    fn empty_or_non_array_is_empty() {
        let graph = KotobaCid::from_bytes(b"g");
        assert!(decode_pinned_logs(&json!({}), &graph).is_empty());
        assert!(decode_slash_logs(&json!(null)).is_empty());
    }

    #[test]
    fn evm_source_fetches_and_decodes_pin_datoms() {
        let graph = KotobaCid::from_bytes(b"g:social");
        let pin = b32(0x11);
        let root = b32(0x22);
        let mut pinner_topic = [0u8; 32];
        pinner_topic[31] = 0x33;
        let logs = json!([{
            "topics": [ topic0_hex(PINNED_SIG), topic_str(&pin), topic_str(&root), topic_str(&pinner_topic) ],
            "data": "0x"
        }]);
        let src = EvmLogObservationSource::new(FakeRpc { logs }, "0xescrow", graph);
        let datoms = src.pin_datoms("0x0", "latest").expect("fetch ok");
        assert_eq!(datoms.len(), 2);
        // decoded Datoms drive PinIndex identically to the direct decoder.
        let mut idx = PinIndex::new();
        idx.apply(
            &datoms
                .into_iter()
                .map(kotoba_query::delta::Delta::assert_datom)
                .collect::<Vec<_>>(),
        );
        assert_eq!(
            idx.root_of(&KotobaCid::from_bytes(&pin)),
            Some(KotobaCid::from_bytes(&root))
        );
    }

    #[test]
    fn kaizen_parser_maps_did_and_skips_malformed() {
        let feed = json!([
            { "did": "did:web:alice", "epoch": 3, "delta": 5, "council_attested": true },
            { "did": "did:web:bob", "epoch": 3, "delta": -2 }, // council_attested defaults false
            { "epoch": 3, "delta": 1 } // missing did → skipped
        ]);
        let obs = parse_kaizen_wellbecoming(&feed);
        assert_eq!(obs.len(), 2);
        assert_eq!(obs[0].did, crate::did_bridge::did_to_cid("did:web:alice"));
        assert_eq!(obs[0].delta, 5);
        assert!(obs[0].council_attested);
        assert_eq!(obs[1].delta, -2);
        assert!(!obs[1].council_attested); // defaulted
    }
}
