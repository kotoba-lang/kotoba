"""Baien-MX architecture (ADR 2605101000).

Per-modality 1.58-bit projectors + a shared cross-modal fusion block,
all built from `bitnet_qat.BitLinear` / `bitnet_qat.BitNetMLP`.

Trunk dimensions are read from `microsoft/BitNet-b1.58-2B-4T-bf16`'s
HF config:

    hidden_size            D    = 2560
    num_hidden_layers      L    = 30      (fusion inserted at L/2 = 15)
    num_attention_heads    Hq   = 20      (head_dim = 128)
    num_key_value_heads    Hkv  = 5       (GQA 1:4)

Defaults below match those numbers; constructors take explicit args
so the module is testable on CPU with a mock trunk.

This module deliberately does NOT load the actual trunk. Trunk surgery
(splitting the HF `BitNetForCausalLM` at layer 15 and threading the
fusion block + non-text tokens through it) lives in the training
runner (`kotodama.primitives.training_run` step 4 of ADR
2605101000), not here. Keeping that concern separate lets us unit
test these modules without 4.5 GB of weights.

Each module's `forward` returns either:
  - `(B, n_tokens, D)` for projectors (a fixed token sequence per
    sample), or
  - `(B, T, D)` for the fusion block (no sequence-length change).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import torch
from torch import Tensor, nn

from .bitnet_qat import BitLinear, BitNetMLP

# ── Trunk constants from microsoft/BitNet-b1.58-2B-4T-bf16/config.json ──
D_TRUNK = 2560
L_TRUNK = 30
H_Q = 20
H_KV = 5
HEAD_DIM = D_TRUNK // H_Q  # 128
FUSION_LAYER_INDEX = L_TRUNK // 2  # 15


# ──────────────────────────────────────────────────────────────────────
# Per-modality input projectors
# ──────────────────────────────────────────────────────────────────────


class BaienMXProjectorTriple(nn.Module):
    """Knowledge-triple projector. Inputs are subject / predicate / object
    integer ids (hashed vertex ids — caller is responsible for the
    hashing). Each id is embedded, the three embeddings are concatenated,
    and a BitNetMLP projects them to `n_tokens * d_model`. Output is
    reshaped to `(B, n_tokens, d_model)`.

    Vocabulary is intentionally fixed-size and hash-based so we never
    grow the table at training time.
    """

    def __init__(
        self,
        vocab_size: int = 100_000,
        d_model: int = D_TRUNK,
        n_tokens: int = 16,
        embed_dim: int = 256,
        hidden_dim: int = 1024,
    ) -> None:
        super().__init__()
        self.n_tokens = n_tokens
        self.d_model = d_model
        self.s_embed = nn.Embedding(vocab_size, embed_dim)
        self.p_embed = nn.Embedding(vocab_size, embed_dim)
        self.o_embed = nn.Embedding(vocab_size, embed_dim)
        self.proj = BitNetMLP(
            in_dim=3 * embed_dim,
            hidden_dim=hidden_dim,
            out_dim=n_tokens * d_model,
        )

    def forward(self, s: Tensor, p: Tensor, o: Tensor) -> Tensor:
        # s, p, o: (B,) int64
        x = torch.cat([self.s_embed(s), self.p_embed(p), self.o_embed(o)], dim=-1)
        out = self.proj(x)  # (B, n_tokens * D)
        return out.view(-1, self.n_tokens, self.d_model)


class BaienMXProjectorVec768(nn.Module):
    """768-d vector embedding projector (vertex_vector_embedding_768)."""

    def __init__(self, d_model: int = D_TRUNK, n_tokens: int = 8) -> None:
        super().__init__()
        self.n_tokens = n_tokens
        self.d_model = d_model
        self.norm = nn.LayerNorm(768)
        self.proj = BitLinear(768, n_tokens * d_model)

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, 768) float
        out = self.proj(self.norm(x))
        return out.view(-1, self.n_tokens, self.d_model)


class BaienMXProjectorVec4096FP8(nn.Module):
    """4096-d FP8 vector embedding projector
    (vertex_vector_embedding_4096_fp8). Caller must dequant FP8 to
    fp32/bf16 before the forward pass — keeping the dequant outside
    this module avoids dragging an FP8 dep into the tests.
    """

    def __init__(self, d_model: int = D_TRUNK, n_tokens: int = 16) -> None:
        super().__init__()
        self.n_tokens = n_tokens
        self.d_model = d_model
        self.norm = nn.LayerNorm(4096)
        self.proj = BitLinear(4096, n_tokens * d_model)

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, 4096) float (caller-dequanted from FP8)
        out = self.proj(self.norm(x))
        return out.view(-1, self.n_tokens, self.d_model)


class BaienMXProjector3dBlob(nn.Module):
    """3-D blob latent projector (vertex_3d_blob).

    The input latent dim is configurable because vertex_3d_blob may
    carry latents from different upstream encoders (point cloud,
    mesh, voxel grid). Default 1024 is a reasonable mid-point.
    """

    def __init__(
        self,
        latent_dim: int = 1024,
        d_model: int = D_TRUNK,
        n_tokens: int = 32,
        hidden_dim: int = 2048,
    ) -> None:
        super().__init__()
        self.n_tokens = n_tokens
        self.d_model = d_model
        self.proj = BitNetMLP(
            in_dim=latent_dim,
            hidden_dim=hidden_dim,
            out_dim=n_tokens * d_model,
        )

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, latent_dim)
        out = self.proj(x)
        return out.view(-1, self.n_tokens, self.d_model)


# ──────────────────────────────────────────────────────────────────────
# Cross-modal fusion block (NEW shared layer at L/2)
# ──────────────────────────────────────────────────────────────────────


class _GroupedQueryAttention(nn.Module):
    """Minimal GQA attention matching the trunk's H_Q / H_KV ratio,
    built from BitLinear so the entire fusion block is 1.58-bit. No
    rotary embedding here; positions inside the fusion block are
    treated as already-encoded by the trunk's first half (the trunk
    applies RoPE inside its own layers, and the fusion block sits
    between them as a residual addition)."""

    def __init__(
        self,
        d_model: int = D_TRUNK,
        n_q_heads: int = H_Q,
        n_kv_heads: int = H_KV,
    ) -> None:
        super().__init__()
        assert d_model % n_q_heads == 0
        assert n_q_heads % n_kv_heads == 0
        self.d_model = d_model
        self.n_q_heads = n_q_heads
        self.n_kv_heads = n_kv_heads
        self.head_dim = d_model // n_q_heads
        self.q_proj = BitLinear(d_model, n_q_heads * self.head_dim)
        self.k_proj = BitLinear(d_model, n_kv_heads * self.head_dim)
        self.v_proj = BitLinear(d_model, n_kv_heads * self.head_dim)
        self.o_proj = BitLinear(n_q_heads * self.head_dim, d_model)

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, T, D)
        b, t, _ = x.shape
        q = self.q_proj(x).view(b, t, self.n_q_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(b, t, self.n_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(b, t, self.n_kv_heads, self.head_dim).transpose(1, 2)
        # GQA: replicate kv heads to match q heads.
        repeat = self.n_q_heads // self.n_kv_heads
        k = k.repeat_interleave(repeat, dim=1)
        v = v.repeat_interleave(repeat, dim=1)
        # SDPA, no causal mask — the fusion block lets non-text tokens
        # attend bidirectionally to the text portion. The trunk's own
        # layers handle causal masking on the text side.
        out = torch.nn.functional.scaled_dot_product_attention(q, k, v)
        out = out.transpose(1, 2).contiguous().view(b, t, self.n_q_heads * self.head_dim)
        return self.o_proj(out)


class BaienMXFusionBlock(nn.Module):
    """Shared 1.58-bit cross-modal attention + FFN block, inserted at
    trunk layer L/2. Standard pre-norm transformer block shape:

        h  = x + Attn(LN(x))
        y  = h + FFN(LN(h))

    Both Attn and FFN are built from BitLinear so the block is fully
    1.58-bit at serve time."""

    def __init__(
        self,
        d_model: int = D_TRUNK,
        n_q_heads: int = H_Q,
        n_kv_heads: int = H_KV,
        ffn_hidden: int = 6912,  # matches trunk intermediate_size
    ) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.attn = _GroupedQueryAttention(d_model, n_q_heads, n_kv_heads)
        self.norm2 = nn.LayerNorm(d_model)
        self.ffn_in = BitLinear(d_model, ffn_hidden)
        self.ffn_out = BitLinear(ffn_hidden, d_model)
        self.act = nn.SiLU()

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, T, D)
        h = x + self.attn(self.norm1(x))
        ffn = self.ffn_out(self.act(self.ffn_in(self.norm2(h))))
        return h + ffn


# ──────────────────────────────────────────────────────────────────────
# Top-level wiring: BaienMXModel
# ──────────────────────────────────────────────────────────────────────


@dataclass
class BaienMXSample:
    """Per-row multimodal sample. Optional fields are None when the
    modality is absent for this sample (pulled directly from the
    `v_training_multimodal_sample` MV LEFT-JOIN result)."""

    text_ids: Tensor                       # (B, T_text) int64, mandatory
    triple: tuple[Tensor, Tensor, Tensor] | None = None  # ((B,), (B,), (B,))
    vec768: Tensor | None = None           # (B, 768)
    vec4096: Tensor | None = None          # (B, 4096) float (caller dequanted)
    threed: Tensor | None = None           # (B, latent_dim) float


class BaienMXModel(nn.Module):
    """Composes the per-modality projectors + the fusion block. The
    actual BitNet 2B trunk is held externally; this module exposes
    `encode_modalities()` (projector forward pass producing the
    non-text token stream) and the standalone `fusion` block. Trunk
    surgery — splitting the trunk into two halves and threading the
    fused stream through layer L/2 — happens in the training runner.

    The split keeps this module CPU-testable without 4.5 GB of
    trunk weights, and lets us reuse the projectors for non-trunk
    contexts later (e.g. retrieval-only embedding emission)."""

    def __init__(
        self,
        d_model: int = D_TRUNK,
        triple_vocab_size: int = 100_000,
        threed_latent_dim: int = 1024,
        n_q_heads: int = H_Q,
        n_kv_heads: int = H_KV,
        ffn_hidden: int = 6912,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.proj_triple = BaienMXProjectorTriple(
            vocab_size=triple_vocab_size, d_model=d_model
        )
        self.proj_vec768 = BaienMXProjectorVec768(d_model=d_model)
        self.proj_vec4096 = BaienMXProjectorVec4096FP8(d_model=d_model)
        self.proj_3d = BaienMXProjector3dBlob(
            latent_dim=threed_latent_dim, d_model=d_model
        )
        self.fusion = BaienMXFusionBlock(
            d_model=d_model,
            n_q_heads=n_q_heads,
            n_kv_heads=n_kv_heads,
            ffn_hidden=ffn_hidden,
        )

    def encode_modalities(self, sample: BaienMXSample) -> dict[str, Tensor]:
        """Run each per-modality projector on whichever inputs are
        present. Returns a dict mapping modality name → (B, n_tokens,
        D) token stream. Modalities missing from `sample` are absent
        from the returned dict (no zero-padding, no waste of
        gradient)."""
        out: dict[str, Tensor] = {}
        if sample.triple is not None:
            s, p, o = sample.triple
            out["triple"] = self.proj_triple(s, p, o)
        if sample.vec768 is not None:
            out["vec768"] = self.proj_vec768(sample.vec768)
        if sample.vec4096 is not None:
            out["vec4096"] = self.proj_vec4096(sample.vec4096)
        if sample.threed is not None:
            out["threed"] = self.proj_3d(sample.threed)
        return out

    def projector_parameters(self, modalities: Iterable[str]) -> list[nn.Parameter]:
        """Return the trainable parameters belonging to the named
        projectors only. Used by the training runner to set up
        per-modality optimizer param groups so each projector gets
        its own learning rate and is saved as a separate
        vertex_training_checkpoint row (per ADR 2605101000 §2)."""
        mapping: dict[str, nn.Module] = {
            "triple": self.proj_triple,
            "vec768": self.proj_vec768,
            "vec4096fp8": self.proj_vec4096,
            "3dblob": self.proj_3d,
        }
        params: list[nn.Parameter] = []
        for m in modalities:
            mod = mapping.get(m)
            if mod is None:
                raise KeyError(
                    f"unknown Baien-MX modality {m!r}; "
                    f"valid: {sorted(mapping.keys())}"
                )
            params.extend(p for p in mod.parameters() if p.requires_grad)
        return params

    def fusion_parameters(self) -> list[nn.Parameter]:
        return [p for p in self.fusion.parameters() if p.requires_grad]


__all__ = [
    "D_TRUNK",
    "L_TRUNK",
    "H_Q",
    "H_KV",
    "HEAD_DIM",
    "FUSION_LAYER_INDEX",
    "BaienMXProjectorTriple",
    "BaienMXProjectorVec768",
    "BaienMXProjectorVec4096FP8",
    "BaienMXProjector3dBlob",
    "BaienMXFusionBlock",
    "BaienMXSample",
    "BaienMXModel",
]
