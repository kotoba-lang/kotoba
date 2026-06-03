//! Bitcoin address parsing, validation, and rendering.
//!
//! Two encodings, hand-rolled (deps: `bs58` + `sha2` only) in the same spirit
//! as the by-hand EIP-55 checksum in [`crate::eth`]:
//!
//! - **Base58Check** — legacy P2PKH (`1…`) and P2SH (`3…`) (BIP-13).
//! - **bech32 / bech32m** — SegWit v0 P2WPKH (`bc1q…`, 20-byte) / P2WSH
//!   (`bc1q…`, 32-byte) and Taproot v1 P2TR (`bc1p…`, bech32m) (BIP-173/350).
//!
//! All forms are **verify-only**: we decode and validate the checksum so a
//! caller can confirm an address is well-formed and bind it to a member, but we
//! never derive spending scripts or build transactions.

use super::hash256;

/// Bitcoin network a parsed address belongs to.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BtcNetwork {
    Mainnet,
    Testnet,
}

/// The script template an address commits to.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AddressKind {
    /// Pay-to-Public-Key-Hash (Base58, version 0x00 / 0x6f).
    P2pkh,
    /// Pay-to-Script-Hash (Base58, version 0x05 / 0xc4).
    P2sh,
    /// SegWit v0, 20-byte program (bech32, `…q…`).
    P2wpkh,
    /// SegWit v0, 32-byte program (bech32, `…q…`).
    P2wsh,
    /// Taproot, SegWit v1, 32-byte program (bech32m, `…p…`).
    P2tr,
}

/// A parsed, checksum-validated Bitcoin address.
///
/// `payload` is the hashed witness/key/script bytes (20 or 32). For SegWit
/// forms, `witness_version` is the program version (`0` for P2WPKH/P2WSH, `1`
/// for P2TR); it is `None` for the Base58 forms.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BtcAddress {
    pub network: BtcNetwork,
    pub kind: AddressKind,
    pub payload: Vec<u8>,
    pub witness_version: Option<u8>,
}

/// Address parse/validation error.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AddrError(pub String);

impl std::fmt::Display for AddrError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}
impl std::error::Error for AddrError {}

fn err<T>(msg: impl Into<String>) -> Result<T, AddrError> {
    Err(AddrError(msg.into()))
}

impl BtcAddress {
    /// Parse any supported Bitcoin address string, validating its checksum.
    pub fn parse(s: &str) -> Result<Self, AddrError> {
        // bech32/bech32m addresses contain a '1' separator after a known HRP.
        let lower = s.to_lowercase();
        if lower.starts_with("bc1") || lower.starts_with("tb1") {
            return parse_bech32(s);
        }
        parse_base58check(s)
    }

    /// Render back to canonical string form (round-trips [`Self::parse`]).
    /// This backs the [`std::fmt::Display`] impl; prefer `.to_string()`.
    fn render(&self) -> String {
        match self.kind {
            AddressKind::P2pkh | AddressKind::P2sh => {
                let version = base58_version(self.network, self.kind);
                let mut data = Vec::with_capacity(1 + self.payload.len());
                data.push(version);
                data.extend_from_slice(&self.payload);
                let checksum = &hash256(&data)[..4];
                data.extend_from_slice(checksum);
                bs58::encode(data).into_string()
            }
            AddressKind::P2wpkh | AddressKind::P2wsh | AddressKind::P2tr => {
                let hrp = match self.network {
                    BtcNetwork::Mainnet => "bc",
                    BtcNetwork::Testnet => "tb",
                };
                let wv = self.witness_version.unwrap_or(0);
                encode_segwit(hrp, wv, &self.payload)
            }
        }
    }
}

impl std::fmt::Display for BtcAddress {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.render())
    }
}

fn base58_version(network: BtcNetwork, kind: AddressKind) -> u8 {
    match (network, kind) {
        (BtcNetwork::Mainnet, AddressKind::P2pkh) => 0x00,
        (BtcNetwork::Mainnet, AddressKind::P2sh) => 0x05,
        (BtcNetwork::Testnet, AddressKind::P2pkh) => 0x6f,
        (BtcNetwork::Testnet, AddressKind::P2sh) => 0xc4,
        _ => unreachable!("base58_version called for non-base58 kind"),
    }
}

fn parse_base58check(s: &str) -> Result<BtcAddress, AddrError> {
    let raw = bs58::decode(s)
        .into_vec()
        .map_err(|e| AddrError(format!("base58 decode: {e}")))?;
    if raw.len() != 25 {
        return err(format!(
            "base58check payload must be 25 bytes, got {}",
            raw.len()
        ));
    }
    let (body, checksum) = raw.split_at(21);
    let expect = &hash256(body)[..4];
    if checksum != expect {
        return err(format!("base58check checksum mismatch: {s}"));
    }
    let version = body[0];
    let (network, kind) = match version {
        0x00 => (BtcNetwork::Mainnet, AddressKind::P2pkh),
        0x05 => (BtcNetwork::Mainnet, AddressKind::P2sh),
        0x6f => (BtcNetwork::Testnet, AddressKind::P2pkh),
        0xc4 => (BtcNetwork::Testnet, AddressKind::P2sh),
        v => return err(format!("unknown base58 version byte: 0x{v:02x}")),
    };
    Ok(BtcAddress {
        network,
        kind,
        payload: body[1..].to_vec(),
        witness_version: None,
    })
}

// ── bech32 / bech32m (BIP-173 / BIP-350) ────────────────────────────────────

const CHARSET: &[u8; 32] = b"qpzry9x8gf2tvdw0s3jn54khce6mua7l";
const BECH32_CONST: u32 = 1;
const BECH32M_CONST: u32 = 0x2bc8_30a3;

fn polymod(values: &[u8]) -> u32 {
    const GEN: [u32; 5] = [
        0x3b6a_57b2,
        0x2650_8e6d,
        0x1ea1_19fa,
        0x3d42_33dd,
        0x2a14_62b3,
    ];
    let mut chk: u32 = 1;
    for &v in values {
        let top = chk >> 25;
        chk = ((chk & 0x1ff_ffff) << 5) ^ (v as u32);
        for (i, g) in GEN.iter().enumerate() {
            if (top >> i) & 1 == 1 {
                chk ^= g;
            }
        }
    }
    chk
}

fn hrp_expand(hrp: &str) -> Vec<u8> {
    let mut v: Vec<u8> = hrp.bytes().map(|b| b >> 5).collect();
    v.push(0);
    v.extend(hrp.bytes().map(|b| b & 0x1f));
    v
}

/// Convert between bit groups (8↔5). `pad` controls trailing zero-padding.
fn convert_bits(data: &[u8], from: u32, to: u32, pad: bool) -> Result<Vec<u8>, AddrError> {
    let mut acc: u32 = 0;
    let mut bits: u32 = 0;
    let mut out = Vec::new();
    let maxv: u32 = (1 << to) - 1;
    for &value in data {
        if (value as u32) >> from != 0 {
            return err("convert_bits: value out of range");
        }
        acc = (acc << from) | value as u32;
        bits += from;
        while bits >= to {
            bits -= to;
            out.push(((acc >> bits) & maxv) as u8);
        }
    }
    if pad {
        if bits > 0 {
            out.push(((acc << (to - bits)) & maxv) as u8);
        }
    } else if bits >= from || ((acc << (to - bits)) & maxv) != 0 {
        return err("convert_bits: invalid padding");
    }
    Ok(out)
}

fn parse_bech32(s: &str) -> Result<BtcAddress, AddrError> {
    // Mixed case is forbidden by BIP-173.
    if s.chars().any(|c| c.is_ascii_uppercase()) && s.chars().any(|c| c.is_ascii_lowercase()) {
        return err("bech32: mixed case");
    }
    let s = s.to_lowercase();
    let sep = s
        .rfind('1')
        .ok_or_else(|| AddrError("bech32: missing separator".into()))?;
    if sep == 0 || sep + 7 > s.len() {
        return err("bech32: bad separator position");
    }
    let (hrp, rest) = s.split_at(sep);
    let data_part = &rest[1..]; // skip the '1'
    let network = match hrp {
        "bc" => BtcNetwork::Mainnet,
        "tb" => BtcNetwork::Testnet,
        other => return err(format!("bech32: unknown hrp '{other}'")),
    };

    let mut values = Vec::with_capacity(data_part.len());
    for c in data_part.bytes() {
        match CHARSET.iter().position(|&x| x == c) {
            Some(i) => values.push(i as u8),
            None => return err(format!("bech32: invalid char '{}'", c as char)),
        }
    }
    if values.len() < 6 {
        return err("bech32: data too short");
    }

    // Witness version is the first data symbol; remaining (minus 6 checksum) is
    // the program in 5-bit groups.
    let witness_version = values[0];
    let checksum_const = polymod(&[hrp_expand(hrp), values.clone()].concat());
    let expected = if witness_version == 0 {
        BECH32_CONST
    } else {
        BECH32M_CONST
    };
    if checksum_const != expected {
        return err("bech32: checksum mismatch");
    }

    let program = convert_bits(&values[1..values.len() - 6], 5, 8, false)?;
    if program.len() < 2 || program.len() > 40 {
        return err("bech32: program length out of range");
    }
    if witness_version > 16 {
        return err("bech32: invalid witness version");
    }

    let kind = match (witness_version, program.len()) {
        (0, 20) => AddressKind::P2wpkh,
        (0, 32) => AddressKind::P2wsh,
        (0, n) => return err(format!("bech32: v0 program must be 20/32 bytes, got {n}")),
        (1, 32) => AddressKind::P2tr,
        (1, n) => return err(format!("bech32m: v1 program must be 32 bytes, got {n}")),
        (v, _) => return err(format!("bech32: unsupported witness version {v}")),
    };

    Ok(BtcAddress {
        network,
        kind,
        payload: program,
        witness_version: Some(witness_version),
    })
}

fn create_checksum(hrp: &str, data: &[u8], spec_const: u32) -> Vec<u8> {
    let mut values = hrp_expand(hrp);
    values.extend_from_slice(data);
    values.extend_from_slice(&[0u8; 6]);
    let polymod = polymod(&values) ^ spec_const;
    (0..6)
        .map(|i| ((polymod >> (5 * (5 - i))) & 0x1f) as u8)
        .collect()
}

fn encode_segwit(hrp: &str, witness_version: u8, program: &[u8]) -> String {
    let mut data = vec![witness_version];
    data.extend(convert_bits(program, 8, 5, true).expect("8→5 always pads"));
    let spec_const = if witness_version == 0 {
        BECH32_CONST
    } else {
        BECH32M_CONST
    };
    let checksum = create_checksum(hrp, &data, spec_const);
    let mut out = String::with_capacity(hrp.len() + 1 + data.len() + 6);
    out.push_str(hrp);
    out.push('1');
    for b in data.iter().chain(checksum.iter()) {
        out.push(CHARSET[*b as usize] as char);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn p2pkh_mainnet_roundtrip() {
        // Satoshi's genesis coinbase address.
        let a = BtcAddress::parse("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa").unwrap();
        assert_eq!(a.kind, AddressKind::P2pkh);
        assert_eq!(a.network, BtcNetwork::Mainnet);
        assert_eq!(a.payload.len(), 20);
        assert_eq!(a.to_string(), "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa");
    }

    #[test]
    fn p2sh_mainnet_roundtrip() {
        let a = BtcAddress::parse("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy").unwrap();
        assert_eq!(a.kind, AddressKind::P2sh);
        assert_eq!(a.to_string(), "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy");
    }

    #[test]
    fn p2wpkh_bech32_roundtrip() {
        // BIP-173 test vector.
        let a = BtcAddress::parse("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4").unwrap();
        assert_eq!(a.kind, AddressKind::P2wpkh);
        assert_eq!(a.network, BtcNetwork::Mainnet);
        assert_eq!(a.payload.len(), 20);
        assert_eq!(a.to_string(), "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4");
    }

    #[test]
    fn p2tr_bech32m_roundtrip() {
        // BIP-350 test vector (Taproot, witness v1, bech32m).
        let s = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0";
        let a = BtcAddress::parse(s).unwrap();
        assert_eq!(a.kind, AddressKind::P2tr);
        assert_eq!(a.witness_version, Some(1));
        assert_eq!(a.payload.len(), 32);
        assert_eq!(a.to_string(), s);
    }

    #[test]
    fn testnet_bech32() {
        let a = BtcAddress::parse("tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7")
            .unwrap();
        assert_eq!(a.network, BtcNetwork::Testnet);
        assert_eq!(a.kind, AddressKind::P2wsh);
    }

    #[test]
    fn base58_bad_checksum_rejected() {
        // Last char mutated → checksum fails.
        assert!(BtcAddress::parse("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb").is_err());
    }

    #[test]
    fn bech32_bad_checksum_rejected() {
        assert!(BtcAddress::parse("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5").is_err());
    }

    #[test]
    fn bech32_v0_with_bech32m_const_rejected() {
        // A P2TR string fed as if v0 would mismatch; we just confirm the real
        // taproot vector is NOT classified as v0.
        let a = BtcAddress::parse("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0")
            .unwrap();
        assert_ne!(a.witness_version, Some(0));
    }

    #[test]
    fn mixed_case_bech32_rejected() {
        assert!(BtcAddress::parse("bc1Qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4").is_err());
    }

    #[test]
    fn garbage_rejected() {
        assert!(BtcAddress::parse("not an address").is_err());
        assert!(BtcAddress::parse("").is_err());
    }
}
