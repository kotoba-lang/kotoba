//! Minimal STUN (RFC 8489) message primitives the TURN relay's listeners need:
//! the 20-byte header, attribute TLV iteration with 4-byte padding, and
//! XOR-MAPPED-ADDRESS (the relayed/mapped address carried in `Allocate` and
//! `Binding` responses). Verified against the RFC 5769 test vectors.
//!
//! Out of scope here: MESSAGE-INTEGRITY computation (uses the auth-core HMAC) and
//! the allocation state machine — wired in when the UDP/TCP listeners land.

use hmac::{Hmac, Mac};
use sha1::Sha1;
use std::net::Ipv4Addr;

type HmacSha1 = Hmac<Sha1>;

/// RFC 8489 magic cookie — bytes 4..8 of every STUN message.
pub const MAGIC_COOKIE: u32 = 0x2112_A442;

/// FINGERPRINT XOR constant (RFC 8489 §14.7).
pub const FINGERPRINT_XOR: u32 = 0x5354_554E;

// Message types (RFC 8489 / RFC 8656). For these low method numbers the request
// class encoding equals the method value.
pub const BINDING_REQUEST: u16 = 0x0001;
pub const BINDING_RESPONSE: u16 = 0x0101;
pub const ALLOCATE_REQUEST: u16 = 0x0003;
pub const ALLOCATE_RESPONSE: u16 = 0x0103;
/// Allocate error response (class = error, method = Allocate).
pub const ALLOCATE_ERROR: u16 = 0x0113;
pub const REFRESH_REQUEST: u16 = 0x0004;
pub const REFRESH_RESPONSE: u16 = 0x0104;
pub const CREATE_PERMISSION_REQUEST: u16 = 0x0008;
pub const CREATE_PERMISSION_RESPONSE: u16 = 0x0108;
pub const CHANNEL_BIND_REQUEST: u16 = 0x0009;
pub const CHANNEL_BIND_RESPONSE: u16 = 0x0109;
/// Send / Data indications (RFC 8656 §10/§11) — class = indication.
pub const SEND_INDICATION: u16 = 0x0016;
pub const DATA_INDICATION: u16 = 0x0017;

// Attribute types.
pub const ATTR_USERNAME: u16 = 0x0006;
pub const ATTR_MESSAGE_INTEGRITY: u16 = 0x0008;
pub const ATTR_ERROR_CODE: u16 = 0x0009;
pub const ATTR_CHANNEL_NUMBER: u16 = 0x000C;
pub const ATTR_LIFETIME: u16 = 0x000D;
pub const ATTR_XOR_PEER_ADDRESS: u16 = 0x0012;
pub const ATTR_DATA: u16 = 0x0013;
pub const ATTR_XOR_RELAYED_ADDRESS: u16 = 0x0016;
pub const ATTR_REQUESTED_TRANSPORT: u16 = 0x0019;
pub const ATTR_XOR_MAPPED_ADDRESS: u16 = 0x0020;
pub const ATTR_SOFTWARE: u16 = 0x8022;
pub const ATTR_FINGERPRINT: u16 = 0x8028;

/// Append a STUN attribute TLV (type, length, value) with RFC 8489 4-byte padding.
/// Does not touch the header length — callers patch that via
/// [`set_attr_length`] / [`append_message_integrity`] / [`append_fingerprint`].
pub fn push_attr(buf: &mut Vec<u8>, typ: u16, value: &[u8]) {
    buf.extend_from_slice(&typ.to_be_bytes());
    buf.extend_from_slice(&(value.len() as u16).to_be_bytes());
    buf.extend_from_slice(value);
    let pad = (4 - (value.len() % 4)) % 4;
    buf.extend(std::iter::repeat_n(0u8, pad));
}

/// Patch the header length field to cover all attributes currently in `buf`
/// (use for responses that carry no MESSAGE-INTEGRITY/FINGERPRINT trailer).
pub fn set_attr_length(buf: &mut [u8]) {
    let len = (buf.len() - 20) as u16;
    buf[2..4].copy_from_slice(&len.to_be_bytes());
}

/// Encode an ERROR-CODE attribute value (RFC 8489 §14.8): 2 reserved bytes, the
/// class (hundreds digit), the number (mod 100), then the UTF-8 reason phrase.
pub fn encode_error_code(code: u16, reason: &str) -> Vec<u8> {
    let mut v = vec![0u8, 0u8, (code / 100) as u8, (code % 100) as u8];
    v.extend_from_slice(reason.as_bytes());
    v
}

/// Encode a 4-byte LIFETIME / 32-bit attribute value (seconds).
pub fn encode_u32(value: u32) -> [u8; 4] {
    value.to_be_bytes()
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum StunError {
    #[error("message shorter than 20-byte header")]
    Short,
    #[error("bad magic cookie")]
    BadMagic,
    #[error("attribute length runs past the message")]
    BadAttr,
    #[error("unsupported address family")]
    BadFamily,
}

/// The fixed 20-byte STUN message header.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Header {
    pub typ: u16,
    /// Length of the attribute section (excludes the header).
    pub length: u16,
    /// 96-bit transaction id.
    pub txid: [u8; 12],
}

impl Header {
    pub fn decode(buf: &[u8]) -> Result<Header, StunError> {
        if buf.len() < 20 {
            return Err(StunError::Short);
        }
        if u32::from_be_bytes([buf[4], buf[5], buf[6], buf[7]]) != MAGIC_COOKIE {
            return Err(StunError::BadMagic);
        }
        let mut txid = [0u8; 12];
        txid.copy_from_slice(&buf[8..20]);
        Ok(Header {
            typ: u16::from_be_bytes([buf[0], buf[1]]),
            length: u16::from_be_bytes([buf[2], buf[3]]),
            txid,
        })
    }

    pub fn encode(&self) -> [u8; 20] {
        let mut out = [0u8; 20];
        out[0..2].copy_from_slice(&self.typ.to_be_bytes());
        out[2..4].copy_from_slice(&self.length.to_be_bytes());
        out[4..8].copy_from_slice(&MAGIC_COOKIE.to_be_bytes());
        out[8..20].copy_from_slice(&self.txid);
        out
    }
}

/// Iterate `(type, value)` attributes from the message body (bytes after the
/// 20-byte header), honoring the STUN 4-byte attribute padding.
pub fn attributes(body: &[u8]) -> Result<Vec<(u16, &[u8])>, StunError> {
    let mut out = Vec::new();
    let mut i = 0;
    while i + 4 <= body.len() {
        let typ = u16::from_be_bytes([body[i], body[i + 1]]);
        let len = u16::from_be_bytes([body[i + 2], body[i + 3]]) as usize;
        let start = i + 4;
        let end = start + len;
        if end > body.len() {
            return Err(StunError::BadAttr);
        }
        out.push((typ, &body[start..end]));
        i = end + ((4 - (len % 4)) % 4); // advance past padding to a 4-byte boundary
    }
    Ok(out)
}

/// Encode an IPv4 XOR-MAPPED-ADDRESS attribute value (8 bytes, RFC 8489 §14.2).
pub fn encode_xor_mapped_v4(ip: Ipv4Addr, port: u16) -> [u8; 8] {
    let x_port = port ^ ((MAGIC_COOKIE >> 16) as u16);
    let x_addr = u32::from(ip) ^ MAGIC_COOKIE;
    let mut v = [0u8; 8];
    v[1] = 0x01; // family: IPv4 (v[0] reserved = 0)
    v[2..4].copy_from_slice(&x_port.to_be_bytes());
    v[4..8].copy_from_slice(&x_addr.to_be_bytes());
    v
}

/// Decode an IPv4 XOR-MAPPED-ADDRESS attribute value.
pub fn decode_xor_mapped_v4(v: &[u8]) -> Result<(Ipv4Addr, u16), StunError> {
    if v.len() != 8 {
        return Err(StunError::BadAttr);
    }
    if v[1] != 0x01 {
        return Err(StunError::BadFamily);
    }
    let port = u16::from_be_bytes([v[2], v[3]]) ^ ((MAGIC_COOKIE >> 16) as u16);
    let x_addr = u32::from_be_bytes([v[4], v[5], v[6], v[7]]);
    Ok((Ipv4Addr::from(x_addr ^ MAGIC_COOKIE), port))
}

/// Offset of attribute `typ`'s TLV start within `body`, or `None`.
fn attribute_offset(body: &[u8], typ: u16) -> Option<usize> {
    let mut i = 0;
    while i + 4 <= body.len() {
        let t = u16::from_be_bytes([body[i], body[i + 1]]);
        let len = u16::from_be_bytes([body[i + 2], body[i + 3]]) as usize;
        if t == typ {
            return Some(i);
        }
        i += 4 + len + ((4 - (len % 4)) % 4);
    }
    None
}

/// CRC-32 (IEEE 802.3, reflected) — the checksum STUN FINGERPRINT is built on.
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc: u32 = 0xFFFF_FFFF;
    for &b in data {
        crc ^= b as u32;
        for _ in 0..8 {
            let mask = (crc & 1).wrapping_neg();
            crc = (crc >> 1) ^ (0xEDB8_8320 & mask);
        }
    }
    !crc
}

/// Append a MESSAGE-INTEGRITY attribute (RFC 8489 §14.5). `buf` must already be a
/// complete header+attributes STUN message (no MI/FINGERPRINT yet). The header
/// length is set to cover the MI attribute, the HMAC-SHA1 is taken over the
/// message up to (not including) the MI TLV, then the 24-byte TLV is appended.
pub fn append_message_integrity(buf: &mut Vec<u8>, key: &[u8]) {
    let covered = (buf.len() - 20 + 24) as u16;
    buf[2..4].copy_from_slice(&covered.to_be_bytes());
    let mut mac = HmacSha1::new_from_slice(key).expect("HMAC accepts any key length");
    mac.update(buf);
    let tag = mac.finalize().into_bytes();
    buf.extend_from_slice(&ATTR_MESSAGE_INTEGRITY.to_be_bytes());
    buf.extend_from_slice(&20u16.to_be_bytes());
    buf.extend_from_slice(&tag);
}

/// Verify a message's MESSAGE-INTEGRITY against `key` (constant-time).
pub fn verify_message_integrity(msg: &[u8], key: &[u8]) -> Result<(), StunError> {
    if msg.len() < 20 {
        return Err(StunError::Short);
    }
    let body = &msg[20..];
    let p = attribute_offset(body, ATTR_MESSAGE_INTEGRITY).ok_or(StunError::BadAttr)?;
    if p + 24 > body.len() {
        return Err(StunError::BadAttr);
    }
    // Recompute over [header | attrs-before-MI] with the length field pointing
    // at the end of the MI attribute — independent of any trailing FINGERPRINT.
    let mut covered = msg[..20 + p].to_vec();
    let len_field = (p + 24) as u16;
    covered[2..4].copy_from_slice(&len_field.to_be_bytes());
    let mut mac = HmacSha1::new_from_slice(key).map_err(|_| StunError::BadAttr)?;
    mac.update(&covered);
    mac.verify_slice(&body[p + 4..p + 24])
        .map_err(|_| StunError::BadAttr)
}

/// Append a FINGERPRINT attribute (RFC 8489 §14.7) — must be the last attribute.
pub fn append_fingerprint(buf: &mut Vec<u8>) {
    let covered = (buf.len() - 20 + 8) as u16;
    buf[2..4].copy_from_slice(&covered.to_be_bytes());
    let crc = crc32(buf) ^ FINGERPRINT_XOR;
    buf.extend_from_slice(&ATTR_FINGERPRINT.to_be_bytes());
    buf.extend_from_slice(&4u16.to_be_bytes());
    buf.extend_from_slice(&crc.to_be_bytes());
}

/// Verify a trailing FINGERPRINT attribute.
pub fn verify_fingerprint(msg: &[u8]) -> bool {
    if msg.len() < 28 {
        return false;
    }
    let fp = msg.len() - 8;
    if u16::from_be_bytes([msg[fp], msg[fp + 1]]) != ATTR_FINGERPRINT {
        return false;
    }
    let expected = crc32(&msg[..fp]) ^ FINGERPRINT_XOR;
    u32::from_be_bytes([msg[fp + 4], msg[fp + 5], msg[fp + 6], msg[fp + 7]]) == expected
}

#[cfg(test)]
mod tests {
    use super::*;

    // RFC 5769 §2.2: the response carries XOR-MAPPED-ADDRESS 192.0.2.1:32853.
    #[test]
    fn xor_mapped_address_matches_rfc5769() {
        let encoded = encode_xor_mapped_v4(Ipv4Addr::new(192, 0, 2, 1), 32853);
        assert_eq!(encoded, [0x00, 0x01, 0xA1, 0x47, 0xE1, 0x12, 0xA6, 0x43]);
        assert_eq!(
            decode_xor_mapped_v4(&encoded).unwrap(),
            (Ipv4Addr::new(192, 0, 2, 1), 32853)
        );
    }

    #[test]
    fn header_round_trips_and_rejects_bad_magic() {
        let h = Header {
            typ: ALLOCATE_REQUEST,
            length: 8,
            txid: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        };
        let bytes = h.encode();
        assert_eq!(Header::decode(&bytes).unwrap(), h);

        let mut bad = bytes;
        bad[4] ^= 0xFF;
        assert_eq!(Header::decode(&bad), Err(StunError::BadMagic));
        assert_eq!(Header::decode(&bytes[..19]), Err(StunError::Short));
    }

    #[test]
    fn attributes_parse_with_padding() {
        // USERNAME(len 3, +1 pad) then SOFTWARE(len 4, no pad).
        let body = [
            0x00, 0x06, 0x00, 0x03, b'a', b'b', b'c', 0x00, 0x80, 0x22, 0x00, 0x04, b'k', b'o',
            b't', b'o',
        ];
        let attrs = attributes(&body).unwrap();
        assert_eq!(attrs.len(), 2);
        assert_eq!(attrs[0], (ATTR_USERNAME, &b"abc"[..]));
        assert_eq!(attrs[1], (ATTR_SOFTWARE, &b"koto"[..]));
    }

    #[test]
    fn attributes_reject_overrun_length() {
        let body = [0x00, 0x06, 0x00, 0xFF, b'a'];
        assert_eq!(attributes(&body), Err(StunError::BadAttr));
    }

    #[test]
    fn crc32_matches_standard_check_value() {
        // The canonical CRC-32/IEEE check value for "123456789".
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    }

    /// A header + one SOFTWARE attribute, no MI/FINGERPRINT yet.
    fn sample_message() -> Vec<u8> {
        let h = Header {
            typ: BINDING_REQUEST,
            length: 0,
            txid: [9; 12],
        };
        let mut buf = h.encode().to_vec();
        buf.extend_from_slice(&ATTR_SOFTWARE.to_be_bytes());
        buf.extend_from_slice(&4u16.to_be_bytes());
        buf.extend_from_slice(b"koto");
        // header length currently 0 — the append_* helpers patch it.
        let attr_len = (buf.len() - 20) as u16;
        buf[2..4].copy_from_slice(&attr_len.to_be_bytes());
        buf
    }

    #[test]
    fn message_integrity_round_trips_and_detects_tamper() {
        let key = b"VOkJxbRl1RmTxUk/WvJxBt"; // RFC 5769 sample short-term password
        let mut msg = sample_message();
        append_message_integrity(&mut msg, key);

        assert!(verify_message_integrity(&msg, key).is_ok());
        assert!(verify_message_integrity(&msg, b"wrong-key").is_err());

        let mut tampered = msg.clone();
        tampered[24] ^= 0xFF; // flip a byte in the SOFTWARE value
        assert!(verify_message_integrity(&tampered, key).is_err());
    }

    #[test]
    fn message_integrity_survives_trailing_fingerprint() {
        let key = b"secret";
        let mut msg = sample_message();
        append_message_integrity(&mut msg, key);
        append_fingerprint(&mut msg);
        // MI must still verify even though the length field now covers FINGERPRINT.
        assert!(verify_message_integrity(&msg, key).is_ok());
        assert!(verify_fingerprint(&msg));
    }

    #[test]
    fn fingerprint_detects_corruption() {
        let mut msg = sample_message();
        append_fingerprint(&mut msg);
        assert!(verify_fingerprint(&msg));
        let mut bad = msg.clone();
        bad[20] ^= 0xFF;
        assert!(!verify_fingerprint(&bad));
    }
}
