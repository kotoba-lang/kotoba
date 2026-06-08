//! git **pkt-line** framing (the wire envelope used by smart-HTTP and the
//! pack protocol).
//!
//! A pkt-line is a 4-byte ASCII hex length prefix followed by `length - 4`
//! payload bytes. The length *includes* the 4 prefix bytes. Two prefixes are
//! special control packets carrying no payload:
//!
//! * `0000` — **flush-pkt**, the end-of-section marker.
//! * `0001` — **delim-pkt** (protocol v2 section delimiter).
//!
//! The maximum pkt-line is 65520 bytes, so the maximum payload is 65516.
//! This module is a pure codec — no I/O, no allocation beyond the produced
//! buffers — and is exercised by byte-exact round-trip tests.

use crate::error::GitError;
use crate::Result;

/// Largest legal pkt-line length (prefix + payload), per the git protocol.
pub const MAX_PKT_LEN: usize = 65520;
/// Largest payload that fits in one data pkt-line.
pub const MAX_PAYLOAD: usize = MAX_PKT_LEN - 4;

/// The flush-pkt (`0000`) — ends a section/response.
pub const FLUSH: &[u8] = b"0000";
/// The delim-pkt (`0001`) — separates sections in protocol v2.
pub const DELIM: &[u8] = b"0001";

/// One decoded pkt-line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PktLine {
    /// A data packet with its payload (the trailing `\n` git usually appends is
    /// part of the payload and preserved verbatim).
    Data(Vec<u8>),
    /// `0000`.
    Flush,
    /// `0001`.
    Delim,
}

/// Append a single data pkt-line for `payload` to `out`.
///
/// Errors if `payload` exceeds [`MAX_PAYLOAD`] (callers must chunk larger data,
/// e.g. side-band streaming in [`super::smart_http`]).
pub fn write_data(out: &mut Vec<u8>, payload: &[u8]) -> Result<()> {
    if payload.len() > MAX_PAYLOAD {
        return Err(GitError::MalformedHeader);
    }
    let len = payload.len() + 4;
    // 4-digit lowercase hex, exactly as git emits it.
    out.extend_from_slice(format!("{len:04x}").as_bytes());
    out.extend_from_slice(payload);
    Ok(())
}

/// Append a data pkt-line for a string payload.
pub fn write_str(out: &mut Vec<u8>, s: &str) -> Result<()> {
    write_data(out, s.as_bytes())
}

/// Append a flush-pkt (`0000`).
pub fn write_flush(out: &mut Vec<u8>) {
    out.extend_from_slice(FLUSH);
}

/// Append a delim-pkt (`0001`).
pub fn write_delim(out: &mut Vec<u8>) {
    out.extend_from_slice(DELIM);
}

/// Encode one data pkt-line into a fresh buffer.
pub fn data(payload: &[u8]) -> Result<Vec<u8>> {
    let mut out = Vec::with_capacity(payload.len() + 4);
    write_data(&mut out, payload)?;
    Ok(out)
}

/// A forward-only reader over a pkt-line stream.
///
/// Holds a borrowed byte slice and yields [`PktLine`]s until the input is
/// exhausted. Malformed length prefixes (non-hex, or a length that overruns the
/// buffer) produce an error rather than a panic — the bytes come from an
/// untrusted client.
pub struct PktLineReader<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> PktLineReader<'a> {
    pub fn new(buf: &'a [u8]) -> Self {
        Self { buf, pos: 0 }
    }

    /// Bytes not yet consumed (used by the pack protocol to hand the trailing
    /// raw packfile — which is *not* pkt-line framed — to the pack reader).
    pub fn remaining(&self) -> &'a [u8] {
        &self.buf[self.pos.min(self.buf.len())..]
    }

    /// Read the next pkt-line, or `None` at end of input.
    pub fn next_pkt(&mut self) -> Result<Option<PktLine>> {
        if self.pos >= self.buf.len() {
            return Ok(None);
        }
        let prefix = self
            .buf
            .get(self.pos..self.pos + 4)
            .ok_or(GitError::MalformedHeader)?;
        let len = parse_hex4(prefix)?;
        match len {
            0 => {
                self.pos += 4;
                Ok(Some(PktLine::Flush))
            }
            1 => {
                self.pos += 4;
                Ok(Some(PktLine::Delim))
            }
            // 2 and 3 are reserved/illegal: a length must be 0/1 or ≥4.
            2 | 3 => Err(GitError::MalformedHeader),
            _ => {
                let end = self.pos + len;
                if len < 4 || end > self.buf.len() {
                    return Err(GitError::MalformedHeader);
                }
                let payload = self.buf[self.pos + 4..end].to_vec();
                self.pos = end;
                Ok(Some(PktLine::Data(payload)))
            }
        }
    }
}

impl Iterator for PktLineReader<'_> {
    type Item = Result<PktLine>;
    fn next(&mut self) -> Option<Self::Item> {
        self.next_pkt().transpose()
    }
}

/// Parse a 4-byte ASCII lowercase/uppercase hex length prefix.
fn parse_hex4(b: &[u8]) -> Result<usize> {
    if b.len() != 4 {
        return Err(GitError::MalformedHeader);
    }
    let s = std::str::from_utf8(b).map_err(|_| GitError::MalformedHeader)?;
    usize::from_str_radix(s, 16).map_err(|_| GitError::MalformedHeader)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn data_line_length_prefix_matches_git() {
        // git: `printf 'hello\n' | git ...` → "000ahello\n" (4 + 6 = 10 = 0x0a).
        let line = data(b"hello\n").unwrap();
        assert_eq!(line, b"000ahello\n");
    }

    #[test]
    fn flush_and_delim_constants() {
        assert_eq!(FLUSH, b"0000");
        assert_eq!(DELIM, b"0001");
    }

    #[test]
    fn roundtrip_stream() {
        let mut buf = Vec::new();
        write_str(&mut buf, "# service=git-upload-pack\n").unwrap();
        write_flush(&mut buf);
        write_data(&mut buf, b"want abc\n").unwrap();
        write_delim(&mut buf);
        write_flush(&mut buf);

        let got: Vec<PktLine> = PktLineReader::new(&buf).map(|r| r.unwrap()).collect();
        assert_eq!(
            got,
            vec![
                PktLine::Data(b"# service=git-upload-pack\n".to_vec()),
                PktLine::Flush,
                PktLine::Data(b"want abc\n".to_vec()),
                PktLine::Delim,
                PktLine::Flush,
            ]
        );
    }

    #[test]
    fn reader_exposes_trailing_raw_bytes() {
        // A receive-pack body is pkt-lines, a flush, then a raw packfile.
        let mut buf = Vec::new();
        write_data(&mut buf, b"old new refs/heads/main\0report-status\n").unwrap();
        write_flush(&mut buf);
        let pack_start = buf.len();
        buf.extend_from_slice(b"PACK....raw....");

        let mut r = PktLineReader::new(&buf);
        assert!(matches!(r.next_pkt().unwrap(), Some(PktLine::Data(_))));
        assert_eq!(r.next_pkt().unwrap(), Some(PktLine::Flush));
        assert_eq!(r.remaining(), &buf[pack_start..]);
    }

    #[test]
    fn rejects_truncated_and_bad_prefix() {
        // length prefix claims 0x0064 bytes but buffer is short
        assert!(PktLineReader::new(b"0064hi").next_pkt().is_err());
        // non-hex prefix
        assert!(PktLineReader::new(b"zzzzpayload").next_pkt().is_err());
        // reserved length 2
        assert!(PktLineReader::new(b"0002").next_pkt().is_err());
    }

    #[test]
    fn oversized_payload_rejected() {
        let big = vec![0u8; MAX_PAYLOAD + 1];
        assert!(data(&big).is_err());
    }
}
