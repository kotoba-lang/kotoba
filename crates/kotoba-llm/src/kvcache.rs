use kotoba_core::cid::KotobaCid;
use kotoba_kqe::arrangement::Arrangement;
use kotoba_kqe::quad::{Quad, QuadObject};
use kotoba_kqe::delta::Delta;

/// KvCache — attention KV-cache as ephemeral Arrangement
/// session_cid = blake3(CBOR{model_cid, prompt_hash, ts})
/// Each KV pair = Datom: Quad(session, "kv/layer/N/seq/M", kv_tensor_cid)
/// Pregel: KV-cache = vertex state during inference supersteps
pub struct KvCache {
    pub session_cid: KotobaCid,
    pub arrangement: Arrangement,
}

impl KvCache {
    pub fn new(session_cid: KotobaCid) -> Self {
        Self { session_cid, arrangement: Arrangement::new() }
    }

    /// Store KV pair for layer N, sequence position M
    pub fn store_kv(&mut self, graph_cid: KotobaCid, layer: u32, seq: u32, kv_cid: KotobaCid) -> Delta {
        let quad = Quad {
            graph:     graph_cid,
            subject:   self.session_cid.clone(),
            predicate: format!("kv/layer/{layer}/seq/{seq}"),
            object:    QuadObject::Cid(kv_cid),
        };
        self.arrangement.insert(&quad);
        Delta::assert(quad)
    }

    /// Clear cache (Vote to Halt → TTL GC)
    pub fn clear(&mut self) { self.arrangement = Arrangement::new(); }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_kqe::delta::Multiplicity;

    fn make_cache() -> KvCache {
        KvCache::new(KotobaCid::from_bytes(b"session"))
    }

    #[test]
    fn store_kv_returns_assert_delta() {
        let mut cache  = make_cache();
        let graph_cid  = KotobaCid::from_bytes(b"graph");
        let kv_cid     = KotobaCid::from_bytes(b"kv");
        let delta = cache.store_kv(graph_cid, 0, 0, kv_cid);
        assert_eq!(delta.mult, Multiplicity::Assert);
    }

    #[test]
    fn store_kv_predicate_encodes_layer_seq() {
        let mut cache = make_cache();
        let delta = cache.store_kv(
            KotobaCid::from_bytes(b"g"), 3, 7, KotobaCid::from_bytes(b"kv"),
        );
        assert_eq!(delta.quad.predicate, "kv/layer/3/seq/7");
    }

    #[test]
    fn store_kv_subject_is_session_cid() {
        let mut cache = make_cache();
        let delta = cache.store_kv(
            KotobaCid::from_bytes(b"g"), 0, 0, KotobaCid::from_bytes(b"kv"),
        );
        assert_eq!(delta.quad.subject, cache.session_cid);
    }

    #[test]
    fn store_kv_object_is_cid() {
        let kv_cid    = KotobaCid::from_bytes(b"kv-blob");
        let mut cache = make_cache();
        let delta = cache.store_kv(KotobaCid::from_bytes(b"g"), 1, 2, kv_cid.clone());
        if let QuadObject::Cid(c) = delta.quad.object {
            assert_eq!(c, kv_cid);
        } else {
            panic!("expected Cid object");
        }
    }

    #[test]
    fn store_kv_inserts_into_arrangement() {
        let mut cache = make_cache();
        let graph_cid = KotobaCid::from_bytes(b"g");
        cache.store_kv(graph_cid.clone(), 0, 5, KotobaCid::from_bytes(b"kv"));
        let quads = cache.arrangement.get_by_predicate("kv/layer/0/seq/5");
        assert!(!quads.is_empty(), "arrangement should have the stored KV entry");
    }

    #[test]
    fn clear_empties_arrangement() {
        let mut cache = make_cache();
        let graph_cid = KotobaCid::from_bytes(b"g");
        cache.store_kv(graph_cid.clone(), 0, 0, KotobaCid::from_bytes(b"kv"));
        cache.clear();
        let quads = cache.arrangement.get_by_predicate("kv/layer/0/seq/0");
        assert!(quads.is_empty(), "arrangement should be empty after clear");
    }
}
