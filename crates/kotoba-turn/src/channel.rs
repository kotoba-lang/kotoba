//! ChannelData message codec (RFC 8656 §12.4) — the high-throughput relay path.
//!
//! Once a client `ChannelBind`s a peer, application data travels as ChannelData
//! frames instead of full STUN Send/Data indications, saving 36 bytes/packet:
//!
//! ```text
//!  0                   1                   2                   3
//!  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
//! +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
//! |         Channel Number        |            Length             |
//! +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
//! |                       Application Data ...
//! ```
//!
//! Channel numbers are 0x4000–0x7FFF; `Length` counts only application data, not
//! the 4-byte padding TCP/TLS requires.

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ChannelError {
    #[error("buffer shorter than the framed length")]
    Short,
    #[error("channel number outside 0x4000–0x7FFF")]
    BadChannel,
}

/// A borrowed view of a decoded ChannelData frame.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ChannelData<'a> {
    pub channel: u16,
    pub data: &'a [u8],
}

fn channel_in_range(n: u16) -> bool {
    (0x4000..=0x7FFF).contains(&n)
}

/// First-byte demux: ChannelData frames start 0x40–0x7F; STUN messages 0x00–0x3F
/// (the two high bits of a STUN message type are always zero). Lets a listener
/// route a datagram without fully parsing it.
pub fn is_channel_data(first_byte: u8) -> bool {
    (0x40..=0x7F).contains(&first_byte)
}

/// Encode a ChannelData frame. When `pad` (TCP/TLS), the data is padded to a
/// 4-byte boundary; the padding is not counted in the Length field.
pub fn encode(channel: u16, data: &[u8], pad: bool) -> Result<Vec<u8>, ChannelError> {
    if !channel_in_range(channel) {
        return Err(ChannelError::BadChannel);
    }
    let mut out = Vec::with_capacity(4 + data.len() + 3);
    out.extend_from_slice(&channel.to_be_bytes());
    out.extend_from_slice(&(data.len() as u16).to_be_bytes());
    out.extend_from_slice(data);
    if pad {
        let rem = (4 - (data.len() % 4)) % 4;
        out.extend(std::iter::repeat_n(0u8, rem));
    }
    Ok(out)
}

/// Decode a ChannelData frame; trailing padding (if any) is ignored.
pub fn decode(buf: &[u8]) -> Result<ChannelData<'_>, ChannelError> {
    if buf.len() < 4 {
        return Err(ChannelError::Short);
    }
    let channel = u16::from_be_bytes([buf[0], buf[1]]);
    if !channel_in_range(channel) {
        return Err(ChannelError::BadChannel);
    }
    let len = u16::from_be_bytes([buf[2], buf[3]]) as usize;
    if 4 + len > buf.len() {
        return Err(ChannelError::Short);
    }
    Ok(ChannelData {
        channel,
        data: &buf[4..4 + len],
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_with_tcp_padding() {
        // 3-byte payload → 4-byte header + 3 + 1 pad = 8 bytes.
        let framed = encode(0x4001, &[0xAA, 0xBB, 0xCC], true).unwrap();
        assert_eq!(framed.len(), 8);
        assert_eq!(&framed[0..4], &[0x40, 0x01, 0x00, 0x03]);
        let d = decode(&framed).unwrap();
        assert_eq!(
            d,
            ChannelData {
                channel: 0x4001,
                data: &[0xAA, 0xBB, 0xCC]
            }
        );
    }

    #[test]
    fn round_trips_without_padding() {
        let framed = encode(0x7FFF, &[1, 2, 3, 4], false).unwrap();
        assert_eq!(framed.len(), 8); // already 4-aligned
        assert_eq!(decode(&framed).unwrap().data, &[1, 2, 3, 4]);
    }

    #[test]
    fn rejects_bad_channel_and_short_buffer() {
        assert_eq!(encode(0x3FFF, &[1], true), Err(ChannelError::BadChannel));
        assert_eq!(decode(&[0x40, 0x01, 0x00]), Err(ChannelError::Short)); // <4 bytes
        assert_eq!(
            decode(&[0x40, 0x01, 0x00, 0x09, 1, 2]),
            Err(ChannelError::Short)
        ); // len>buf
        assert_eq!(
            decode(&[0x00, 0x01, 0x00, 0x00]),
            Err(ChannelError::BadChannel)
        ); // STUN-range channel
    }

    #[test]
    fn demux_distinguishes_channel_data_from_stun() {
        assert!(is_channel_data(0x40)); // ChannelData
        assert!(is_channel_data(0x7F));
        assert!(!is_channel_data(0x00)); // STUN Binding request
        assert!(!is_channel_data(0x01)); // STUN Allocate response high byte
        assert!(!is_channel_data(0x80)); // above the channel range
    }
}
