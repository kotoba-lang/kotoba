use super::source_chain::ChainEntry;
use super::warrant::Warrant;

/// Gossip protocol — neighborhood-scoped (not full mesh)
/// Each node forwards validated entries to K nearest peers
pub struct GossipMessage {
    pub kind: GossipKind,
}

pub enum GossipKind {
    Entry(Box<ChainEntry>),
    Warrant(Warrant),
}

/// Gossip router (placeholder — full libp2p GossipSub integration in kotoba-net)
pub struct GossipRouter;

impl GossipRouter {
    pub fn validate_and_forward(_entry: &ChainEntry) -> Result<(), GossipError> {
        // Phase 1: signature check + seq continuity
        // Phase 2: CACAO capability chain
        // Phase 3: Prolly consistency (for Commit entries)
        Ok(())
    }
}

#[derive(Debug, thiserror::Error)]
pub enum GossipError {
    #[error("validation failed: {0}")]
    ValidationFailed(String),
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::cid::KotobaCid;
    use super::super::source_chain::{ChainContent, ChainEntry};

    fn make_entry() -> ChainEntry {
        ChainEntry::new(
            None,
            "did:example:alice".to_string(),
            0,
            ChainContent::Commit {
                graph_cid:   KotobaCid::from_bytes(b"graph"),
                prolly_root: KotobaCid::from_bytes(b"root"),
            },
            vec![0u8; 64],
        )
    }

    #[test]
    fn validate_and_forward_returns_ok() {
        let entry = make_entry();
        assert!(GossipRouter::validate_and_forward(&entry).is_ok());
    }

    #[test]
    fn gossip_error_validation_failed_display() {
        let e = GossipError::ValidationFailed("bad sig".to_string());
        assert_eq!(e.to_string(), "validation failed: bad sig");
    }

    #[test]
    fn gossip_message_entry_kind() {
        let entry = make_entry();
        let msg = GossipMessage { kind: GossipKind::Entry(Box::new(entry.clone())) };
        if let GossipKind::Entry(e) = msg.kind {
            assert_eq!(e.agent, entry.agent);
        } else {
            panic!("expected Entry kind");
        }
    }
}
