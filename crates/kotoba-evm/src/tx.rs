//! kotoba-EVM R1b — signed legacy/EIP-155 transaction decode + sender recovery →
//! execution (ADR-2606091500). The `eth_sendRawTransaction` path with NO external
//! EVM-tx dependency: a minimal hand-rolled RLP codec + `kotoba-auth` keccak256 +
//! secp256k1 recovery, validated against the canonical EIP-155 test vector.
//!
//! R1b scope: legacy + EIP-155 transactions (the `f8…` RLP-list form). Typed
//! envelopes (EIP-2930 `0x01` / EIP-1559 `0x02`) are an explicit follow-up.

use kotoba_auth::eth::{keccak256, recover_eth_address};
use kotoba_core::cid::KotobaCid;
use kotoba_query::evm_state::EvmStateView;
use revm::primitives::U256;

use crate::ExecOutcome;

// ── minimal RLP (enough for a flat legacy-tx list of byte-strings) ────────────

fn rlp_encode_bytes(b: &[u8]) -> Vec<u8> {
    if b.len() == 1 && b[0] < 0x80 {
        return vec![b[0]];
    }
    let mut out = Vec::new();
    if b.len() <= 55 {
        out.push(0x80 + b.len() as u8);
    } else {
        let len_be = minimal_be(b.len() as u64);
        out.push(0xb7 + len_be.len() as u8);
        out.extend_from_slice(&len_be);
    }
    out.extend_from_slice(b);
    out
}

fn rlp_encode_list(items: &[Vec<u8>]) -> Vec<u8> {
    let mut payload = Vec::new();
    for it in items {
        payload.extend(rlp_encode_bytes(it));
    }
    let mut out = Vec::new();
    if payload.len() <= 55 {
        out.push(0xc0 + payload.len() as u8);
    } else {
        let len_be = minimal_be(payload.len() as u64);
        out.push(0xf7 + len_be.len() as u8);
        out.extend_from_slice(&len_be);
    }
    out.extend(payload);
    out
}

fn minimal_be(n: u64) -> Vec<u8> {
    if n == 0 {
        return Vec::new();
    }
    let b = n.to_be_bytes();
    let first = b.iter().position(|&x| x != 0).unwrap();
    b[first..].to_vec()
}

/// Decode one RLP item at `buf[*pos..]`; returns its payload bytes (for strings)
/// and advances `pos`. Lists are returned as their inner payload (caller re-parses).
fn rlp_read_item<'a>(buf: &'a [u8], pos: &mut usize) -> Result<(&'a [u8], bool), String> {
    if *pos >= buf.len() {
        return Err("rlp: truncated".into());
    }
    let b = buf[*pos];
    if b <= 0x7f {
        let s = &buf[*pos..*pos + 1];
        *pos += 1;
        Ok((s, false))
    } else if b <= 0xb7 {
        let len = (b - 0x80) as usize;
        *pos += 1;
        let s = buf.get(*pos..*pos + len).ok_or("rlp: short string oob")?;
        *pos += len;
        Ok((s, false))
    } else if b <= 0xbf {
        let ll = (b - 0xb7) as usize;
        *pos += 1;
        let lb = buf.get(*pos..*pos + ll).ok_or("rlp: strlen oob")?;
        *pos += ll;
        let len = be_to_usize(lb);
        let s = buf.get(*pos..*pos + len).ok_or("rlp: long string oob")?;
        *pos += len;
        Ok((s, false))
    } else if b <= 0xf7 {
        let len = (b - 0xc0) as usize;
        *pos += 1;
        let s = buf.get(*pos..*pos + len).ok_or("rlp: list oob")?;
        *pos += len;
        Ok((s, true))
    } else {
        let ll = (b - 0xf7) as usize;
        *pos += 1;
        let lb = buf.get(*pos..*pos + ll).ok_or("rlp: listlen oob")?;
        *pos += ll;
        let len = be_to_usize(lb);
        let s = buf.get(*pos..*pos + len).ok_or("rlp: long list oob")?;
        *pos += len;
        Ok((s, true))
    }
}

fn be_to_usize(b: &[u8]) -> usize {
    let mut n = 0usize;
    for &x in b {
        n = (n << 8) | x as usize;
    }
    n
}

fn be_to_u64(b: &[u8]) -> u64 {
    let mut n = 0u64;
    for &x in b {
        n = (n << 8) | x as u64;
    }
    n
}

/// Parse a legacy-tx RLP list into its 9 string items.
fn parse_legacy_items(raw: &[u8]) -> Result<Vec<Vec<u8>>, String> {
    let mut pos = 0usize;
    let (inner, is_list) = rlp_read_item(raw, &mut pos)?;
    if !is_list {
        return Err("rlp: tx is not a list".into());
    }
    let mut items = Vec::new();
    let mut ip = 0usize;
    while ip < inner.len() {
        let (it, _) = rlp_read_item(inner, &mut ip)?;
        items.push(it.to_vec());
    }
    if items.len() != 9 {
        return Err(format!("legacy tx must have 9 fields, got {}", items.len()));
    }
    Ok(items)
}

/// A decoded + sender-recovered transaction.
#[derive(Debug, Clone)]
pub struct RecoveredTx {
    pub from: [u8; 20],
    /// `None` for a contract-creation tx (empty `to`).
    pub to: Option<[u8; 20]>,
    pub value: U256,
    pub input: Vec<u8>,
    pub nonce: u64,
    pub gas_limit: u64,
    pub chain_id: Option<u64>,
}

/// Decode a raw signed legacy/EIP-155 tx and recover its sender (secp256k1).
pub fn decode_and_recover(raw: &[u8]) -> Result<RecoveredTx, String> {
    if raw.is_empty() {
        return Err("empty tx".into());
    }
    if raw[0] == 0x01 || raw[0] == 0x02 {
        return Err("typed (EIP-2930/1559) tx not supported at R1b; legacy/EIP-155 only".into());
    }
    let items = parse_legacy_items(raw)?;
    let nonce = be_to_u64(&items[0]);
    let gas_limit = be_to_u64(&items[2]);
    let to = if items[3].len() == 20 {
        let mut a = [0u8; 20];
        a.copy_from_slice(&items[3]);
        Some(a)
    } else {
        None
    };
    let mut value_bytes = [0u8; 32];
    let vlen = items[4].len().min(32);
    value_bytes[32 - vlen..].copy_from_slice(&items[4][items[4].len() - vlen..]);
    let value = U256::from_be_bytes(value_bytes);
    let input = items[5].clone();
    let v = be_to_u64(&items[6]);

    // recovery id + chain id (EIP-155: v = 35 + 2*chainid + recid; pre-155: 27/28).
    let (rec_id, chain_id) = if v >= 35 {
        (((v - 35) % 2) as u8, Some((v - 35) / 2))
    } else if v == 27 || v == 28 {
        ((v - 27) as u8, None)
    } else {
        return Err(format!("unexpected v={v}"));
    };

    // signing hash: keccak(rlp([nonce,gasPrice,gasLimit,to,value,data, chainid,0,0]))
    // — re-encode the (canonical) decoded field bytes; EIP-155 appends chainid,0,0.
    let mut sign_items: Vec<Vec<u8>> = items[0..6].to_vec();
    if let Some(cid) = chain_id {
        sign_items.push(minimal_be(cid));
        sign_items.push(Vec::new());
        sign_items.push(Vec::new());
    }
    let sign_hash = keccak256(&rlp_encode_list(&sign_items));

    // sig = r(32) || s(32) || recid
    let mut sig = [0u8; 65];
    let r = &items[7];
    let s = &items[8];
    sig[32 - r.len()..32].copy_from_slice(r);
    sig[64 - s.len()..64].copy_from_slice(s);
    sig[64] = rec_id;
    let from = recover_eth_address(&sign_hash, &sig).map_err(|e| format!("recover: {e}"))?;

    Ok(RecoveredTx { from, to, value, input, nonce, gas_limit, chain_id })
}

/// `eth_sendRawTransaction`: decode + recover + execute over the Datom state.
/// Returns the recovered tx + execution outcome (whose `datoms` are the diff to
/// commit). Contract-creation txs are rejected at R1b.
pub fn apply_raw_tx(
    view: &EvmStateView,
    raw: &[u8],
    graph: &KotobaCid,
) -> Result<(RecoveredTx, ExecOutcome), String> {
    let tx = decode_and_recover(raw)?;
    let out = match tx.to {
        Some(to) => crate::apply_call(
            view,
            tx.from,
            to,
            tx.value,
            tx.input.clone(),
            tx.nonce,
            tx.gas_limit,
            graph,
        )?,
        // contract creation (`to` empty) → deploy init_code (R4 / forge create).
        None => crate::apply_create(
            view,
            tx.from,
            tx.value,
            tx.input.clone(),
            tx.nonce,
            tx.gas_limit,
            graph,
        )?,
    };
    Ok((tx, out))
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_query::delta::Delta;
    use kotoba_query::evm_state::account_datoms;

    fn graph() -> KotobaCid {
        KotobaCid::from_bytes(b"g:evm")
    }
    fn u256(n: u128) -> [u8; 32] {
        U256::from(n).to_be_bytes()
    }

    // Canonical EIP-155 example tx (EIP-155 spec): nonce 9, gasPrice 20e9, gas
    // 21000, to 0x3535..3535, value 1e18, chainId 1; signer (pk 0x4646..4646) =
    // 0x9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f.
    const EIP155_RAW: &str = "f86c098504a817c800825208943535353535353535353535353535353535353535880de0b6b3a76400008025a028ef61340bd939bc2195fe537567866003e1a15d3c71ff63e1590620aa636276a067cbe9d8997f761aecb703304b3800ccf555c9f3dc64214b297fb1966a3b6d83";

    #[test]
    fn rlp_roundtrip_list() {
        let items: Vec<Vec<u8>> = vec![vec![], vec![0x09], vec![0xde, 0xad], vec![0u8; 20]];
        let enc = rlp_encode_list(&items);
        let mut pos = 0;
        let (inner, is_list) = rlp_read_item(&enc, &mut pos).unwrap();
        assert!(is_list);
        let mut ip = 0;
        let mut got = Vec::new();
        while ip < inner.len() {
            let (it, _) = rlp_read_item(inner, &mut ip).unwrap();
            got.push(it.to_vec());
        }
        assert_eq!(got, items);
    }

    #[test]
    fn decode_recovers_eip155_sender_and_fields() {
        let raw = hex::decode(EIP155_RAW).unwrap();
        let tx = decode_and_recover(&raw).expect("decode+recover");
        assert_eq!(
            hex::encode(tx.from),
            "9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f",
            "EIP-155 canonical sender"
        );
        assert_eq!(hex::encode(tx.to.unwrap()), "3535353535353535353535353535353535353535");
        assert_eq!(tx.value, U256::from(1_000_000_000_000_000_000u128));
        assert_eq!(tx.nonce, 9);
        assert_eq!(tx.chain_id, Some(1));
    }

    #[test]
    fn typed_tx_rejected_at_r1b() {
        assert!(decode_and_recover(&[0x02, 0xc0]).is_err());
    }

    #[test]
    fn send_raw_transaction_executes_over_datom_state() {
        let raw = hex::decode(EIP155_RAW).unwrap();
        let mut from = [0u8; 20];
        from.copy_from_slice(&hex::decode("9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f").unwrap());

        let mut v = EvmStateView::new();
        let d: Vec<Delta> =
            account_datoms(&from, 9, &u256(2_000_000_000_000_000_000), None, &graph())
                .into_iter()
                .map(Delta::assert_datom)
                .collect();
        v.apply(&d);

        let (tx, out) = apply_raw_tx(&v, &raw, &graph()).expect("send raw tx");
        assert!(out.success);
        assert_eq!(tx.from, from);

        let post: Vec<Delta> = out.datoms.into_iter().map(Delta::assert_datom).collect();
        let mut pv = EvmStateView::new();
        pv.apply(&post);
        let mut to = [0u8; 20];
        to.copy_from_slice(&hex::decode("3535353535353535353535353535353535353535").unwrap());
        assert_eq!(pv.balance_of(&to), u256(1_000_000_000_000_000_000));
        assert_eq!(pv.nonce_of(&from), 10);
    }
}
