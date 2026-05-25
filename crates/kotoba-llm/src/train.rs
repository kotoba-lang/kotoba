/// Training pipeline types: TrainBatch, GradientRef, AdamMoments, OptimizerStep.
///
/// Datom encoding (ADR-2605250004):
///   grad  → Quad(model_cid, "grad/layer/{N}/step/{M}",    TensorCid{f32})  — ephemeral
///   adam  → Quad(model_cid, "train/adam/m1/layer/{N}",    TensorCid{f32})  — persistent
///   adam  → Quad(model_cid, "train/adam/m2/layer/{N}",    TensorCid{f32})  — persistent
///   weight update: retract(old) + assert(new) — atomic pair
use kotoba_core::cid::KotobaCid;
use kotoba_kqe::quad::{Quad, QuadObject, TensorDtype};
use kotoba_kqe::delta::Delta;

/// A training mini-batch: token sequences with a quality score.
///
/// `quality` ∈ [0.0, 1.0] scales the CE loss gradient so low-quality
/// data has proportionally less influence on weight updates.
#[derive(Debug, Clone)]
pub struct TrainBatch {
    /// Input token IDs — shape `[seq_len]`
    pub input_tokens:  Vec<u32>,
    /// Target token IDs — shape `[seq_len]`
    pub target_tokens: Vec<u32>,
    /// Curation quality score: 1.0 = gold data, 0.0 = skip
    pub quality:       f32,
}

/// CID-addressed gradient tensor stored as a Datom (ephemeral).
///
/// Gradient tensors are f32 (WebGPU native) and are retracted from
/// the Arrangement immediately after the optimizer step completes.
#[derive(Debug, Clone)]
pub struct GradientRef {
    pub model_cid: KotobaCid,
    /// Layer index (0 = embedding, 1 = LM head in the 2-layer scope)
    pub layer:     u32,
    /// Optimizer step counter — used as part of the predicate to avoid
    /// CID collisions when multiple steps are in flight
    pub step:      u64,
    pub blob_cid:  KotobaCid,
    pub shape:     Vec<u32>,
}

impl GradientRef {
    /// Assert gradient into Arrangement.
    pub fn to_assert_delta(&self, graph_cid: KotobaCid) -> Delta {
        Delta::assert(self.quad(graph_cid))
    }

    /// Retract gradient from Arrangement (call after optimizer step).
    pub fn to_retract_delta(&self, graph_cid: KotobaCid) -> Delta {
        Delta::retract(self.quad(graph_cid))
    }

    fn quad(&self, graph_cid: KotobaCid) -> Quad {
        Quad {
            graph:     graph_cid,
            subject:   self.model_cid.clone(),
            predicate: format!("grad/layer/{}/step/{}", self.layer, self.step),
            object:    QuadObject::TensorCid {
                cid:   self.blob_cid.clone(),
                shape: self.shape.clone(),
                dtype: TensorDtype::F32,
            },
        }
    }
}

/// AdamW first and second moment tensors for one layer (persistent).
#[derive(Debug, Clone)]
pub struct AdamMoments {
    pub model_cid: KotobaCid,
    pub layer:     u32,
    /// First moment (mean of gradients) — f32
    pub m1_cid:    KotobaCid,
    /// Second moment (uncentered variance) — f32
    pub m2_cid:    KotobaCid,
    pub shape:     Vec<u32>,
}

impl AdamMoments {
    /// Assert both moment tensors.
    pub fn to_assert_deltas(&self, graph_cid: KotobaCid) -> [Delta; 2] {
        [
            Delta::assert(self.m1_quad(graph_cid.clone())),
            Delta::assert(self.m2_quad(graph_cid)),
        ]
    }

    /// Retract both moment tensors (before replacing with updated moments).
    pub fn to_retract_deltas(&self, graph_cid: KotobaCid) -> [Delta; 2] {
        [
            Delta::retract(self.m1_quad(graph_cid.clone())),
            Delta::retract(self.m2_quad(graph_cid)),
        ]
    }

    fn m1_quad(&self, graph_cid: KotobaCid) -> Quad {
        Quad {
            graph:     graph_cid,
            subject:   self.model_cid.clone(),
            predicate: format!("train/adam/m1/layer/{}", self.layer),
            object:    QuadObject::TensorCid {
                cid:   self.m1_cid.clone(),
                shape: self.shape.clone(),
                dtype: TensorDtype::F32,
            },
        }
    }

    fn m2_quad(&self, graph_cid: KotobaCid) -> Quad {
        Quad {
            graph:     graph_cid,
            subject:   self.model_cid.clone(),
            predicate: format!("train/adam/m2/layer/{}", self.layer),
            object:    QuadObject::TensorCid {
                cid:   self.m2_cid.clone(),
                shape: self.shape.clone(),
                dtype: TensorDtype::F32,
            },
        }
    }
}

/// One complete optimizer step: old weight out, new weight in.
///
/// Produces an atomic Delta pair: retract(old) + assert(new).
/// The caller applies both to the Arrangement / Journal in sequence.
#[derive(Debug, Clone)]
pub struct OptimizerStep {
    pub model_cid:      KotobaCid,
    pub layer:          u32,
    /// Previous weight (to be retracted)
    pub old_weight_cid: KotobaCid,
    /// Updated weight (to be asserted, stored in Vault as FP8)
    pub new_weight_cid: KotobaCid,
    pub shape:          Vec<u32>,
    /// AdamW step count (bias-correction denominator: sqrt(1-β2^t)/(1-β1^t))
    pub step:           u64,
}

impl OptimizerStep {
    /// Atomic weight-swap Delta pair: [retract_old, assert_new].
    pub fn weight_deltas(&self, graph_cid: KotobaCid) -> [Delta; 2] {
        let old_quad = Quad {
            graph:     graph_cid.clone(),
            subject:   self.model_cid.clone(),
            predicate: format!("weight/layer/{}", self.layer),
            object:    QuadObject::TensorCid {
                cid:   self.old_weight_cid.clone(),
                shape: self.shape.clone(),
                dtype: TensorDtype::F8E4M3,
            },
        };
        let new_quad = Quad {
            graph:     graph_cid,
            subject:   self.model_cid.clone(),
            predicate: format!("weight/layer/{}", self.layer),
            object:    QuadObject::TensorCid {
                cid:   self.new_weight_cid.clone(),
                shape: self.shape.clone(),
                dtype: TensorDtype::F8E4M3,
            },
        };
        [Delta::retract(old_quad), Delta::assert(new_quad)]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::cid::KotobaCid;
    use kotoba_kqe::delta::Multiplicity;
    use kotoba_kqe::quad::QuadObject;

    fn cid(s: &[u8]) -> KotobaCid { KotobaCid::from_bytes(s) }
    fn g() -> KotobaCid { cid(b"graph") }

    #[test]
    fn gradient_ref_assert_retract_roundtrip() {
        let gr = GradientRef {
            model_cid: cid(b"model"),
            layer: 0,
            step: 1,
            blob_cid: cid(b"grad_blob"),
            shape: vec![32000, 2048],
        };
        let assert_d  = gr.to_assert_delta(g());
        let retract_d = gr.to_retract_delta(g());

        assert_eq!(assert_d.mult,  Multiplicity::Assert);
        assert_eq!(retract_d.mult, Multiplicity::Retract);
        assert_eq!(assert_d.quad.predicate,  "grad/layer/0/step/1");
        assert_eq!(retract_d.quad.predicate, "grad/layer/0/step/1");
        assert!(matches!(assert_d.quad.object, QuadObject::TensorCid { dtype: TensorDtype::F32, .. }));
    }

    #[test]
    fn adam_moments_assert_retract() {
        let m = AdamMoments {
            model_cid: cid(b"model"),
            layer: 1,
            m1_cid: cid(b"m1"),
            m2_cid: cid(b"m2"),
            shape: vec![2048, 32000],
        };
        let [a1, a2] = m.to_assert_deltas(g());
        let [r1, r2] = m.to_retract_deltas(g());

        assert_eq!(a1.mult, Multiplicity::Assert);
        assert_eq!(r1.mult, Multiplicity::Retract);
        assert_eq!(a1.quad.predicate, "train/adam/m1/layer/1");
        assert_eq!(a2.quad.predicate, "train/adam/m2/layer/1");
        assert_eq!(r1.quad.predicate, "train/adam/m1/layer/1");
        assert_eq!(r2.quad.predicate, "train/adam/m2/layer/1");
    }

    #[test]
    fn optimizer_step_weight_deltas_are_retract_then_assert() {
        let step = OptimizerStep {
            model_cid: cid(b"model"),
            layer: 0,
            old_weight_cid: cid(b"w_old"),
            new_weight_cid: cid(b"w_new"),
            shape: vec![32000, 2048],
            step: 5,
        };
        let [retract, assert_d] = step.weight_deltas(g());
        assert_eq!(retract.mult,  Multiplicity::Retract);
        assert_eq!(assert_d.mult, Multiplicity::Assert);
        assert_eq!(retract.quad.predicate,  "weight/layer/0");
        assert_eq!(assert_d.quad.predicate, "weight/layer/0");
        // old CID in retract, new CID in assert
        if let QuadObject::TensorCid { cid: blob_cid, .. } = &retract.quad.object {
            assert_eq!(*blob_cid, cid(b"w_old"));
        }
    }
}
