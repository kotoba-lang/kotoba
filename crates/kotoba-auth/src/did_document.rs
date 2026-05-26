use serde::{Deserialize, Serialize};

const X25519_KEY_TYPE: &str  = "X25519KeyAgreementKey2020";
const ED25519_KEY_TYPE_2020: &str = "Ed25519VerificationKey2020";
const ED25519_KEY_TYPE_2018: &str = "Ed25519VerificationKey2018";

/// DID Document — Kotoba Vertex declaration
/// capabilityInvocation key → Source Chain write right
/// capabilityDelegation key → CACAO delegation issuance
/// service[KotobaNode] → 8-bit frame endpoint (libp2p multiaddr)
/// service[KotobaGraphMembership] → Pregel Edge declaration (graph subscriptions)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DidDocument {
    #[serde(rename = "@context")]
    pub context: Vec<String>,
    pub id: String,
    #[serde(rename = "verificationMethod")]
    pub verification_method: Vec<VerificationMethod>,
    pub authentication: Vec<String>,
    #[serde(rename = "assertionMethod")]
    pub assertion_method: Vec<String>,
    #[serde(rename = "capabilityInvocation")]
    pub capability_invocation: Vec<String>,
    #[serde(rename = "capabilityDelegation")]
    pub capability_delegation: Vec<String>,
    pub service: Vec<ServiceEndpoint>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationMethod {
    pub id: String,
    #[serde(rename = "type")]
    pub key_type: String,
    pub controller: String,
    #[serde(rename = "publicKeyMultibase")]
    pub public_key_multibase: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceEndpoint {
    pub id: String,
    #[serde(rename = "type")]
    pub service_type: String,
    #[serde(rename = "serviceEndpoint")]
    pub endpoint: ServiceEndpointValue,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ServiceEndpointValue {
    Single(String),
    Multiple(Vec<String>),
}

impl DidDocument {
    pub fn kotoba_endpoint(&self) -> Option<&str> {
        self.service.iter()
            .find(|s| s.service_type == "KotobaNode")
            .and_then(|s| match &s.endpoint {
                ServiceEndpointValue::Single(u) => Some(u.as_str()),
                _ => None,
            })
    }

    pub fn graph_memberships(&self) -> Vec<&str> {
        self.service.iter()
            .find(|s| s.service_type == "KotobaGraphMembership")
            .and_then(|s| match &s.endpoint {
                ServiceEndpointValue::Multiple(v) => Some(v.iter().map(|s| s.as_str()).collect()),
                _ => None,
            })
            .unwrap_or_default()
    }

    /// Extract the X25519 key agreement public key from `verificationMethod`.
    ///
    /// Returns `None` if no `X25519KeyAgreementKey2020` entry is present or
    /// if the multibase-encoded key cannot be decoded to exactly 32 bytes.
    pub fn x25519_public_key(&self) -> Option<[u8; 32]> {
        let vm = self.verification_method
            .iter()
            .find(|vm| vm.key_type == X25519_KEY_TYPE)?;

        let (_base, raw) = multibase::decode(&vm.public_key_multibase).ok()?;
        if raw.len() != 32 {
            return None;
        }
        let mut key = [0u8; 32];
        key.copy_from_slice(&raw);
        Some(key)
    }

    /// Extract the Ed25519 verification public key from `verificationMethod`.
    ///
    /// Searches for `Ed25519VerificationKey2020` or `Ed25519VerificationKey2018`.
    /// Returns `None` if no matching entry is present or the multibase-encoded
    /// key cannot be decoded to exactly 32 bytes.
    pub fn ed25519_public_key(&self) -> Option<[u8; 32]> {
        let vm = self.verification_method.iter().find(|vm| {
            vm.key_type == ED25519_KEY_TYPE_2020 || vm.key_type == ED25519_KEY_TYPE_2018
        })?;

        let (_base, raw) = multibase::decode(&vm.public_key_multibase).ok()?;
        if raw.len() != 32 {
            return None;
        }
        let mut key = [0u8; 32];
        key.copy_from_slice(&raw);
        Some(key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_doc(id: &str) -> DidDocument {
        DidDocument {
            context:                vec!["https://www.w3.org/ns/did/v1".to_string()],
            id:                     id.to_string(),
            verification_method:    vec![],
            authentication:         vec![],
            assertion_method:       vec![],
            capability_invocation:  vec![],
            capability_delegation:  vec![],
            service:                vec![],
        }
    }

    fn with_service(mut doc: DidDocument, stype: &str, endpoint: ServiceEndpointValue) -> DidDocument {
        doc.service.push(ServiceEndpoint {
            id:           format!("{}#{}", doc.id, stype),
            service_type: stype.to_string(),
            endpoint,
        });
        doc
    }

    // ── kotoba_endpoint ───────────────────────────────────────────────────────

    #[test]
    fn kotoba_endpoint_returns_none_when_absent() {
        let doc = base_doc("did:key:zTest");
        assert!(doc.kotoba_endpoint().is_none());
    }

    #[test]
    fn kotoba_endpoint_returns_single_url() {
        let doc = with_service(
            base_doc("did:key:zTest"),
            "KotobaNode",
            ServiceEndpointValue::Single("/ip4/127.0.0.1/tcp/4001".to_string()),
        );
        assert_eq!(doc.kotoba_endpoint(), Some("/ip4/127.0.0.1/tcp/4001"));
    }

    #[test]
    fn kotoba_endpoint_returns_none_for_multiple_value() {
        let doc = with_service(
            base_doc("did:key:zTest"),
            "KotobaNode",
            ServiceEndpointValue::Multiple(vec!["/ip4/1.2.3.4/tcp/4001".to_string()]),
        );
        assert!(doc.kotoba_endpoint().is_none());
    }

    // ── graph_memberships ─────────────────────────────────────────────────────

    #[test]
    fn graph_memberships_returns_empty_when_absent() {
        assert!(base_doc("did:key:z").graph_memberships().is_empty());
    }

    #[test]
    fn graph_memberships_returns_list() {
        let doc = with_service(
            base_doc("did:key:z"),
            "KotobaGraphMembership",
            ServiceEndpointValue::Multiple(vec![
                "graph-cid-1".to_string(),
                "graph-cid-2".to_string(),
            ]),
        );
        let memberships = doc.graph_memberships();
        assert_eq!(memberships.len(), 2);
        assert!(memberships.contains(&"graph-cid-1"));
    }

    // ── key extraction ────────────────────────────────────────────────────────

    #[test]
    fn ed25519_public_key_returns_none_when_absent() {
        assert!(base_doc("did:key:z").ed25519_public_key().is_none());
    }

    #[test]
    fn x25519_public_key_returns_none_when_absent() {
        assert!(base_doc("did:key:z").x25519_public_key().is_none());
    }

    #[test]
    fn ed25519_public_key_extracted_correctly() {
        let raw_key = [0x42u8; 32];
        let encoded = multibase::encode(multibase::Base::Base58Btc, &raw_key);
        let mut doc = base_doc("did:key:z");
        doc.verification_method.push(VerificationMethod {
            id:                   "did:key:z#key-1".to_string(),
            key_type:             "Ed25519VerificationKey2020".to_string(),
            controller:           "did:key:z".to_string(),
            public_key_multibase: encoded,
        });
        let extracted = doc.ed25519_public_key().unwrap();
        assert_eq!(extracted, raw_key);
    }

    // ── JSON roundtrip ────────────────────────────────────────────────────────

    #[test]
    fn did_document_json_roundtrip() {
        let doc   = base_doc("did:key:zTestRoundtrip");
        let json  = serde_json::to_string(&doc).unwrap();
        let back: DidDocument = serde_json::from_str(&json).unwrap();
        assert_eq!(back.id, doc.id);
    }

    // ── x25519 key extraction ─────────────────────────────────────────────────

    #[test]
    fn x25519_public_key_extracted_correctly() {
        let raw_key = [0xABu8; 32];
        let encoded = multibase::encode(multibase::Base::Base58Btc, &raw_key);
        let mut doc = base_doc("did:key:zX25519");
        doc.verification_method.push(VerificationMethod {
            id:                   "did:key:zX25519#key-x25519".to_string(),
            key_type:             X25519_KEY_TYPE.to_string(),
            controller:           "did:key:zX25519".to_string(),
            public_key_multibase: encoded,
        });
        let extracted = doc.x25519_public_key().unwrap();
        assert_eq!(extracted, raw_key);
    }

    #[test]
    fn x25519_wrong_length_returns_none() {
        // Encode only 16 bytes — should fail the 32-byte length check
        let short_key = [0x01u8; 16];
        let encoded = multibase::encode(multibase::Base::Base58Btc, &short_key);
        let mut doc = base_doc("did:key:zShort");
        doc.verification_method.push(VerificationMethod {
            id:                   "did:key:zShort#key-1".to_string(),
            key_type:             X25519_KEY_TYPE.to_string(),
            controller:           "did:key:zShort".to_string(),
            public_key_multibase: encoded,
        });
        assert!(doc.x25519_public_key().is_none());
    }

    // ── Ed25519 2018 type ─────────────────────────────────────────────────────

    #[test]
    fn ed25519_2018_type_is_recognised() {
        let raw_key = [0x55u8; 32];
        let encoded = multibase::encode(multibase::Base::Base58Btc, &raw_key);
        let mut doc = base_doc("did:key:z2018");
        doc.verification_method.push(VerificationMethod {
            id:                   "did:key:z2018#key-1".to_string(),
            key_type:             ED25519_KEY_TYPE_2018.to_string(),
            controller:           "did:key:z2018".to_string(),
            public_key_multibase: encoded,
        });
        let extracted = doc.ed25519_public_key().unwrap();
        assert_eq!(extracted, raw_key);
    }

    // ── kotoba_endpoint ignores non-KotobaNode services ───────────────────────

    #[test]
    fn kotoba_endpoint_ignores_non_kotoba_node_service() {
        let mut doc = with_service(
            base_doc("did:key:zMulti"),
            "OtherService",
            ServiceEndpointValue::Single("https://other.example.com".to_string()),
        );
        doc.service.push(ServiceEndpoint {
            id:           "did:key:zMulti#kotoba".to_string(),
            service_type: "KotobaNode".to_string(),
            endpoint:     ServiceEndpointValue::Single("/ip4/10.0.0.1/tcp/4001".to_string()),
        });
        assert_eq!(doc.kotoba_endpoint(), Some("/ip4/10.0.0.1/tcp/4001"));
    }

    // ── graph_memberships with Single endpoint → empty ────────────────────────

    #[test]
    fn graph_memberships_single_endpoint_returns_empty() {
        let doc = with_service(
            base_doc("did:key:zSingle"),
            "KotobaGraphMembership",
            ServiceEndpointValue::Single("only-one".to_string()),
        );
        // Single variant is not Multiple, so memberships should be empty
        assert!(doc.graph_memberships().is_empty());
    }

    // ── malformed JSON deserialization ────────────────────────────────────────

    #[test]
    fn malformed_json_returns_error() {
        let bad_json = r#"{"id": "did:key:z", "broken json: }"#;
        let result: Result<DidDocument, _> = serde_json::from_str(bad_json);
        assert!(result.is_err(), "malformed JSON must fail to deserialize");
    }

    // ── both key types present ─────────────────────────────────────────────────

    #[test]
    fn both_key_types_present_each_extracted_independently() {
        let raw_ed  = [0x11u8; 32];
        let raw_x25 = [0x22u8; 32];
        let enc_ed  = multibase::encode(multibase::Base::Base58Btc, &raw_ed);
        let enc_x25 = multibase::encode(multibase::Base::Base58Btc, &raw_x25);

        let mut doc = base_doc("did:key:zBoth");
        doc.verification_method.push(VerificationMethod {
            id:                   "did:key:zBoth#ed".to_string(),
            key_type:             ED25519_KEY_TYPE_2020.to_string(),
            controller:           "did:key:zBoth".to_string(),
            public_key_multibase: enc_ed,
        });
        doc.verification_method.push(VerificationMethod {
            id:                   "did:key:zBoth#x25519".to_string(),
            key_type:             X25519_KEY_TYPE.to_string(),
            controller:           "did:key:zBoth".to_string(),
            public_key_multibase: enc_x25,
        });

        assert_eq!(doc.ed25519_public_key().unwrap(), raw_ed);
        assert_eq!(doc.x25519_public_key().unwrap(), raw_x25);
    }
}
