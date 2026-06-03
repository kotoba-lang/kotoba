//! CAIP (Chain Agnostic Improvement Proposals) identifiers for Bitcoin-family
//! chains, under the `bip122` namespace.
//!
//! - CAIP-2  chain id:   `bip122:000000000019d6689c085ae165831e93` — namespace
//!   `bip122` + the **first 32 hex chars of the genesis block hash** (leading 16 bytes).
//! - CAIP-10 account id: `bip122:<ref>:<address>` — address kept verbatim;
//!   Base58Check and bech32 are case-sensitive, NOT lowercased like EVM 0x-hex.
//! - CAIP-19 asset type: `bip122:<ref>/slip44:0` — native BTC (SLIP-44 coin 0).
//!
//! These string forms are how KOTOBA scopes Bitcoin facts into named graphs /
//! quad subjects, exactly as [`crate::eth::caip`] does for EVM (`eip155:*`).
//! Together the two namespaces give kotoba the chain-agnostic CAIP-10 account
//! surface that multichain wallets (e.g. Coinbase) expose — the same standard,
//! now spanning both `eip155` and `bip122`.
//!
//! Reference: <https://github.com/ChainAgnostic/namespaces/tree/main/bip122>

use super::address::BtcAddress;
use super::BtcError;

/// Bitcoin-family CAIP-2 namespace.
pub const BIP122: &str = "bip122";

/// CAIP-2 chain reference for Bitcoin **mainnet** (genesis block hash prefix).
pub const MAINNET_REF: &str = "000000000019d6689c085ae165831e93";
/// CAIP-2 chain reference for Bitcoin **testnet3** (genesis block hash prefix).
pub const TESTNET_REF: &str = "000000000933ea01ad0ee984209779ba";
/// SLIP-44 coin type for native BTC.
pub const SLIP44_BTC: u32 = 0;

/// Build a CAIP-2 chain id from a genesis-hash-prefix reference,
/// e.g. `caip2(MAINNET_REF) == "bip122:000000000019d6689c085ae165831e93"`.
pub fn caip2(reference: &str) -> String {
    format!("{BIP122}:{reference}")
}

/// Parse a CAIP-2 `bip122` chain id, returning the chain reference.
/// Rejects non-`bip122` namespaces.
pub fn parse_caip2(s: &str) -> Result<String, BtcError> {
    let (ns, reference) = s
        .split_once(':')
        .ok_or_else(|| BtcError::Did(format!("not a caip-2 id: {s}")))?;
    if ns != BIP122 {
        return Err(BtcError::Did(format!("unsupported caip-2 namespace: {ns}")));
    }
    if reference.is_empty() {
        return Err(BtcError::Did(format!("empty chain reference: {s}")));
    }
    Ok(reference.to_string())
}

/// Build a CAIP-10 account id, e.g.
/// `bip122:000000000019d6689c085ae165831e93:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`.
/// The address string is preserved verbatim (case-significant).
pub fn caip10_account(reference: &str, address: &str) -> String {
    format!("{BIP122}:{reference}:{address}")
}

/// Parse a CAIP-10 `bip122` account id into `(reference, BtcAddress)`.
/// The address is validated (checksum / bech32) via [`BtcAddress::parse`].
pub fn parse_caip10(s: &str) -> Result<(String, BtcAddress), BtcError> {
    let parts: Vec<&str> = s.split(':').collect();
    if parts.len() != 3 || parts[0] != BIP122 {
        return Err(BtcError::Did(format!("not a bip122 caip-10 account: {s}")));
    }
    let addr = BtcAddress::parse(parts[2]).map_err(|e| BtcError::Addr(e.to_string()))?;
    Ok((parts[1].to_string(), addr))
}

/// Build a CAIP-19 native-asset (SLIP-44) id, e.g.
/// `bip122:000000000019d6689c085ae165831e93/slip44:0`.
pub fn caip19_native(reference: &str) -> String {
    format!("{BIP122}:{reference}/slip44:{SLIP44_BTC}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn caip2_roundtrip() {
        assert_eq!(
            caip2(MAINNET_REF),
            "bip122:000000000019d6689c085ae165831e93"
        );
        assert_eq!(parse_caip2(&caip2(MAINNET_REF)).unwrap(), MAINNET_REF);
        assert_eq!(parse_caip2(&caip2(TESTNET_REF)).unwrap(), TESTNET_REF);
    }

    #[test]
    fn caip2_rejects_other_namespaces() {
        assert!(parse_caip2("eip155:1").is_err());
        assert!(parse_caip2("cosmos:cosmoshub-3").is_err());
        assert!(parse_caip2("garbage").is_err());
        assert!(parse_caip2("bip122:").is_err());
    }

    #[test]
    fn caip10_roundtrip_mainnet() {
        let addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa";
        let id = caip10_account(MAINNET_REF, addr);
        let (reference, parsed) = parse_caip10(&id).unwrap();
        assert_eq!(reference, MAINNET_REF);
        assert_eq!(parsed.to_string(), addr);
    }

    #[test]
    fn caip10_roundtrip_bech32() {
        let addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4";
        let id = caip10_account(MAINNET_REF, addr);
        let (_, parsed) = parse_caip10(&id).unwrap();
        assert_eq!(parsed.to_string(), addr);
    }

    #[test]
    fn caip10_rejects_malformed() {
        assert!(parse_caip10("bip122:ref").is_err());
        assert!(parse_caip10("eip155:1:0xabc").is_err());
    }

    #[test]
    fn caip19_native_asset() {
        assert_eq!(
            caip19_native(MAINNET_REF),
            "bip122:000000000019d6689c085ae165831e93/slip44:0"
        );
    }
}
