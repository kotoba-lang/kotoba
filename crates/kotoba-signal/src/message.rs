/// Application-layer message schema: thread, reply, reaction.
use serde::{Deserialize, Serialize};

pub const SIGNAL_CONTENT_TYPE: &str = "application/x-signal-envelope";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum MessageType {
    /// 1:1 Double Ratchet message.
    DirectMessage,
    /// Group Sender Key message.
    GroupMessage,
    /// Delivery receipt.
    Receipt,
}

/// Wire-format message envelope for `ai.gftd.signal.sendMessage`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalMessage {
    pub message_type:   MessageType,
    pub sender_did:     String,
    pub recipient_did:  String,
    pub device_id:      String,
    /// Optional group ID for GroupMessage.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group_id:       Option<String>,
    /// Serialised `RatchetMessage` or `SenderKeyMessage` (JSON).
    pub ciphertext_envelope: String,
    /// RFC 3339 timestamp.
    pub timestamp:      String,
    /// For initial X3DH messages: sender's ephemeral public key (base64url).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ephemeral_key:  Option<String>,
    /// For initial X3DH messages: consumed one-time pre-key ID.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub one_time_prekey_id: Option<u32>,
}

/// Application-level thread message (plaintext, nested inside ciphertext_envelope).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ThreadMessage {
    /// Message ID (CID or UUID).
    pub id:          String,
    pub sender_did:  String,
    pub text:        String,
    /// Reply-to message ID.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reply_to:    Option<String>,
    /// Inline reactions at creation time.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub reactions:   Vec<Reaction>,
    pub timestamp:   String,
}

/// Emoji reaction.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Reaction {
    pub sender_did: String,
    pub emoji:      String,
    pub message_id: String,
}

/// Delivery / read receipt.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeliveryReceipt {
    pub message_ids: Vec<String>,
    pub status:      ReceiptStatus,
    pub timestamp:   String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ReceiptStatus {
    Delivered,
    Read,
}
