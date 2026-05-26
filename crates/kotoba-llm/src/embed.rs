use kotoba_core::cid::KotobaCid;
use kotoba_kqe::quad::{Quad, QuadObject};
use kotoba_kqe::delta::Delta;

/// Embedding — vector<f32> stored as typed QuadObject
/// dim ≤ 1024: inline in Quad.object as VectorF32
/// dim > 1024: Vault blob CID as TensorCid
pub struct Embedding {
    pub doc_cid:   KotobaCid,
    pub model_cid: KotobaCid,
    pub vector:    Vec<f32>,
}

/// Convert embedding to Datom Delta for Arrangement insertion
pub fn embed_to_quad(emb: &Embedding, graph_cid: KotobaCid) -> Delta {
    let object = if emb.vector.len() <= 1024 {
        QuadObject::VectorF32(emb.vector.clone())
    } else {
        // Large vectors → serialize to blob CID (stored in Vault separately)
        let bytes: Vec<u8> = emb.vector.iter()
            .flat_map(|f| f.to_le_bytes())
            .collect();
        let cid = KotobaCid::from_bytes(&bytes);
        QuadObject::TensorCid {
            cid,
            shape: vec![emb.vector.len() as u32],
            dtype: kotoba_kqe::quad::TensorDtype::F32,
        }
    };

    let quad = Quad {
        graph:     graph_cid,
        subject:   emb.doc_cid.clone(),
        predicate: format!("embedding/{}", emb.model_cid.to_multibase()),
        object,
    };
    Delta::assert(quad)
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_kqe::delta::Multiplicity;

    fn cid(seed: &[u8]) -> KotobaCid { KotobaCid::from_bytes(seed) }

    fn embedding(size: usize) -> Embedding {
        Embedding {
            doc_cid:   cid(b"doc"),
            model_cid: cid(b"model"),
            vector:    vec![1.0f32; size],
        }
    }

    #[test]
    fn embed_to_quad_is_assert_delta() {
        let d = embed_to_quad(&embedding(4), cid(b"g"));
        assert_eq!(d.mult, Multiplicity::Assert);
    }

    #[test]
    fn embed_to_quad_predicate_contains_model_cid() {
        let emb = embedding(4);
        let d   = embed_to_quad(&emb, cid(b"g"));
        assert!(d.quad.predicate.starts_with("embedding/"),
            "predicate should start with 'embedding/': {}", d.quad.predicate);
    }

    #[test]
    fn embed_to_quad_small_vector_is_inline() {
        let d = embed_to_quad(&embedding(10), cid(b"g"));
        assert!(matches!(d.quad.object, QuadObject::VectorF32(_)),
            "small vector (≤1024) should be inline VectorF32");
    }

    #[test]
    fn embed_to_quad_exactly_1024_is_inline() {
        let d = embed_to_quad(&embedding(1024), cid(b"g"));
        assert!(matches!(d.quad.object, QuadObject::VectorF32(_)),
            "exactly 1024 dims should be inline");
    }

    #[test]
    fn embed_to_quad_large_vector_is_tensor_cid() {
        let d = embed_to_quad(&embedding(1025), cid(b"g"));
        assert!(matches!(d.quad.object, QuadObject::TensorCid { .. }),
            "vector > 1024 dims should be TensorCid");
    }

    #[test]
    fn embed_to_quad_subject_is_doc_cid() {
        let emb = embedding(5);
        let d   = embed_to_quad(&emb, cid(b"g"));
        assert_eq!(d.quad.subject, emb.doc_cid);
    }

    #[test]
    fn embed_to_quad_large_shape_is_vector_len() {
        let emb = embedding(2048);
        let d   = embed_to_quad(&emb, cid(b"g"));
        if let QuadObject::TensorCid { shape, .. } = d.quad.object {
            assert_eq!(shape, vec![2048u32]);
        } else {
            panic!("expected TensorCid");
        }
    }
}
