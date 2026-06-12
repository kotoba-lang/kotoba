//! CAIP (Chain Agnostic Improvement Proposals) identifiers for EVM chains.
//!
//! - CAIP-2  chain id:   `eip155:1`
//! - CAIP-10 account id:  `eip155:1:0x<checksum-address>`
//! - CAIP-19 asset type:  `eip155:1/erc20:0x<token>`
//! - CAIP-19 asset id:    `eip155:1/erc721:0x<token>/<tokenId>`
//!
//! These string forms are the canonical way KOTOBA scopes EVM facts into named
//! graphs / quad subjects (the `kotoba-hello` example already uses `eip155:1`).
//!
//! Reference: <https://chainagnostic.org/CAIPs/caip-2>

use super::{parse_address, to_checksum_address, EthError};

/// EVM CAIP-2 namespace.
pub const EIP155: &str = "eip155";

/// Build a CAIP-2 chain id for an EVM chain, e.g. `caip2(1) == "eip155:1"`.
pub fn caip2(chain_id: u64) -> String {
    format!("{EIP155}:{chain_id}")
}

/// Parse a CAIP-2 EVM chain id, returning the numeric chain id.
/// Rejects non-`eip155` namespaces.
pub fn parse_caip2(s: &str) -> Result<u64, EthError> {
    let (ns, reference) = s
        .split_once(':')
        .ok_or_else(|| EthError::Did(format!("not a caip-2 id: {s}")))?;
    if ns != EIP155 {
        return Err(EthError::Did(format!("unsupported caip-2 namespace: {ns}")));
    }
    reference
        .parse::<u64>()
        .map_err(|_| EthError::Did(format!("bad chain id: {reference}")))
}

/// Build a CAIP-10 account id with an EIP-55 checksummed address,
/// e.g. `eip155:1:0xAb58…`.
pub fn caip10_account(chain_id: u64, addr: &[u8; 20]) -> String {
    format!("{EIP155}:{chain_id}:{}", to_checksum_address(addr))
}

/// Parse a CAIP-10 account id into `(chain_id, address)`.
pub fn parse_caip10(s: &str) -> Result<(u64, [u8; 20]), EthError> {
    let parts: Vec<&str> = s.split(':').collect();
    if parts.len() != 3 || parts[0] != EIP155 {
        return Err(EthError::Did(format!("not an eip155 caip-10 account: {s}")));
    }
    let chain_id = parts[1]
        .parse::<u64>()
        .map_err(|_| EthError::Did(format!("bad chain id: {}", parts[1])))?;
    let addr = parse_address(parts[2])?;
    Ok((chain_id, addr))
}

/// Build a CAIP-19 fungible (ERC-20) asset type, e.g. `eip155:1/erc20:0x…`.
pub fn caip19_erc20(chain_id: u64, token: &[u8; 20]) -> String {
    format!("{EIP155}:{chain_id}/erc20:{}", to_checksum_address(token))
}

/// Build a CAIP-19 non-fungible (ERC-721) asset id, e.g.
/// `eip155:1/erc721:0x…/1234`. `token_id` is rendered in decimal.
pub fn caip19_erc721(chain_id: u64, token: &[u8; 20], token_id: &str) -> String {
    format!(
        "{EIP155}:{chain_id}/erc721:{}/{token_id}",
        to_checksum_address(token)
    )
}

/// Build a CAIP-19 ERC-1155 asset id, e.g. `eip155:1/erc1155:0x…/5`.
pub fn caip19_erc1155(chain_id: u64, token: &[u8; 20], token_id: &str) -> String {
    format!(
        "{EIP155}:{chain_id}/erc1155:{}/{token_id}",
        to_checksum_address(token)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn caip2_roundtrip() {
        assert_eq!(caip2(1), "eip155:1");
        assert_eq!(caip2(8453), "eip155:8453"); // Base
        assert_eq!(parse_caip2("eip155:1").unwrap(), 1);
        assert_eq!(parse_caip2("eip155:8453").unwrap(), 8453);
    }

    #[test]
    fn caip2_rejects_non_eip155() {
        assert!(parse_caip2("cosmos:cosmoshub-3").is_err());
        assert!(parse_caip2("garbage").is_err());
    }

    #[test]
    fn caip10_roundtrip_checksummed() {
        let addr = [0xAB_u8; 20];
        let id = caip10_account(1, &addr);
        assert!(id.starts_with("eip155:1:0x"));
        let (chain, parsed) = parse_caip10(&id).unwrap();
        assert_eq!(chain, 1);
        assert_eq!(parsed, addr);
    }

    #[test]
    fn caip10_rejects_malformed() {
        assert!(parse_caip10("eip155:1").is_err());
        assert!(parse_caip10("solana:x:y").is_err());
    }

    #[test]
    fn caip19_asset_forms() {
        let token = [0x11u8; 20];
        assert!(caip19_erc20(1, &token).starts_with("eip155:1/erc20:0x"));
        assert!(caip19_erc721(1, &token, "42").ends_with("/42"));
        assert!(caip19_erc1155(8453, &token, "5").starts_with("eip155:8453/erc1155:0x"));
    }
}
