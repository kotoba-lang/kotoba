//! DIDComm v2 message envelope model for Kotoba.
//!
//! The crate intentionally models the plaintext envelope and storage
//! projection.  Encryption/packing can sit above this boundary while Datom
//! remains the internal SSoT.

use kotoba_core::cid::KotobaCid;
use kotoba_datomic::Datom;
use kotoba_edn::EdnValue;
use serde::{Deserialize, Serialize};

pub const DIDCOMM_MESSAGING_SERVICE: &str = "DIDCommMessaging";

pub const ATTR_DIDCOMM_ID: &str = "didcomm/id";
pub const ATTR_DIDCOMM_CID: &str = "didcomm/cid";
pub const ATTR_DIDCOMM_PROTOCOL: &str = "didcomm/protocol";
pub const ATTR_DIDCOMM_SERVICE_TYPE: &str = "didcomm/serviceType";
pub const ATTR_DIDCOMM_WIRE_FORMAT: &str = "didcomm/wireFormat";
pub const ATTR_DIDCOMM_TYPE: &str = "didcomm/type";
pub const ATTR_DIDCOMM_FROM: &str = "didcomm/from";
pub const ATTR_DIDCOMM_FROM_CID: &str = "didcomm/fromCid";
pub const ATTR_DIDCOMM_TO: &str = "didcomm/to";
pub const ATTR_DIDCOMM_TO_CID: &str = "didcomm/toCid";
pub const ATTR_DIDCOMM_THREAD: &str = "didcomm/thread";
pub const ATTR_DIDCOMM_THREAD_SCOPE: &str = "didcomm/threadScope";
pub const ATTR_DIDCOMM_PARENT_THREAD: &str = "didcomm/parentThread";
pub const ATTR_DIDCOMM_CREATED_TIME: &str = "didcomm/createdTime";
pub const ATTR_DIDCOMM_EXPIRES_TIME: &str = "didcomm/expiresTime";
pub const ATTR_DIDCOMM_BODY: &str = "didcomm/body";
pub const ATTR_DIDCOMM_BODY_FIELD_PREFIX: &str = "didcomm/body/";
pub const ATTR_DIDCOMM_ATTACHMENT: &str = "didcomm/attachment";
pub const ATTR_DIDCOMM_ATTACHMENT_CID: &str = "didcomm/attachmentCid";
pub const ATTR_DIDCOMM_ATTACHMENT_MESSAGE_CID: &str = "didcomm/attachment/messageCid";
pub const ATTR_DIDCOMM_ATTACHMENT_ID: &str = "didcomm/attachment/id";
pub const ATTR_DIDCOMM_ATTACHMENT_DESCRIPTION: &str = "didcomm/attachment/description";
pub const ATTR_DIDCOMM_ATTACHMENT_MEDIA_TYPE: &str = "didcomm/attachment/mediaType";
pub const ATTR_DIDCOMM_ATTACHMENT_DATA: &str = "didcomm/attachment/data";
pub const ATTR_DIDCOMM_WIRE_ID: &str = "id";
pub const ATTR_DIDCOMM_WIRE_TYPE: &str = "type";
pub const ATTR_DIDCOMM_WIRE_FROM: &str = "from";
pub const ATTR_DIDCOMM_WIRE_TO: &str = "to";
pub const ATTR_DIDCOMM_WIRE_THREAD: &str = "thid";
pub const ATTR_DIDCOMM_WIRE_PARENT_THREAD: &str = "pthid";
pub const ATTR_DIDCOMM_WIRE_CREATED_TIME: &str = "created_time";
pub const ATTR_DIDCOMM_WIRE_EXPIRES_TIME: &str = "expires_time";
pub const ATTR_DIDCOMM_WIRE_BODY: &str = "body";
pub const ATTR_DIDCOMM_WIRE_ATTACHMENT: &str = "attachments";

#[derive(Debug, thiserror::Error)]
pub enum DidCommError {
    #[error("json encode: {0}")]
    Json(String),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Attachment {
    pub id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub media_type: Option<String>,
    pub data: serde_json::Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DidCommMessage {
    pub id: String,
    #[serde(rename = "type")]
    pub message_type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub from: Option<String>,
    #[serde(default)]
    pub to: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub thid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pthid: Option<String>,
    #[serde(
        rename = "created_time",
        default,
        skip_serializing_if = "Option::is_none"
    )]
    pub created_time: Option<u64>,
    #[serde(
        rename = "expires_time",
        default,
        skip_serializing_if = "Option::is_none"
    )]
    pub expires_time: Option<u64>,
    #[serde(default)]
    pub body: serde_json::Value,
    #[serde(default)]
    pub attachments: Vec<Attachment>,
}

impl DidCommMessage {
    pub fn cid(&self) -> Result<KotobaCid, DidCommError> {
        let bytes = serde_json::to_vec(self).map_err(|e| DidCommError::Json(e.to_string()))?;
        Ok(KotobaCid::from_bytes(&bytes))
    }

    pub fn thread_id(&self) -> &str {
        self.thid.as_deref().unwrap_or(&self.id)
    }

    pub fn thread_scope(&self) -> String {
        format!("didcomm://thread/{}", self.thread_id())
    }

    pub fn to_datoms(&self, tx: KotobaCid) -> Result<Vec<Datom>, DidCommError> {
        let e = self.cid()?;
        let thread_scope = self.thread_scope();
        let mut out = vec![
            datom(&e, ATTR_DIDCOMM_ID, EdnValue::string(&self.id), &tx),
            datom(
                &e,
                ATTR_DIDCOMM_CID,
                EdnValue::string(e.to_multibase()),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_PROTOCOL,
                EdnValue::string("DIDComm v2"),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_SERVICE_TYPE,
                EdnValue::string(DIDCOMM_MESSAGING_SERVICE),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_WIRE_FORMAT,
                EdnValue::string("application/didcomm-plain+json"),
                &tx,
            ),
            datom(&e, ATTR_DIDCOMM_WIRE_ID, EdnValue::string(&self.id), &tx),
            datom(
                &e,
                ATTR_DIDCOMM_TYPE,
                EdnValue::string(&self.message_type),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_WIRE_TYPE,
                EdnValue::string(&self.message_type),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_THREAD,
                EdnValue::string(self.thread_id()),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_THREAD_SCOPE,
                EdnValue::string(&thread_scope),
                &tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_WIRE_THREAD,
                EdnValue::string(self.thread_id()),
                &tx,
            ),
            datom(&e, ATTR_DIDCOMM_TO, string_vec(&self.to), &tx),
            datom(&e, ATTR_DIDCOMM_WIRE_TO, string_vec(&self.to), &tx),
            datom(&e, ATTR_DIDCOMM_BODY, json_to_edn(&self.body), &tx),
            datom(&e, ATTR_DIDCOMM_WIRE_BODY, json_to_edn(&self.body), &tx),
        ];
        for to in &self.to {
            out.push(datom(
                &e,
                ATTR_DIDCOMM_TO_CID,
                EdnValue::string(did_derived_cid(to).to_multibase()),
                &tx,
            ));
        }
        append_json_field_datoms(
            &mut out,
            &e,
            ATTR_DIDCOMM_BODY_FIELD_PREFIX,
            &self.body,
            &tx,
        );
        if let Some(from) = &self.from {
            out.push(datom(&e, ATTR_DIDCOMM_FROM, EdnValue::string(from), &tx));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_FROM_CID,
                EdnValue::string(did_derived_cid(from).to_multibase()),
                &tx,
            ));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_WIRE_FROM,
                EdnValue::string(from),
                &tx,
            ));
        }
        if let Some(pthid) = &self.pthid {
            out.push(datom(
                &e,
                ATTR_DIDCOMM_PARENT_THREAD,
                EdnValue::string(pthid),
                &tx,
            ));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_WIRE_PARENT_THREAD,
                EdnValue::string(pthid),
                &tx,
            ));
        }
        if let Some(created_time) = self.created_time {
            out.push(datom(
                &e,
                ATTR_DIDCOMM_CREATED_TIME,
                EdnValue::Integer(created_time as i64),
                &tx,
            ));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_WIRE_CREATED_TIME,
                EdnValue::Integer(created_time as i64),
                &tx,
            ));
        }
        if let Some(expires_time) = self.expires_time {
            out.push(datom(
                &e,
                ATTR_DIDCOMM_EXPIRES_TIME,
                EdnValue::Integer(expires_time as i64),
                &tx,
            ));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_WIRE_EXPIRES_TIME,
                EdnValue::Integer(expires_time as i64),
                &tx,
            ));
        }
        for attachment in &self.attachments {
            let attachment_cid = attachment.cid()?;
            out.push(datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_CID,
                EdnValue::string(attachment_cid.to_multibase()),
                &tx,
            ));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT,
                attachment_to_edn(attachment),
                &tx,
            ));
            out.push(datom(
                &e,
                ATTR_DIDCOMM_WIRE_ATTACHMENT,
                attachment_to_edn(attachment),
                &tx,
            ));
            out.extend(attachment.to_datoms(&e, &tx)?);
        }
        out.push(datom(&e, &self.message_type, json_to_edn(&self.body), &tx));
        Ok(out)
    }
}

impl Attachment {
    pub fn cid(&self) -> Result<KotobaCid, DidCommError> {
        let bytes = serde_json::to_vec(self).map_err(|e| DidCommError::Json(e.to_string()))?;
        Ok(KotobaCid::from_bytes(&bytes))
    }

    pub fn to_datoms(
        &self,
        message_cid: &KotobaCid,
        tx: &KotobaCid,
    ) -> Result<Vec<Datom>, DidCommError> {
        let e = self.cid()?;
        let mut out = vec![
            datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_CID,
                EdnValue::string(e.to_multibase()),
                tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_MESSAGE_CID,
                EdnValue::string(message_cid.to_multibase()),
                tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_ID,
                EdnValue::string(&self.id),
                tx,
            ),
            datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_DATA,
                json_to_edn(&self.data),
                tx,
            ),
        ];
        if let Some(description) = &self.description {
            out.push(datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_DESCRIPTION,
                EdnValue::string(description),
                tx,
            ));
        }
        if let Some(media_type) = &self.media_type {
            out.push(datom(
                &e,
                ATTR_DIDCOMM_ATTACHMENT_MEDIA_TYPE,
                EdnValue::string(media_type),
                tx,
            ));
        }
        Ok(out)
    }
}

fn datom(e: &KotobaCid, a: &str, v: EdnValue, tx: &KotobaCid) -> Datom {
    Datom::assert(e.clone(), a.to_string(), v, tx.clone())
}

fn did_derived_cid(did: &str) -> KotobaCid {
    KotobaCid::from_bytes(did.as_bytes())
}

fn string_vec(xs: &[String]) -> EdnValue {
    EdnValue::vector(xs.iter().cloned().map(EdnValue::string))
}

fn append_json_field_datoms(
    out: &mut Vec<Datom>,
    e: &KotobaCid,
    attr_prefix: &str,
    value: &serde_json::Value,
    tx: &KotobaCid,
) {
    let Some(obj) = value.as_object() else {
        return;
    };
    for (key, value) in obj {
        let attr = format!("{attr_prefix}{key}");
        out.push(datom(e, &attr, json_to_edn(value), tx));
        append_json_field_datoms(out, e, &format!("{attr}/"), value, tx);
    }
}

fn attachment_to_edn(attachment: &Attachment) -> EdnValue {
    let mut fields = vec![
        (EdnValue::kw_bare("id"), EdnValue::string(&attachment.id)),
        (EdnValue::kw_bare("data"), json_to_edn(&attachment.data)),
    ];
    if let Some(description) = &attachment.description {
        fields.push((
            EdnValue::kw_bare("description"),
            EdnValue::string(description),
        ));
    }
    if let Some(media_type) = &attachment.media_type {
        fields.push((
            EdnValue::kw_bare("media_type"),
            EdnValue::string(media_type),
        ));
    }
    EdnValue::map(fields)
}

fn json_to_edn(value: &serde_json::Value) -> EdnValue {
    match value {
        serde_json::Value::Null => EdnValue::Nil,
        serde_json::Value::Bool(b) => EdnValue::Bool(*b),
        serde_json::Value::Number(n) => n
            .as_i64()
            .map(EdnValue::Integer)
            .or_else(|| n.as_f64().map(EdnValue::float))
            .unwrap_or_else(|| EdnValue::string(n.to_string())),
        serde_json::Value::String(s) => EdnValue::string(s),
        serde_json::Value::Array(xs) => EdnValue::vector(xs.iter().map(json_to_edn)),
        serde_json::Value::Object(obj) => EdnValue::Map(
            obj.iter()
                .map(|(k, v)| (EdnValue::kw_bare(k), json_to_edn(v)))
                .collect(),
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn didcomm_message_projects_to_datoms() {
        let msg = DidCommMessage {
            id: "msg-1".into(),
            message_type: "https://didcomm.org/basicmessage/2.0/message".into(),
            from: Some("did:key:zAlice".into()),
            to: vec!["did:key:zBob".into()],
            thid: Some("thread-1".into()),
            pthid: None,
            created_time: Some(1),
            expires_time: None,
            body: json!({"content": "hello", "meta": {"lang": "en"}, "tags": ["chat"]}),
            attachments: vec![Attachment {
                id: "att-1".into(),
                description: Some("profile".into()),
                media_type: Some("application/json".into()),
                data: json!({"json": {"name": "Alice"}}),
            }],
        };
        let datoms = msg.to_datoms(KotobaCid::from_bytes(b"tx")).unwrap();
        let e = msg.cid().unwrap();
        let attachment_cid = msg.attachments[0].cid().unwrap();
        assert!(datoms
            .iter()
            .any(|d| d.a == ATTR_DIDCOMM_CID && d.v == EdnValue::string(e.to_multibase())));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_TYPE));
        assert!(datoms
            .iter()
            .any(|d| d.a == ATTR_DIDCOMM_PROTOCOL && d.v == EdnValue::string("DIDComm v2")));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_SERVICE_TYPE
            && d.v == EdnValue::string(DIDCOMM_MESSAGING_SERVICE)));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_WIRE_FORMAT
            && d.v == EdnValue::string("application/didcomm-plain+json")));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_FROM_CID
            && d.v == EdnValue::string(KotobaCid::from_bytes(b"did:key:zAlice").to_multibase())));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_TO_CID
            && d.v == EdnValue::string(KotobaCid::from_bytes(b"did:key:zBob").to_multibase())));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_THREAD));
        assert!(datoms.iter().any(|d| {
            d.a == ATTR_DIDCOMM_THREAD_SCOPE && d.v == EdnValue::string("didcomm://thread/thread-1")
        }));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_BODY));
        assert!(datoms.iter().any(|d| d.a == ATTR_DIDCOMM_WIRE_TYPE));
        assert!(datoms
            .iter()
            .any(|d| d.a == ATTR_DIDCOMM_WIRE_THREAD && d.v == EdnValue::string("thread-1")));
        let body_edn = datoms
            .iter()
            .find(|d| d.a == ATTR_DIDCOMM_BODY)
            .map(|d| kotoba_edn::to_string(&d.v))
            .unwrap();
        assert!(body_edn.contains(":meta {:lang \"en\""));
        assert!(body_edn.contains(":tags [\"chat\"]"));
        assert!(datoms
            .iter()
            .any(|d| d.a == "didcomm/body/content" && d.v == EdnValue::string("hello")));
        assert!(datoms
            .iter()
            .any(|d| d.a == "didcomm/body/meta"
                && kotoba_edn::to_string(&d.v).contains(":lang \"en\"")));
        assert!(datoms
            .iter()
            .any(|d| d.a == "didcomm/body/meta/lang" && d.v == EdnValue::string("en")));
        assert!(datoms
            .iter()
            .any(|d| d.a == "didcomm/body/tags"
                && kotoba_edn::to_string(&d.v).contains("[\"chat\"]")));
        assert!(datoms.iter().any(|d| {
            d.e == e
                && d.a == ATTR_DIDCOMM_ATTACHMENT_CID
                && d.v == EdnValue::string(attachment_cid.to_multibase())
        }));
        assert!(datoms.iter().any(|d| {
            d.e == attachment_cid
                && d.a == ATTR_DIDCOMM_ATTACHMENT_MESSAGE_CID
                && d.v == EdnValue::string(e.to_multibase())
        }));
        assert!(datoms.iter().any(|d| {
            d.e == attachment_cid
                && d.a == ATTR_DIDCOMM_ATTACHMENT_ID
                && d.v == EdnValue::string("att-1")
        }));
        assert!(datoms.iter().any(|d| {
            d.e == attachment_cid
                && d.a == ATTR_DIDCOMM_ATTACHMENT_DESCRIPTION
                && d.v == EdnValue::string("profile")
        }));
        assert!(datoms.iter().any(|d| {
            d.e == attachment_cid
                && d.a == ATTR_DIDCOMM_ATTACHMENT_MEDIA_TYPE
                && d.v == EdnValue::string("application/json")
        }));
        assert!(datoms.iter().any(|d| {
            d.e == attachment_cid
                && d.a == ATTR_DIDCOMM_ATTACHMENT_DATA
                && kotoba_edn::to_string(&d.v).contains(":json {:name \"Alice\"")
        }));
        let attachment_edn = datoms
            .iter()
            .find(|d| d.a == ATTR_DIDCOMM_ATTACHMENT)
            .map(|d| kotoba_edn::to_string(&d.v))
            .unwrap();
        assert!(attachment_edn.contains(":description \"profile\""));
        assert!(attachment_edn.contains(":media_type \"application/json\""));
        assert!(attachment_edn.contains(":json {:name \"Alice\""));
        assert!(datoms
            .iter()
            .any(|d| d.a == "https://didcomm.org/basicmessage/2.0/message"));
    }

    fn msg(id: &str, thid: Option<&str>) -> DidCommMessage {
        DidCommMessage {
            id: id.into(),
            message_type: "https://didcomm.org/basicmessage/2.0/message".into(),
            from: None,
            to: vec![],
            thid: thid.map(Into::into),
            pthid: None,
            created_time: None,
            expires_time: None,
            body: json!({}),
            attachments: vec![],
        }
    }

    #[test]
    fn thread_id_and_scope_group_a_conversation() {
        // DIDComm threading: a thread-starter has no `thid`, so its thread IS its
        // own id; a reply carries `thid` = the thread root. thread_scope() is what
        // groups a conversation, so a bug here (returning own id for a reply, or
        // mismatched scopes) would scatter messages that belong together.
        let root = msg("msg-root", None);
        assert_eq!(
            root.thread_id(),
            "msg-root",
            "a starter's thread is its own id"
        );
        assert_eq!(root.thread_scope(), "didcomm://thread/msg-root");

        let reply = msg("msg-reply-1", Some("msg-root"));
        assert_eq!(
            reply.thread_id(),
            "msg-root",
            "a reply joins its thread, not its own id"
        );
        assert_eq!(
            reply.thread_scope(),
            root.thread_scope(),
            "a reply must share the root's thread scope"
        );

        // A second reply groups into the same conversation …
        let reply2 = msg("msg-reply-2", Some("msg-root"));
        assert_eq!(reply2.thread_scope(), root.thread_scope());
        // … yet remains a distinct content-addressed message.
        assert_ne!(
            reply.cid().unwrap(),
            reply2.cid().unwrap(),
            "distinct messages must have distinct CIDs"
        );
    }

    #[test]
    fn cid_is_deterministic_and_field_sensitive() {
        // The message CID is its content-addressed identity: stable for identical
        // content, and changing any field changes it (so a tampered/edited message
        // can never masquerade as the original).
        let a = msg("m", Some("t"));
        assert_eq!(
            a.cid().unwrap(),
            a.cid().unwrap(),
            "cid must be deterministic"
        );
        let mut b = a.clone();
        b.id = "m2".into();
        assert_ne!(
            a.cid().unwrap(),
            b.cid().unwrap(),
            "changing id changes the cid"
        );
        let mut c = a.clone();
        c.body = json!({"x": 1});
        assert_ne!(
            a.cid().unwrap(),
            c.cid().unwrap(),
            "changing body changes the cid"
        );
    }
}
