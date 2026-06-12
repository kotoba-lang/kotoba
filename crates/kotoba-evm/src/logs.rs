//! kotoba-EVM R3 — receipts, logs bloom, and `eth_getLogs` filtering over the
//! event logs revm emits during execution (ADR-2606091500).

use kotoba_auth::eth::keccak256;

use crate::EvmLog;

/// A transaction receipt: status + gas + the logs it emitted + the per-receipt bloom.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Receipt {
    pub success: bool,
    pub gas_used: u64,
    pub logs: Vec<EvmLog>,
    pub logs_bloom: [u8; 256],
}

impl Receipt {
    pub fn new(success: bool, gas_used: u64, logs: Vec<EvmLog>) -> Self {
        let logs_bloom = logs_bloom(&logs);
        Self {
            success,
            gas_used,
            logs,
            logs_bloom,
        }
    }
}

/// Ethereum 2048-bit logs bloom over a set of logs: every log address and every
/// topic contributes 3 bits (derived from `keccak256(item)`), matching the
/// yellow-paper `M3:2048` bloom so standard `eth_getLogs` bloom pre-filtering works.
pub fn logs_bloom(logs: &[EvmLog]) -> [u8; 256] {
    let mut bloom = [0u8; 256];
    for log in logs {
        add_to_bloom(&mut bloom, &log.address);
        for t in &log.topics {
            add_to_bloom(&mut bloom, t);
        }
    }
    bloom
}

fn add_to_bloom(bloom: &mut [u8; 256], item: &[u8]) {
    let h = keccak256(item);
    // three 11-bit indices from the first three 16-bit big-endian pairs of the hash.
    for pair in 0..3 {
        let bit = (((h[pair * 2] as usize) << 8) | h[pair * 2 + 1] as usize) & 0x7ff;
        // MSB-first: bit 0 → highest bit of the last byte (yellow-paper convention).
        let byte_index = 256 - 1 - (bit / 8);
        let bit_in_byte = bit % 8;
        bloom[byte_index] |= 1u8 << bit_in_byte;
    }
}

/// `eth_getLogs`-style filter over a block's logs: keep logs whose address matches
/// (when `address` is `Some`) AND whose first topic matches (when `topic0` is `Some`).
pub fn filter_logs<'a>(
    logs: &'a [EvmLog],
    address: Option<&[u8; 20]>,
    topic0: Option<&[u8; 32]>,
) -> Vec<&'a EvmLog> {
    logs.iter()
        .filter(|l| address.is_none_or(|a| &l.address == a))
        .filter(|l| topic0.is_none_or(|t| l.topics.first() == Some(t)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn addr(t: u8) -> [u8; 20] {
        let mut a = [0u8; 20];
        a[19] = t;
        a
    }
    fn topic(t: u8) -> [u8; 32] {
        let mut a = [0u8; 32];
        a[31] = t;
        a
    }

    #[test]
    fn bloom_contains_logged_address_and_topic() {
        let log = EvmLog {
            address: addr(0xAA),
            topics: vec![topic(0x01)],
            data: vec![],
        };
        let bloom = logs_bloom(&[log]);
        // a single-item bloom over the same address must match its own bits.
        let mut probe = [0u8; 256];
        add_to_bloom(&mut probe, &addr(0xAA));
        for (i, &b) in probe.iter().enumerate() {
            assert_eq!(bloom[i] & b, b, "address bits present in bloom at byte {i}");
        }
        // an unrelated address is (almost surely) not fully present.
        let mut other = [0u8; 256];
        add_to_bloom(&mut other, &addr(0xBB));
        let fully = other.iter().enumerate().all(|(i, &b)| bloom[i] & b == b);
        assert!(!fully, "unrelated address should not be fully set");
    }

    #[test]
    fn filter_by_address_and_topic() {
        let logs = vec![
            EvmLog {
                address: addr(0x01),
                topics: vec![topic(0xAA)],
                data: vec![],
            },
            EvmLog {
                address: addr(0x02),
                topics: vec![topic(0xBB)],
                data: vec![],
            },
            EvmLog {
                address: addr(0x01),
                topics: vec![topic(0xBB)],
                data: vec![],
            },
        ];
        assert_eq!(filter_logs(&logs, Some(&addr(0x01)), None).len(), 2);
        assert_eq!(filter_logs(&logs, None, Some(&topic(0xBB))).len(), 2);
        assert_eq!(
            filter_logs(&logs, Some(&addr(0x01)), Some(&topic(0xBB))).len(),
            1
        );
        assert_eq!(filter_logs(&logs, None, None).len(), 3);
        assert_eq!(filter_logs(&logs, Some(&addr(0x09)), None).len(), 0);
    }

    #[test]
    fn receipt_carries_bloom() {
        let logs = vec![EvmLog {
            address: addr(0xAA),
            topics: vec![],
            data: vec![],
        }];
        let r = Receipt::new(true, 21000, logs.clone());
        assert!(r.success);
        assert_eq!(r.logs_bloom, logs_bloom(&logs));
    }

    #[test]
    fn empty_logs_zero_bloom() {
        assert_eq!(logs_bloom(&[]), [0u8; 256]);
    }
}
