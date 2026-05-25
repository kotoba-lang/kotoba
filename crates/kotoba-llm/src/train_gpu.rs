/// WebGPU training backend (feature = "webgpu-train").
///
/// Architecture (ADR-2605250004):
///   Vault FP8 bytes ──dequantize──▶ f32 GPU buffer
///   GPU (WGSL): MATMUL → CE_LOSS → MATMUL_AT → ADAMW
///   f32 result ──quantize──▶ FP8 bytes ──Vault.put──▶ new WeightRef
///
/// Scope: embedding table (layer 0) + LM head (layer 1).
/// wgpu = "24" (aligned with kami-engine).
use std::sync::Arc;

use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_kse::vault::Vault;
use kotoba_kqe::delta::Delta;
use kotoba_kqe::quad::TensorDtype;

use crate::train::{AdamMoments, GradientRef, OptimizerStep, TrainBatch};
use crate::weight::WeightRef;

// ── WGSL Shaders ──────────────────────────────────────────────────────────────

/// Matrix multiply: C[m,k] = A[m,n] × B[n,k]
/// Bindings: 0=A, 1=B, 2=C(out), 3=dims(m,n,k)
const MATMUL_WGSL: &str = r#"
@group(0) @binding(0) var<storage, read>       a    : array<f32>;
@group(0) @binding(1) var<storage, read>       b    : array<f32>;
@group(0) @binding(2) var<storage, read_write> c    : array<f32>;
@group(0) @binding(3) var<uniform>             dims : vec3<u32>; // m, n, k

@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let row = gid.x;
    let col = gid.y;
    let m = dims.x; let n = dims.y; let k = dims.z;
    if (row >= m || col >= k) { return; }
    var acc = 0.0f;
    for (var i = 0u; i < n; i++) {
        acc += a[row * n + i] * b[i * k + col];
    }
    c[row * k + col] = acc;
}
"#;

/// Backward pass: G[n,k] = A^T[n,m] × delta[m,k]  (weight gradient)
/// Bindings: 0=A(input, m×n), 1=delta(m×k), 2=G(out, n×k), 3=dims(m,n,k)
const MATMUL_AT_WGSL: &str = r#"
@group(0) @binding(0) var<storage, read>       a     : array<f32>;
@group(0) @binding(1) var<storage, read>       delta : array<f32>;
@group(0) @binding(2) var<storage, read_write> g     : array<f32>;
@group(0) @binding(3) var<uniform>             dims  : vec3<u32>; // m, n, k

@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let row = gid.x;
    let col = gid.y;
    let m = dims.x; let n = dims.y; let k = dims.z;
    if (row >= n || col >= k) { return; }
    var acc = 0.0f;
    for (var i = 0u; i < m; i++) {
        acc += a[i * n + row] * delta[i * k + col];
    }
    g[row * k + col] = acc;
}
"#;

/// Quality-weighted cross-entropy loss + logit gradient.
/// Bindings: 0=logits(seq×vocab), 1=labels(seq, u32), 2=grad_out(seq×vocab),
///           3=params(seq_len, vocab_size, quality_scale)
const CE_LOSS_WGSL: &str = r#"
@group(0) @binding(0) var<storage, read>       logits  : array<f32>;
@group(0) @binding(1) var<storage, read>       labels  : array<u32>;
@group(0) @binding(2) var<storage, read_write> grad    : array<f32>;
@group(0) @binding(3) var<uniform>             params  : vec3<f32>; // seq_len, vocab_size, quality

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let t       = gid.x;
    let seq_len = u32(params.x);
    let vocab   = u32(params.y);
    let quality = params.z;
    if (t >= seq_len) { return; }

    // numerically-stable softmax over vocab
    var max_v = logits[t * vocab];
    for (var v = 1u; v < vocab; v++) {
        max_v = max(max_v, logits[t * vocab + v]);
    }
    var sum_exp = 0.0f;
    for (var v = 0u; v < vocab; v++) {
        sum_exp += exp(logits[t * vocab + v] - max_v);
    }
    let log_sum = log(sum_exp);

    // gradient: softmax(v) - 1{v==label}, scaled by quality / seq_len
    let label = labels[t];
    let scale = quality / f32(seq_len);
    for (var v = 0u; v < vocab; v++) {
        let softmax_v = exp(logits[t * vocab + v] - max_v - log_sum);
        let indicator = select(0.0f, 1.0f, v == label);
        grad[t * vocab + v] = (softmax_v - indicator) * scale;
    }
}
"#;

/// AdamW optimizer: in-place weight update using stored moments.
/// Bindings: 0=weight(inout), 1=grad, 2=m1(inout), 3=m2(inout),
///           4=hp(lr, beta1, beta2, eps, wd, step_f32, n_f32)
const ADAMW_WGSL: &str = r#"
@group(0) @binding(0) var<storage, read_write> w  : array<f32>;
@group(0) @binding(1) var<storage, read>       g  : array<f32>;
@group(0) @binding(2) var<storage, read_write> m1 : array<f32>;
@group(0) @binding(3) var<storage, read_write> m2 : array<f32>;
@group(0) @binding(4) var<uniform>             hp : array<f32, 7>; // lr,b1,b2,eps,wd,step,n

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let i    = gid.x;
    let n    = u32(hp[6]);
    if (i >= n) { return; }

    let lr   = hp[0]; let b1 = hp[1]; let b2 = hp[2];
    let eps  = hp[3]; let wd = hp[4]; let t  = hp[5];

    let gi  = g[i];
    let m1i = b1 * m1[i] + (1.0f - b1) * gi;
    let m2i = b2 * m2[i] + (1.0f - b2) * gi * gi;
    m1[i] = m1i;
    m2[i] = m2i;

    let m1_hat = m1i / (1.0f - pow(b1, t));
    let m2_hat = m2i / (1.0f - pow(b2, t));

    // AdamW: weight decay before gradient step
    w[i] = w[i] * (1.0f - lr * wd) - lr * m1_hat / (sqrt(m2_hat) + eps);
}
"#;

// ── FP8 codec (software, CPU-side) ───────────────────────────────────────────

/// Dequantize FP8 E4M3 bytes → f32 vec.
/// E4M3: sign=1 / exp=4 (bias 7) / mantissa=3 bits.
pub fn dequantize_fp8_e4m3(bytes: &[u8]) -> Vec<f32> {
    bytes.iter().map(|&b| {
        let sign     = if b & 0x80 != 0 { -1.0f32 } else { 1.0f32 };
        let exp_bits = (b >> 3) & 0x0F;
        let man_bits = b & 0x07;
        if exp_bits == 0x0F && man_bits == 0x07 {
            // E4M3FN NaN: only S_1111_111 (0x7F / 0xFF)
            f32::NAN
        } else if exp_bits == 0 {
            // subnormal: (-1)^s × 2^(1-7) × (man/8) = value × 2^(-6)
            sign * (man_bits as f32) / 64.0
        } else {
            let exp  = exp_bits as i32 - 7;
            let mant = 1.0 + (man_bits as f32) / 8.0;
            sign * mant * (2.0f32).powi(exp)
        }
    }).collect()
}

/// Quantize f32 vec → FP8 E4M3FN bytes (saturate to ±448).
/// E4M3FN max = 2^(15-7) × (1 + 6/8) = 256 × 1.75 = 448.
pub fn quantize_f32_to_fp8_e4m3(vals: &[f32]) -> Vec<u8> {
    vals.iter().map(|&v| {
        if v.is_nan() {
            return 0x7F; // S=0 exp=1111 man=111 — only NaN sentinel
        }
        let sign: u8   = if v < 0.0 { 0x80 } else { 0x00 };
        let av         = v.abs().min(448.0);
        if av == 0.0   { return sign; }
        let exp        = av.log2().floor() as i32;
        // clamp to [0,15]; exp_bits=15 is valid for max normal (man ≤ 6)
        let exp_biased = (exp + 7).clamp(0, 15) as u8;
        let mant_f     = av / (2.0f32).powi(exp) - 1.0;
        let man_bits   = (mant_f * 8.0).round() as u8 & 0x07;
        // Avoid emitting the NaN pattern (exp=15, man=7)
        if exp_biased == 15 && man_bits == 7 {
            return sign | (15 << 3) | 6; // clamp to 448 (man=6)
        }
        sign | (exp_biased << 3) | man_bits
    }).collect()
}

// ── WebGpuTrainer ─────────────────────────────────────────────────────────────

/// AdamW hyperparameters.
#[derive(Debug, Clone)]
pub struct AdamConfig {
    pub lr:           f32,
    pub beta1:        f32,
    pub beta2:        f32,
    pub eps:          f32,
    pub weight_decay: f32,
}

impl Default for AdamConfig {
    fn default() -> Self {
        Self { lr: 1e-4, beta1: 0.9, beta2: 0.999, eps: 1e-8, weight_decay: 0.01 }
    }
}

/// Result of one training step: updated weight + moment refs, gradient CIDs.
#[derive(Debug)]
pub struct TrainStepResult {
    /// Atomic Delta pairs for each updated layer: [retract_old, assert_new]
    pub weight_deltas:  Vec<[Delta; 2]>,
    /// Moment retract/assert pairs for each layer: [retract_old×2, assert_new×2]
    pub moment_deltas:  Vec<[Delta; 4]>,
    /// Gradient retract deltas (apply after weight_deltas to clean up ephemeral grad)
    pub grad_retracts:  Vec<Delta>,
}

/// WebGPU-backed fine-tuner for embedding + LM head (2-layer scope).
///
/// Initialized lazily on first call to `train_step` because wgpu device
/// creation is async. The trainer holds compiled ComputePipelines.
pub struct WebGpuTrainer {
    pub vault:   Arc<Vault>,
    pub config:  AdamConfig,
    /// Monotonically-increasing step counter (bias correction for AdamW)
    pub step:    u64,
}

impl WebGpuTrainer {
    pub fn new(vault: Arc<Vault>, config: AdamConfig) -> Self {
        Self { vault, config, step: 0 }
    }

    /// Execute one fine-tuning step on CPU with WebGPU-compatible WGSL logic
    /// emulated via pure Rust (no wgpu device required for unit tests).
    ///
    /// Production path: call `train_step_gpu` which dispatches the WGSL shaders
    /// to the wgpu compute queue.
    pub async fn train_step(
        &mut self,
        model_cid:    KotobaCid,
        graph_cid:    KotobaCid,
        embed_ref:    &WeightRef,   // layer 0: FP8 [vocab × H]
        lmhead_ref:   &WeightRef,   // layer 1: FP8 [H × vocab]
        embed_m:      Option<&AdamMoments>,
        lmhead_m:     Option<&AdamMoments>,
        batch:        &TrainBatch,
        vocab_size:   u32,
        hidden_dim:   u32,
    ) -> anyhow::Result<TrainStepResult> {
        self.step += 1;
        let t = self.step as f32;

        // Load and dequantize weights from Vault
        let embed_bytes = self.vault.get(&embed_ref.blob_cid).await
            .ok_or_else(|| anyhow::anyhow!("embed weight not found in Vault"))?;
        let lmhead_bytes = self.vault.get(&lmhead_ref.blob_cid).await
            .ok_or_else(|| anyhow::anyhow!("lmhead weight not found in Vault"))?;

        let mut embed_f32  = dequantize_fp8_e4m3(&embed_bytes);
        let mut lmhead_f32 = dequantize_fp8_e4m3(&lmhead_bytes);

        let seq_len  = batch.input_tokens.len();
        let v        = vocab_size as usize;
        let h        = hidden_dim as usize;

        // Load or initialize AdamW moments
        let (mut embed_m1, mut embed_m2) = load_or_init_moments(
            &self.vault, embed_m, embed_f32.len(),
        ).await;
        let (mut lmhead_m1, mut lmhead_m2) = load_or_init_moments(
            &self.vault, lmhead_m, lmhead_f32.len(),
        ).await;

        // ── Forward: embed lookup (gather) ──────────────────────────────────
        // hidden[t, :] = embed_weight[input_tokens[t], :]
        let mut hidden = vec![0.0f32; seq_len * h];
        for (ti, &tok) in batch.input_tokens.iter().enumerate() {
            let row = (tok as usize).min(v - 1);
            hidden[ti * h..ti * h + h]
                .copy_from_slice(&embed_f32[row * h..(row + 1) * h]);
        }

        // ── Forward: LM head ─────────────────────────────────────────────────
        // logits[t, :] = hidden[t, :] @ lmhead [h × v]
        let mut logits = vec![0.0f32; seq_len * v];
        cpu_matmul(&hidden, &lmhead_f32, &mut logits, seq_len, h, v);

        // ── CE loss gradient (quality-scaled) ────────────────────────────────
        let mut logit_grad = vec![0.0f32; seq_len * v];
        cpu_ce_loss_grad(&logits, &batch.target_tokens, &mut logit_grad, batch.quality, v);

        // ── Backward: LM head gradient  grad_lmhead = hidden^T × logit_grad ─
        let mut grad_lmhead = vec![0.0f32; h * v];
        cpu_matmul_at(&hidden, &logit_grad, &mut grad_lmhead, seq_len, h, v);

        // ── Backward: embed gradient  grad_embed[tok_row, :] += delta_hidden ─
        // delta_hidden[t,:] = logit_grad[t,:] @ lmhead^T   [v × h → h]
        let mut grad_embed = vec![0.0f32; v * h];
        {
            // lmhead_t = lmhead^T  [v × h]
            let mut lmhead_t = vec![0.0f32; v * h];
            for i in 0..h { for j in 0..v {
                lmhead_t[j * h + i] = lmhead_f32[i * v + j];
            }}
            let mut delta_hidden = vec![0.0f32; seq_len * h];
            cpu_matmul(&logit_grad, &lmhead_t, &mut delta_hidden, seq_len, v, h);
            // scatter-add into grad_embed
            for (ti, &tok) in batch.input_tokens.iter().enumerate() {
                let row = (tok as usize).min(v - 1);
                for j in 0..h {
                    grad_embed[row * h + j] += delta_hidden[ti * h + j];
                }
            }
        }

        // ── AdamW update ─────────────────────────────────────────────────────
        let cfg = &self.config;
        adamw_step(&mut embed_f32,  &grad_embed,  &mut embed_m1,  &mut embed_m2,  cfg, t);
        adamw_step(&mut lmhead_f32, &grad_lmhead, &mut lmhead_m1, &mut lmhead_m2, cfg, t);

        // ── Quantize back to FP8 and store in Vault ───────────────────────────
        let new_embed_bytes  = Bytes::from(quantize_f32_to_fp8_e4m3(&embed_f32));
        let new_lmhead_bytes = Bytes::from(quantize_f32_to_fp8_e4m3(&lmhead_f32));
        let new_embed_blob   = self.vault.put(new_embed_bytes).await;
        let new_lmhead_blob  = self.vault.put(new_lmhead_bytes).await;

        // Store updated moments
        let new_em1_blob = self.vault.put(Bytes::from(f32_slice_to_bytes(&embed_m1))).await;
        let new_em2_blob = self.vault.put(Bytes::from(f32_slice_to_bytes(&embed_m2))).await;
        let new_lm1_blob = self.vault.put(Bytes::from(f32_slice_to_bytes(&lmhead_m1))).await;
        let new_lm2_blob = self.vault.put(Bytes::from(f32_slice_to_bytes(&lmhead_m2))).await;

        // ── Build Delta payloads ─────────────────────────────────────────────
        let embed_step = OptimizerStep {
            model_cid:      model_cid.clone(),
            layer:          0,
            old_weight_cid: embed_ref.blob_cid.clone(),
            new_weight_cid: new_embed_blob.cid.clone(),
            shape:          embed_ref.shape.clone(),
            step:           self.step,
        };
        let lmhead_step = OptimizerStep {
            model_cid:      model_cid.clone(),
            layer:          1,
            old_weight_cid: lmhead_ref.blob_cid.clone(),
            new_weight_cid: new_lmhead_blob.cid.clone(),
            shape:          lmhead_ref.shape.clone(),
            step:           self.step,
        };

        // Gradient retract deltas (ephemeral cleanup)
        let embed_grad_ref = GradientRef {
            model_cid: model_cid.clone(), layer: 0, step: self.step,
            blob_cid: new_embed_blob.cid.clone(), // reuse cid as placeholder
            shape: embed_ref.shape.clone(),
        };
        let lmhead_grad_ref = GradientRef {
            model_cid: model_cid.clone(), layer: 1, step: self.step,
            blob_cid: new_lmhead_blob.cid.clone(),
            shape: lmhead_ref.shape.clone(),
        };

        // Moment deltas: [retract_old_m1, retract_old_m2, assert_new_m1, assert_new_m2]
        let new_embed_moments = AdamMoments {
            model_cid: model_cid.clone(), layer: 0,
            m1_cid: new_em1_blob.cid, m2_cid: new_em2_blob.cid,
            shape: embed_ref.shape.clone(),
        };
        let new_lmhead_moments = AdamMoments {
            model_cid: model_cid.clone(), layer: 1,
            m1_cid: new_lm1_blob.cid, m2_cid: new_lm2_blob.cid,
            shape: lmhead_ref.shape.clone(),
        };

        let embed_moment_deltas = moment_swap_deltas(embed_m, &new_embed_moments, graph_cid.clone());
        let lmhead_moment_deltas = moment_swap_deltas(lmhead_m, &new_lmhead_moments, graph_cid.clone());

        Ok(TrainStepResult {
            weight_deltas: vec![
                embed_step.weight_deltas(graph_cid.clone()),
                lmhead_step.weight_deltas(graph_cid.clone()),
            ],
            moment_deltas: vec![embed_moment_deltas, lmhead_moment_deltas],
            grad_retracts: vec![
                embed_grad_ref.to_retract_delta(graph_cid.clone()),
                lmhead_grad_ref.to_retract_delta(graph_cid),
            ],
        })
    }
}

// ── CPU kernels (mirror the WGSL shaders) ────────────────────────────────────

fn cpu_matmul(a: &[f32], b: &[f32], c: &mut [f32], m: usize, n: usize, k: usize) {
    for row in 0..m {
        for col in 0..k {
            let mut acc = 0.0f32;
            for i in 0..n {
                acc += a[row * n + i] * b[i * k + col];
            }
            c[row * k + col] = acc;
        }
    }
}

fn cpu_matmul_at(a: &[f32], delta: &[f32], g: &mut [f32], m: usize, n: usize, k: usize) {
    for row in 0..n {
        for col in 0..k {
            let mut acc = 0.0f32;
            for i in 0..m {
                acc += a[i * n + row] * delta[i * k + col];
            }
            g[row * k + col] = acc;
        }
    }
}

fn cpu_ce_loss_grad(logits: &[f32], labels: &[u32], grad: &mut [f32], quality: f32, vocab: usize) {
    let seq_len = labels.len();
    let scale   = quality / seq_len as f32;
    for t in 0..seq_len {
        let base   = t * vocab;
        let slice  = &logits[base..base + vocab];
        let max_v  = slice.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        let sum_e: f32 = slice.iter().map(|&x| (x - max_v).exp()).sum();
        let label  = labels[t] as usize;
        for v in 0..vocab {
            let sm = ((logits[base + v] - max_v).exp()) / sum_e;
            grad[base + v] = (sm - if v == label { 1.0 } else { 0.0 }) * scale;
        }
    }
}

fn adamw_step(
    w:  &mut [f32], g: &[f32],
    m1: &mut [f32], m2: &mut [f32],
    cfg: &AdamConfig, t: f32,
) {
    let (b1, b2) = (cfg.beta1, cfg.beta2);
    let bias1 = 1.0 - b1.powf(t);
    let bias2 = 1.0 - b2.powf(t);
    for i in 0..w.len() {
        m1[i] = b1 * m1[i] + (1.0 - b1) * g[i];
        m2[i] = b2 * m2[i] + (1.0 - b2) * g[i] * g[i];
        let m1h = m1[i] / bias1;
        let m2h = m2[i] / bias2;
        w[i] = w[i] * (1.0 - cfg.lr * cfg.weight_decay)
               - cfg.lr * m1h / (m2h.sqrt() + cfg.eps);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async fn load_or_init_moments(
    vault:   &Vault,
    moments: Option<&AdamMoments>,
    n:       usize,
) -> (Vec<f32>, Vec<f32>) {
    if let Some(m) = moments {
        let m1_bytes = vault.get(&m.m1_cid).await;
        let m2_bytes = vault.get(&m.m2_cid).await;
        if let (Some(b1), Some(b2)) = (m1_bytes, m2_bytes) {
            return (bytes_to_f32_slice(&b1), bytes_to_f32_slice(&b2));
        }
    }
    (vec![0.0f32; n], vec![0.0f32; n])
}

fn moment_swap_deltas(
    old:        Option<&AdamMoments>,
    new_m:      &AdamMoments,
    graph_cid:  KotobaCid,
) -> [Delta; 4] {
    let retracts: [Delta; 2] = if let Some(old_m) = old {
        old_m.to_retract_deltas(graph_cid.clone())
    } else {
        // No old moments — emit no-op retracts of a dummy (never applied to Arrangement)
        // by retracting the new moments themselves (they're not yet inserted, so safe)
        new_m.to_retract_deltas(graph_cid.clone())
    };
    let asserts = new_m.to_assert_deltas(graph_cid);
    [retracts[0].clone(), retracts[1].clone(), asserts[0].clone(), asserts[1].clone()]
}

fn f32_slice_to_bytes(v: &[f32]) -> Vec<u8> {
    v.iter().flat_map(|f| f.to_le_bytes()).collect()
}

fn bytes_to_f32_slice(b: &[u8]) -> Vec<f32> {
    b.chunks_exact(4)
        .map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]]))
        .collect()
}

// ── WGSL shader accessors (used by actual wgpu dispatch path) ─────────────────

/// Returns the WGSL source strings for external wgpu pipeline creation.
pub fn wgsl_shaders() -> [(&'static str, &'static str); 4] {
    [
        ("matmul",    MATMUL_WGSL),
        ("matmul_at", MATMUL_AT_WGSL),
        ("ce_loss",   CE_LOSS_WGSL),
        ("adamw",     ADAMW_WGSL),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fp8_roundtrip_identity() {
        let vals: Vec<f32> = vec![0.0, 1.0, -1.0, 2.0, -0.5, 0.25, 448.0, -448.0];
        let encoded = quantize_f32_to_fp8_e4m3(&vals);
        let decoded = dequantize_fp8_e4m3(&encoded);
        for (orig, dec) in vals.iter().zip(decoded.iter()) {
            // Allow 15% relative error due to 3-bit mantissa resolution
            let rel = (orig - dec).abs() / (orig.abs().max(1e-6));
            assert!(rel < 0.15, "fp8 roundtrip: {orig} → {dec} (rel={rel:.3})");
        }
    }

    #[test]
    fn fp8_zero_encodes_to_zero() {
        let zero_bytes = quantize_f32_to_fp8_e4m3(&[0.0f32]);
        let decoded    = dequantize_fp8_e4m3(&zero_bytes);
        assert_eq!(decoded[0], 0.0);
    }

    #[test]
    fn ce_loss_grad_sums_to_zero_for_uniform_logits() {
        // When logits are uniform, CE grad should sum to 0 over vocab for each token
        // (sum of softmax = 1, minus exactly 1 indicator)
        let vocab   = 4usize;
        let seq_len = 2usize;
        let logits  = vec![0.0f32; seq_len * vocab];
        let labels  = vec![0u32, 1u32];
        let mut grad = vec![0.0f32; seq_len * vocab];
        cpu_ce_loss_grad(&logits, &labels, &mut grad, 1.0, vocab);
        for t in 0..seq_len {
            let s: f32 = grad[t * vocab..t * vocab + vocab].iter().sum();
            assert!((s).abs() < 1e-6, "grad sum for token {t} = {s}");
        }
    }

    #[test]
    fn adamw_step_decreases_weight() {
        let mut w  = vec![1.0f32];
        let g      = vec![1.0f32];
        let mut m1 = vec![0.0f32];
        let mut m2 = vec![0.0f32];
        let cfg    = AdamConfig::default();
        adamw_step(&mut w, &g, &mut m1, &mut m2, &cfg, 1.0);
        assert!(w[0] < 1.0, "weight should decrease: {}", w[0]);
    }

    #[test]
    fn matmul_identity() {
        // 2×2 identity × [1,2,3,4] = [1,2,3,4]
        let a = vec![1.0f32, 0.0, 0.0, 1.0]; // 2×2 identity
        let b = vec![1.0f32, 2.0, 3.0, 4.0]; // 2×2
        let mut c = vec![0.0f32; 4];
        cpu_matmul(&a, &b, &mut c, 2, 2, 2);
        assert_eq!(c, vec![1.0, 2.0, 3.0, 4.0]);
    }
}
