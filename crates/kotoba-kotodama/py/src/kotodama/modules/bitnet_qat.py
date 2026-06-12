"""BitNet b1.58 quantization-aware training (QAT) primitives.

ADR 2605101000 (Baien-MX). Every NEW Baien-MX module — per-modality
input projectors, the cross-modal fusion block, optional trunk LoRAs —
is constructed from `BitLinear`. We do NOT train fp16 layers and
quantize post-hoc; that path forfeits the 1.58-bit win.

Reference: "The Era of 1-bit LLMs" (Ma et al., arXiv 2402.17764).
Quantization rule:

    W_quant   = roundClip(W / gamma, -1, +1),   gamma = mean(|W|)
    X_quant   = roundClip(X / s,     -Q, +Q-1), s = max(|X|) / Q,  Q = 127
    Y         = (W_quant @ X_quant) * gamma * s / Q

Backward pass uses the straight-through estimator (STE) — gradients
flow through the rounding as if it were the identity.

All public symbols are intentionally small so the module reads as a
single page of contract. No external deps beyond torch.
"""

from __future__ import annotations

from typing import cast

import torch
from torch import Tensor, nn


# ──────────────────────────────────────────────────────────────────────
# Quantization helpers (autograd-aware via STE)
# ──────────────────────────────────────────────────────────────────────


def _ste_round(x: Tensor) -> Tensor:
    """Straight-through estimator round: forward = round, backward = id."""
    return (x.round() - x).detach() + x


def weight_quant_158(weight: Tensor, eps: float = 1e-5) -> tuple[Tensor, Tensor]:
    """Quantize a weight tensor to ternary {-1, 0, +1} + a per-tensor scale.

    Returns (W_quant, gamma) where W_quant has the same shape as `weight`
    and contains values in {-1, 0, +1} (still in float dtype because we
    multiply through gamma at matmul time). gamma is a 0-dim tensor.

    Forward = roundClip(W / gamma, -1, 1). Backward = identity (STE).
    """
    gamma = weight.abs().mean().clamp_min(eps)
    w_quant = _ste_round((weight / gamma).clamp(-1.0, 1.0))
    return w_quant, gamma


def activation_quant_int8(x: Tensor, eps: float = 1e-5) -> tuple[Tensor, Tensor]:
    """Quantize activations to int8 range [-127, 127] + per-token scale.

    The scale is per-row (per-token) absmax. Returns (X_quant, s) where
    X_quant is in float dtype but contains integer values in
    [-127, 127], and s has shape (..., 1) ready to broadcast at the
    matmul output.
    """
    q_max = 127.0
    s = x.abs().amax(dim=-1, keepdim=True).clamp_min(eps) / q_max
    x_quant = _ste_round((x / s).clamp(-q_max, q_max))
    return x_quant, s


# ──────────────────────────────────────────────────────────────────────
# BitLinear — the QAT linear layer
# ──────────────────────────────────────────────────────────────────────


class BitLinear(nn.Linear):
    """Drop-in replacement for `nn.Linear` that performs the BitNet b1.58
    QAT forward pass during training and emits a ternary-quantized output
    that matches the i2_s serving kernel.

    The full-precision `weight` parameter is what the optimizer actually
    updates; quantization happens on every forward. At export time, call
    `pack_ternary()` to obtain the ternary blob the i2_s GGUF wants.

    Bias is supported but uses fp32/bf16 (it's a tiny tensor). It does
    not affect the 1.58-bit footprint.
    """

    def __init__(self, in_features: int, out_features: int, bias: bool = False) -> None:
        super().__init__(in_features, out_features, bias=bias)

    def forward(self, x: Tensor) -> Tensor:  # type: ignore[override]
        # 1. Sub-LayerNorm-style normalization on the activations is the
        #    paper's recommendation. We rely on the caller to insert a
        #    LayerNorm before BitLinear when wiring blocks; doing it here
        #    would double-normalize for callers that already have one.
        # 2. Quantize weight (ternary) and activations (int8) with STE.
        w_quant, gamma = weight_quant_158(self.weight)
        x_quant, scale = activation_quant_int8(x)
        # 3. Effective matmul. Both operands are quantized but stored in
        #    float dtype, so this is still a regular F.linear call. The
        #    serving kernel performs the same op with int8/int2 SIMD.
        out = torch.nn.functional.linear(x_quant, w_quant, self.bias)
        # 4. Re-scale by the activation per-token scale and weight scale.
        return out * gamma * scale

    @torch.no_grad()
    def pack_ternary(self) -> tuple[Tensor, Tensor]:
        """Return (ternary_int8, gamma) ready to be written to an i2_s
        blob. ternary_int8 is `int8` with values in {-1, 0, +1}; gamma
        is the per-tensor scale used by the serving kernel."""
        w_quant, gamma = weight_quant_158(self.weight)
        # Detach + cast to int8 for storage. Values are already integer.
        return cast(Tensor, w_quant.detach().to(torch.int8)), gamma.detach()


# ──────────────────────────────────────────────────────────────────────
# Convenience: BitNet MLP block (used by Baien-MX projectors)
# ──────────────────────────────────────────────────────────────────────


class BitNetMLP(nn.Module):
    """Minimal 2-layer BitNet MLP block: LayerNorm → BitLinear → SiLU
    → BitLinear. Used by per-modality input projectors. Caller chooses
    the `out_dim` (= trunk hidden dim D) and `hidden_dim` (intermediate
    width). Activation = SiLU per the paper's ablation table.
    """

    def __init__(self, in_dim: int, hidden_dim: int, out_dim: int) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(in_dim)
        self.fc1 = BitLinear(in_dim, hidden_dim)
        self.act = nn.SiLU()
        self.fc2 = BitLinear(hidden_dim, out_dim)

    def forward(self, x: Tensor) -> Tensor:
        return self.fc2(self.act(self.fc1(self.norm(x))))


__all__ = [
    "weight_quant_158",
    "activation_quant_int8",
    "BitLinear",
    "BitNetMLP",
]
