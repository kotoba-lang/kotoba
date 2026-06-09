//! Decode anchor-chain `MishmarBondEscrow` event logs (`eth_getLogs` JSON) into
//! the projected Datoms that drive `kotoba_kqe::social::PinIndex`, plus `Slashed`
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
use kotoba_kqe::datom::{Datom, Value};
use kotoba_kqe::social::{PIN_PINNER_PRED, PIN_ROOT_PRED};

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
/// `mishmar/pin/{pinner,root}` Datoms that feed `PinIndex`. `graph` is the graph
/// CID the projected Datoms are written under. Non-`Pinned` / malformed logs are
/// skipped. `logs` is the JSON array (the `result` field of an `eth_getLogs` reply).
pub fn decode_pinned_logs(logs: &serde_json::Value, graph: &KotobaCid) -> Vec<Datom> {
    let want = topic0_hex(PINNED_SIG);
    let mut out = Vec::new();
    let Some(arr) = logs.as_array() else {
        return out;
    };
    for log in arr {
        let Some(topics) = topics_of(log) else { continue };
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
            pin_cid,
            PIN_PINNER_PRED.to_string(),
            Value::Cid(pinner_cid),
            graph.clone(),
        ));
    }
    out
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
        let Some(topics) = topics_of(log) else { continue };
        if topics.len() < 2 {
            continue;
        }
        if !format!("0x{}", hex::encode(topics[0])).eq_ignore_ascii_case(&want) {
            continue;
        }
        let Some(data_str) = log.get("data").and_then(|d| d.as_str()) else { continue };
        let body = data_str.strip_prefix("0x").unwrap_or(data_str);
        let Ok(bytes) = hex::decode(body) else { continue };
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

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_kqe::social::PinIndex;
    use serde_json::json;

    fn topic_str(bytes: &[u8; 32]) -> String {
        format!("0x{}", hex::encode(bytes))
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
        let deltas: Vec<_> = datoms.into_iter().map(kotoba_kqe::delta::Delta::assert_datom).collect();
        idx.apply(&deltas);
        let pin_cid = KotobaCid::from_bytes(&pin);
        assert_eq!(idx.root_of(&pin_cid), Some(KotobaCid::from_bytes(&root)));
        assert_eq!(idx.pinner_of(&pin_cid), Some(KotobaCid::from_bytes(&addr20(&pinner_topic))));
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
}
