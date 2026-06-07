"""Unit tests for `kotodama.modules.baien_mx` (ADR 2605101000).

These pin the architecture contract before any H100 hours are spent:
 - each per-modality projector emits its declared (n_tokens, D) shape
 - all weights end up in {-1, 0, +1} after pack_ternary on each
   constituent BitLinear (1.58-bit invariant holds across the wire)
 - encode_modalities skips absent modalities (no waste of gradient)
 - the cross-modal fusion block preserves the (B, T, D) shape and is
   shape-compatible with concatenated multi-modality token streams
 - projector_parameters() returns the right per-modality slice and
   raises on an unknown modality name (catches typos in the training
   runner before they corrupt vertex_training_checkpoint rows)
 - one optimizer step on a tiny synthetic problem decreases loss
   end-to-end through fusion + a single projector
"""

from __future__ import annotations

import math

import pytest
import torch

from kotodama.modules.baien_mx import (
    D_TRUNK,
    FUSION_LAYER_INDEX,
    H_KV,
    H_Q,
    L_TRUNK,
    BaienMXFusionBlock,
    BaienMXModel,
    BaienMXProjector3dBlob,
    BaienMXProjectorTriple,
    BaienMXProjectorVec768,
    BaienMXProjectorVec4096FP8,
    BaienMXSample,
)
from kotodama.modules.bitnet_qat import BitLinear


# Trim the trunk hidden dim for fast CPU tests. Real shape is asserted
# below in a single dedicated test.
D_TEST = 64


def test_trunk_constants_match_hf_config():
    """Hard-pin the constants we read from the HF config so any drift
    is caught here before it silently corrupts a fusion block at
    serve time."""
    assert D_TRUNK == 2560
    assert L_TRUNK == 30
    assert H_Q == 20
    assert H_KV == 5
    assert FUSION_LAYER_INDEX == 15
    assert H_Q % H_KV == 0  # GQA replication ratio is integer


def test_triple_projector_shape():
    proj = BaienMXProjectorTriple(vocab_size=1024, d_model=D_TEST, n_tokens=4)
    s = torch.randint(0, 1024, (3,))
    p = torch.randint(0, 1024, (3,))
    o = torch.randint(0, 1024, (3,))
    out = proj(s, p, o)
    assert out.shape == (3, 4, D_TEST)


def test_vec768_projector_shape():
    proj = BaienMXProjectorVec768(d_model=D_TEST, n_tokens=8)
    x = torch.randn(2, 768)
    out = proj(x)
    assert out.shape == (2, 8, D_TEST)


def test_vec4096_projector_shape():
    proj = BaienMXProjectorVec4096FP8(d_model=D_TEST, n_tokens=16)
    x = torch.randn(1, 4096)
    out = proj(x)
    assert out.shape == (1, 16, D_TEST)


def test_3dblob_projector_shape():
    proj = BaienMXProjector3dBlob(latent_dim=512, d_model=D_TEST, n_tokens=8)
    x = torch.randn(2, 512)
    out = proj(x)
    assert out.shape == (2, 8, D_TEST)


def test_fusion_block_preserves_shape():
    # Use a small head config divisible by the test D.
    blk = BaienMXFusionBlock(d_model=D_TEST, n_q_heads=8, n_kv_heads=2, ffn_hidden=128)
    x = torch.randn(2, 12, D_TEST)
    y = blk(x)
    assert y.shape == x.shape
    assert torch.isfinite(y).all()


def test_fusion_block_with_concat_multimodal_stream():
    """Simulate concatenating triple + vec768 + text projector outputs
    and feeding them to the fusion block."""
    blk = BaienMXFusionBlock(d_model=D_TEST, n_q_heads=8, n_kv_heads=2, ffn_hidden=128)
    triple_tokens = torch.randn(1, 4, D_TEST)
    vec_tokens = torch.randn(1, 2, D_TEST)
    text_tokens = torch.randn(1, 6, D_TEST)
    fused = blk(torch.cat([triple_tokens, vec_tokens, text_tokens], dim=1))
    assert fused.shape == (1, 12, D_TEST)


def test_encode_modalities_skips_missing():
    model = BaienMXModel(
        d_model=D_TEST,
        triple_vocab_size=1024,
        threed_latent_dim=256,
        n_q_heads=8,
        n_kv_heads=2,
        ffn_hidden=128,
    )
    sample = BaienMXSample(
        text_ids=torch.randint(0, 1024, (2, 10)),
        triple=None,
        vec768=torch.randn(2, 768),
        vec4096=None,
        threed=torch.randn(2, 256),
    )
    streams = model.encode_modalities(sample)
    assert set(streams.keys()) == {"vec768", "threed"}
    assert streams["vec768"].shape[-1] == D_TEST
    assert streams["threed"].shape[-1] == D_TEST


def test_projector_parameters_returns_per_modality_slice():
    model = BaienMXModel(
        d_model=D_TEST,
        triple_vocab_size=1024,
        threed_latent_dim=256,
        n_q_heads=8,
        n_kv_heads=2,
        ffn_hidden=128,
    )
    p_triple = model.projector_parameters(["triple"])
    p_all = model.projector_parameters(
        ["triple", "vec768", "vec4096fp8", "3dblob"]
    )
    # Triple projector has more params than vec768 (it has 3 embedding tables).
    assert len(p_triple) >= 4
    assert len(p_all) > len(p_triple)
    # Disjoint per-modality groups: any vec768 param must not appear in
    # the triple-only slice.
    triple_ids = {id(p) for p in p_triple}
    vec768_ids = {id(p) for p in model.projector_parameters(["vec768"])}
    assert triple_ids.isdisjoint(vec768_ids)


def test_projector_parameters_rejects_unknown_modality():
    model = BaienMXModel(
        d_model=D_TEST,
        triple_vocab_size=64,
        threed_latent_dim=32,
        n_q_heads=8,
        n_kv_heads=2,
        ffn_hidden=128,
    )
    with pytest.raises(KeyError):
        model.projector_parameters(["definitely-not-a-modality"])


def test_pack_ternary_holds_across_all_bitlinear_in_model():
    """Every BitLinear inside Baien-MX must produce a strictly ternary
    int8 tensor on pack. This is the 1.58-bit edge invariant — break
    it and the GGUF won't quantize cleanly."""
    model = BaienMXModel(
        d_model=D_TEST,
        triple_vocab_size=128,
        threed_latent_dim=32,
        n_q_heads=8,
        n_kv_heads=2,
        ffn_hidden=128,
    )
    bitlinear_count = 0
    for name, mod in model.named_modules():
        if isinstance(mod, BitLinear):
            bitlinear_count += 1
            packed, gamma = mod.pack_ternary()
            assert packed.dtype == torch.int8, name
            unique = set(torch.unique(packed).tolist())
            assert unique.issubset({-1, 0, 1}), f"non-ternary in {name}: {unique}"
            assert gamma.item() > 0, name
    # Sanity: we should have many BitLinear modules (4 projectors +
    # fusion attention QKV+O + fusion FFN in/out).
    assert bitlinear_count >= 8, f"only found {bitlinear_count} BitLinear modules"


def test_one_optimizer_step_decreases_loss_through_fusion_and_projector():
    """End-to-end gradient sanity: a vec768 projector → fusion block
    → mean-pool readout, trained to predict a scalar regressor.
    Catches any STE disconnection between projector and fusion."""
    torch.manual_seed(0)
    proj = BaienMXProjectorVec768(d_model=D_TEST, n_tokens=4)
    fusion = BaienMXFusionBlock(d_model=D_TEST, n_q_heads=8, n_kv_heads=2, ffn_hidden=128)
    head = torch.nn.Linear(D_TEST, 1)
    opt = torch.optim.Adam(
        list(proj.parameters()) + list(fusion.parameters()) + list(head.parameters()),
        lr=5e-3,
    )
    x = torch.randn(32, 768)
    target = (x.sum(dim=-1, keepdim=True) > 0).float()

    def step() -> float:
        opt.zero_grad()
        tokens = proj(x)               # (32, 4, D)
        fused = fusion(tokens)         # (32, 4, D)
        pooled = fused.mean(dim=1)     # (32, D)
        pred = head(pooled)            # (32, 1)
        loss = ((pred - target) ** 2).mean()
        loss.backward()
        opt.step()
        return float(loss.detach())

    loss_0 = step()
    for _ in range(20):
        step()
    loss_n = step()
    assert math.isfinite(loss_0) and math.isfinite(loss_n)
    assert loss_n < loss_0, f"end-to-end loss did not decrease: {loss_0} -> {loss_n}"


def test_full_size_fusion_block_constructs():
    """Make sure the real-trunk-shaped fusion block (D=2560, 20q/5kv)
    is constructible — we don't run a forward on it (memory) but the
    constructor catches obvious shape mismatches."""
    blk = BaienMXFusionBlock(d_model=D_TRUNK, n_q_heads=H_Q, n_kv_heads=H_KV)
    n_params = sum(p.numel() for p in blk.parameters())
    # Sanity bound: ≤ ~50M params for a single transformer block at
    # D=2560 with FFN hidden 6912.
    assert n_params < 60_000_000, f"fusion block too large: {n_params}"
    assert n_params > 5_000_000, f"fusion block suspiciously small: {n_params}"
