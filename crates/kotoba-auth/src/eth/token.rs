//! Read-only ERC-20 / ERC-721 / ERC-1155 helpers.
//!
//! Each function builds the `eth_call` **calldata** for a view method, and a
//! matching `decode_*` interprets the returned bytes. No transactions are
//! constructed or signed — this is strictly the read side, consistent with the
//! etzhayyim operating-entity boundary (on-chain origination/settlement is
//! etzhayyim-exclusive; consuming chain state via `eth_call` is not).
//!
//! Usage pattern (host or guest holds the RPC bridge):
//! ```ignore
//! let calldata = erc20::balance_of(&holder);
//! let ret = evm.eth_call(rpc, token_addr_hex, calldata, None)?; // raw bytes
//! let raw = erc20::decode_balance(&ret)?;                       // [u8;32]
//! let human = abi::format_units(&raw, decimals);                // "1.5"
//! ```

use super::abi::{self, AbiError, WORD};

/// ERC-20 fungible-token view calls.
pub mod erc20 {
    use super::*;

    /// `balanceOf(address)` calldata.
    pub fn balance_of(owner: &[u8; 20]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("balanceOf(address)"),
            &[abi::encode_address(owner)],
        )
    }

    /// `allowance(address owner, address spender)` calldata.
    pub fn allowance(owner: &[u8; 20], spender: &[u8; 20]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("allowance(address,address)"),
            &[abi::encode_address(owner), abi::encode_address(spender)],
        )
    }

    /// `totalSupply()` calldata.
    pub fn total_supply() -> Vec<u8> {
        abi::encode_call(abi::selector("totalSupply()"), &[])
    }

    /// `decimals()` calldata.
    pub fn decimals() -> Vec<u8> {
        abi::encode_call(abi::selector("decimals()"), &[])
    }

    /// `name()` calldata.
    pub fn name() -> Vec<u8> {
        abi::encode_call(abi::selector("name()"), &[])
    }

    /// `symbol()` calldata.
    pub fn symbol() -> Vec<u8> {
        abi::encode_call(abi::selector("symbol()"), &[])
    }

    /// Decode a `balanceOf` / `totalSupply` / `allowance` uint256 return.
    pub fn decode_balance(data: &[u8]) -> Result<[u8; WORD], AbiError> {
        abi::decode_u256(data)
    }

    /// Decode a `decimals()` return.
    pub fn decode_decimals(data: &[u8]) -> Result<u8, AbiError> {
        abi::decode_u8(data)
    }

    /// Decode a `name()` / `symbol()` return, tolerating the legacy `bytes32`
    /// form used by a handful of early tokens (MKR etc.).
    pub fn decode_string(data: &[u8]) -> Result<String, AbiError> {
        abi::decode_string_or_bytes32(data)
    }
}

/// ERC-721 non-fungible-token view calls.
pub mod erc721 {
    use super::*;

    /// `ownerOf(uint256 tokenId)` calldata. `token_id` is a big-endian uint256.
    pub fn owner_of(token_id: &[u8; WORD]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("ownerOf(uint256)"),
            &[abi::encode_u256(token_id)],
        )
    }

    /// `balanceOf(address owner)` calldata — number of NFTs held.
    pub fn balance_of(owner: &[u8; 20]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("balanceOf(address)"),
            &[abi::encode_address(owner)],
        )
    }

    /// `tokenURI(uint256 tokenId)` calldata.
    pub fn token_uri(token_id: &[u8; WORD]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("tokenURI(uint256)"),
            &[abi::encode_u256(token_id)],
        )
    }

    /// `getApproved(uint256 tokenId)` calldata.
    pub fn get_approved(token_id: &[u8; WORD]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("getApproved(uint256)"),
            &[abi::encode_u256(token_id)],
        )
    }

    /// `isApprovedForAll(address owner, address operator)` calldata.
    pub fn is_approved_for_all(owner: &[u8; 20], operator: &[u8; 20]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("isApprovedForAll(address,address)"),
            &[abi::encode_address(owner), abi::encode_address(operator)],
        )
    }

    /// Decode an `ownerOf` / `getApproved` address return.
    pub fn decode_address(data: &[u8]) -> Result<[u8; 20], AbiError> {
        abi::decode_address(data)
    }

    /// Decode a `balanceOf` count.
    pub fn decode_count(data: &[u8]) -> Result<[u8; WORD], AbiError> {
        abi::decode_u256(data)
    }

    /// Decode a `tokenURI` dynamic string.
    pub fn decode_uri(data: &[u8]) -> Result<String, AbiError> {
        abi::decode_string(data)
    }

    /// Decode an `isApprovedForAll` bool.
    pub fn decode_bool(data: &[u8]) -> Result<bool, AbiError> {
        abi::decode_bool(data)
    }
}

/// ERC-1155 multi-token view calls.
pub mod erc1155 {
    use super::*;

    /// `balanceOf(address account, uint256 id)` calldata.
    pub fn balance_of(account: &[u8; 20], id: &[u8; WORD]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("balanceOf(address,uint256)"),
            &[abi::encode_address(account), abi::encode_u256(id)],
        )
    }

    /// `isApprovedForAll(address account, address operator)` calldata.
    pub fn is_approved_for_all(account: &[u8; 20], operator: &[u8; 20]) -> Vec<u8> {
        abi::encode_call(
            abi::selector("isApprovedForAll(address,address)"),
            &[abi::encode_address(account), abi::encode_address(operator)],
        )
    }

    /// `uri(uint256 id)` calldata.
    pub fn uri(id: &[u8; WORD]) -> Vec<u8> {
        abi::encode_call(abi::selector("uri(uint256)"), &[abi::encode_u256(id)])
    }

    /// Decode a `balanceOf` uint256 return.
    pub fn decode_balance(data: &[u8]) -> Result<[u8; WORD], AbiError> {
        abi::decode_u256(data)
    }

    /// Decode a `uri` dynamic string return.
    pub fn decode_uri(data: &[u8]) -> Result<String, AbiError> {
        abi::decode_string(data)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn erc20_balance_of_calldata() {
        // balanceOf(vitalik) — selector 0x70a08231 + left-padded address
        let cd = erc20::balance_of(&[
            0xd8, 0xda, 0x6B, 0xF2, 0x69, 0x64, 0xaf, 0x9D, 0x7e, 0xed, 0x9e, 0x03, 0xE5, 0x34,
            0x15, 0xD3, 0x7a, 0xA9, 0x60, 0x45,
        ]);
        assert_eq!(cd.len(), 36);
        assert_eq!(&cd[..4], &[0x70, 0xa0, 0x82, 0x31]);
        assert_eq!(&cd[4..16], &[0u8; 12]); // left padding
    }

    #[test]
    fn erc20_allowance_two_args() {
        let cd = erc20::allowance(&[0x11; 20], &[0x22; 20]);
        assert_eq!(cd.len(), 4 + 32 + 32);
        assert_eq!(&cd[16..36], &[0x11; 20]);
        assert_eq!(&cd[48..68], &[0x22; 20]);
    }

    #[test]
    fn erc20_decimals_roundtrip() {
        assert_eq!(erc20::decimals(), vec![0x31, 0x3c, 0xe5, 0x67]);
        let mut ret = [0u8; 32];
        ret[31] = 6;
        assert_eq!(erc20::decode_decimals(&ret).unwrap(), 6);
    }

    #[test]
    fn erc20_symbol_decode_dynamic_and_legacy() {
        // Dynamic "USDC"
        let mut dynret = vec![0u8; 96];
        dynret[31] = 0x20;
        dynret[63] = 4;
        dynret[64..68].copy_from_slice(b"USDC");
        assert_eq!(erc20::decode_string(&dynret).unwrap(), "USDC");
        // Legacy bytes32 "MKR"
        let mut legacy = [0u8; 32];
        legacy[..3].copy_from_slice(b"MKR");
        assert_eq!(erc20::decode_string(&legacy).unwrap(), "MKR");
    }

    #[test]
    fn erc721_owner_of_calldata_and_decode() {
        let mut token_id = [0u8; 32];
        token_id[31] = 42;
        let cd = erc721::owner_of(&token_id);
        assert_eq!(&cd[..4], &[0x63, 0x52, 0x21, 0x1e]); // ownerOf(uint256)
        assert_eq!(cd[35], 42);

        let mut ret = [0u8; 32];
        ret[12..].copy_from_slice(&[0x99u8; 20]);
        assert_eq!(erc721::decode_address(&ret).unwrap(), [0x99u8; 20]);
    }

    #[test]
    fn erc721_token_uri_decode() {
        let mut ret = vec![0u8; 96];
        ret[31] = 0x20;
        ret[63] = 19;
        ret[64..83].copy_from_slice(b"ipfs://Qm123/0.json");
        assert_eq!(erc721::decode_uri(&ret).unwrap(), "ipfs://Qm123/0.json");
    }

    #[test]
    fn erc1155_balance_of_calldata() {
        let mut id = [0u8; 32];
        id[31] = 7;
        let cd = erc1155::balance_of(&[0xAB; 20], &id);
        // balanceOf(address,uint256) selector 0x00fdd58e
        assert_eq!(&cd[..4], &[0x00, 0xfd, 0xd5, 0x8e]);
        assert_eq!(cd.len(), 4 + 32 + 32);
        assert_eq!(&cd[16..36], &[0xAB; 20]);
        assert_eq!(cd[67], 7);
    }

    #[test]
    fn all_token_calldata_selectors_match_canonical_eip_values() {
        // Every selector is keccak256(signature)[..4]. A typo in any signature
        // string (a stray space, wrong arg type) computes a WRONG selector — the
        // call reverts on-chain while a structural test (length/arg-placement) still
        // passes. Pin each builder against its published 4-byte value (these are the
        // canonical, widely-documented ERC-20/721/1155 selectors).
        let a = [0u8; 20];
        let id = [0u8; 32];
        // ── ERC-20 ──
        assert_eq!(
            &erc20::balance_of(&a)[..4],
            &[0x70, 0xa0, 0x82, 0x31],
            "balanceOf(address)"
        );
        assert_eq!(
            &erc20::allowance(&a, &a)[..4],
            &[0xdd, 0x62, 0xed, 0x3e],
            "allowance(address,address)"
        );
        assert_eq!(
            &erc20::total_supply()[..4],
            &[0x18, 0x16, 0x0d, 0xdd],
            "totalSupply()"
        );
        assert_eq!(
            &erc20::decimals()[..4],
            &[0x31, 0x3c, 0xe5, 0x67],
            "decimals()"
        );
        assert_eq!(&erc20::name()[..4], &[0x06, 0xfd, 0xde, 0x03], "name()");
        assert_eq!(&erc20::symbol()[..4], &[0x95, 0xd8, 0x9b, 0x41], "symbol()");
        // ── ERC-721 ──
        assert_eq!(
            &erc721::owner_of(&id)[..4],
            &[0x63, 0x52, 0x21, 0x1e],
            "ownerOf(uint256)"
        );
        assert_eq!(
            &erc721::balance_of(&a)[..4],
            &[0x70, 0xa0, 0x82, 0x31],
            "balanceOf(address)"
        );
        assert_eq!(
            &erc721::token_uri(&id)[..4],
            &[0xc8, 0x7b, 0x56, 0xdd],
            "tokenURI(uint256)"
        );
        assert_eq!(
            &erc721::get_approved(&id)[..4],
            &[0x08, 0x18, 0x12, 0xfc],
            "getApproved(uint256)"
        );
        assert_eq!(
            &erc721::is_approved_for_all(&a, &a)[..4],
            &[0xe9, 0x85, 0xe9, 0xc5],
            "isApprovedForAll(address,address)"
        );
        // ── ERC-1155 ──
        assert_eq!(
            &erc1155::balance_of(&a, &id)[..4],
            &[0x00, 0xfd, 0xd5, 0x8e],
            "balanceOf(address,uint256)"
        );
        assert_eq!(
            &erc1155::is_approved_for_all(&a, &a)[..4],
            &[0xe9, 0x85, 0xe9, 0xc5],
            "isApprovedForAll(address,address)"
        );
    }
}
