//! Portable C3 merge-transaction marker: canonical DAG-CBOR + CID.
//!
//! Ported 2026-08-18 from the pre-rename `net-kotobase` checkout, where it
//! sat uncommitted at `sdk/kotobase-rust/src/lib.rs`. That crate also carried
//! a ureq/tungstenite client which is NOT ported: this crate's own
//! `KotobaseClient` (reqwest) supersedes it.

use cid::Cid;
use multihash_codetable::{Code, MultihashDigest};
use serde::Serialize;

pub const MERGE_TRANSACTION_CONTRACT: &str = "kotobase.merge-transaction.v1";
pub const MERGE_CONFLICT_RULE: &str =
    "causal-height-then-cid-bytes-last-operation-wins";
pub const PUBLIC_STATE_PROFILE: &str = "kotobase.peer.public.v1";
const DAG_CBOR_CODEC: u64 = 0x71;

#[derive(Debug, Serialize)]
struct MergeTransaction<'a> {
    schema: &'static str,
    basis_frontier: &'a [String],
    ordered_commits: &'a [String],
    conflict_rule: &'static str,
    semantics: &'a str,
    state_profile: &'static str,
}

fn canonical_cids(values: &[String]) -> Result<Vec<String>, String> {
    let mut parsed = values
        .iter()
        .map(|value| Cid::try_from(value.as_str()).map(|cid| (cid.to_bytes(), value.clone())))
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| format!("invalid CID: {error}"))?;
    parsed.sort_by(|left, right| left.0.cmp(&right.0));
    if parsed.windows(2).any(|pair| pair[0].0 == pair[1].0) {
        return Err("frontier CIDs must be unique".into());
    }
    Ok(parsed.into_iter().map(|(_, value)| value).collect())
}

/// Encode the portable C3 merge marker and return its CID.
///
/// CID sorting uses decoded CID bytes, never provider or arrival order. The
/// returned bytes are canonical DAG-CBOR and therefore form a runtime-neutral
/// compatibility boundary. This SDK is not a required canonical Kotobase
/// runtime or toolchain.
pub fn encode_merge_transaction(
    basis_frontier: &[String],
    ordered_commits: &[String],
    semantics: &str,
) -> Result<(Vec<u8>, String, Vec<String>), String> {
    if basis_frontier.len() < 2 {
        return Err("merge frontier requires at least two CIDs".into());
    }
    if ordered_commits.len() < 2 {
        return Err("ordered commit list requires at least two CIDs".into());
    }
    let frontier = canonical_cids(basis_frontier)?;
    for value in ordered_commits {
        Cid::try_from(value.as_str()).map_err(|error| format!("invalid ordered CID: {error}"))?;
    }
    Cid::try_from(semantics).map_err(|error| format!("invalid semantics CID: {error}"))?;
    let marker = MergeTransaction {
        schema: MERGE_TRANSACTION_CONTRACT,
        basis_frontier: &frontier,
        ordered_commits,
        conflict_rule: MERGE_CONFLICT_RULE,
        semantics,
        state_profile: PUBLIC_STATE_PROFILE,
    };
    let bytes = serde_ipld_dagcbor::to_vec(&marker)
        .map_err(|error| format!("DAG-CBOR encode failed: {error}"))?;
    let digest = Code::Sha2_256.digest(&bytes);
    let cid = Cid::new_v1(DAG_CBOR_CODEC, digest).to_string();
    Ok((bytes, cid, frontier))
}

fn fixed_merge_conformance() -> bool {
    let frontier = vec![
        "bafyreihpagul4qa6sd5l5b7ba2hbdvtdlkeanlawigyft64mkasa2fbdui".into(),
        "bafyreig5bdm356eflcubsk4q3vwtd5u7xpfog42vi5ioflruc5oldtkewu".into(),
    ];
    let ordered = vec![
        "bafyreiego7c7hto5cf2h6xrretmngop55krzlffmsugs7h3oujb24b6enq".into(),
        "bafyreig5bdm356eflcubsk4q3vwtd5u7xpfog42vi5ioflruc5oldtkewu".into(),
        "bafyreihpagul4qa6sd5l5b7ba2hbdvtdlkeanlawigyft64mkasa2fbdui".into(),
    ];
    encode_merge_transaction(
        &frontier,
        &ordered,
        "bafyreiabdtkeiiiy67buz2a47ga7uubfztdfrq42yh2quxlpsk4oh35cda",
    )
    .map(|(bytes, cid, canonical)| {
        hex(&bytes) == include_str!("../tests/fixtures/cid-merge-v1.hex").trim()
            && cid == "bafyreifmrh7jiy6jb6mr7t4ktomsbpnsdrijrrplj4z7fez7as3pqji5qu"
            && canonical == vec![
                "bafyreig5bdm356eflcubsk4q3vwtd5u7xpfog42vi5ioflruc5oldtkewu",
                "bafyreihpagul4qa6sd5l5b7ba2hbdvtdlkeanlawigyft64mkasa2fbdui",
            ]
    })
    .unwrap_or(false)
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        result.push(DIGITS[(byte >> 4) as usize] as char);
        result.push(DIGITS[(byte & 0x0f) as usize] as char);
    }
    result
}

/// Executed directly by Node/wasmtime after compiling this crate to
/// wasm32-unknown-unknown. A return value of 1 means the WASM runtime produced
/// the exact reference DAG-CBOR bytes and CID.
#[unsafe(no_mangle)]
pub extern "C" fn kotobase_merge_conformance_v1() -> i32 {
    i32::from(fixed_merge_conformance())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The same fixture the Node/wasmtime cross-runtime check consumes, so a
    /// divergence here means the runtimes disagree — not that a test drifted.
    #[test]
    fn native_merge_marker_matches_cross_runtime_fixture() {
        assert!(fixed_merge_conformance());
    }

    #[test]
    fn frontier_shorter_than_two_is_refused() {
        let one = vec!["bafyreihpagul4qa6sd5l5b7ba2hbdvtdlkeanlawigyft64mkasa2fbdui".to_string()];
        assert!(encode_merge_transaction(&one, &one, "bafyreihpagul4qa6sd5l5b7ba2hbdvtdlkeanlawigyft64mkasa2fbdui").is_err());
    }
}
