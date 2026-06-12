//! Wire format for Pregel messages exchanged between KOTOBA nodes via GossipSub.
//! Serialized as JSON for human-readability during dev; switch to CBOR in prod.

use base64::{engine::general_purpose::STANDARD as B64, Engine as _};

/// Wire format for Pregel inter-node messages.
/// Serialized as JSON for human-readability during dev; switch to CBOR in prod.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct PregelNetMessage {
    /// Source vertex ID (multibase-encoded CID)
    pub src: String,
    /// Destination vertex ID (multibase-encoded CID)
    pub dst: String,
    /// Opaque payload (base64-encoded)
    pub payload_b64: String,
}

/// GossipSub topic key for Pregel inter-node messages.
/// Passed to `KotobaSwarm::subscribe` / `publish` — the swarm prepends `kotoba/`.
pub const PREGEL_GOSSIP_TOPIC: &str = "pregel/messages";

pub const MAX_PREGEL_JSON_BYTES: usize = 256 * 1024;
pub const MAX_PREGEL_ENDPOINT_BYTES: usize = 256;
pub const MAX_PREGEL_PAYLOAD_BYTES: usize = 64 * 1024;
const MAX_PREGEL_PAYLOAD_B64_BYTES: usize = MAX_PREGEL_PAYLOAD_BYTES.div_ceil(3) * 4;

impl PregelNetMessage {
    pub fn new(
        src: impl Into<String>,
        dst: impl Into<String>,
        payload: &[u8],
    ) -> Result<Self, String> {
        if payload.len() > MAX_PREGEL_PAYLOAD_BYTES {
            return Err(format!(
                "pregel payload exceeds {MAX_PREGEL_PAYLOAD_BYTES} byte limit"
            ));
        }
        let msg = Self {
            src: src.into(),
            dst: dst.into(),
            payload_b64: B64.encode(payload),
        };
        msg.validate()?;
        Ok(msg)
    }

    pub fn to_json_vec(&self) -> Result<Vec<u8>, String> {
        self.validate()?;
        let bytes = serde_json::to_vec(self).map_err(|e| e.to_string())?;
        if bytes.len() > MAX_PREGEL_JSON_BYTES {
            return Err(format!(
                "pregel JSON exceeds {MAX_PREGEL_JSON_BYTES} byte limit"
            ));
        }
        Ok(bytes)
    }

    pub fn from_json_slice(bytes: &[u8]) -> Result<Self, String> {
        if bytes.len() > MAX_PREGEL_JSON_BYTES {
            return Err(format!(
                "pregel JSON exceeds {MAX_PREGEL_JSON_BYTES} byte limit"
            ));
        }
        let msg: Self = serde_json::from_slice(bytes).map_err(|e| e.to_string())?;
        msg.validate()?;
        Ok(msg)
    }

    pub fn payload_bytes(&self) -> Result<Vec<u8>, String> {
        if self.payload_b64.len() > MAX_PREGEL_PAYLOAD_B64_BYTES {
            return Err(format!(
                "pregel payload_b64 exceeds {MAX_PREGEL_PAYLOAD_B64_BYTES} byte limit"
            ));
        }
        let payload = B64.decode(&self.payload_b64).map_err(|e| e.to_string())?;
        if payload.len() > MAX_PREGEL_PAYLOAD_BYTES {
            return Err(format!(
                "pregel payload exceeds {MAX_PREGEL_PAYLOAD_BYTES} byte limit"
            ));
        }
        Ok(payload)
    }

    pub fn validate(&self) -> Result<(), String> {
        validate_endpoint("src", &self.src)?;
        validate_endpoint("dst", &self.dst)?;
        self.payload_bytes().map(|_| ())
    }
}

fn validate_endpoint(field: &str, value: &str) -> Result<(), String> {
    if value.is_empty() {
        return Err(format!("pregel {field} must not be empty"));
    }
    if value.len() > MAX_PREGEL_ENDPOINT_BYTES {
        return Err(format!(
            "pregel {field} exceeds {MAX_PREGEL_ENDPOINT_BYTES} byte limit"
        ));
    }
    if value.bytes().any(|b| b.is_ascii_control()) {
        return Err(format!("pregel {field} contains control byte"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pregel_gossip_topic_has_no_kotoba_prefix() {
        // The swarm prepends "kotoba/"; the constant must NOT include it.
        assert!(!PREGEL_GOSSIP_TOPIC.starts_with("kotoba/"));
        assert_eq!(PREGEL_GOSSIP_TOPIC, "pregel/messages");
    }

    #[test]
    fn pregel_net_message_json_roundtrip() {
        let msg = PregelNetMessage {
            src: "bsrc000cid".to_string(),
            dst: "bdst000cid".to_string(),
            payload_b64: "aGVsbG8=".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let back: PregelNetMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(back.src, msg.src);
        assert_eq!(back.dst, msg.dst);
        assert_eq!(back.payload_b64, msg.payload_b64);
    }

    #[test]
    fn pregel_net_message_json_field_names() {
        let msg = PregelNetMessage {
            src: "s".to_string(),
            dst: "d".to_string(),
            payload_b64: "p".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        assert!(json.contains("\"src\""));
        assert!(json.contains("\"dst\""));
        assert!(json.contains("\"payload_b64\""));
    }

    #[test]
    fn empty_src_and_dst_roundtrip() {
        let msg = PregelNetMessage {
            src: "".to_string(),
            dst: "".to_string(),
            payload_b64: "".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let back: PregelNetMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(back.src, "");
        assert_eq!(back.dst, "");
        assert_eq!(back.payload_b64, "");
    }

    #[test]
    fn large_payload_b64_roundtrip() {
        // 1 KB of 'A' characters as payload_b64
        let big = "A".repeat(1024);
        let msg = PregelNetMessage {
            src: "bsrcbig".to_string(),
            dst: "bdstbig".to_string(),
            payload_b64: big.clone(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let back: PregelNetMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(back.payload_b64, big);
    }

    #[test]
    fn wire_helper_rejects_empty_endpoint() {
        let msg = PregelNetMessage {
            src: "".to_string(),
            dst: "bdst".to_string(),
            payload_b64: "aGVsbG8=".to_string(),
        };

        let err = msg.to_json_vec().unwrap_err();
        assert!(
            err.contains("src must not be empty"),
            "error should mention src validation: {err}"
        );
    }

    #[test]
    fn wire_helper_rejects_invalid_base64() {
        let json = br#"{"src":"bsrc","dst":"bdst","payload_b64":"not base64!"}"#;

        let err = PregelNetMessage::from_json_slice(json).unwrap_err();
        assert!(
            err.contains("Invalid") || err.contains("invalid"),
            "error should mention base64 validation: {err}"
        );
    }

    #[test]
    fn wire_helper_rejects_oversized_payload() {
        let payload = vec![7u8; MAX_PREGEL_PAYLOAD_BYTES + 1];

        let err = PregelNetMessage::new("bsrc", "bdst", &payload).unwrap_err();
        assert!(
            err.contains("payload exceeds"),
            "error should mention payload cap: {err}"
        );
    }

    #[test]
    fn wire_helper_rejects_oversized_json_before_parse() {
        let bytes = vec![b' '; MAX_PREGEL_JSON_BYTES + 1];

        let err = PregelNetMessage::from_json_slice(&bytes).unwrap_err();
        assert!(
            err.contains("JSON exceeds"),
            "error should mention JSON cap: {err}"
        );
    }

    #[test]
    fn wire_helper_decodes_payload_bytes() {
        let msg = PregelNetMessage::new("bsrc", "bdst", b"hello").unwrap();
        let json = msg.to_json_vec().unwrap();
        let decoded = PregelNetMessage::from_json_slice(&json).unwrap();

        assert_eq!(decoded.payload_bytes().unwrap(), b"hello");
    }

    #[test]
    fn deserialize_from_handcrafted_json() {
        let json = r#"{"src":"bsrc1","dst":"bdst1","payload_b64":"dGVzdA=="}"#;
        let msg: PregelNetMessage = serde_json::from_str(json).unwrap();
        assert_eq!(msg.src, "bsrc1");
        assert_eq!(msg.dst, "bdst1");
        assert_eq!(msg.payload_b64, "dGVzdA==");
    }

    #[test]
    fn clone_produces_equal_message() {
        let msg = PregelNetMessage {
            src: "bclone".to_string(),
            dst: "bdst".to_string(),
            payload_b64: "cGF5bG9hZA==".to_string(),
        };
        let cloned = msg.clone();
        assert_eq!(cloned.src, msg.src);
        assert_eq!(cloned.dst, msg.dst);
        assert_eq!(cloned.payload_b64, msg.payload_b64);
    }

    // ── New tests ─────────────────────────────────────────────────────────────

    #[test]
    fn pregel_gossip_topic_is_non_empty() {
        assert!(!PREGEL_GOSSIP_TOPIC.is_empty());
    }

    #[test]
    fn pregel_gossip_topic_contains_slash() {
        // "pregel/messages" — must contain a slash as sub-topic separator.
        assert!(PREGEL_GOSSIP_TOPIC.contains('/'));
    }

    #[test]
    fn pregel_net_message_debug_contains_field_values() {
        let msg = PregelNetMessage {
            src: "bsrcdbg".to_string(),
            dst: "bdstdbg".to_string(),
            payload_b64: "payload".to_string(),
        };
        let dbg = format!("{msg:?}");
        assert!(dbg.contains("bsrcdbg"));
        assert!(dbg.contains("bdstdbg"));
        assert!(dbg.contains("payload"));
    }

    #[test]
    fn pregel_net_message_src_dst_can_be_multibase_cids() {
        // Verify realistic CID-like strings round-trip correctly.
        let msg = PregelNetMessage {
            src: "bafy2bzacexxxxxxxxxx".to_string(),
            dst: "bafy2bzaceyyyyyyyyyy".to_string(),
            payload_b64: "dGVzdA==".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let back: PregelNetMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(back.src, "bafy2bzacexxxxxxxxxx");
        assert_eq!(back.dst, "bafy2bzaceyyyyyyyyyy");
    }

    #[test]
    fn pregel_net_message_missing_field_deserialize_fails() {
        // Missing "payload_b64" field should fail deserialization.
        let json = r#"{"src":"bsrc1","dst":"bdst1"}"#;
        let result: Result<PregelNetMessage, _> = serde_json::from_str(json);
        assert!(result.is_err(), "missing payload_b64 should fail");
    }

    #[test]
    fn pregel_net_message_with_unicode_src_dst() {
        // Unicode characters in src/dst survive round-trip (JSON escaping).
        let msg = PregelNetMessage {
            src: "src_日本語".to_string(),
            dst: "dst_漢字".to_string(),
            payload_b64: "dGVzdA==".to_string(),
        };
        let json = serde_json::to_string(&msg).unwrap();
        let back: PregelNetMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(back.src, "src_日本語");
        assert_eq!(back.dst, "dst_漢字");
    }
}
