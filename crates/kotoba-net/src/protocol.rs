/// /kotoba/sync/1.0.0 — 8-bit KAIS frame protocol over libp2p stream
pub const KOTOBA_SYNC_PROTOCOL: &str = "/kotoba/sync/1.0.0";
pub const KOTOBA_BITSWAP_PROTOCOL: &str = "/kotoba/bitswap/1.0.0";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sync_protocol_has_correct_path() {
        assert_eq!(KOTOBA_SYNC_PROTOCOL, "/kotoba/sync/1.0.0");
    }

    #[test]
    fn bitswap_protocol_has_correct_path() {
        assert_eq!(KOTOBA_BITSWAP_PROTOCOL, "/kotoba/bitswap/1.0.0");
    }

    #[test]
    fn protocols_have_kotoba_prefix() {
        assert!(KOTOBA_SYNC_PROTOCOL.starts_with("/kotoba/"));
        assert!(KOTOBA_BITSWAP_PROTOCOL.starts_with("/kotoba/"));
    }

    #[test]
    fn protocols_have_version_suffix() {
        assert!(KOTOBA_SYNC_PROTOCOL.ends_with("/1.0.0"));
        assert!(KOTOBA_BITSWAP_PROTOCOL.ends_with("/1.0.0"));
    }

    #[test]
    fn protocols_are_distinct() {
        assert_ne!(KOTOBA_SYNC_PROTOCOL, KOTOBA_BITSWAP_PROTOCOL);
    }
}
