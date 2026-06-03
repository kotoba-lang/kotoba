//! Minimal Ethereum ABI encoder/decoder for read-only contract calls.
//!
//! Scope is deliberately small: the static head/tail subset needed to build
//! `eth_call` calldata for ERC-20/721/1155 view methods and to decode their
//! returns. It is NOT a general-purpose ABI library (no tuples, no arrays of
//! dynamic types, no events). It depends only on `sha3` + `hex` so it stays
//! portable — relocatable into a standalone `kotoba-evm` crate or a wasm guest
//! without dragging in `kotoba-datomic`/`kotoba-core`.
//!
//! Reference: <https://docs.soliditylang.org/en/latest/abi-spec.html>

use sha3::{Digest, Keccak256};

/// ABI word size in bytes (every static value is padded to 32 bytes).
pub const WORD: usize = 32;

/// Compute the 4-byte function selector for a Solidity signature.
///
/// `signature` is the canonical form with no spaces, e.g. `"balanceOf(address)"`
/// or `"transfer(address,uint256)"`. The selector is the first 4 bytes of the
/// keccak256 of the ASCII signature.
pub fn selector(signature: &str) -> [u8; 4] {
    let hash = Keccak256::digest(signature.as_bytes());
    [hash[0], hash[1], hash[2], hash[3]]
}

/// Left-pad a 20-byte address into a 32-byte ABI word (12 zero bytes + address).
pub fn encode_address(addr: &[u8; 20]) -> [u8; WORD] {
    let mut word = [0u8; WORD];
    word[12..].copy_from_slice(addr);
    word
}

/// Encode a `u128` as a big-endian uint256 word (right-aligned).
pub fn encode_u128(value: u128) -> [u8; WORD] {
    let mut word = [0u8; WORD];
    word[WORD - 16..].copy_from_slice(&value.to_be_bytes());
    word
}

/// Encode a raw 32-byte big-endian uint256 (identity — already a word).
pub fn encode_u256(value: &[u8; WORD]) -> [u8; WORD] {
    *value
}

/// Encode a bool as a uint256 word (0 or 1).
pub fn encode_bool(value: bool) -> [u8; WORD] {
    let mut word = [0u8; WORD];
    word[WORD - 1] = value as u8;
    word
}

/// Build calldata from a selector and a list of pre-encoded static words.
///
/// Only valid when every argument is a static type (address/uintN/bool/bytesN).
/// For the ERC-20/721/1155 view surface this covers every call we make.
pub fn encode_call(selector: [u8; 4], static_words: &[[u8; WORD]]) -> Vec<u8> {
    let mut out = Vec::with_capacity(4 + static_words.len() * WORD);
    out.extend_from_slice(&selector);
    for w in static_words {
        out.extend_from_slice(w);
    }
    out
}

/// Errors from decoding ABI-encoded return data.
#[derive(Debug, PartialEq, Eq)]
pub enum AbiError {
    /// Return data was shorter than the decoder required.
    Short {
        /// Bytes available.
        got: usize,
        /// Bytes required.
        need: usize,
    },
    /// A dynamic offset or length pointed outside the buffer.
    BadOffset,
    /// UTF-8 decode failed for a `string` return.
    Utf8,
}

impl core::fmt::Display for AbiError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            AbiError::Short { got, need } => {
                write!(f, "abi: short data: got {got} bytes, need {need}")
            }
            AbiError::BadOffset => write!(f, "abi: dynamic offset out of bounds"),
            AbiError::Utf8 => write!(f, "abi: invalid utf-8 in string return"),
        }
    }
}

impl std::error::Error for AbiError {}

/// Read the first 32-byte word as a raw big-endian uint256.
pub fn decode_u256(data: &[u8]) -> Result<[u8; WORD], AbiError> {
    if data.len() < WORD {
        return Err(AbiError::Short {
            got: data.len(),
            need: WORD,
        });
    }
    let mut word = [0u8; WORD];
    word.copy_from_slice(&data[..WORD]);
    Ok(word)
}

/// Decode the first word as a `u8` (e.g. ERC-20 `decimals()`).
///
/// Takes the low byte; values above 255 are truncated (no token uses them).
pub fn decode_u8(data: &[u8]) -> Result<u8, AbiError> {
    let word = decode_u256(data)?;
    Ok(word[WORD - 1])
}

/// Decode the first word as a bool (`ownerOf` style flags, `isApprovedForAll`).
pub fn decode_bool(data: &[u8]) -> Result<bool, AbiError> {
    let word = decode_u256(data)?;
    Ok(word.iter().any(|&b| b != 0))
}

/// Decode the first word as a 20-byte address (low 20 bytes).
pub fn decode_address(data: &[u8]) -> Result<[u8; 20], AbiError> {
    let word = decode_u256(data)?;
    let mut addr = [0u8; 20];
    addr.copy_from_slice(&word[12..]);
    Ok(addr)
}

/// Read a big-endian word at byte offset `off` as a `usize`, rejecting overflow.
fn word_as_usize(data: &[u8], off: usize) -> Result<usize, AbiError> {
    let end = off.checked_add(WORD).ok_or(AbiError::BadOffset)?;
    if data.len() < end {
        return Err(AbiError::BadOffset);
    }
    // High 24 bytes must be zero for the value to fit a usize/buffer index.
    if data[off..end - 8].iter().any(|&b| b != 0) {
        return Err(AbiError::BadOffset);
    }
    let mut buf = [0u8; 8];
    buf.copy_from_slice(&data[end - 8..end]);
    Ok(u64::from_be_bytes(buf) as usize)
}

/// Decode a single dynamic `string` return value.
///
/// Layout for a function returning one `string`: word0 = offset (usually 0x20),
/// then at that offset: word = byte length, followed by the UTF-8 bytes (zero
/// padded to a word boundary).
pub fn decode_string(data: &[u8]) -> Result<String, AbiError> {
    let offset = word_as_usize(data, 0)?;
    let len = word_as_usize(data, offset)?;
    let start = offset.checked_add(WORD).ok_or(AbiError::BadOffset)?;
    let end = start.checked_add(len).ok_or(AbiError::BadOffset)?;
    if data.len() < end {
        return Err(AbiError::BadOffset);
    }
    String::from_utf8(data[start..end].to_vec()).map_err(|_| AbiError::Utf8)
}

/// Decode a legacy `bytes32` string (e.g. MKR's `name()`/`symbol()` which return
/// a fixed `bytes32` instead of a dynamic `string`). Trailing zero bytes are
/// trimmed and the remainder is interpreted as UTF-8.
pub fn decode_bytes32_string(data: &[u8]) -> Result<String, AbiError> {
    let word = decode_u256(data)?;
    let trimmed: Vec<u8> = word.iter().copied().take_while(|&b| b != 0).collect();
    String::from_utf8(trimmed).map_err(|_| AbiError::Utf8)
}

/// Best-effort string decode: try the dynamic `string` layout first, and fall
/// back to the legacy `bytes32` interpretation when the data is exactly one word
/// (so callers don't have to know which ABI a given token uses).
pub fn decode_string_or_bytes32(data: &[u8]) -> Result<String, AbiError> {
    if data.len() == WORD {
        return decode_bytes32_string(data);
    }
    decode_string(data)
}

/// Convert a big-endian 32-byte uint256 to a base-10 string (no allocation of a
/// bignum crate — repeated division by 10 on the byte array).
pub fn u256_to_decimal_string(value: &[u8; WORD]) -> String {
    if value.iter().all(|&b| b == 0) {
        return "0".to_string();
    }
    let mut bytes = *value;
    let mut digits = Vec::new();
    while bytes.iter().any(|&b| b != 0) {
        let mut remainder: u16 = 0;
        for byte in bytes.iter_mut() {
            let acc = (remainder << 8) | *byte as u16;
            *byte = (acc / 10) as u8;
            remainder = acc % 10;
        }
        digits.push(b'0' + remainder as u8);
    }
    digits.reverse();
    // Safe: digits only contains ASCII '0'..='9'.
    String::from_utf8(digits).unwrap()
}

/// Apply ERC-20 `decimals` to a raw uint256 balance, producing a human-readable
/// fixed-point decimal string (e.g. raw `1500000`, decimals `6` → `"1.5"`).
pub fn format_units(value: &[u8; WORD], decimals: u8) -> String {
    let raw = u256_to_decimal_string(value);
    let decimals = decimals as usize;
    if decimals == 0 {
        return raw;
    }
    if raw.len() <= decimals {
        let pad = decimals - raw.len();
        let frac = format!("{}{}", "0".repeat(pad), raw);
        let frac = frac.trim_end_matches('0');
        if frac.is_empty() {
            "0".to_string()
        } else {
            format!("0.{frac}")
        }
    } else {
        let split = raw.len() - decimals;
        let int_part = &raw[..split];
        let frac_part = raw[split..].trim_end_matches('0');
        if frac_part.is_empty() {
            int_part.to_string()
        } else {
            format!("{int_part}.{frac_part}")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selector_known_vectors() {
        // ERC-20 transfer(address,uint256) = 0xa9059cbb
        assert_eq!(
            selector("transfer(address,uint256)"),
            [0xa9, 0x05, 0x9c, 0xbb]
        );
        // balanceOf(address) = 0x70a08231
        assert_eq!(selector("balanceOf(address)"), [0x70, 0xa0, 0x82, 0x31]);
        // decimals() = 0x313ce567
        assert_eq!(selector("decimals()"), [0x31, 0x3c, 0xe5, 0x67]);
        // ownerOf(uint256) = 0x6352211e
        assert_eq!(selector("ownerOf(uint256)"), [0x63, 0x52, 0x21, 0x1e]);
    }

    #[test]
    fn encode_address_left_pads() {
        let addr = [0x11u8; 20];
        let word = encode_address(&addr);
        assert_eq!(&word[..12], &[0u8; 12]);
        assert_eq!(&word[12..], &addr);
    }

    #[test]
    fn encode_u128_right_aligns() {
        let word = encode_u128(0x1234);
        assert_eq!(word[WORD - 1], 0x34);
        assert_eq!(word[WORD - 2], 0x12);
        assert!(word[..WORD - 2].iter().all(|&b| b == 0));
    }

    #[test]
    fn encode_call_concatenates() {
        let cd = encode_call(
            selector("balanceOf(address)"),
            &[encode_address(&[0xABu8; 20])],
        );
        assert_eq!(cd.len(), 4 + 32);
        assert_eq!(&cd[..4], &[0x70, 0xa0, 0x82, 0x31]);
        assert_eq!(&cd[16..], &[0xABu8; 20]);
    }

    #[test]
    fn decode_u8_reads_low_byte() {
        let mut data = [0u8; 32];
        data[31] = 18; // USDC-style decimals
        assert_eq!(decode_u8(&data).unwrap(), 18);
    }

    #[test]
    fn decode_address_reads_low_20() {
        let mut data = [0u8; 32];
        data[12..].copy_from_slice(&[0xCDu8; 20]);
        assert_eq!(decode_address(&data).unwrap(), [0xCDu8; 20]);
    }

    #[test]
    fn decode_bool_true_false() {
        let mut t = [0u8; 32];
        t[31] = 1;
        assert!(decode_bool(&t).unwrap());
        assert!(!decode_bool(&[0u8; 32]).unwrap());
    }

    #[test]
    fn decode_string_dynamic_layout() {
        // offset=0x20, len=5, "hello" padded to a word
        let mut data = vec![0u8; 32 * 3];
        data[31] = 0x20; // offset
        data[63] = 5; // length
        data[64..69].copy_from_slice(b"hello");
        assert_eq!(decode_string(&data).unwrap(), "hello");
    }

    #[test]
    fn decode_string_rejects_oob_offset() {
        let mut data = vec![0u8; 32];
        data[31] = 0xFF; // offset 255, past the 32-byte buffer
        assert_eq!(decode_string(&data), Err(AbiError::BadOffset));
    }

    #[test]
    fn decode_string_rejects_length_exceeding_buffer() {
        // Valid offset (0x20), but the length word claims more bytes than follow.
        // A malicious RPC response could over-read / over-allocate here; the decoder
        // must reject (the checked end-bound), distinct from the bad-offset case.
        let mut data = vec![0u8; 64];
        data[31] = 0x20; // offset → word at byte 32 is the length
        data[63] = 100; // length = 100, but 0 bytes follow the length word
        assert_eq!(decode_string(&data), Err(AbiError::BadOffset));
    }

    #[test]
    fn decode_string_rejects_length_word_with_high_bytes_set() {
        // A length word whose high bytes are non-zero encodes a value far larger
        // than usize. word_as_usize must reject it (high 24 bytes must be zero)
        // rather than truncate to a small in-bounds length and mis-decode / over-read.
        let mut data = vec![0u8; 64];
        data[31] = 0x20; // offset → length word at byte 32
        data[32] = 0xFF; // most-significant byte of the length word is set
        assert_eq!(decode_string(&data), Err(AbiError::BadOffset));
    }

    #[test]
    fn decode_bytes32_string_legacy_mkr() {
        // "MKR" left-aligned in a bytes32 word
        let mut data = [0u8; 32];
        data[..3].copy_from_slice(b"MKR");
        assert_eq!(decode_bytes32_string(&data).unwrap(), "MKR");
    }

    #[test]
    fn decode_string_or_bytes32_dispatches() {
        // One word → legacy bytes32 path
        let mut one = [0u8; 32];
        one[..3].copy_from_slice(b"DAI");
        assert_eq!(decode_string_or_bytes32(&one).unwrap(), "DAI");
        // Three words → dynamic string path
        let mut dyn_data = vec![0u8; 96];
        dyn_data[31] = 0x20;
        dyn_data[63] = 3;
        dyn_data[64..67].copy_from_slice(b"USD");
        assert_eq!(decode_string_or_bytes32(&dyn_data).unwrap(), "USD");
    }

    #[test]
    fn u256_decimal_string_vectors() {
        let zero = [0u8; 32];
        assert_eq!(u256_to_decimal_string(&zero), "0");

        let mut one = [0u8; 32];
        one[31] = 1;
        assert_eq!(u256_to_decimal_string(&one), "1");

        // 256
        let mut v = [0u8; 32];
        v[30] = 1;
        assert_eq!(u256_to_decimal_string(&v), "256");

        // 1_000_000 (USDC 1.0 at 6 decimals)
        let million = encode_u128(1_000_000);
        assert_eq!(u256_to_decimal_string(&million), "1000000");

        // u128::MAX
        let max = encode_u128(u128::MAX);
        assert_eq!(u256_to_decimal_string(&max), u128::MAX.to_string());
    }

    #[test]
    fn u256_decimal_full_width() {
        // 2^256 - 1
        let max = [0xFFu8; 32];
        let expected =
            "115792089237316195423570985008687907853269984665640564039457584007913129639935";
        assert_eq!(u256_to_decimal_string(&max), expected);
    }

    #[test]
    fn format_units_vectors() {
        // 1.5 USDC at 6 decimals
        assert_eq!(format_units(&encode_u128(1_500_000), 6), "1.5");
        // exactly 1 token
        assert_eq!(format_units(&encode_u128(1_000_000), 6), "1");
        // sub-unit: 0.000001
        assert_eq!(format_units(&encode_u128(1), 6), "0.000001");
        // 18-decimal whole ether
        assert_eq!(
            format_units(&encode_u128(1_000_000_000_000_000_000), 18),
            "1"
        );
        // decimals = 0 → identity
        assert_eq!(format_units(&encode_u128(42), 0), "42");
        // zero
        assert_eq!(format_units(&[0u8; 32], 6), "0");
    }
}
